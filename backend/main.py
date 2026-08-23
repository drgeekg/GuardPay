"""
GuardPay — FastAPI backend entry point.

Commit 3: app boots, /health, /webhook/razorpay stub.
Commit 4: /transactions stub added so the attack simulator can POST to it.
Commit 5: velocity engine wired into /transactions.
Commit 6: alert store wired in; GET /alerts and POST override live.
Commit 8: LLM incident dossier generation wired into GET /alerts/{id}/dossier.
Full endpoint implementations land in commit 9 per docs/PLAN.md.
"""
import logging
from typing import List

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.alerts import alert_store
from backend.config import settings  # noqa: F401 — verifies env loads cleanly
from backend.dossier import generate_dossier
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
        alert = alert_store.ingest_anomaly(anomaly)
        logger.warning(
            "ALERT %s | pattern=%s severity=%s bin=%s subnet=%s txn_count=%d",
            alert.alert_id,
            anomaly.pattern_type,
            anomaly.severity,
            anomaly.affected_bin,
            anomaly.affected_subnet,
            len(anomaly.transaction_ids),
        )

    return TransactionEventResponse(accepted=True, transaction_id=req.transaction_id)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@app.get("/alerts", tags=["alerts"])
def list_alerts() -> List[dict]:
    """
    Returns the live alert feed, most recent first.
    Shape matches docs/API.md GET /alerts.
    """
    return [a.to_dict() for a in alert_store.get_all()]


@app.get("/alerts/{alert_id}/dossier", tags=["alerts"])
def get_dossier(alert_id: str) -> dict:
    """
    Returns the LLM-generated incident dossier for a given alert.
    Generated lazily on first request, cached after (commit 8).
    """
    alert = alert_store.get_by_id(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return generate_dossier(alert)


@app.post("/alerts/{alert_id}/override", tags=["alerts"])
def override_alert(alert_id: str) -> dict:
    """
    Merchant marks an alert as a false positive.
    Logged for the false-positive metric in docs/METRICS.md.
    Does NOT delete the alert — it remains visible in the audit trail.
    """
    ok = alert_store.mark_overridden(alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return {"alert_id": alert_id, "overridden": True}


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
