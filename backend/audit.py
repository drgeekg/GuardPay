"""
GuardPay Immutable Audit Log Store — commit 9

Every money-touching action and merchant override writes an immutable,
append-only audit log entry.

Hard design constraints (docs/DESIGN.md & docs/API.md):
  1. Source of truth for "explainable, bounded, gated" requirement:
     every entry traces back to an alert, actor, timestamp, and explicit reason.
  2. Bounded & reversible: records `reversible_until` timestamps (24h default).
  3. Reversal tracking: captures `undone` status updates without deleting historical rows.
"""

import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional


class AuditLogEntry:
    def __init__(
        self,
        audit_log_id: str,
        action_id: Optional[str],
        alert_id: str,
        actor: str,
        action_type: str,
        reason: str,
        timestamp: datetime,
        reversible_until: Optional[datetime] = None,
        undone: bool = False,
    ):
        self.audit_log_id = audit_log_id
        self.action_id = action_id or ""
        self.alert_id = alert_id
        self.actor = actor
        self.action_type = action_type
        self.reason = reason
        self.timestamp = timestamp
        self.reversible_until = reversible_until
        self.undone = undone

    def to_dict(self) -> dict:
        return {
            "audit_log_id": self.audit_log_id,
            "action_id": self.action_id,
            "alert_id": self.alert_id,
            "actor": self.actor,
            "action_type": self.action_type,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "reversible_until": self.reversible_until.isoformat() if self.reversible_until else None,
            "undone": self.undone,
        }


class AuditStore:
    """
    Append-only thread-safe store for audit log entries.
    """

    def __init__(self) -> None:
        self._entries: List[AuditLogEntry] = []
        self._by_id: Dict[str, AuditLogEntry] = {}
        self._counter = 0
        self._lock = threading.Lock()

    def _next_id(self) -> str:
        self._counter += 1
        return f"audit_{self._counter:04d}"

    def record(
        self,
        action_id: Optional[str],
        alert_id: str,
        actor: str,
        action_type: str,
        reason: str,
        reversible_until: Optional[datetime] = None,
    ) -> AuditLogEntry:
        now = datetime.now(timezone.utc)
        with self._lock:
            audit_id = self._next_id()
            entry = AuditLogEntry(
                audit_log_id=audit_id,
                action_id=action_id,
                alert_id=alert_id,
                actor=actor,
                action_type=action_type,
                reason=reason,
                timestamp=now,
                reversible_until=reversible_until,
                undone=False,
            )
            self._entries.append(entry)
            self._by_id[audit_id] = entry
            return entry

    def mark_action_undone(self, action_id: str) -> None:
        with self._lock:
            for entry in self._entries:
                if entry.action_id == action_id:
                    entry.undone = True

    def get_all(self) -> List[AuditLogEntry]:
        """Returns all audit log entries, newest first."""
        with self._lock:
            return list(reversed(self._entries))

    def get_by_id(self, audit_log_id: str) -> Optional[AuditLogEntry]:
        with self._lock:
            return self._by_id.get(audit_log_id)

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()
            self._by_id.clear()
            self._counter = 0


# Module-level singleton
audit_store = AuditStore()
