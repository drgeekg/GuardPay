"""
Commit 12 verification — Evaluation metrics & summary endpoint.

Tests:
  1. GET /metrics/summary returns 200 with all fields per docs/API.md.
  2. Batch size is 500 with valid precision and recall bounds (0 <= val <= 1).
  3. Static SPA frontend serves index.html on root / for single-port deployment.

Run from repo root:
    .\\venv\\Scripts\\python.exe backend\\verify_commit12.py
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from fastapi.testclient import TestClient
from backend.main import app

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

client = TestClient(app)

# ── 1. Test GET /metrics/summary ─────────────────────────────────────────────
r = client.get("/metrics/summary")
check("GET /metrics/summary returns 200", r.status_code == 200)
metrics = r.json()

REQUIRED_FIELDS = [
    "batch_size",
    "true_positives",
    "false_positives",
    "false_negatives",
    "precision",
    "recall",
    "false_positive_cost_estimate_paise",
]

for field in REQUIRED_FIELDS:
    check(f"Metrics summary has '{field}'", field in metrics)

check("Batch size is 500", metrics.get("batch_size") == 500)
check("Precision is valid float > 0.90", 0.90 <= metrics.get("precision", 0) <= 1.0)
check("Recall is valid float > 0.90", 0.90 <= metrics.get("recall", 0) <= 1.0)
check("Estimated FP cost is >= 0", metrics.get("false_positive_cost_estimate_paise", -1) >= 0)

# ── 2. Test Single-Port Deployment Serving (GET / returns React HTML) ─────────
r_root = client.get("/")
check("GET / serves built frontend SPA", r_root.status_code == 200 and "GuardPay" in r_root.text)

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{PASSED} passed / {FAILED} failed")
if FAILED:
    print("SOME CHECKS FAILED - do not commit")
    sys.exit(1)
else:
    print("Commit 12: evaluation metrics & deployment serving verified [OK]")
