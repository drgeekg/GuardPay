"""
Commit 6 verification — alert generation.

Tests:
  1. AnomalyResult from engine produces an Alert in the store.
  2. Repeated anomalies with same pattern+subnet are merged (deduplication).
  3. Different pattern or subnet creates a new alert.
  4. GET /alerts returns the alert feed.
  5. POST /alerts/{id}/override marks the alert correctly.
  6. GET /alerts/{id}/dossier returns stub dossier.

Run from repo root:
    .\\venv\\Scripts\\python.exe backend\\verify_commit6.py
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from datetime import datetime, timezone
from fastapi.testclient import TestClient
from backend.main import app
from backend.velocity import engine, VelocityEngine, TransactionEvent
from backend.alerts import alert_store

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

# Reset shared state between tests
engine.reset()
alert_store.reset()
client = TestClient(app)

def utc():
    return datetime.now(timezone.utc).isoformat()

# ── Helper: push N attack transactions through the HTTP endpoint ──────────────
def push_attack_txns(n, bin="411111", subnet_prefix="103.21.58"):
    for i in range(n):
        client.post("/transactions", json={
            "transaction_id": f"txn_a{i:04d}",
            "card_bin": bin,
            "amount_paise": 300,
            "ip_address": f"{subnet_prefix}.{(i % 200) + 1}",
            "timestamp": utc(),
        })

# ── Test 1: alert created after burst ────────────────────────────────────────
engine.reset(); alert_store.reset()
# Need burst_size > velocity_txn_per_card_per_min (default 10)
push_attack_txns(12)
alerts = alert_store.get_all()
check("Alert created after burst", len(alerts) >= 1,
      f"got {len(alerts)} alerts")
if alerts:
    a = alerts[0]
    check("Alert has correct pattern_type", a.pattern_type == "card_testing",
          f"got {a.pattern_type}")
    check("Alert has severity=high", a.severity == "high", f"got {a.severity}")
    check("Alert has transaction_ids", len(a.transaction_ids) > 0)
    check("Alert has alert_id", a.alert_id.startswith("alert_"))

# ── Test 2: subsequent matching anomalies merge into existing alert ───────────
engine.reset(); alert_store.reset()
# First burst creates alert_001
push_attack_txns(12, bin="411111", subnet_prefix="103.21.58")
count_before = len(alert_store.get_all())
# Second burst, same pattern+subnet — should merge
push_attack_txns(12, bin="411111", subnet_prefix="103.21.58")
count_after = len(alert_store.get_all())
check("Matching bursts merge into same alert (dedup)", count_before == count_after,
      f"before={count_before} after={count_after}")
merged = alert_store.get_all()[0] if alert_store.get_all() else None
check("Merged alert has more transaction_ids", merged and len(merged.transaction_ids) > 11)

# ── Test 3: different subnet creates separate alert ──────────────────────────
engine.reset(); alert_store.reset()
push_attack_txns(12, bin="411111", subnet_prefix="103.21.58")
push_attack_txns(12, bin="411111", subnet_prefix="45.119.200")
check("Different subnet creates new alert",
      len(alert_store.get_all()) >= 2,
      f"got {len(alert_store.get_all())} alerts")

# ── Test 4: GET /alerts returns feed ─────────────────────────────────────────
engine.reset(); alert_store.reset()
push_attack_txns(12)
r = client.get("/alerts")
check("GET /alerts returns 200", r.status_code == 200, f"got {r.status_code}")
alerts_json = r.json()
check("GET /alerts returns list", isinstance(alerts_json, list))
if alerts_json:
    a = alerts_json[0]
    for field in ("alert_id", "severity", "pattern_type", "affected_bin",
                  "affected_subnet", "transaction_ids", "created_at"):
        check(f"GET /alerts response has field '{field}'", field in a)

# ── Test 5: POST /alerts/{id}/override ───────────────────────────────────────
if alerts_json:
    aid = alerts_json[0]["alert_id"]
    r = client.post(f"/alerts/{aid}/override")
    check("POST /override returns 200", r.status_code == 200, f"got {r.status_code}")
    check("Override response has overridden=True",
          r.json().get("overridden") is True, f"got {r.json()}")
    # Alert still exists in store (not deleted)
    check("Alert still in store after override",
          alert_store.get_by_id(aid) is not None)
    check("Alert flagged as overridden",
          alert_store.get_by_id(aid).overridden is True)
    # 404 for unknown id
    r404 = client.post("/alerts/alert_999/override")
    check("POST /override 404 for missing alert", r404.status_code == 404)

# ── Test 6: GET /alerts/{id}/dossier returns stub ────────────────────────────
engine.reset(); alert_store.reset()
push_attack_txns(12)
r = client.get("/alerts")
if r.json():
    aid = r.json()[0]["alert_id"]
    rd = client.get(f"/alerts/{aid}/dossier")
    check("GET /dossier returns 200", rd.status_code == 200, f"got {rd.status_code}")
    d = rd.json()
    for field in ("alert_id", "root_cause", "estimated_fee_damage_paise",
                  "blast_radius", "confidence", "summary"):
        check(f"Dossier stub has field '{field}'", field in d)
    # 404 for missing
    rd404 = client.get("/alerts/alert_999/dossier")
    check("GET /dossier 404 for missing alert", rd404.status_code == 404)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{PASSED} passed / {FAILED} failed")
if FAILED:
    print("SOME CHECKS FAILED — do not commit")
    sys.exit(1)
else:
    print("All commit-6 checks passed [OK]")
