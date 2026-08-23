"""
Commit 5 verification — velocity engine unit tests.

Tests every rule in isolation, checks thresholds match config,
and verifies clean transactions produce no anomaly.

Run from repo root:
    .\\venv\\Scripts\\python.exe backend\\verify_commit5.py
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from datetime import datetime, timezone, timedelta
from backend.velocity import VelocityEngine, TransactionEvent, _subnet24
from backend.config import settings

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

def utcnow():
    return datetime.now(timezone.utc)

def make_txn(bin="411111", ip="103.21.58.10", amount=500, offset_sec=0, txn_id=None):
    t = utcnow() + timedelta(seconds=offset_sec)
    return TransactionEvent(
        transaction_id=txn_id or f"txn_{abs(hash((bin, ip, offset_sec))) % 100000:05d}",
        card_bin=bin,
        amount_paise=amount,
        ip_address=ip,
        timestamp=t,
    )

# ── Helpers ──────────────────────────────────────────────────────────────────
check(
    "_subnet24 extracts /24 prefix correctly",
    _subnet24("103.21.58.14") == "103.21.58" and
    _subnet24("49.207.192.33") == "49.207.192"
)

# ── Rule 1: txn_per_bin ───────────────────────────────────────────────────────
eng = VelocityEngine()
# Send transactions below threshold — no anomaly.
# Use a single IP so we don't accidentally trigger subnet_cluster (Rule 3).
limit = settings.velocity_txn_per_card_per_min
for i in range(limit):
    result = eng.ingest(make_txn(bin="411111", ip="10.0.0.1"))
check("Rule 1 — below threshold: no anomaly", result is None,
      f"got {result}")

# One more push it over
result = eng.ingest(make_txn(bin="411111", ip="10.0.0.99", txn_id="trigger_txn"))
check("Rule 1 — over threshold: anomaly fires", result is not None and result.flagged)
check("Rule 1 — correct pattern_type", result is not None and result.pattern_type == "card_testing",
      f"got {getattr(result, 'pattern_type', None)}")
check("Rule 1 — severity=high", result is not None and result.severity == "high",
      f"got {getattr(result, 'severity', None)}")
check("Rule 1 — affected_bin matches", result is not None and result.affected_bin == "411111",
      f"got {getattr(result, 'affected_bin', None)}")
check("Rule 1 — transaction_ids list non-empty",
      result is not None and len(result.transaction_ids) > 0)

# ── Rule 2: bin_clustering ────────────────────────────────────────────────────
eng = VelocityEngine()
subnet = "203.0.113"
threshold = settings.velocity_bin_cluster_threshold
bins = [f"4111{str(i).zfill(2)}" for i in range(threshold)]
for i, b in enumerate(bins):
    result = eng.ingest(make_txn(bin=b, ip=f"{subnet}.{i+1}", amount=50000))
check("Rule 2 — bin_clustering fires on threshold",
      result is not None and result.pattern_type == "bin_clustering",
      f"got {result}")
check("Rule 2 — severity=high", result is not None and result.severity == "high")
check("Rule 2 — affected_subnet ends in /24",
      result is not None and result.affected_subnet.endswith("/24"),
      f"got {getattr(result, 'affected_subnet', None)}")

# ── Rule 3: subnet_cluster ────────────────────────────────────────────────────
eng = VelocityEngine()
subnet3 = "198.51.100"
threshold3 = settings.velocity_subnet_cluster_threshold
# Same BIN, different IPs from same /24 — doesn't trigger rule 1 or 2
for i in range(threshold3):
    result = eng.ingest(make_txn(bin="457173", ip=f"{subnet3}.{i+10}", amount=50000))
check("Rule 3 — subnet_cluster fires on threshold",
      result is not None and result.pattern_type == "subnet_clustering",
      f"got {result}")
check("Rule 3 — severity=medium", result is not None and result.severity == "medium")

# ── Clean transaction — no rule fires ─────────────────────────────────────────
eng = VelocityEngine()
result = eng.ingest(make_txn(bin="457173", ip="49.207.1.5", amount=299900))
check("Clean txn — no anomaly", result is None, f"got {result}")

# ── Rolling window prune ──────────────────────────────────────────────────────
# Transactions with timestamps older than the window should be pruned
eng = VelocityEngine()
old_offset = -(settings.velocity_window_seconds + 10)  # 10s older than window
for i in range(limit + 5):
    eng.ingest(make_txn(bin="411111", ip="10.0.0.1", offset_sec=old_offset))
# Now send one fresh one — window should be pruned, so no anomaly
result = eng.ingest(make_txn(bin="411111", ip="10.0.0.2", offset_sec=0))
check("Rolling window prunes old transactions (no stale anomaly)", result is None,
      f"got {result}")

# ── Via HTTP endpoint ─────────────────────────────────────────────────────────
from fastapi.testclient import TestClient
from backend.main import app
from backend.velocity import engine as global_engine

global_engine.reset()
client = TestClient(app)

payload = {
    "transaction_id": "txn_http_test",
    "card_bin": "542418",
    "amount_paise": 150000,
    "ip_address": "117.96.50.1",
    "timestamp": utcnow().isoformat(),
}
r = client.post("/transactions", json=payload)
check("HTTP /transactions still returns 202", r.status_code == 202,
      f"got {r.status_code}")
check("HTTP response has accepted=True", r.json().get("accepted") is True,
      f"got {r.json()}")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{PASSED} passed / {FAILED} failed")
if FAILED:
    print("SOME CHECKS FAILED — do not commit")
    sys.exit(1)
else:
    print("All commit-5 checks passed [OK]")
