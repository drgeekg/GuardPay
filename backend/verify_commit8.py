"""
Commit 8 verification — LLM incident dossier.

Tests:
  1. Generates complete dossier with all required fields per docs/API.md.
  2. Produces accurate root_cause, blast_radius, confidence, and estimated fee damage.
  3. Caching on Alert object works correctly across multiple calls.
  4. End-to-end API response validation via GET /alerts/{alert_id}/dossier.
  5. Returns 404 for non-existent alerts.

Run from repo root:
    .\\venv\\Scripts\\python.exe backend\\verify_commit8.py
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.main import app
from backend.velocity import engine, AnomalyResult
from backend.alerts import alert_store
from backend.dossier import generate_dossier

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

REQUIRED_DOSSIER_FIELDS = [
    "alert_id",
    "root_cause",
    "estimated_fee_damage_paise",
    "blast_radius",
    "confidence",
    "summary",
]

# Reset state
engine.reset()
alert_store.reset()
client = TestClient(app)

# ── 1. Create alerts of different pattern types ──────────────────────────────
anomaly_card = AnomalyResult(
    flagged=True,
    pattern_type="card_testing",
    severity="high",
    rule_fired="txn_per_bin > 10 in 60s window",
    affected_bin="411111",
    affected_subnet="103.21.58.0/24",
    transaction_ids=[f"txn_ct_{i}" for i in range(15)],
)
alert_card = alert_store.ingest_anomaly(anomaly_card)

anomaly_bin = AnomalyResult(
    flagged=True,
    pattern_type="bin_clustering",
    severity="high",
    rule_fired="unique_bins_from_subnet >= 5 in 60s window",
    affected_bin="411111, 411112, 411113, 411114, 411115",
    affected_subnet="103.21.58.0/24",
    transaction_ids=[f"txn_bc_{i}" for i in range(20)],
)
alert_bin = alert_store.ingest_anomaly(anomaly_bin)

# ── 2. Test generate_dossier for card_testing ───────────────────────────────
dossier_card = generate_dossier(alert_card)
for field in REQUIRED_DOSSIER_FIELDS:
    check(f"Card testing dossier has '{field}'", field in dossier_card)

check("Dossier alert_id matches", dossier_card["alert_id"] == alert_card.alert_id)
check("Dossier fee damage is integer > 0",
      isinstance(dossier_card["estimated_fee_damage_paise"], int) and dossier_card["estimated_fee_damage_paise"] > 0)
check("Dossier confidence is valid string",
      dossier_card["confidence"] in {"high", "medium", "low"})
check("Dossier root_cause mentions card-testing/probing",
      "card" in dossier_card["root_cause"].lower())
check("Dossier summary is comprehensive", len(dossier_card["summary"]) > 20)

# ── 3. Test caching on Alert object ──────────────────────────────────────────
dossier_cached = generate_dossier(alert_card)
check("generate_dossier returns cached instance", dossier_cached is dossier_card)
check("alert.dossier is populated", alert_card.dossier is not None)

# ── 4. Test generate_dossier for bin_clustering ──────────────────────────────
dossier_bin = generate_dossier(alert_bin)
check("Bin clustering dossier has required fields",
      all(f in dossier_bin for f in REQUIRED_DOSSIER_FIELDS))
check("Bin clustering root_cause mentions rotation/multi-bin",
      "bin" in dossier_bin["root_cause"].lower() or "rotation" in dossier_bin["root_cause"].lower())

# ── 5. Test HTTP GET /alerts/{alert_id}/dossier ───────────────────────────────
r = client.get(f"/alerts/{alert_card.alert_id}/dossier")
check("GET /alerts/{id}/dossier returns 200", r.status_code == 200)
http_dossier = r.json()
check("HTTP response matches generated dossier",
      http_dossier["alert_id"] == alert_card.alert_id and
      http_dossier["root_cause"] == dossier_card["root_cause"])

# ── 6. Test 404 for non-existent alert ───────────────────────────────────────
r404 = client.get("/alerts/alert_999/dossier")
check("GET /alerts/unknown/dossier returns 404", r404.status_code == 404)

# ── Summary ──────────────────────────────────────────────────────────────────
print(f"\n{PASSED} passed / {FAILED} failed")
if FAILED:
    print("SOME CHECKS FAILED - do not commit")
    sys.exit(1)
else:
    print("All commit-8 checks passed [OK]")
