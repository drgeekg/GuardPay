"""
GuardPay — FastAPI backend entry point.

Commit 3: app boots, /health, /webhook/razorpay stub.
Commit 4: /transactions stub added so the attack simulator can POST to it.
Commit 5: velocity engine wired into /transactions; alert store in commit 6.
Full endpoint implementations land in commits 6-9 per docs/PLAN.md.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings  # noqa: F401 — verifies env loads cleanly
from backend.models import TransactionEventRequest, TransactionEventResponse
from backend.velocity import TransactionEvent, engine

logger = logging.getLogger(__name__)

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
# Ingestion — /transactions  (velocity engine live as of commit 5)
# ---------------------------------------------------------------------------

@app.post("/transactions", tags=["ingestion"], status_code=202,
          response_model=TransactionEventResponse)
async def ingest_transaction(req: TransactionEventRequest):
    """
    Accepts a transaction event from the simulator or Razorpay webhook.
    Passes it through the deterministic velocity engine and returns 202.

    Detection path (commit 5): velocity engine evaluates all rules.
    Alert persistence (commit 6): anomalies will be stored as Alert objects.
    """
    # Convert API model → internal domain type
    txn = TransactionEvent(
        transaction_id=req.transaction_id,
        card_bin=req.card_bin,
        amount_paise=req.amount_paise,
        ip_address=req.ip_address,
        timestamp=req.timestamp,
    )

    # Detection — deterministic, no LLM (docs/DESIGN.md constraint)
    anomaly = engine.ingest(txn)

    if anomaly:
        logger.warning(
            "ANOMALY | pattern=%s severity=%s rule=%s bin=%s subnet=%s txn_count=%d",
            anomaly.pattern_type,
            anomaly.severity,
            anomaly.rule_fired,
            anomaly.affected_bin,
            anomaly.affected_subnet,
            len(anomaly.transaction_ids),
        )
        # TODO (commit 6): persist anomaly as an Alert object in the alert store

    return TransactionEventResponse(accepted=True, transaction_id=req.transaction_id)


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
