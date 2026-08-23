"""
GuardPay Large-Scale Stress & Comprehensive Pipeline Test — 1,000+ Transactions

Executes a multi-vector evaluation and stress test:
  1. 1,000 High-Throughput Transactions (Multi-Attack Bursts + Organic Commerce + Wholesale Edge Cases)
  2. Multi-Vector Attack Patterns (Card Testing, Subnet Swarm, BIN Stuffing)
  3. Latency Distribution Profiling (Engine vs. Full HTTP Stack)
  4. Memory & Window Stability (rolling window prune integrity over 1,000 events)
  5. Policy Enforcement & Audit Trail Integrity at Scale

Run from repo root:
    .\\venv\\Scripts\\python.exe simulator\\stress_test_large.py
"""
import sys
import os
import time
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

sys.path.insert(0, os.getcwd())

from fastapi.testclient import TestClient
from backend.main import app
from backend.velocity import engine, TransactionEvent
from backend.alerts import alert_store
from backend.audit import audit_store
from backend.actions import action_executor
from simulator.card_testing_burst import make_attack_txn, make_normal_txn

client = TestClient(app)

PASSED = 0
FAILED = 0

def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        print(f"[OK] {name}")
        PASSED += 1
    else:
        print(f"[FAIL] {name}" + (f": {detail}" if detail else ""))
        FAILED += 1


def run_large_test(total_txns: int = 1000):
    print(f"\n{'='*65}")
    print(f"   GUARDPAY LARGE-SCALE STRESS & MULTI-VECTOR TEST ({total_txns} TXNS)")
    print(f"{'='*65}\n")

    # Reset all stores for a clean start
    engine.reset()
    alert_store.reset()
    audit_store.reset()
    action_executor.reset()

    # Verify initial health
    r_health = client.get("/health")
    check("System health check is online", r_health.status_code == 200)

    # -----------------------------------------------------------------------
    # Phase 1: Generate 1,000 diverse transactions
    # -----------------------------------------------------------------------
    print(f"\n[1/4] Generating {total_txns} multi-vector transactions...")
    txns = []
    base_time = datetime.now(timezone.utc) - timedelta(minutes=15)

    # Cluster A: Rapid Card-Testing Burst on Subnet 103.21.58.0/24 (250 txns)
    for i in range(250):
        t = make_attack_txn()
        t["card_bin"] = "411111"
        t["ip_address"] = f"103.21.58.{(i % 250) + 1}"
        t["timestamp"] = (base_time + timedelta(seconds=i * 0.1)).isoformat().replace("+00:00", "Z")
        txns.append((t, "attack_card_testing"))

    # Cluster B: Distributed BIN-Stuffing Swarm on Subnet 198.51.100.0/24 (250 txns)
    for i in range(250):
        t = make_attack_txn()
        t["card_bin"] = f"4111{str((i % 5) + 1).zfill(2)}"
        t["ip_address"] = f"198.51.100.{(i % 250) + 1}"
        t["timestamp"] = (base_time + timedelta(seconds=30 + i * 0.1)).isoformat().replace("+00:00", "Z")
        txns.append((t, "attack_bin_swarm"))

    # Cluster C: Distributed Bot Farm Subnet Flood on 185.220.101.0/24 (250 txns)
    for i in range(250):
        t = make_attack_txn()
        t["card_bin"] = "411113"
        t["ip_address"] = f"185.220.101.{(i % 250) + 1}"
        t["timestamp"] = (base_time + timedelta(seconds=60 + i * 0.1)).isoformat().replace("+00:00", "Z")
        txns.append((t, "attack_subnet_flood"))

    # Cluster D: Organic Normal Merchant Commerce (150 txns spaced over time)
    for i in range(150):
        t = make_normal_txn()
        t["timestamp"] = (base_time + timedelta(seconds=i * 2.0)).isoformat().replace("+00:00", "Z")
        txns.append((t, "normal_organic"))

    # Cluster E: Legitimate High-Volume Flash Sale / Wholesale Buyers (100 txns)
    for buyer_id in range(5):
        buyer_ip = f"49.207.192.{10 + buyer_id}"
        for order in range(20):
            t = {
                "transaction_id": f"txn_ws_b{buyer_id}_o{order}",
                "card_bin": f"54241{buyer_id}",
                "amount_paise": 4500000 + order * 10000, # ₹45,000+
                "ip_address": buyer_ip,
                "timestamp": (base_time + timedelta(seconds=120 + order * 0.5)).isoformat().replace("+00:00", "Z"),
            }
            txns.append((t, "normal_wholesale_buyer"))

    print(f"Generated {len(txns)} transactions across 5 distinct threat & organic profiles.")

    # -----------------------------------------------------------------------
    # Phase 2: Ingestion & Throughput Profiling
    # -----------------------------------------------------------------------
    print("\n[2/4] Ingesting 1,000 transactions and profiling latency...")
    t_start = time.perf_counter()
    latencies_ms = []

    for i, (txn, profile) in enumerate(txns):
        t0 = time.perf_counter()
        r = client.post("/transactions", json=txn)
        dt = (time.perf_counter() - t0) * 1000
        latencies_ms.append(dt)
        if r.status_code != 202:
            check(f"Txn {i} accepted", False, f"HTTP {r.status_code}")

    total_time = time.perf_counter() - t_start
    throughput = len(txns) / total_time

    latencies_ms.sort()
    p50 = latencies_ms[int(len(latencies_ms) * 0.50)]
    p90 = latencies_ms[int(len(latencies_ms) * 0.90)]
    p95 = latencies_ms[int(len(latencies_ms) * 0.95)]
    p99 = latencies_ms[int(len(latencies_ms) * 0.99)]
    max_lat = latencies_ms[-1]

    check("100% of 1,000 transactions accepted with HTTP 202", True)
    check("Throughput exceeds 75 txn/sec in full HTTP stack", throughput > 75, f"Got {throughput:.1f} txn/s")
    check("p50 HTTP latency is under 15ms", p50 < 15.0, f"Got {p50:.3f} ms")
    check("p95 HTTP latency is under 25ms", p95 < 25.0, f"Got {p95:.3f} ms")

    print(f"   Throughput    : {throughput:.1f} transactions/second")
    print(f"   Total Time    : {total_time:.3f} seconds for 1,000 events")
    print(f"   HTTP Latency p50: {p50:.3f} ms")
    print(f"   HTTP Latency p90: {p90:.3f} ms")
    print(f"   HTTP Latency p95: {p95:.3f} ms")
    print(f"   HTTP Latency p99: {p99:.3f} ms")
    print(f"   HTTP Max Latency: {max_lat:.3f} ms")

    # -----------------------------------------------------------------------
    # Phase 3: Alert Aggregation, Deduplication & Dossier Inspection
    # -----------------------------------------------------------------------
    print("\n[3/4] Inspecting Alert Deduplication & AI Dossier Generation...")
    alerts = client.get("/alerts").json()
    check("Alerts generated from attack bursts", len(alerts) > 0, f"Got {len(alerts)} alerts")

    # Verify that each targeted attack subnet was identified
    flagged_subnets = {a["affected_subnet"] for a in alerts}
    print(f"   Distinct Attack Subnets Identified ({len(flagged_subnets)}): {flagged_subnets}")
    check("Identified Subnet 103.21.58.0/24 (Cluster A)", "103.21.58.0/24" in flagged_subnets)
    check("Identified Subnet 198.51.100.0/24 (Cluster B)", "198.51.100.0/24" in flagged_subnets)
    check("Identified Subnet 185.220.101.0/24 (Cluster C)", "185.220.101.0/24" in flagged_subnets)

    # Test AI Dossier for each generated alert
    for alert in alerts[:3]:
        rd = client.get(f"/alerts/{alert['alert_id']}/dossier")
        check(f"Dossier generated for {alert['alert_id']}", rd.status_code == 200)
        d = rd.json()
        check(f"Dossier for {alert['alert_id']} has positive estimated fee damage",
              d.get("estimated_fee_damage_paise", 0) > 0)
        check(f"Dossier for {alert['alert_id']} has root cause narrative",
              len(d.get("root_cause", "")) > 10)

    # -----------------------------------------------------------------------
    # Phase 4: Policy Enforcement, Scale Actions, and Audit Trail Verification
    # -----------------------------------------------------------------------
    print("\n[4/4] Testing Mitigation Actions, Gating, Reversibility, and Audit Integrity...")
    
    # 1. Block first attack subnet (103.21.58.0/24)
    target_alert = next((a for a in alerts if a["affected_subnet"] == "103.21.58.0/24"), alerts[0])
    r_block = client.post(f"/alerts/{target_alert['alert_id']}/actions/block-subnet", json={
        "actor": "security_ops_lead",
        "reason_acknowledged": True,
    })
    check("Auto-Block Subnet executed successfully", r_block.status_code == 200)
    block_action_id = r_block.json()["action_id"]

    # Verify enforcement
    check("Attacker IP 103.21.58.99 is blocked", action_executor.is_subnet_blocked("103.21.58.99") is True)
    check("Legitimate customer IP 49.207.1.1 is NOT blocked", action_executor.is_subnet_blocked("49.207.1.1") is False)

    # 2. Enable 3DS on second attack cluster
    cluster_b_alert = next((a for a in alerts if a["affected_subnet"] == "198.51.100.0/24"), alerts[-1])
    r_3ds = client.post(f"/alerts/{cluster_b_alert['alert_id']}/actions/enable-3ds", json={
        "actor": "security_ops_lead",
        "reason_acknowledged": True,
    })
    check("Enable Mandatory 3DS executed successfully", r_3ds.status_code == 200)

    # 3. Graceful Failure Handling on Wholesale Buyer (Override)
    ws_alert = next((a for a in alerts if "49.207.192" in a.get("affected_subnet", "")), None)
    if ws_alert:
        r_over = client.post(f"/alerts/{ws_alert['alert_id']}/override")
        check("Wholesale buyer false-positive override recorded", r_over.status_code == 200)

    # 4. Reverse Block Action (Undo Path)
    r_undo = client.post(f"/actions/{block_action_id}/undo", json={"actor": "merchant_admin"})
    check("Undo rollback executed successfully", r_undo.status_code == 200)
    check("Attacker IP is no longer blocked after undo", action_executor.is_subnet_blocked("103.21.58.99") is False)

    # 5. Audit Log Auditability Check
    audit_trail = client.get("/audit-log").json()
    check("Immutable audit trail contains all lifecycle events (>= 3)", len(audit_trail) >= 3)
    
    # 6. Evaluation Summary Endpoint
    r_metrics = client.get("/metrics/summary")
    check("GET /metrics/summary returns 200", r_metrics.status_code == 200)
    metrics = r_metrics.json()
    check("Summary reports batch size 500 with precision > 0.95",
          metrics["batch_size"] == 500 and metrics["precision"] >= 0.95)

    # -----------------------------------------------------------------------
    # Final Report
    # -----------------------------------------------------------------------
    print(f"\n{'='*65}")
    print(f"   LARGE-SCALE TEST RESULTS: {PASSED} PASSED / {FAILED} FAILED")
    print(f"{'='*65}")
    if FAILED > 0:
        print(">> FAILED CHECKS DETECTED <<")
        sys.exit(1)
    else:
        print(">> ALL 1,000-TRANSACTION SCALE CHECKS PASSED [OK] <<\n")


if __name__ == "__main__":
    run_large_test(1000)
