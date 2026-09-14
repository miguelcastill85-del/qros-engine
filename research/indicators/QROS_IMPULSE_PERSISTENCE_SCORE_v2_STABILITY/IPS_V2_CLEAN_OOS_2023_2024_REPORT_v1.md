# IPS v2-STABILITY — Clean OOS 2023–2024

Decision: **PASS**

This is the originally preregistered clean confirmatory OOS. The indicator weights, threshold and event ontology were frozen before materialization and scoring.

## Frozen indicator
- Weights: 15 / 5 / 10 / 20 / 30 / 20
- Threshold: 65
- Retuning: FORBIDDEN

## Data freeze
- Exact evaluation record range: `[387092539, 519057574)`
- Evaluation ticks: 131,965,035
- Exact evaluation bytes SHA-256: `8e5a743af448aad305917f1fefd62b809a42611b3e29fe25f79ff6eb8f147ff7`
- Warm-up stream SHA-256: `8116717809e7b71148bdbe4089d66a580345d3f4a95f2591e2c4ec0b6add0e1d`

## Independent parity
- Main events: 18,386
- Oracle events: 18,386
- Total field mismatches: 0
- Maximum numeric absolute error: 0

## OOS result
- Raw evaluation events: 15,251
- Executable events: 14,450
- High-score events: 1,899
- Baseline hit rate: 26.4152%
- IPS v2 >=65 hit rate: 33.2807%
- Lift: **6.865 pp**
- Relative lift: **25.99%**
- Exact one-sided p: **5.876e-13**
- Day-block bootstrap 95%: **[4.888, 8.804] pp**

## Stability
- BUY lift: 6.730 pp
- SELL lift: 7.230 pp
- 2023 lift: 7.834 pp
- 2024 lift: 5.855 pp
- Score-bin Spearman rho: 1.000
- Positive months: 23/24
- Worst month lift: -4.411 pp
- Positive quarters: 8/8
- Worst quarter lift: 3.561 pp

## Scientific interpretation
The clean confirmatory OOS passes all frozen gates. The effect is smaller than the previously exposed 2021–2022 materialized OOS, but remains strongly positive, significant, directionally stable and temporally broad.

2023–2024 is now permanently EXPOSED for the IPS genealogy and cannot be reused as a clean holdout. 2025–2026 remains SEALED.

MT5 compile/parity remains a separate operational gate. This result does not turn IPS into a trading strategy and does not assign portfolio risk.
