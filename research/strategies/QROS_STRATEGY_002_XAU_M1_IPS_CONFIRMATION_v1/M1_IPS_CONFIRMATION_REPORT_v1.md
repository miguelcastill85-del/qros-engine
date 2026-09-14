# QROS — XAU M1 + IPS v2 Confirmation v1

## Decisión

**INCONCLUSIVE_SUPPORT**

El filtro fue preregistrado antes de leer su PnL. La base XAU M1 fue reproducida primero de forma exacta contra su golden vector de 61 operaciones 2018–2024.

## Base independiente: XAU M1

- Operaciones: 61
- Neto: 29.468389R
- Expectancy: 0.483088R
- PF: 2.510163
- Win rate: 59.02%
- DD máximo: 2.440645R

## Regla IPS congelada

Se conserva una operación M1 sólo si existe un evento IPS BUY con score v2 >=65, estrictamente anterior a la entrada M1, dentro de los 60 minutos previos y en el mismo día raw/UTC. No se cambia entrada, SL, TP, gestión ni R de M1.

## Resultado desarrollo expuesto 2018–2024

- Operaciones filtradas: 5 / 61 (8.20%)
- Neto filtrado: 5.372884R
- Expectancy filtrada: 1.074577R
- PF filtrado: INF_NO_LOSSES
- Win rate: 100.00%
- DD máximo: 0.000000R
- Años con operaciones filtradas positivos: 3/3
- Top-3 / neto filtrado: 80.45%

### Operaciones confirmadas

- 2020: R=0.615012, IPS=65.732, anticipación=13.70 min
- 2020: R=1.071525, IPS=68.481, anticipación=27.34 min
- 2022: R=0.435565, IPS=65.697, anticipación=33.08 min
- 2024: R=1.449445, IPS=68.761, anticipación=46.17 min
- 2024: R=1.801336, IPS=67.399, anticipación=34.88 min

## Gates

El patrón económico es favorable, pero falla el gate de potencia/muestra:
- mínimo 8 operaciones: FAIL
- cobertura >=10%: FAIL
- concentración top-3 <=70% del neto: FAIL

Los gates de neto, expectancy, PF, DD, estabilidad por años con muestra y 2024 sí pasan.

## Interpretación

La evidencia es **soporte observacional fuerte pero insuficiente**. No se abre 2025–2026, porque gastar evidencia limpia para cinco observaciones sería metodológicamente débil.

No se amplía retrospectivamente la ventana de 60 minutos ni se baja el umbral IPS. Cualquier regla distinta debe ser una nueva genealogía.

M1 conserva su estado previo. IPS v2 conserva `APPROVED_RESEARCH`.
