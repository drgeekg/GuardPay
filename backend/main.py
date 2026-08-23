"""
GuardPay — FastAPI backend entry point.

Commit 3: app boots, /health, /webhook/razorpay stub.
Commit 4: /transactions stub added so the attack simulator can POST to it.
Full endpoint implementations land in commits 5-9 per docs/PLAN.md.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings  # noqa: F401 — verifies env loads cleanly

app = FastAPI(
    title="GuardPay",
    description="AI fraud triage dashboard for Razorpay merchants.",
    version="0.1.0",
)

# Allow the React dev server (commit 10) to call the backend without CORS errors.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"])
def health():
    """
    Returns 200 {"status": "ok"}.
    Used by the simulator and frontend to confirm the backend is up.
    """
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Ingestion — /transactions stub (velocity engine wired in commit 5)
# ---------------------------------------------------------------------------

@app.post("/transactions", tags=["ingestion"], status_code=202)
async def ingest_transaction(request: Request):
    """
    Accepts a transaction event from the simulator or a Razorpay webhook.
    Returns 202 Accepted immediately.

    Stub: accepts and acknowledges the payload.
    Commit 5 wires the velocity/clustering engine into this path.
    Commit 6 wires alert generation.
    """
    payload = await request.json()
    txn_id = payload.get("transaction_id", "unknown")
    # TODO (commit 5): pass payload to velocity engine
    # TODO (commit 6): check if engine raised an alert and persist it
    return {"accepted": True, "transaction_id": txn_id}


# ---------------------------------------------------------------------------
# Webhook receiver — stub (wired up fully in commit 9)
# ---------------------------------------------------------------------------

@app.post("/webhook/razorpay", tags=["ingestion"], status_code=200)
async def razorpay_webhook(request: Request):
    """
    Receives Razorpay test-mode webhook events (payment.authorized,
    payment.failed, etc.) and will normalize them into the internal
    transaction event shape.

    Stub only — signature verification and event normalization land in
    commit 9.
    """
    payload = await request.json()
    event_type = payload.get("event", "unknown")
    # TODO (commit 9): verify HMAC signature using settings.razorpay_key_secret
    # TODO (commit 9): normalize into TransactionEvent and feed to velocity engine
    return {"received": True, "event": event_type}
