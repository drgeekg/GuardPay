"""
GuardPay Mitigation Actions & Executor — commit 9

Implements bounded, explainable, and reversible risk mitigation actions:
  1. Auto-Block Subnet: declines transactions from the affected /24 subnet for 24h.
  2. Enable Mandatory 3DS: enforces 3DS verification step-up for the affected card BIN for 24h.
  3. Action Undo: reverses any active block or 3DS step-up before expiry.

Hard design constraints (docs/DESIGN.md & docs/PLAN.md):
  - Every action requires reason acknowledgment (gated).
  - Every action defines its blast radius and duration (bounded).
  - Every action writes to the append-only AuditStore.
  - Every action is reversible.
"""

import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

from backend.alerts import Alert, alert_store
from backend.audit import audit_store


class MitigationAction:
    def __init__(
        self,
        action_id: str,
        alert_id: str,
        action_type: str,  # "block_subnet" | "enable_3ds"
        target: str,       # subnet (e.g. "103.21.58.0/24") or BIN (e.g. "411111")
        effect: str,
        actor: str,
        created_at: datetime,
        reversible_until: datetime,
        audit_log_id: str,
    ):
        self.action_id = action_id
        self.alert_id = alert_id
        self.action_type = action_type
        self.target = target
        self.effect = effect
        self.actor = actor
        self.created_at = created_at
        self.reversible_until = reversible_until
        self.audit_log_id = audit_log_id
        self.undone = False

    def is_active(self, now: Optional[datetime] = None) -> bool:
        if self.undone:
            return False
        current_time = now or datetime.now(timezone.utc)
        return current_time <= self.reversible_until

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "alert_id": self.alert_id,
            "action_type": self.action_type,
            "target": self.target,
            "effect": self.effect,
            "actor": self.actor,
            "created_at": self.created_at.isoformat(),
            "reversible_until": self.reversible_until.isoformat(),
            "audit_log_id": self.audit_log_id,
            "undone": self.undone,
        }


class ActionExecutor:
    def __init__(self) -> None:
        self._actions: List[MitigationAction] = []
        self._by_id: Dict[str, MitigationAction] = {}
        self._counter = 0
        self._lock = threading.Lock()

    def _next_id(self) -> str:
        self._counter += 1
        return f"act_{self._counter:03d}"

    def block_subnet(self, alert_id: str, actor: str, reason_acknowledged: bool) -> MitigationAction:
        """
        Blocks the affected subnet for 24 hours. Writes an audit log entry.
        """
        if not reason_acknowledged:
            raise ValueError("Reason acknowledgment is required to execute a mitigation action.")

        alert = alert_store.get_by_id(alert_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found.")

        now = datetime.now(timezone.utc)
        reversible_until = now + timedelta(hours=24)
        subnet = alert.affected_subnet
        effect = f"Subnet {subnet} blocked for 24h"

        with self._lock:
            action_id = self._next_id()
            reason = f"Merchant confirmed subnet block for {alert.pattern_type} attack from {subnet}"
            audit_entry = audit_store.record(
                action_id=action_id,
                alert_id=alert_id,
                actor=actor,
                action_type="block_subnet",
                reason=reason,
                reversible_until=reversible_until,
            )

            action = MitigationAction(
                action_id=action_id,
                alert_id=alert_id,
                action_type="block_subnet",
                target=subnet,
                effect=effect,
                actor=actor,
                created_at=now,
                reversible_until=reversible_until,
                audit_log_id=audit_entry.audit_log_id,
            )
            self._actions.append(action)
            self._by_id[action_id] = action
            return action

    def enable_3ds(self, alert_id: str, actor: str, reason_acknowledged: bool) -> MitigationAction:
        """
        Enables mandatory 3DS step-up for the affected BIN for 24 hours. Writes an audit log entry.
        """
        if not reason_acknowledged:
            raise ValueError("Reason acknowledgment is required to execute a mitigation action.")

        alert = alert_store.get_by_id(alert_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found.")

        now = datetime.now(timezone.utc)
        reversible_until = now + timedelta(hours=24)
        card_bin = alert.affected_bin
        effect = f"Mandatory 3DS step-up enabled for BIN {card_bin} for 24h"

        with self._lock:
            action_id = self._next_id()
            reason = f"Merchant enabled 3DS step-up for BIN {card_bin} due to {alert.pattern_type}"
            audit_entry = audit_store.record(
                action_id=action_id,
                alert_id=alert_id,
                actor=actor,
                action_type="enable_3ds",
                reason=reason,
                reversible_until=reversible_until,
            )

            action = MitigationAction(
                action_id=action_id,
                alert_id=alert_id,
                action_type="enable_3ds",
                target=card_bin,
                effect=effect,
                actor=actor,
                created_at=now,
                reversible_until=reversible_until,
                audit_log_id=audit_entry.audit_log_id,
            )
            self._actions.append(action)
            self._by_id[action_id] = action
            return action

    def undo_action(self, action_id: str, actor: str = "merchant_admin") -> dict:
        """
        Reverses an executed action and writes an undo audit log entry.
        """
        with self._lock:
            action = self._by_id.get(action_id)
            if not action:
                raise ValueError(f"Action {action_id} not found.")
            if action.undone:
                raise ValueError(f"Action {action_id} has already been undone.")

            now = datetime.now(timezone.utc)
            if now > action.reversible_until:
                raise ValueError(f"Action {action_id} is no longer reversible (expired at {action.reversible_until}).")

            action.undone = True
            audit_store.mark_action_undone(action_id)

            reverse_effect = f"Reversed: {action.effect}"
            undo_entry = audit_store.record(
                action_id=action_id,
                alert_id=action.alert_id,
                actor=actor,
                action_type="undo",
                reason=f"Merchant reversed action {action_id} ({action.action_type})",
            )

            return {
                "action_id": action.action_id,
                "status": "undone",
                "effect": reverse_effect,
                "audit_log_id": undo_entry.audit_log_id,
            }

    def is_subnet_blocked(self, ip_address: str) -> bool:
        """Checks if the given IP address falls into an actively blocked /24 subnet."""
        now = datetime.now(timezone.utc)
        parts = ip_address.split(".")
        if len(parts) < 3:
            return False
        target_subnet = f"{'.'.join(parts[:3])}.0/24"

        with self._lock:
            for act in self._actions:
                if act.action_type == "block_subnet" and act.is_active(now):
                    if act.target == target_subnet:
                        return True
        return False

    def is_3ds_required(self, card_bin: str) -> bool:
        """Checks if the given BIN is under active mandatory 3DS step-up."""
        now = datetime.now(timezone.utc)
        with self._lock:
            for act in self._actions:
                if act.action_type == "enable_3ds" and act.is_active(now):
                    # Check if BIN is in target (single or comma-separated)
                    if card_bin in [b.strip() for b in act.target.split(",")]:
                        return True
        return False

    def get_by_id(self, action_id: str) -> Optional[MitigationAction]:
        with self._lock:
            return self._by_id.get(action_id)

    def get_all(self) -> List[MitigationAction]:
        with self._lock:
            return list(reversed(self._actions))

    def reset(self) -> None:
        with self._lock:
            self._actions.clear()
            self._by_id.clear()
            self._counter = 0


# Module-level singleton
action_executor = ActionExecutor()
