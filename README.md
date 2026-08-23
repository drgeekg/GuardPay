# GuardPay — AI Security & Fraud Desk for Merchants

**Razorpay AI Buildathon 2026 — Track 02 (AI Risk Manager)**

A plug-and-play fraud triage dashboard. A merchant connects their Razorpay
test-mode account, GuardPay watches the live transaction stream, flags
attack patterns (card testing, bot bursts, fake-return fraud) in real time,
and gives the merchant a one-click, explainable mitigation action —
not just an alert.

## The problem

Card-testing bots and low-value fraud bursts cost merchants real money in
processing fees and chargebacks, and by the time a human notices the
pattern in a dashboard, the damage is done. Existing fraud tools flag
transactions one at a time; they don't explain the attack, size the blast
radius, or act.

## What GuardPay does

1. Simulates or ingests a burst of suspicious transactions.
2. A deterministic velocity/clustering engine flags the anomaly fast
   (no LLM latency on the detection path).
3. An LLM agent turns the flagged cluster into an **Incident Dossier**:
   root cause, affected BIN/subnet, estimated fee damage.
4. The merchant gets two bounded, reversible actions:
   `Auto-Block Subnet` and `Enable Mandatory 3DS Step-up` — every action
   is logged, explainable, and undoable.

Full write-up: see [`docs/DESIGN.md`](docs/DESIGN.md).
Build plan / commit log: see [`docs/PLAN.md`](docs/PLAN.md).
API contract: see [`docs/API.md`](docs/API.md).
Evaluation results: see [`docs/METRICS.md`](docs/METRICS.md).

## Quick start

```bash
# 1. Clone and install
git clone <repo-url> && cd guardpay
cp .env.example .env   # add Razorpay test-mode keys

# 2. Backend
cd backend && pip install -r requirements.txt
uvicorn main:app --reload

# 3. Frontend
cd frontend && npm install && npm run dev

# 4. Run the attack simulator against your local backend
python simulator/card_testing_burst.py --target http://localhost:8000
```

## Tech stack

- **Backend:** FastAPI (Python) — webhook receiver, velocity engine, LLM agent orchestration
- **Frontend:** React + Tailwind — live alert feed, incident dossier view
- **Payments:** Razorpay test-mode APIs + webhooks
- **LLM:** Claude API — incident narrative generation only, never the detection path
- **Data:** synthetic transaction generator (`simulator/`) for demo + eval

## Repo structure

```
guardpay/
├── README.md
├── docs/
│   ├── PLAN.md          # build plan, commit-by-commit
│   ├── DESIGN.md        # architecture, data flow, decisions
│   ├── API.md           # endpoint contracts
│   └── METRICS.md       # precision/recall/false-positive results
├── backend/
├── frontend/
└── simulator/
```

## Status

Build in progress for the Razorpay AI Buildathon. See `docs/PLAN.md` for
current milestone.
