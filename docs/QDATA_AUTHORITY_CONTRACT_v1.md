# QDATA Authority Contract v1

## Objetivo

QDATA separa la autoridad de datos de la lógica de estrategia. Un backtest sólo puede consumir bytes cuya identidad, estructura, cobertura, sesiones, unidades y evidencia estén selladas y auditadas.

## Artefactos mínimos

1. `ticks.csv`: `seq,ts_ns,session_day,bid_u,ask_u`.
2. `sessions.csv`: fronteras autoritativas por sesión.
3. `manifest.qdata`: identidad, hashes, escala, propósito y políticas.
4. `timezone_evidence.txt`: receipt estructurado `QROS_TIMEZONE_EVIDENCE_V1`.
5. `source_evidence.txt`: receipt estructurado `QROS_SOURCE_EVIDENCE_V1`.

## Invariantes de ticks

- `seq` estrictamente creciente y autoridad primaria del orden causal.
- `ts_ns > 0`, no decreciente; timestamps iguales son admisibles si `seq` avanza.
- `session_day` no puede retroceder.
- Bid/Ask son enteros fixed-point; no se usa `float` para precios.
- `Ask < Bid` es corrupción.
- spread cero se audita y nunca se usa para fills; su tolerancia máxima está en ppm en el manifest.
- los precios deben respetar `tick_size_u`.
- filas vacías o campos vacíos están prohibidos.
- máximo duro: 10^12 registros por autoridad QDATA v1.

## Sesiones

Cada `open_seq`, `close_seq`, `open_ts_ns` y `close_ts_ns` debe corresponder exactamente a registros reales. EOF no sustituye una frontera de sesión. Cada tick debe pertenecer a una sesión declarada.

## Timezone / DST

`timezone_status` no basta por sí solo. El receipt de timezone debe coincidir con:

- `authority_id`;
- `timezone_name`;
- SHA-256 exacto de `sessions.csv`;
- primer y último `session_day`;
- número de transiciones de offset observadas;
- máximo salto de offset observado;
- estado de verificación declarado.

## Procedencia

El receipt de fuente debe coincidir con:

- `authority_id`;
- `source_kind`;
- `source_id`;
- SHA-256 exacto de `ticks.csv`;
- SHA-256 exacto de `sessions.csv`.

En v0.3 esto demuestra integridad y vínculo semántico del receipt, **no demuestra por sí mismo la verdad de la procedencia externa**.

## TEST_ONLY vs RESEARCH

- `TEST_ONLY`: puede alcanzar `TEST_READY` con evidence status `TEST_ONLY` y todos los invariantes íntegros.
- `RESEARCH`: requiere verificación de producción independiente contra bytes fuente externos.
- En v0.3 `production_evidence_verifier_available=0`; por diseño ningún dataset puede alcanzar `RESEARCH_READY` todavía.

Esto evita promover datos sintéticos o receipts autodeclarados a investigación real.
