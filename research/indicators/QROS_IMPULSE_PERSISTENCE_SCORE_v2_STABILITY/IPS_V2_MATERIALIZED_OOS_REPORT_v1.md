# IPS v2-STABILITY — Materialized OOS 2021–2022

Decision: **PASS_MATERIALIZED_OOS**

Data used: only already-materialized XAU canonical ZIPs. Warm-up: parts 014–018. Evaluation: 2021-01-01 through 2022-08-14 complete source-clock days.

## Primary OOS
- Raw evaluation events: 12,245
- Executable events: 11,691
- IPS v2 >=65 events: 1,505
- Baseline hit rate: 23.6849%
- High-score hit rate: 32.5581%
- Lift: 8.873 pp
- Relative lift: 37.46%
- Exact one-sided p: 2.58786e-17
- Day-block bootstrap 95% CI: [6.702, 11.112] pp
- BUY lift: 8.412 pp
- SELL lift: 9.039 pp
- 2021 lift: 8.037 pp
- 2022 materialized lift: 9.839 pp
- Score-bin Spearman rho: 1.000
- Parity main/oracle: PASS (13752/13752; 0 mismatches)

## Secondary frozen v1 benchmark
- v1 lift: 6.008 pp
- v2-v1 lift difference: 2.865 pp
- Paired day-bootstrap v2-v1 95% CI: [1.220, 4.477] pp

## Stability diagnostics
- Positive months: 18/20
- Worst month: -2.568 pp
- Positive quarters: 7/7
- Worst quarter: 3.988 pp

The period is now EXPOSED and cannot be reused as a clean holdout for the IPS genealogy.
