#!/usr/bin/env python3
"""
GuardPay Attack Simulator — commit 4

Fires synthetic card-testing bursts at the GuardPay backend.

Used for:
  - Live demo in the pitch video: fires a burst and the dashboard lights up
  - Evaluation batches (commit 12): generates labeled attack + normal traffic
    for honest precision/recall measurement

Usage:
    # Demo burst — 40 txn at 10/s against local backend
    python simulator/card_testing_burst.py --target http://localhost:8000

    # Larger burst, faster
    python simulator/card_testing_burst.py --target http://localhost:8000 \\
        --burst-size 80 --rate 20

    # Eval mode — 500 labeled txn at 5/s, labels saved to JSON for commit 12
    python simulator/card_testing_burst.py --target http://localhost:8000 \\
        --eval-mode --output simulator/eval_labels.json

Hard constraint (docs/DESIGN.md): this simulator generates only the basic
card-testing pattern needed for demo + eval. It does not implement or reveal
novel fraud optimization techniques.
"""
import argparse
import json
import random
import sys
import time
import uuid
from datetime import datetime, timezone

import httpx

# ---------------------------------------------------------------------------
# BIN + IP pools
# ---------------------------------------------------------------------------
# Attack traffic: concentrated BINs (1-5 cards), clustered /24 subnet, tiny
# amounts. This is the minimum needed to trigger the velocity/BIN/subnet rules.
ATTACK_BINS = ["411111", "411112", "411113", "411114", "411115"]
ATTACK_SUBNET_PREFIX = "103.21.58"  # all attacker IPs are in this /24

# Normal traffic: varied BINs across issuers, varied subnets, realistic amounts.
NORMAL_BINS = [
    "457173", "542418", "601200", "411082", "543210",
    "510510", "604502", "370000", "378282", "456789",
    "524413", "431274", "601070", "448471", "529080",
    "411858", "516189", "459150", "522120", "535110",
]
NORMAL_SUBNETS = [
    "49.207", "117.96", "223.196", "45.119", "182.73",
    "103.102", "27.56", "59.180", "14.139", "115.248",
    "106.193", "122.172", "203.88", "171.48", "157.41",
]


# ---------------------------------------------------------------------------
# Transaction generators
# ---------------------------------------------------------------------------

def _txn_id() -> str:
    return f"txn_{uuid.uuid4().hex[:8]}"


def make_attack_txn() -> dict:
    """Low-value auth attempt — card-testing pattern."""
    return {
        "transaction_id": _txn_id(),
        "card_bin": random.choice(ATTACK_BINS),
        "amount_paise": random.choice([100, 200, 300, 500]),  # very small amounts
        "ip_address": f"{ATTACK_SUBNET_PREFIX}.{random.randint(1, 254)}",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def make_normal_txn() -> dict:
    """Varied BIN + IP — organic merchant traffic."""
    subnet = random.choice(NORMAL_SUBNETS)
    return {
        "transaction_id": _txn_id(),
        "card_bin": random.choice(NORMAL_BINS),
        "amount_paise": random.randint(5000, 500_000),  # realistic purchase sizes
        "ip_address": f"{subnet}.{random.randint(1, 254)}.{random.randint(1, 254)}",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


# ---------------------------------------------------------------------------
# Burst runner
# ---------------------------------------------------------------------------

def run_burst(
    target: str,
    burst_size: int,
    rate: float,
    attack_ratio: float = 0.75,
) -> dict:
    """
    Fire `burst_size` transactions at `rate` txn/s.
    `attack_ratio` fraction are card-testing; the rest are normal traffic.

    Returns a summary dict with ok/fail counts and per-txn labels (for eval).
    """
    url = f"{target}/transactions"
    interval = 1.0 / rate

    # Build the send list: attack burst first, then normal, then shuffle
    n_attack = int(burst_size * attack_ratio)
    n_normal = burst_size - n_attack
    txns = (
        [(make_attack_txn(), "attack") for _ in range(n_attack)]
        + [(make_normal_txn(), "normal") for _ in range(n_normal)]
    )
    # Keep attack transactions as a contiguous burst at the start (realistic
    # card-testing behaviour), with normal traffic interleaved after.
    # First ~80% of positions: attack; last ~20%: normal — already ordered above.

    results = {"ok": 0, "fail": 0, "attack_sent": 0, "normal_sent": 0, "labels": []}

    with httpx.Client(timeout=10.0) as client:
        for i, (txn, label) in enumerate(txns):
            try:
                r = client.post(url, json=txn)
                if r.status_code in (200, 202):
                    results["ok"] += 1
                else:
                    results["fail"] += 1
                    print(f"  [WARN] txn {i+1}/{burst_size} → HTTP {r.status_code}")
            except httpx.RequestError as exc:
                results["fail"] += 1
                print(f"  [ERR]  txn {i+1}/{burst_size} → {exc}")

            results[f"{label}_sent"] += 1
            results["labels"].append(
                {"transaction_id": txn["transaction_id"], "label": label}
            )

            if i < len(txns) - 1:
                time.sleep(interval)

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="GuardPay attack simulator")
    parser.add_argument(
        "--target", default="http://localhost:8000",
        help="Backend base URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--burst-size", type=int, default=40,
        help="Total transactions to send (default: 40)"
    )
    parser.add_argument(
        "--rate", type=float, default=10.0,
        help="Transactions per second (default: 10)"
    )
    parser.add_argument(
        "--attack-ratio", type=float, default=0.75,
        help="Fraction of transactions that are attack traffic (default: 0.75)"
    )
    parser.add_argument(
        "--eval-mode", action="store_true",
        help="Eval mode: 500 transactions at 5 txn/s for commit-12 metrics"
    )
    parser.add_argument(
        "--output", default=None,
        help="Write per-txn labels to this JSON file (for eval)"
    )
    args = parser.parse_args()

    if args.eval_mode:
        args.burst_size = 500
        args.rate = 5.0
        print(f"[eval-mode] Generating {args.burst_size} labeled transactions "
              f"at {args.rate} txn/s ...")
    else:
        print(f"[demo-mode] Burst: {args.burst_size} txn @ {args.rate}/s "
              f"({int(args.attack_ratio * 100)}% attack) -> {args.target}")

    # Health check — fail fast if backend is down
    try:
        r = httpx.get(f"{args.target}/health", timeout=5.0)
        if r.status_code != 200:
            print(f"[ERROR] Backend health check failed: HTTP {r.status_code}")
            return 1
        print(f"[OK]   Backend is up at {args.target}")
    except httpx.RequestError as exc:
        print(f"[ERROR] Cannot reach {args.target}: {exc}")
        print("        Is the backend running?  uvicorn backend.main:app --reload")
        return 1

    results = run_burst(
        target=args.target,
        burst_size=args.burst_size,
        rate=args.rate,
        attack_ratio=args.attack_ratio,
    )

    print(f"\n--- Burst complete ---")
    print(f"  Attack sent : {results['attack_sent']}")
    print(f"  Normal sent : {results['normal_sent']}")
    print(f"  Accepted    : {results['ok']}")
    print(f"  Failed      : {results['fail']}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results["labels"], f, indent=2)
        print(f"  Labels saved: {args.output}")

    return 0 if results["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
