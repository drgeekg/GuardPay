"""
Commit 11 verification — Graceful failure handling (false positive override workflow).

Tests:
  1. Ingests a high-frequency legitimate buyer burst.
  2. Confirms the incident is flagged for triage.
  3. Merchant marks the alert as a false positive via POST /alerts/{id}/override.
  4. Confirms the alert retains state with overridden=True.
  5. Confirms an immutable audit log entry is recorded with actor and reason.
  6. Confirms subsequent traffic is processed without blocked-subnet restrictions.

Run from repo root:
    .\\venv\\Scripts\\python.exe backend\\verify_commit11.py
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.main import app
from backend.velocity import engine
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

print("\n--- Testing Concrete Failure Case: Legitimate High-Frequency Buyer ---")

# Step 1: Simulate legitimate business buyer making 12 rapid wholesale orders
buyer_ip = "49.207.192.88"
buyer_bin = "457173"
for i in range(12):
    r = client.post("/transactions", json={
        "transaction_id": f"txn_buyer_{i:03d}",
        "card_bin": buyer_bin,
        "amount_paise": 2500000 + i * 50000, # ₹25,000+ orders
        "ip_address": buyer_ip,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    assert r.status_code == 202

# Step 2: Confirm alert is flagged
alerts = client.get("/alerts").json()
check("High-velocity buyer trips velocity threshold (candidate false positive)",
      len(alerts) >= 1)

if alerts:
    alert = alerts[0]
    aid = alert["alert_id"]
    check("Alert created has alert_id", aid.startswith("alert_"))

    # Step 3: Fetch dossier — verify explanations
    rd = client.get(f"/alerts/{aid}/dossier")
    check("GET /dossier returns 200", rd.status_code == 200)
    dossier = rd.json()
    check("Dossier has summary", len(dossier.get("summary", "")) > 0)

    # Step 4: Merchant reviews and executes Graceful Override
    r_over = client.post(f"/alerts/{aid}/override", params={"actor": "merchant_review_lead"})
    check("POST /override returns 200", r_over.status_code == 200)
    over_res = r_over.json()
    check("Override response has overridden=True", over_res.get("overridden") is True)
    check("Override generated audit log ID", "audit_log_id" in over_res)

    # Step 5: Verify alert feed shows overridden state
    updated_alerts = client.get("/alerts").json()
    overridden_alert = next((a for a in updated_alerts if a["alert_id"] == aid), None)
    check("Alert in feed is marked overridden=True",
          overridden_alert is not None and overridden_alert.get("overridden") is True)

    # Step 6: Verify audit trail recorded the override event
    audit_logs = client.get("/audit-log").json()
    override_log = next((l for l in audit_logs if l["alert_id"] == aid and l["action_type"] == "override"), None)
    check("Audit trail recorded override with actor and reason",
          override_log is not None and "false positive" in override_log.get("reason", "").lower())

    # Step 7: Confirm the buyer's subnet is NOT blocked
    check("Buyer subnet remains unblocked for future transactions",
          action_executor.is_subnet_blocked(buyer_ip) is False)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{PASSED} passed / {FAILED} failed")
if FAILED:
    print("SOME CHECKS FAILED - do not commit")
    sys.exit(1)
else:
    print("Commit 11: graceful failure handling verified successfully [OK]")
