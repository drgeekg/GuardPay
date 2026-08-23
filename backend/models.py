"""
GuardPay shared Pydantic models.

These are the request/response shapes that cross the HTTP boundary.
Internal engine types (TransactionEvent, AnomalyResult) live in velocity.py.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

class TransactionEventRequest(BaseModel):
    """Body for POST /transactions — matches docs/API.md exactly."""
    transaction_id: str
    card_bin: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    amount_paise: int = Field(..., ge=0)
    ip_address: str
    timestamp: datetime


class TransactionEventResponse(BaseModel):
    accepted: bool
    transaction_id: str


# ---------------------------------------------------------------------------
# Alerts  (response shapes; store filled in commit 6)
# ---------------------------------------------------------------------------

class AlertOut(BaseModel):
    alert_id: str
    severity: str
    pattern_type: str
    affected_bin: str
    affected_subnet: str
    transaction_ids: List[str]
    created_at: datetime


# ---------------------------------------------------------------------------
# Dossier  (filled in commit 8)
# ---------------------------------------------------------------------------

class DossierOut(BaseModel):
    alert_id: str
    root_cause: str
    estimated_fee_damage_paise: int
    blast_radius: str
    confidence: str
    summary: str


# ---------------------------------------------------------------------------
# Actions  (filled in commit 9)
# ---------------------------------------------------------------------------

class ActionRequest(BaseModel):
    actor: str
    reason_acknowledged: bool


class ActionOut(BaseModel):
    action_id: str
    effect: str
    reversible_until: datetime
    audit_log_id: str


# ---------------------------------------------------------------------------
# Audit log  (filled in commit 9)
# ---------------------------------------------------------------------------

class AuditLogEntryOut(BaseModel):
    audit_log_id: str
    action_id: str
    alert_id: str
    actor: str
    action_type: str
    reason: str
    timestamp: datetime
    reversible_until: Optional[datetime]
    undone: bool


# ---------------------------------------------------------------------------
# Metrics  (filled in commit 12)
# ---------------------------------------------------------------------------

class MetricsSummaryOut(BaseModel):
    batch_size: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    false_positive_cost_estimate_paise: int
