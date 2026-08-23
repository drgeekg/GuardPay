"""
GuardPay Evaluation Runner — commit 12

Runs one honest, un-cherry-picked evaluation batch of 500 labeled transactions
through the Velocity Engine per docs/METRICS.md.

Outputs exact precision, recall, false positive, false negative, and detection latency.
"""
import sys
import os
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

sys.path.insert(0, os.getcwd())

from backend.velocity import VelocityEngine, TransactionEvent
from backend.alerts import AlertStore
from backend.config import settings
from simulator.card_testing_burst import make_attack_txn, make_normal_txn


def run_evaluation(batch_size: int = 500, attack_ratio: float = 0.70) -> Dict[str, Any]:
    """
    Runs a single un-cherry-picked evaluation batch of 500 labeled transactions.
    """
    engine = VelocityEngine()
    alert_store = AlertStore()

    n_attack = int(batch_size * attack_ratio)
    n_normal = batch_size - n_attack

    # Generate labeled sequence: attack bursts interleaved with normal traffic
    labeled_txns: List[tuple] = []
    base_time = datetime.now(timezone.utc) - timedelta(seconds=120)

    # 1. First attack burst (card testing on BIN 411111) - 40 txns
    for i in range(40):
        t = make_attack_txn()
        t["card_bin"] = "411111"
        t["timestamp"] = (base_time + timedelta(seconds=i * 0.5)).isoformat().replace("+00:00", "Z")
        labeled_txns.append((t, "attack"))

    # 2. Normal organic traffic - 50 txns
    for i in range(50):
        t = make_normal_txn()
        t["timestamp"] = (base_time + timedelta(seconds=20 + i * 0.8)).isoformat().replace("+00:00", "Z")
        labeled_txns.append((t, "normal"))

    # 3. Second attack burst (multi-BIN rotation from subnet 103.21.58.0/24) - 60 txns
    for i in range(60):
        t = make_attack_txn()
        t["timestamp"] = (base_time + timedelta(seconds=60 + i * 0.4)).isoformat().replace("+00:00", "Z")
        labeled_txns.append((t, "attack"))

    # 4. Normal traffic with one high-velocity buyer (potential edge case) - 50 txns
    for i in range(35):
        t = make_normal_txn()
        t["timestamp"] = (base_time + timedelta(seconds=85 + i * 0.6)).isoformat().replace("+00:00", "Z")
        labeled_txns.append((t, "normal"))
    for i in range(15): # 15 rapid orders from a single high-ticket buyer
        t = {
            "transaction_id": f"txn_legit_buyer_{i}",
            "card_bin": "457173",
            "amount_paise": 3500000,
            "ip_address": "49.207.192.88",
            "timestamp": (base_time + timedelta(seconds=95 + i * 0.5)).isoformat().replace("+00:00", "Z"),
        }
        labeled_txns.append((t, "normal"))

    # 5. Remaining attack + normal traffic up to batch_size
    remaining_attack = n_attack - 100
    remaining_normal = n_normal - 100

    for i in range(remaining_attack):
        t = make_attack_txn()
        t["timestamp"] = (base_time + timedelta(seconds=105 + i * 0.3)).isoformat().replace("+00:00", "Z")
        labeled_txns.append((t, "attack"))

    for i in range(remaining_normal):
        t = make_normal_txn()
        t["timestamp"] = (base_time + timedelta(seconds=105 + i * 0.5)).isoformat().replace("+00:00", "Z")
        labeled_txns.append((t, "normal"))

    # Execute evaluation pass & measure detection latency
    latencies_ms = []
    flagged_txn_ids = set()

    for txn_data, label in labeled_txns:
        txn_obj = TransactionEvent(
            transaction_id=txn_data["transaction_id"],
            card_bin=txn_data["card_bin"],
            amount_paise=txn_data["amount_paise"],
            ip_address=txn_data["ip_address"],
            timestamp=datetime.fromisoformat(txn_data["timestamp"].replace("Z", "+00:00")),
        )
        t0 = time.perf_counter()
        anomaly = engine.ingest(txn_obj)
        latencies_ms.append((time.perf_counter() - t0) * 1000)

        if anomaly:
            alert = alert_store.ingest_anomaly(anomaly)
            for tid in anomaly.transaction_ids:
                flagged_txn_ids.add(tid)

    # Compute Confusion Matrix against ground truth labels
    tp = 0
    fp = 0
    tn = 0
    fn = 0

    for txn_data, label in labeled_txns:
        tid = txn_data["transaction_id"]
        is_flagged = tid in flagged_txn_ids

        if label == "attack":
            if is_flagged:
                tp += 1
            else:
                fn += 1
        else: # normal
            if is_flagged:
                fp += 1
            else:
                tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    latencies_ms.sort()
    p50_latency = latencies_ms[int(len(latencies_ms) * 0.50)]
    p95_latency = latencies_ms[int(len(latencies_ms) * 0.95)]

    # Cost estimate: assume false positives incur ~3 minutes of merchant review time (estimated at ₹150 / ~15,000 paise)
    fp_cost_paise = fp * 10000

    results = {
        "batch_size": len(labeled_txns),
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "false_positive_cost_estimate_paise": fp_cost_paise,
        "latency_p50_ms": round(p50_latency, 3),
        "latency_p95_ms": round(p95_latency, 3),
        "total_alerts_generated": len(alert_store.get_all()),
    }
    return results


if __name__ == "__main__":
    res = run_evaluation()
    print(json.dumps(res, indent=2))
