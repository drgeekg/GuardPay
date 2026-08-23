# API Contract

Base URL (local): `http://localhost:8000`

## Health

### `GET /health`
Returns `200 {"status": "ok"}`. Used by the simulator and frontend to
confirm the backend is up before a demo run.

---

## Ingestion

### `POST /transactions`
Used by the Attack Simulator (and, in real usage, by Razorpay webhooks) to
feed transaction events into the velocity engine.

**Request body**
```json
{
  "transaction_id": "txn_00123",
  "card_bin": "411111",
  "amount_paise": 500,
  "ip_address": "103.21.58.14",
  "timestamp": "2026-08-23T10:15:32Z"
}
```

**Response `202`**
```json
{ "accepted": true, "transaction_id": "txn_00123" }
```

### `POST /webhook/razorpay`
Receives real Razorpay test-mode webhook events (`payment.authorized`,
`payment.failed`, etc.) and normalizes them into the same internal
transaction event shape as `/transactions`.

---

## Alerts

### `GET /alerts`
Returns the live alert feed, most recent first.

**Response `200`**
```json
[
  {
    "alert_id": "alert_045",
    "severity": "high",
    "pattern_type": "card_testing",
    "affected_bin": "411111",
    "affected_subnet": "103.21.58.0/24",
    "transaction_ids": ["txn_00123", "txn_00124", "..."],
    "created_at": "2026-08-23T10:15:40Z"
  }
]
```

### `GET /alerts/{alert_id}/dossier`
Returns the LLM-generated incident dossier for a given alert. Generated
lazily on first request, cached after.

**Response `200`**
```json
{
  "alert_id": "alert_045",
  "root_cause": "Coordinated low-value authorization attempts consistent with card-testing, originating from a single /24 subnet.",
  "estimated_fee_damage_paise": 18500,
  "blast_radius": "1 BIN, 1 subnet, 42 transactions over 90 seconds",
  "confidence": "high",
  "summary": "Plain-language explanation for the merchant."
}
```

---

## Actions

### `POST /alerts/{alert_id}/actions/block-subnet`
Blocks the affected subnet. Bounded, gated, reversible.

**Request body**
```json
{ "actor": "merchant_demo_1", "reason_acknowledged": true }
```

**Response `200`**
```json
{
  "action_id": "act_009",
  "effect": "Subnet 103.21.58.0/24 blocked for 24h",
  "reversible_until": "2026-08-24T10:20:00Z",
  "audit_log_id": "audit_1042"
}
```

### `POST /alerts/{alert_id}/actions/enable-3ds`
Enables mandatory 3DS step-up for the affected BIN. Same shape as above.

### `POST /actions/{action_id}/undo`
Reverses a previously executed action. Always available until
`reversible_until` expires.

### `POST /alerts/{alert_id}/override`
Merchant marks an alert as a false positive. Logged, does not delete the
alert — used for the false-positive metric in `docs/METRICS.md`.

---

## Audit log

### `GET /audit-log`
Returns every action ever taken (block, enable-3ds, undo, override), in
order, with actor/reason/timestamp. This endpoint is the source of truth
for the "explainable, bounded, gated" requirement — every row must trace
back to an alert and a stated reason.

---

## Metrics

### `GET /metrics/summary`
Returns precision/recall/false-positive numbers computed against the last
evaluation batch (see `docs/METRICS.md` for methodology).

**Response `200`**
```json
{
  "batch_size": 500,
  "true_positives": 41,
  "false_positives": 6,
  "false_negatives": 3,
  "precision": 0.872,
  "recall": 0.932,
  "false_positive_cost_estimate_paise": 0
}
```
