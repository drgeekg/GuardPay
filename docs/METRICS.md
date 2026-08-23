# Evaluation Metrics

Status: **template — fill in after commit 12 (`docs: metrics`)**

The buildathon brief is explicit: "Honest metrics including false-positive
cost." This file exists so results get reported from one real batch run,
not a cherry-picked demo run.

## Methodology

1. Generate one held-out evaluation batch with the Attack Simulator:
   mix of labeled attack traffic (card-testing bursts) and labeled normal
   traffic (organic-looking varied transactions), minimum 500 transactions.
2. Run the batch through the Velocity Engine exactly once, no re-runs to
   cherry-pick a better result.
3. Compare flagged alerts against ground-truth labels from the simulator.
4. Compute precision, recall, false positives, false negatives.
5. Estimate false-positive cost: for each false positive, what it would
   have cost a real merchant (lost legitimate sale if auto-blocked,
   or support/review time if only flagged).
6. Report the numbers below as-is, including if they're mediocre. A
   documented 70% precision run is worth more than an undocumented claim
   of 95%.

## Results

*(fill in after running the evaluation batch)*

| Metric | Value |
|---|---|
| Batch size | — |
| True positives | — |
| False positives | — |
| False negatives | — |
| Precision | — |
| Recall | — |
| Estimated false-positive cost | — |
| Detection latency (p50 / p95) | — |

## False positive breakdown

*(list each false positive case and why it happened — this is what
"honest" means here, not just the aggregate number)*

| Transaction pattern | Why it was flagged | Why it was actually legitimate |
|---|---|---|
| — | — | — |

## Known limitations

- Evaluated on synthetic data only — real-world fraud patterns may differ.
- Thresholds tuned on this batch; not validated against a second
  independent batch (documented as future work).
- Only one attack pattern type (card-testing burst) is evaluated
  end-to-end; fake-return abuse detection is out of scope for this build
  (see `docs/DESIGN.md` — Out of scope).
