"""
GuardPay Alert Store — commit 6

Converts AnomalyResult objects from the velocity engine into persisted
Alert objects and exposes them via GET /alerts.

Design notes:
  - In-memory store (list + dict) — no external DB required for the demo.
  - Deduplication: a new anomaly is merged into an existing open alert if
    it shares the same pattern_type AND affected_subnet, and the alert is
    less than `ALERT_MERGE_WINDOW_SECONDS` old. This prevents 40+ alerts
    from a single burst appearing as separate incidents on the dashboard.
  - Alert IDs are sequential strings ("alert_001", "alert_002", ...) so
    they sort naturally in the UI.
  - Thread-safe; shares the same lock model as the velocity engine.
"""

import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.velocity import AnomalyResult

# How many seconds to keep an alert "open" for merging new anomalies.
# After this window, a fresh anomaly creates a new alert.
ALERT_MERGE_WINDOW_SECONDS = 300  # 5 minutes


class Alert:
    """
    A persisted fraud incident. Created when the velocity engine raises an
    anomaly; updated (merged) when subsequent anomalies match the same
    pattern + subnet within the merge window.
    """

    def __init__(self, alert_id: str, anomaly: AnomalyResult, created_at: datetime):
        self.alert_id = alert_id
        self.severity = anomaly.severity
        self.pattern_type = anomaly.pattern_type
        self.rule_fired = anomaly.rule_fired
        self.affected_bin = anomaly.affected_bin
        self.affected_subnet = anomaly.affected_subnet
        self.transaction_ids: List[str] = list(anomaly.transaction_ids)
        self.created_at = created_at
        self.dossier: Optional[dict] = None   # filled by LLM agent in commit 8
        self.overridden: bool = False          # set True by POST /alerts/{id}/override

    def merge(self, anomaly: AnomalyResult) -> None:
        """Add new transaction IDs from a matching anomaly into this alert."""
        existing = set(self.transaction_ids)
        for tid in anomaly.transaction_ids:
            if tid not in existing:
                self.transaction_ids.append(tid)
                existing.add(tid)
        # Update affected fields if the new anomaly expands the blast radius
        if anomaly.severity == "high" and self.severity != "high":
            self.severity = "high"

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity,
            "pattern_type": self.pattern_type,
            "affected_bin": self.affected_bin,
            "affected_subnet": self.affected_subnet,
            "transaction_ids": self.transaction_ids,
            "created_at": self.created_at.isoformat(),
            "overridden": self.overridden,
        }


class AlertStore:
    """
    In-memory store for Alert objects.
    Thread-safe; one instance shared across all requests.
    """

    def __init__(self) -> None:
        self._alerts: List[Alert] = []
        self._by_id: Dict[str, Alert] = {}
        self._counter = 0
        self._lock = threading.Lock()

    def _next_id(self) -> str:
        self._counter += 1
        return f"alert_{self._counter:03d}"

    def ingest_anomaly(self, anomaly: AnomalyResult) -> Alert:
        """
        Convert an AnomalyResult into a new or merged Alert.

        Merge logic: if there is already an open alert with the same
        pattern_type and affected_subnet created within ALERT_MERGE_WINDOW_SECONDS,
        merge the new anomaly into it rather than creating a duplicate.
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            # Try to find a merge target
            for existing in reversed(self._alerts):
                age = (now - existing.created_at).total_seconds()
                if (
                    not existing.overridden
                    and existing.pattern_type == anomaly.pattern_type
                    and existing.affected_subnet == anomaly.affected_subnet
                    and age <= ALERT_MERGE_WINDOW_SECONDS
                ):
                    existing.merge(anomaly)
                    return existing

            # No merge target — create a fresh alert
            alert_id = self._next_id()
            alert = Alert(alert_id=alert_id, anomaly=anomaly, created_at=now)
            self._alerts.append(alert)
            self._by_id[alert_id] = alert
            return alert

    def get_all(self) -> List[Alert]:
        """Return all alerts, most recent first."""
        with self._lock:
            return list(reversed(self._alerts))

    def get_by_id(self, alert_id: str) -> Optional[Alert]:
        with self._lock:
            return self._by_id.get(alert_id)

    def mark_overridden(self, alert_id: str) -> bool:
        """Mark alert as a false positive override. Returns False if not found."""
        with self._lock:
            alert = self._by_id.get(alert_id)
            if alert is None:
                return False
            alert.overridden = True
            return True

    def reset(self) -> None:
        """Clear all alerts. Used by tests."""
        with self._lock:
            self._alerts.clear()
            self._by_id.clear()
            self._counter = 0


# Module-level singleton
alert_store = AlertStore()
