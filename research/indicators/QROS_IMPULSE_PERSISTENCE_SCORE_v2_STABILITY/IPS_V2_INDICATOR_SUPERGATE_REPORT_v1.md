# IPS v2-STABILITY — Indicator Supergate

Decision: **PASS_SUPERGATE**

Scope: adversarial robustness using only already-exposed/materialized evidence. This is not a new independent holdout.

## Primary frozen indicator
- Weights: 15 / 5 / 10 / 20 / 30 / 20
- Threshold: 65
- Executable events: 11,691
- High-score events: 1,505
- Baseline hit rate: 23.6849%
- High-score hit rate: 32.5581%
- Lift: 8.873 pp
- Exact one-sided p: 2.588e-17
- Day bootstrap 95%: [6.702, 11.112] pp

## Supergate
- SG01 Primary OOS: PASS
- SG02 Temporal stability: PASS
- SG03 Cluster bootstrap: PASS
  - Weekly 95%: [6.799, 11.047] pp
  - Monthly 95%: [6.537, 11.195] pp
- SG04 Concentration: PASS
  - top 5% days share of positive excess: 23.73%
  - lift after removing those days: 6.172 pp
- SG05 Threshold sensitivity: PASS
- SG06 Weight plateau: PASS
  - neighbors: 14
  - positive-lift neighbors: 100.00%
  - median neighbor lift / frozen v2 lift: 95.79%
  - worst neighbor lift: 6.603 pp
- SG07 Regime stability: PASS
- SG08 BUY/SELL and year stability: PASS

## Threshold stress
- 60.0: N=3318, hit=29.476%, lift=5.791 pp
- 62.5: N=2295, hit=30.937%, lift=7.252 pp
- 65.0: N=1505, hit=32.558%, lift=8.873 pp
- 67.5: N=935, hit=33.904%, lift=10.219 pp
- 70.0: N=501, hit=32.934%, lift=9.249 pp

## Regime stress
- ATR quartile lifts: 11.414 pp, 7.054 pp, 8.883 pp, 7.431 pp
- Spread-reference quartile lifts: 9.204 pp, 9.953 pp, 5.609 pp, 11.146 pp

## Component ablation (diagnostic only)
- remove disp_q: N=2021, lift=6.944 pp
- remove eff_q: N=1477, lift=8.746 pp
- remove pullback_q: N=2148, lift=5.924 pp
- remove recovery_q: N=509, lift=11.875 pp
- remove micro_q: N=3002, lift=4.430 pp
- remove spread_q: N=2314, lift=6.523 pp

## Scientific state

The indicator passes the preregistered robustness Supergate and is promoted to **APPROVED_RESEARCH**.

This does **not** mean APPROVED_FINAL and does not make IPS a trading strategy. MT5 compilation/parity remains pending, and no portfolio risk is assigned.

No retuning is allowed under the IPS v2 identity.
