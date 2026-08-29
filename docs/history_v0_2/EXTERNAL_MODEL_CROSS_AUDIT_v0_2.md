# QROS ENGINE v0.2 — Auditoría transversal de motores externos

Estado: `DEVELOPMENT_RUNNING`
Fecha: 2026-08-27

## Objetivo

Extraer principios verificables de motores y stacks cuantitativos maduros para endurecer QROS ENGINE sin convertirlos en dependencias científicas ni copiar código externo. Todo principio incorporado debe quedar reimplementado de forma original y pasar tests propios.

## Fuentes auditadas

1. QuantConnect LEAN — arquitectura modular, time frontier, reality models, backtest/live.
   - https://www.quantconnect.com/docs/v2/lean-engine/getting-started
   - https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/time-modeling/timeslices
   - https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/key-concepts
   - https://github.com/QuantConnect/Lean/blob/master/LICENSE
2. NautilusTrader — core nativo, simulación determinista, secuenciación, mensajes inmutables, event sourcing.
   - https://nautilustrader.io/docs/latest/concepts/backtesting/
   - https://nautilustrader.io/docs/latest/concepts/backtesting/execution-flow/
   - https://nautilustrader.io/docs/latest/developer_guide/design_principles/
   - https://nautilustrader.io/docs/latest/concepts/dst/
   - https://github.com/nautechsystems/nautilus_trader
3. vectorbt — Numba/vectorización y representación records para eventos dispersos.
   - https://github.com/polakowo/vectorbt
4. Backtrader — modelo broker/slippage y separación broker/strategy.
   - https://www.backtrader.com/docu/slippage/slippage/
   - https://github.com/mementum/backtrader
5. Apache Arrow — layout columnar, alineación, zero-copy, seguridad de buffers.
   - https://arrow.apache.org/docs/format/Columnar.html
   - https://arrow.apache.org/docs/format/Security.html
6. Polars — lazy execution y streaming por lotes.
   - https://docs.pola.rs/user-guide/lazy/
   - https://docs.pola.rs/user-guide/concepts/streaming/
7. DuckDB — ejecución vectorizada, out-of-core, límites explícitos de memoria/hilos.
   - https://duckdb.org/docs/lts/internals/vector
   - https://duckdb.org/docs/current/guides/performance/environment
   - https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview
8. MetaTrader 5 Strategy Tester — modos de tick y comportamiento de real ticks.
   - https://www.mql5.com/en/docs/runtime/testing

## Matriz de hallazgos

| Sistema | Principio valioso | Riesgo/limitación para QROS | Decisión QROS |
|---|---|---|---|
| LEAN | Time frontier: el algoritmo sólo ve presente/pasado | Un motor genérico puede tener diferencias fill/resolución entre backtest y live | Adoptar frontier causal explícito; no depender de LEAN |
| LEAN | Reality models separados: fill/slippage/fee/brokerage | Defaults pueden ser demasiado optimistas para mercados concretos | QROS tendrá ExecutionPolicy versionada por activo/broker |
| Nautilus | Fases deterministas de mercado → estrategia → settlement | Su semántica exacta no es automáticamente la nuestra | Adoptar contrato de fases propio en v0.3 |
| Nautilus | Mensajes inmutables y replay determinista | LGPLv3 si se copia/enlaza código | Adoptar principio, reimplementar desde cero |
| Nautilus | IDs deterministas | Hash/ID específico no debe copiarse | v0.2 añade `run_id` SHA-256 determinista propio |
| vectorbt | Records compactos para eventos dispersos | Commons Clause limita ciertos usos comerciales; matriz vectorizada puede ocultar orden causal | Adoptar diseño sparse-record, no código ni dependencia core |
| Backtrader | Slippage/broker model explícito | GPLv3; Python event loop no es nuestro objetivo de rendimiento | Sólo referencia conceptual |
| Arrow | Buffers columnares alineados y zero-copy | Input binario inválido puede provocar accesos inseguros | QDATA v1 usará layout versionado + validación estricta antes de mmap |
| Polars | Lazy/streaming | No garantiza semántica causal de trading | Adaptador ETL opcional, nunca execution oracle |
| DuckDB | Vectorized/out-of-core y resource caps | SQL arbitrario equivale a código arbitrario; memoria fuera del buffer manager | Analítica/result-store opcional con queries construidas, límites explícitos |
| MT5 | Validación independiente con real ticks | `real ticks` puede descartar ticks y sustituirlos por generados si no concuerdan con M1 o faltan | MT5 no es oráculo absoluto; exigir provenance contract por ejecución |

## Auditoría de licencias

- LEAN: Apache-2.0. Compatible con uso comercial, pero QROS no necesita incorporar su código.
- NautilusTrader: LGPL-3.0. No copiar/vendorear código en el core QROS sin análisis legal específico.
- vectorbt: Apache 2.0 + Commons Clause. No convertirlo en componente distribuido/comercial del core.
- Backtrader: GPLv3+. No incorporar código al core propietario/comercial.
- Arrow: Apache-2.0.
- Polars: MIT.
- DuckDB: MIT.
- NumPy: BSD-3-Clause.
- Numba: BSD-2-Clause.

**Política congelada:** QROS ENGINE v0.x contiene código original propio. Las fuentes externas sirven para contraste de arquitectura y pruebas adversariales. Toda incorporación de código de terceros requeriría un `THIRD_PARTY_CODE_RECEIPT` separado con licencia, versión, hash y justificación.

## Fallos propios descubiertos por la auditoría

### X1 — frontera de señal declarativa no anclada
En v0.1 el intent podía declarar `signal_seq`/timestamp sin demostrar que esa combinación pertenecía exactamente a un tick autoritativo.

**Corrección v0.2:** `signal_seq` debe existir y su `ts_ns` y `session_day` deben coincidir exactamente con el intent. Si no, `DATA_ERROR`.

### X2 — dataset truncado podía aparentar session close
v0.1 usaba el último quote disponible del día como cierre, aunque el archivo terminase antes del cierre real.

**Corrección v0.2:** el intent lleva `session_close_seq`, que debe existir y pertenecer al mismo `session_day`. El engine nunca infiere que EOF significa cierre.

### X3 — salida inmediata fabricada al no existir quote posterior
v0.1 inicializaba `last_exec_i` con el tick de entrada. Si no había otra cotización ejecutable podía cerrar artificialmente usando el mismo tick.

**Corrección v0.2:** se requiere un quote ejecutable posterior a la entrada. Si no existe, estado `UNRESOLVED_CLOSE`; no se fabrica fill.

### X4 — parser y static analyzer
GCC `-fanalyzer` produjo advertencias en la ruta `unordered_set`/libstdc++. Aunque eran compatibles con falso positivo, no se aceptó como PASS.

**Corrección v0.2:** parser reducido a `std::array<string_view>` + búsqueda lineal pequeña. Repetición de `-fanalyzer -Werror`: PASS limpio.

### X5 — reproducibilidad de build no demostrada
v0.1 verificaba ejecución reproducible, pero no que dos builds limpios produjeran el mismo binario.

**Corrección v0.2:** dos builds estáticos limpios produjeron SHA-256 idéntico:
`cb21b144dba82ddf3071b31ed4c9d64a156211ec94b0b48500e29d342e3111f8`.

## Principios que pasan a contrato QROS

1. **Scientific core minimal:** ejecución científica sin Python ni dependencias de dataframe.
2. **Exact frontier:** cada decisión referencia un evento autoritativo real, no una hora aproximada.
3. **Session authority:** EOF nunca equivale a cierre de sesión.
4. **Immutable facts:** intents, events, receipts y ledgers finales no se mutan.
5. **Deterministic identity:** cada run recibe identidad derivada de versión + hashes exactos.
6. **Separate reality policy:** señal y ejecución/costes viven en capas diferentes.
7. **Sparse universe:** millones de configuraciones se representan como masks/records/graphs, no objetos Python.
8. **Bounded resources:** todo runner futuro declara presupuesto de RAM, threads y disco temporal.
9. **Optional ecosystem:** Arrow/Polars/DuckDB/NumPy/Numba pueden acelerar ETL/análisis, pero nunca cambian la semántica del core.
10. **Independent oracle:** Python reference + MT5 + golden ledgers; ninguna implementación valida a sí misma.

## Pendientes bloqueantes antes de usar v0.x para selección OOS

- QDATA Authority con timezone/DST demostrado, escala/point size, sesión y provenance.
- Holdout Vault con separación física/capability.
- Event-phase contract `MARKET_APPLY → STRATEGY_DECIDE → EXECUTION_SETTLE`.
- Warmup/frontier contract sin órdenes durante priming.
- ExecutionPolicy: costes central/conservador/severo, slippage, latency y execution failures.
- Bars compiler independiente con regla SL-first intrabar y paridad contra tick path.
- Golden corpus real XAUUSD y NQX.
- MT5 Validation Receipt completo.

## Decisión

`QROS_ENGINE_v0.2` mejora objetivamente v0.1, pero continúa en `DEVELOPMENT_RUNNING`. No está autorizado para abrir holdouts ni sustituir validación MT5.
