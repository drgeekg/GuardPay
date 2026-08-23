"""
Commit 7 — First shippable milestone integration test.

Runs the full pipeline end-to-end using TestClient (no live server needed):
  Simulator payloads → POST /transactions → velocity engine → alert store →
  GET /alerts confirms alert with correct fields.

This is the proof that the detection loop works before any AI or UI is added.

Per docs/PLAN.md: "Run the simulator, confirm the alert appears with correct
fields. Commit a short test/demo script that proves it, not just manual
verification."

Run from repo root:
    .\\venv\\Scripts\\python.exe simulator\\test_pipeline.py
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.main import app
from backend.velocity import engine
from backend.alerts import alert_store
from simulator.card_testing_burst import make_attack_txn, make_normal_txn

client = TestClient(app)

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


def post_txn(txn: dict) -> int:
    r = client.post("/transactions", json=txn)
    return r.status_code


# ============================================================
# SCENARIO 1: Card-testing burst fires an alert
# ============================================================
print("\n--- Scenario 1: card-testing burst ---")
engine.reset()
alert_store.reset()

# Health check first (mirrors what the real simulator does)
r = client.get("/health")
check("Backend health check passes", r.status_code == 200 and r.json() == {"status": "ok"})

# Send 12 attack transactions (default threshold = 10, so 12 crosses it)
attack_txns = [make_attack_txn() for _ in range(12)]
for txn in attack_txns:
    sc = post_txn(txn)
    check(f"POST /transactions {txn['transaction_id']} -> 202", sc == 202,
          f"got {sc}")

# Confirm alert appeared
r = client.get("/alerts")
check("GET /alerts returns 200", r.status_code == 200)
alerts = r.json()
check("At least one alert exists after burst", len(alerts) >= 1,
      f"got {len(alerts)}")

if alerts:
    a = alerts[0]   # most recent first
    ATTACK_PATTERNS = {"card_testing", "bin_clustering", "subnet_clustering"}
    check("Alert severity is 'high' or 'medium'",  a["severity"] in {"high", "medium"}, f"got {a['severity']}")
    check("Alert pattern is an attack pattern",    a["pattern_type"] in ATTACK_PATTERNS, f"got {a['pattern_type']}")
    check("Alert affected_subnet is /24",          a["affected_subnet"].endswith("/24"), f"got {a['affected_subnet']}")
    check("Alert has transaction_ids list",        len(a["transaction_ids"]) >= 1)
    check("Alert txn_ids are from the burst",
          any(tid in a["transaction_ids"] for tid in [t["transaction_id"] for t in attack_txns]))
    check("Alert has created_at timestamp",        "created_at" in a)
    alert_id = a["alert_id"]
    check("Alert has alert_id",                    alert_id.startswith("alert_"))
    # The affected_bin field contains the BIN(s) involved — just check non-empty
    check("Alert has non-empty affected_bin",      len(a.get("affected_bin", "")) > 0)

    # Dossier stub returns all required fields
    rd = client.get(f"/alerts/{alert_id}/dossier")
    check("Dossier endpoint returns 200", rd.status_code == 200)
    d = rd.json()
    for field in ("alert_id", "root_cause", "estimated_fee_damage_paise",
                  "blast_radius", "confidence", "summary"):
        check(f"Dossier has '{field}'", field in d, f"missing from {list(d.keys())}")


# ============================================================
# SCENARIO 2: Normal traffic alone does NOT fire an alert
# ============================================================
print("\n--- Scenario 2: normal traffic — no alert ---")
engine.reset()
alert_store.reset()

# 20 normal transactions: varied BINs, varied subnets, high amounts
for _ in range(20):
    post_txn(make_normal_txn())

alerts_normal = client.get("/alerts").json()
check("Normal traffic does NOT create an alert",
      len(alerts_normal) == 0,
      f"got {len(alerts_normal)} alert(s): {alerts_normal}")


# ============================================================
# SCENARIO 3: False positive override (graceful failure case)
# ============================================================
print("\n--- Scenario 3: false positive override ---")
engine.reset()
alert_store.reset()

# Fire a burst to get an alert
for txn in [make_attack_txn() for _ in range(12)]:
    post_txn(txn)

alerts = client.get("/alerts").json()
check("Alert exists to override", len(alerts) >= 1)
if alerts:
    aid = alerts[0]["alert_id"]
    ro = client.post(f"/alerts/{aid}/override")
    check("Override returns 200", ro.status_code == 200)
    check("Override response: overridden=True", ro.json().get("overridden") is True)
    # Alert is still in the list (not deleted — it's the audit record)
    check("Alert still visible in feed after override",
          any(al["alert_id"] == aid for al in client.get("/alerts").json()))


# ============================================================
# Summary
# ============================================================
print(f"\n{'='*50}")
print(f"  {PASSED} passed / {FAILED} failed")
print(f"{'='*50}")
if FAILED:
    print("PIPELINE TEST FAILED — do not ship")
    sys.exit(1)
else:
    print("First shippable milestone: simulator -> alert fires correctly [OK]")
    print("M2 (Detection works end-to-end) is COMPLETE.")
