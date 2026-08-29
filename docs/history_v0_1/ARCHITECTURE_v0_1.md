# QROS ENGINE — arquitectura auditada v0.1

Estado: DEVELOPMENT_RUNNING. Este artefacto es infraestructura experimental, no un backtest aprobado ni reemplaza MT5.

## Decisión de diseño

No construir un "nuevo Python" generalista. Construir un runtime cuantitativo propio, pequeño, determinista y versionado.
Python queda fuera del camino crítico de producción: sólo se conserva una implementación independiente de referencia/paridad.
El núcleo v0.1 está implementado en C++20 sin dependencias de terceros y puede enlazarse estáticamente.

## Capas objetivo

1. QDATA Authority
   - datos normalizados, manifiesto de origen, zona horaria/DST demostrada, escala de precio/punto, SHA-256/content root.
2. QROS IR
   - representación intermedia tipada, declarativa, sin eval ni plugins ejecutables dentro de una estrategia.
3. Causal/Event Compiler
   - orden por `seq` autoritativo, timestamps como dato secundario, features sólo del pasado permitido.
4. Execution Kernel
   - BUY entra Ask/sale Bid; SELL entra Bid/sale Ask; sin fills en spread cero; gap al primer precio observable; cierre intradía.
5. Universe Compiler
   - familias y parámetros representados como grafos/máscaras, no millones de objetos o scripts.
6. Result Store
   - artefactos inmutables, hashes, receipts, checkpoints y CAS/fencing antes de promoción.
7. Gate/Supergate
   - evaluación estadística separada de generación de señal y gestión.
8. Holdout Vault
   - permisos/capabilities que impiden acceso durante desarrollo; apertura única registrada.
9. Reference Interpreter
   - implementación independiente y lenta para golden ledgers/paridad.
10. MT5 Bridge
   - exportación del candidato congelado y paridad trade-by-trade real.

## Invariantes ya implementadas en v0.1

- precios y PnL en enteros fixed-point `int64_t`;
- R exacto representado como fracción `r_num/r_den`, sin redondeo flotante;
- `seq` estrictamente creciente como orden causal autoritativo;
- timestamp no puede retroceder;
- `session_day` explícito; el engine no presume UTC ni timezone del broker;
- crossed market Ask<Bid => fallo de datos;
- spread cero se audita y nunca se usa para fills;
- BUY entra por Ask y sale por Bid;
- SELL entra por Bid y sale por Ask;
- entrada sólo después de `signal_seq`;
- gap ejecutado al primer precio realmente observado;
- cierre de sesión intradía obligatorio en el último quote ejecutable;
- niveles SL/TP con checks de overflow;
- input ligado por SHA-256;
- output final inmutable; rerun idéntico es idempotente, bytes distintos en la misma ruta fallan;
- `fsync` + promoción atómica en Linux;
- receipt de replay con hashes de ticks, intent y ledger;
- parser declarativo cerrado: claves desconocidas y duplicadas fallan.

## Fuera de alcance de v0.1 — NO afirmar todavía

- parser/compilador completo de estrategias QROS;
- QDATA binario/mmap;
- motor vector/multicore del universo;
- bars y regla SL-first ante ambigüedad intrabar;
- timezone/DST authority manifest;
- holdout vault y capability separation;
- lease/fencing/CAS multiwriter de campañas completas;
- clustering/deduplicación semántica;
- Gate A/Supergate;
- exportador MQL5;
- paridad con datos reales XAU/NDX;
- benchmarks end-to-end contra runners QROS actuales.

## Regla de promoción

Una optimización sólo puede promoverse si conserva el golden ledger y pasa:
compilación estricta -> unit tests -> sanitizers -> paridad independiente -> hashes/receipts -> benchmark CPU/RAM -> replay real controlado -> MT5 parity cuando corresponda.
