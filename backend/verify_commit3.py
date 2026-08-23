"""
Commit 3 verification script.
Runs in-process using FastAPI's TestClient — no live server needed.
"""
import sys
import os

# Run from repo root, so `backend` package is importable
sys.path.insert(0, os.getcwd())

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

# --- Test 1: /health ---
r = client.get("/health")
assert r.status_code == 200, f"/health returned {r.status_code}"
assert r.json() == {"status": "ok"}, f"/health body wrong: {r.json()}"
print(f"[OK] GET /health -> {r.status_code}  {r.json()}")

# --- Test 2: /webhook/razorpay (stub) ---
r = client.post("/webhook/razorpay", json={"event": "payment.authorized", "payload": {}})
assert r.status_code == 200, f"/webhook/razorpay returned {r.status_code}"
body = r.json()
assert body.get("received") is True, f"expected received=true, got {body}"
assert body.get("event") == "payment.authorized", f"event mismatch: {body}"
print(f"[OK] POST /webhook/razorpay -> {r.status_code}  {body}")

# --- Test 3: config loads without crashing ---
from backend.config import settings
assert isinstance(settings.velocity_txn_per_card_per_min, int)
print(f"[OK] Config loaded -- velocity window: {settings.velocity_window_seconds}s  "
      f"txn/card/min threshold: {settings.velocity_txn_per_card_per_min}")

print("\nAll commit-3 checks passed [OK]")
