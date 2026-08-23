"""
Commit 9 verification — mitigation actions, audit log, and undo path.

Tests:
  1. POST /alerts/{id}/actions/block-subnet (gated, bounded, audit logged).
  2. POST /alerts/{id}/actions/enable-3ds (gated, bounded, audit logged).
  3. Action enforcement checks (is_subnet_blocked, is_3ds_required).
  4. POST /actions/{id}/undo (reversal, audit logged, policy cleared).
  5. POST /alerts/{id}/override writes to audit log.
  6. GET /audit-log returns immutable trail with who/what/when/why.
  7. POST /webhook/razorpay normalizes Razorpay payment event.

Run from repo root:
    .\\venv\\Scripts\\python.exe backend\\verify_commit9.py
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.main import app
from backend.velocity import engine, AnomalyResult
from backend.alerts import alert_store
from backend.audit import audit_store
from backend.actions import action_executor

PASSED = 0
FAILED = 0

def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        print(f"[OK] {name}")
        PASSED += 1
    else:
        print(f"[FAIL] {name}" + (f": {detail}" if detail else ""))
        FAILED += 1

# Reset all stores
engine.reset()
alert_store.reset()
audit_store.reset()
action_executor.reset()
client = TestClient(app)

# Create test alert
anomaly = AnomalyResult(
    flagged=True,
    pattern_type="card_testing",
    severity="high",
    rule_fired="txn_per_bin > 10 in 60s window",
    affected_bin="411111",
    affected_subnet="103.21.58.0/24",
    transaction_ids=[f"txn_m_{i}" for i in range(12)],
)
alert = alert_store.ingest_anomaly(anomaly)
aid = alert.alert_id

# ── 1. Gating test: action rejected without reason_acknowledged ──────────────
r_gated = client.post(f"/alerts/{aid}/actions/block-subnet", json={
    "actor": "merchant_demo",
    "reason_acknowledged": False
})
check("Action rejected when reason_acknowledged=False", r_gated.status_code == 400)

# ── 2. Block Subnet Action ───────────────────────────────────────────────────
r_block = client.post(f"/alerts/{aid}/actions/block-subnet", json={
    "actor": "merchant_demo",
    "reason_acknowledged": True
})
check("POST block-subnet returns 200", r_block.status_code == 200)
block_data = r_block.json()
check("Block action returns action_id", block_data.get("action_id", "").startswith("act_"))
check("Block action returns effect", "103.21.58.0/24" in block_data.get("effect", ""))
check("Block action has reversible_until", "reversible_until" in block_data)
check("Block action has audit_log_id", block_data.get("audit_log_id", "").startswith("audit_"))

action_id_block = block_data["action_id"]

# Verify subnet block enforcement
check("Attacker IP is recognized as blocked",
      action_executor.is_subnet_blocked("103.21.58.42") is True)
check("Different subnet IP is NOT blocked",
      action_executor.is_subnet_blocked("49.207.1.1") is False)

# ── 3. Enable 3DS Action ─────────────────────────────────────────────────────
r_3ds = client.post(f"/alerts/{aid}/actions/enable-3ds", json={
    "actor": "merchant_demo",
    "reason_acknowledged": True
})
check("POST enable-3ds returns 200", r_3ds.status_code == 200)
data_3ds = r_3ds.json()
check("3DS action returns effect mentioning BIN", "411111" in data_3ds.get("effect", ""))

# Verify 3DS enforcement
check("Affected BIN requires 3DS", action_executor.is_3ds_required("411111") is True)
check("Other BIN does not require 3DS", action_executor.is_3ds_required("542418") is False)

# ── 4. Undo Path ─────────────────────────────────────────────────────────────
r_undo = client.post(f"/actions/{action_id_block}/undo", json={"actor": "merchant_admin"})
check("POST /actions/{id}/undo returns 200", r_undo.status_code == 200)
undo_data = r_undo.json()
check("Undo status is 'undone'", undo_data.get("status") == "undone")
check("Undo returns new audit_log_id", undo_data.get("audit_log_id", "").startswith("audit_"))

# Check that IP is now unblocked
check("Attacker IP is no longer blocked after undo",
      action_executor.is_subnet_blocked("103.21.58.42") is False)

# Double undo should be rejected
r_double_undo = client.post(f"/actions/{action_id_block}/undo")
check("Double undo returns 400", r_double_undo.status_code == 400)

# ── 5. Override with Audit Trail ─────────────────────────────────────────────
r_over = client.post(f"/alerts/{aid}/override")
check("Override returns 200", r_over.status_code == 200)
check("Override returns audit_log_id", r_over.json().get("audit_log_id", "").startswith("audit_"))

# ── 6. GET /audit-log Trail Inspection ───────────────────────────────────────
r_audit = client.get("/audit-log")
check("GET /audit-log returns 200", r_audit.status_code == 200)
entries = r_audit.json()
check("Audit log contains entries", len(entries) >= 4)  # block, 3ds, undo, override

action_types = [e["action_type"] for e in entries]
check("Audit log has 'block_subnet'", "block_subnet" in action_types)
check("Audit log has 'enable_3ds'", "enable_3ds" in action_types)
check("Audit log has 'undo'", "undo" in action_types)
check("Audit log has 'override'", "override" in action_types)

for e in entries:
    for req_key in ("audit_log_id", "alert_id", "actor", "action_type", "reason", "timestamp", "undone"):
        check(f"Audit entry has '{req_key}'", req_key in e)

# ── 7. Razorpay Webhook Ingestion ────────────────────────────────────────────
webhook_payload = {
    "entity": "event",
    "account_id": "acc_test123",
    "event": "payment.authorized",
    "contains": ["payment"],
    "payload": {
        "payment": {
            "entity": {
                "id": "pay_test_001",
                "amount": 25000,
                "currency": "INR",
                "status": "authorized",
                "card": {"network": "Visa", "emi_sub_type": "411111"},
                "ip_address": "122.172.15.4",
                "created_at": int(datetime.now(timezone.utc).timestamp()),
            }
        }
    }
}
r_hook = client.post("/webhook/razorpay", json=webhook_payload)
check("POST /webhook/razorpay returns 200", r_hook.status_code == 200)
check("Webhook received=True", r_hook.json().get("received") is True)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{PASSED} passed / {FAILED} failed")
if FAILED:
    print("SOME CHECKS FAILED - do not commit")
    sys.exit(1)
else:
    print("All commit-9 checks passed [OK]")
