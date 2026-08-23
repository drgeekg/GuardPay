"""
GuardPay Velocity / Clustering Engine — commit 5

Deterministic-only anomaly detection. NO LLM calls anywhere in this module.

This is the detection path — it must be fast, reproducible, and auditable.
Every rule that fires can be pointed to by name and threshold value.

Rules implemented
-----------------
1. txn_per_bin     : too many transactions with the same card BIN in the
                     rolling window  →  pattern_type="card_testing"
2. bin_clustering  : too many unique BINs arriving from the same /24 subnet
                     (bot rotating cards to avoid per-BIN limits)
                     →  pattern_type="bin_clustering"
3. subnet_cluster  : too many unique IPs from the same /24 subnet
                     (bot farm using a hosting block)
                     →  pattern_type="subnet_clustering"

All thresholds are read from backend.config.settings — no hardcoded values.

Design constraint (docs/DESIGN.md §Design principles):
  The decision to flag a transaction cluster never depends on an LLM call.
  Velocity and clustering rules do that, fast and reproducibly.
"""

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from backend.config import settings


# ---------------------------------------------------------------------------
# Internal data types
# ---------------------------------------------------------------------------

@dataclass
class TransactionEvent:
    """Internal representation of a single transaction on the detection path."""
    transaction_id: str
    card_bin: str
    amount_paise: int
    ip_address: str
    timestamp: datetime   # must be timezone-aware (UTC)


@dataclass
class AnomalyResult:
    """Returned by VelocityEngine.ingest() when a rule fires."""
    flagged: bool
    pattern_type: str     # "card_testing" | "bin_clustering" | "subnet_clustering"
    severity: str         # "high" | "medium"
    rule_fired: str       # human-readable: rule name + threshold that was breached
    affected_bin: str     # BIN or comma-separated list of BINs
    affected_subnet: str  # CIDR notation, e.g. "103.21.58.0/24"
    transaction_ids: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _subnet24(ip: str) -> str:
    """
    Extract the /24 network prefix from an IPv4 address.
    '103.21.58.14'  →  '103.21.58'
    '49.207.192.33' →  '49.207.192'
    """
    parts = ip.split(".")
    return ".".join(parts[:3]) if len(parts) >= 3 else ip


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class VelocityEngine:
    """
    Rolling-window velocity and clustering engine.

    Thread-safe; a single instance is created at module import time and
    shared across all FastAPI requests.  The lock is held only for the
    duration of the in-memory window operations — no I/O inside the lock.

    Hard constraint: this class must never make LLM calls, network calls,
    or non-deterministic decisions.  See docs/DESIGN.md.
    """

    def __init__(self) -> None:
        # Ordered by arrival time — popleft() prunes the oldest entries.
        self._window: deque = deque()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(self, txn: TransactionEvent) -> Optional[AnomalyResult]:
        """
        Record *txn* in the rolling window and evaluate all detection rules.

        Returns an AnomalyResult if any rule fires, None if the transaction
        looks clean.

        Called once per transaction on the synchronous detection path.
        """
        with self._lock:
            self._prune(txn.timestamp)
            self._window.append(txn)
            return self._evaluate(txn)

    def window_size(self) -> int:
        """Number of transactions currently held in the rolling window."""
        with self._lock:
            return len(self._window)

    def reset(self) -> None:
        """Clear the window.  Used by tests to start from a clean state."""
        with self._lock:
            self._window.clear()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _prune(self, now: datetime) -> None:
        """Discard transactions older than the configured rolling window."""
        cutoff = now - timedelta(seconds=settings.velocity_window_seconds)
        while self._window and self._window[0].timestamp < cutoff:
            self._window.popleft()

    def _evaluate(self, trigger: TransactionEvent) -> Optional[AnomalyResult]:
        """
        Check all rules against the current window in priority order.
        First match is returned; subsequent rules are not evaluated.

        Rules are ordered from highest-confidence to lowest so that the
        most specific pattern wins when multiple rules would fire.
        """

        # ── Rule 1 — txn_per_bin ─────────────────────────────────────────
        # Many transactions sharing the same 6-digit BIN in a short window
        # is the hallmark of card-testing bots probing card validity.
        # Threshold: VELOCITY_TXN_PER_CARD_PER_MIN (default 10).
        bin_txns = [t for t in self._window if t.card_bin == trigger.card_bin]
        if len(bin_txns) > settings.velocity_txn_per_card_per_min:
            return AnomalyResult(
                flagged=True,
                pattern_type="card_testing",
                severity="high",
                rule_fired=(
                    f"txn_per_bin > {settings.velocity_txn_per_card_per_min} "
                    f"in {settings.velocity_window_seconds}s window"
                ),
                affected_bin=trigger.card_bin,
                affected_subnet=f"{_subnet24(trigger.ip_address)}.0/24",
                transaction_ids=[t.transaction_id for t in bin_txns],
            )

        # ── Rule 2 — bin_clustering ───────────────────────────────────────
        # Multiple distinct BINs arriving from the same /24 subnet suggests
        # a bot rotating cards to stay under per-BIN velocity limits.
        # Threshold: VELOCITY_BIN_CLUSTER_THRESHOLD (default 5 unique BINs).
        subnet = _subnet24(trigger.ip_address)
        subnet_txns = [t for t in self._window if _subnet24(t.ip_address) == subnet]
        unique_bins = {t.card_bin for t in subnet_txns}
        if len(unique_bins) >= settings.velocity_bin_cluster_threshold:
            return AnomalyResult(
                flagged=True,
                pattern_type="bin_clustering",
                severity="high",
                rule_fired=(
                    f"unique_bins_from_subnet >= {settings.velocity_bin_cluster_threshold} "
                    f"in {settings.velocity_window_seconds}s window"
                ),
                affected_bin=", ".join(sorted(unique_bins)),
                affected_subnet=f"{subnet}.0/24",
                transaction_ids=[t.transaction_id for t in subnet_txns],
            )

        # ── Rule 3 — subnet_cluster ───────────────────────────────────────
        # Many distinct source IPs from a single /24 subnet. Indicates a
        # distributed bot farm operating out of one hosting block.
        # Threshold: VELOCITY_SUBNET_CLUSTER_THRESHOLD (default 8 unique IPs).
        unique_ips = {t.ip_address for t in subnet_txns}
        if len(unique_ips) >= settings.velocity_subnet_cluster_threshold:
            return AnomalyResult(
                flagged=True,
                pattern_type="subnet_clustering",
                severity="medium",
                rule_fired=(
                    f"unique_ips_from_subnet >= {settings.velocity_subnet_cluster_threshold} "
                    f"in {settings.velocity_window_seconds}s window"
                ),
                affected_bin=trigger.card_bin,
                affected_subnet=f"{subnet}.0/24",
                transaction_ids=[t.transaction_id for t in subnet_txns],
            )

        return None  # transaction is clean; no rule fired


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
# One engine instance, created at import time, shared across all requests.
# Tests should call engine.reset() between runs to clear the rolling window.
engine = VelocityEngine()
