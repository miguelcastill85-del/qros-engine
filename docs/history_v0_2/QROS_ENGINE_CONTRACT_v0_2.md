# QROS ENGINE Contract v0.2

Estado: `DEVELOPMENT_RUNNING`

## Invariantes ejecutables actuales

- fixed-point `int64_t` para precios/PnL;
- R exacto como fracción;
- `seq` estrictamente creciente es autoridad causal;
- timestamps no decrecientes, pero no deciden por sí solos el orden;
- `signal_seq` debe existir y coincidir exactamente con `signal_ts_ns/session_day`;
- `session_close_seq` debe existir, ser posterior a la señal y pertenecer al mismo día;
- no crossed quotes;
- zero spread se audita y nunca llena órdenes;
- BUY entra Ask y sale Bid; SELL entra Bid y sale Ask;
- entrada estrictamente posterior a la señal;
- gap usa primer quote ejecutable realmente observado;
- no se fabrica session close a partir de EOF;
- no se permite salida usando el mismo tick de entrada por falta de datos posteriores;
- output final inmutable + idempotencia de rerun idéntico;
- receipt con hashes exactos + `run_id` determinista;
- parser declarativo cerrado y sin eval;
- build Release usa `_GLIBCXX_ASSERTIONS`;
- compilación con warnings como errores;
- test suite no depende de `assert`.

## Invariantes de arquitectura congelados pero aún no implementados

- QDATA Authority;
- Holdout Vault;
- event phases;
- ExecutionPolicy versionada;
- Universe Compiler sparse;
- Result Store con CAS/fencing de campaña;
- Supergate;
- MT5 bridge.
