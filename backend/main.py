"""
GuardPay — FastAPI backend entry point.

Commit 3: app boots, /health, /webhook/razorpay stub.
Commit 4: /transactions stub added so the attack simulator can POST to it.
Commit 5: velocity engine wired into /transactions.
Commit 6: alert store wired in; GET /alerts and POST override live.
Commit 8: LLM incident dossier generation wired into GET /alerts/{id}/dossier.
Commit 9: mitigation actions (block-subnet, enable-3ds, undo), audit log, and webhook receiver.
"""
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.actions import action_executor
from backend.alerts import alert_store
from backend.audit import audit_store
from backend.config import settings  # noqa: F401 — verifies env loads cleanly
from backend.dossier import generate_dossier
from backend.models import (
    ActionOut,
    ActionRequest,
    AuditLogEntryOut,
    TransactionEventRequest,
    TransactionEventResponse,
)
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
# Ingestion — /transactions
# ---------------------------------------------------------------------------

@app.post("/transactions", tags=["ingestion"], status_code=202,
          response_model=TransactionEventResponse)
async def ingest_transaction(req: TransactionEventRequest):
    """
    Accepts a transaction event from the simulator or Razorpay webhook.
    Passes it through the deterministic velocity engine and returns 202.
    """
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
    Generated lazily on first request, cached after.
    """
    alert = alert_store.get_by_id(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return generate_dossier(alert)


@app.post("/alerts/{alert_id}/override", tags=["alerts"])
def override_alert(alert_id: str, actor: str = "merchant_user") -> dict:
    """
    Merchant marks an alert as a false positive.
    Logged in the audit trail for the false-positive metric in docs/METRICS.md.
    Does NOT delete the alert — it remains visible in the audit trail.
    """
    alert = alert_store.get_by_id(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    alert_store.mark_overridden(alert_id)
    audit_entry = audit_store.record(
        action_id=None,
        alert_id=alert_id,
        actor=actor,
        action_type="override",
        reason=f"Merchant marked alert {alert_id} ({alert.pattern_type}) as false positive",
    )
    return {"alert_id": alert_id, "overridden": True, "audit_log_id": audit_entry.audit_log_id}


# ---------------------------------------------------------------------------
# Mitigation Actions
# ---------------------------------------------------------------------------

@app.post("/alerts/{alert_id}/actions/block-subnet", tags=["actions"], response_model=ActionOut)
def block_subnet_action(alert_id: str, req: ActionRequest):
    """
    Blocks the affected subnet for 24h. Bounded, gated, reversible.
    """
    try:
        action = action_executor.block_subnet(
            alert_id=alert_id,
            actor=req.actor,
            reason_acknowledged=req.reason_acknowledged,
        )
        return ActionOut(
            action_id=action.action_id,
            effect=action.effect,
            reversible_until=action.reversible_until,
            audit_log_id=action.audit_log_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/alerts/{alert_id}/actions/enable-3ds", tags=["actions"], response_model=ActionOut)
def enable_3ds_action(alert_id: str, req: ActionRequest):
    """
    Enables mandatory 3DS step-up for the affected BIN for 24h.
    """
    try:
        action = action_executor.enable_3ds(
            alert_id=alert_id,
            actor=req.actor,
            reason_acknowledged=req.reason_acknowledged,
        )
        return ActionOut(
            action_id=action.action_id,
            effect=action.effect,
            reversible_until=action.reversible_until,
            audit_log_id=action.audit_log_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/actions/{action_id}/undo", tags=["actions"])
def undo_action_endpoint(action_id: str, req: Optional[dict] = None):
    """
    Reverses a previously executed mitigation action before expiration.
    """
    actor = (req or {}).get("actor", "merchant_admin") if req else "merchant_admin"
    try:
        return action_executor.undo_action(action_id=action_id, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

@app.get("/audit-log", tags=["audit-log"])
def get_audit_log() -> List[dict]:
    """
    Returns every action ever taken (block, enable-3ds, undo, override), in order, with actor/reason/timestamp.
    """
    return [entry.to_dict() for entry in audit_store.get_all()]


# ---------------------------------------------------------------------------
# Webhook receiver — Razorpay test-mode webhook events
# ---------------------------------------------------------------------------

@app.post("/webhook/razorpay", tags=["ingestion"], status_code=200)
async def razorpay_webhook(request: Request):
    """
    Receives Razorpay test-mode webhook events (payment.authorized,
    payment.failed, etc.) and normalizes them into the internal
    transaction event shape.
    """
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    secret = settings.razorpay_key_secret.strip()
    if signature and secret and not secret.startswith("YOUR_"):
        expected_sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

    payload = json.loads(body.decode() or "{}") if body else {}
    event_type = payload.get("event", "unknown")
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    if payment:
        txn_id = payment.get("id", f"txn_{uuid.uuid4().hex[:8]}")
        card = payment.get("card", {})
        raw_bin = str(card.get("emi_sub_type") or card.get("network") or "411111")
        card_bin = raw_bin[:6].ljust(6, "0")
        amount = int(payment.get("amount", 0))
        ip = payment.get("ip_address") or "127.0.0.1"
        created_at_ts = payment.get("created_at")
        txn_time = datetime.fromtimestamp(created_at_ts, tz=timezone.utc) if created_at_ts else datetime.now(timezone.utc)

        txn = TransactionEvent(
            transaction_id=txn_id,
            card_bin=card_bin,
            amount_paise=amount,
            ip_address=ip,
            timestamp=txn_time,
        )
        anomaly = engine.ingest(txn)
        if anomaly:
            alert_store.ingest_anomaly(anomaly)

    return {"received": True, "event": event_type}

