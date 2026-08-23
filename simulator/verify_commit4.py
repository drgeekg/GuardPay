"""
Commit 4 verification script.

Tests:
  1. /transactions stub accepts valid payloads and returns 202.
  2. Simulator payload generators produce correctly shaped dicts.
  3. A mini-burst (5 txn) fires through TestClient and all succeed.

Run from repo root:
    .\\venv\\Scripts\\python.exe simulator\\verify_commit4.py
"""
import sys
import os
sys.path.insert(0, os.getcwd())

from fastapi.testclient import TestClient
from backend.main import app
from simulator.card_testing_burst import make_attack_txn, make_normal_txn, run_burst

client = TestClient(app)

REQUIRED_FIELDS = {"transaction_id", "card_bin", "amount_paise", "ip_address", "timestamp"}

# ── Test 1: /transactions stub accepts valid payload ──────────────────────
txn = make_attack_txn()
r = client.post("/transactions", json=txn)
assert r.status_code == 202, f"Expected 202, got {r.status_code}"
body = r.json()
assert body.get("accepted") is True, f"Expected accepted=true: {body}"
assert body.get("transaction_id") == txn["transaction_id"], "txn_id mismatch"
print(f"[OK] POST /transactions -> 202  {body}")

# ── Test 2: Attack txn shape ──────────────────────────────────────────────
for _ in range(10):
    t = make_attack_txn()
    missing = REQUIRED_FIELDS - t.keys()
    assert not missing, f"Attack txn missing fields: {missing}"
    assert t["card_bin"] in {"411111","411112","411113","411114","411115"}, \
        f"Unexpected attack BIN: {t['card_bin']}"
    assert t["ip_address"].startswith("103.21.58."), \
        f"Attack IP not in expected subnet: {t['ip_address']}"
    assert t["amount_paise"] <= 500, \
        f"Attack amount too high for card-testing pattern: {t['amount_paise']}"
print("[OK] make_attack_txn() - shape, BIN, subnet, amount all valid (10 samples)")

# ── Test 3: Normal txn shape ──────────────────────────────────────────────
for _ in range(10):
    t = make_normal_txn()
    missing = REQUIRED_FIELDS - t.keys()
    assert not missing, f"Normal txn missing fields: {missing}"
    assert t["amount_paise"] >= 5000, \
        f"Normal amount suspiciously low: {t['amount_paise']}"
    assert not t["ip_address"].startswith("103.21.58."), \
        f"Normal txn in attack subnet: {t['ip_address']}"
print("[OK] make_normal_txn() - shape, amount, subnet all valid (10 samples)")

# ── Test 4: Mini burst through TestClient (no live server needed) ──────────
# Patch httpx to use TestClient transport
import httpx
from starlette.testclient import TestClient as StarletteTC

transport = httpx.MockTransport  # we'll monkey-patch differently — use direct calls
# Instead: fire 5 transactions manually through the TestClient
sent = 0
for i in range(3):
    r = client.post("/transactions", json=make_attack_txn())
    assert r.status_code == 202
    sent += 1
for i in range(2):
    r = client.post("/transactions", json=make_normal_txn())
    assert r.status_code == 202
    sent += 1
print(f"[OK] Mini-burst ({sent} txn via TestClient) - all returned 202")

print("\nAll commit-4 checks passed [OK]")
print("Simulator is ready. Demo run:")
print("  .\\\\venv\\\\Scripts\\\\uvicorn.exe backend.main:app --reload")
print("  .\\\\venv\\\\Scripts\\\\python.exe simulator\\\\card_testing_burst.py --target http://localhost:8000")
