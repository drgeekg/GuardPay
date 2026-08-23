# Build Plan

Solo build, ~3-4 focused days. Each commit below is one PR-sized chunk —
push after each one so the repo shows real incremental progress (judges
can see this, and it's proof you built it, not generated it in one shot).

## Definition of done (from the buildathon brief)

Before calling this finished, all of these must be true:

- [ ] Real problem, working product, meaningful use of AI (Open Track bar)
- [ ] Every money-touching action is explainable, bounded, and gated
- [ ] At least one failure case is handled gracefully, and shown in the demo
- [ ] Honest metrics reported, including false-positive cost — no cherry-picking
- [ ] Public repo + 5-minute pitch video + architecture doc, all linked from README

## Milestones

| Milestone | Commits | Target |
|---|---|---|
| M1 — Skeleton runs | 1-3 | Day 1 morning |
| M2 — Detection works end-to-end | 4-7 | Day 1 evening |
| M3 — AI + actions layer | 8-9 | Day 2 |
| M4 — Demo-ready dashboard | 10-11 | Day 3 |
| M5 — Metrics + polish + video | 12-13 | Day 3-4 |

## Commit-by-commit

### Phase 1 — Skeleton

**1. `init: repo scaffold, README, LICENSE`** — 15 min
Folder structure as in README, MIT license, `.env.example`, `.gitignore`.

**2. `docs: architecture diagram + track justification`** — 30 min
Write `docs/DESIGN.md` before writing code. This is a required deliverable —
doing it early also forces you to think through the design instead of
discovering problems mid-build.

**3. `feat: backend scaffold`** — 45 min
FastAPI app boots, `/health` endpoint, Razorpay test-mode key config loaded
from env, empty webhook receiver stub at `/webhook/razorpay`.

### Phase 2 — Detection engine (the demo's core loop)

**4. `feat: attack simulator`** — 2 hrs
Script that fires a burst of synthetic low-value transactions (varied
IP/BIN, configurable rate) at the backend. This is what you'll run live in
your pitch video, so make it reliable before anything else.

**5. `feat: velocity filter engine`** — 2-3 hrs
Deterministic rules only, no LLM: transactions/min per card, BIN
clustering, IP subnet clustering. Fast and explainable by design — this is
the detection path, keep it free of LLM latency and non-determinism.

**6. `feat: alert generation`** — 1 hr
Anomaly → structured alert object: severity, pattern type, affected
BIN/subnet, timestamp, transaction IDs.

**7. `test: simulator → alert fires correctly`** — 30 min
**First shippable milestone.** Run the simulator, confirm the alert
appears with correct fields. Commit a short test/demo script that proves
it, not just manual verification.

### Phase 3 — AI + bounded actions

**8. `feat: LLM incident dossier`** — 2-3 hrs
Given an alert, the LLM writes: root-cause narrative, estimated fee
damage, blast radius. LLM is explanation-only here — it does not decide
whether to flag, the velocity engine already did that.

**9. `feat: mitigation actions`** — 2 hrs
`Auto-Block Subnet` and `Enable 3DS Step-up`. Non-negotiable requirements
per the buildathon brief:
- Every action writes an audit log entry (who/what/when/why)
- Every action is reversible (an "undo" path exists)
- Every action's trigger reasoning is shown to the merchant before they click

### Phase 4 — Demo surface

**10. `feat: frontend dashboard`** — 3-4 hrs
Live alert feed, incident dossier detail view, the two action buttons,
audit log view.

**11. `feat: graceful failure handling`** — 1-2 hrs
Pick one concrete failure case and handle it visibly in the UI — e.g. a
false positive gets flagged, merchant overrides it, override is logged.
This satisfies "show one failure handled gracefully" from the brief.

### Phase 5 — Proof + submission

**12. `docs: metrics`** — 1-2 hrs
Run the simulator against a mixed batch (attack traffic + normal traffic),
fill in `docs/METRICS.md` with actual precision/recall and false-positive
cost. Do not report a cherry-picked single run.

**13. `docs: final README + pitch video`** — 1 hr
Record the 5-minute video: problem (30s) → live simulator attack (60s) →
dashboard alert + incident dossier (90s) → one-click action + audit log
(60s) → metrics + one failure case handled (60s). Link the video in
README.

## Working rule

Push after every commit above, in order. Don't batch commits — a repo
with 13 small commits over 3 days reads as "built it," a repo with 2 giant
commits reads as "dumped it."
