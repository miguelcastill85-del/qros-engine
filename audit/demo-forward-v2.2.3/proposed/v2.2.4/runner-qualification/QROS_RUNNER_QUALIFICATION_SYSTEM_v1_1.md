# QROS RUNNER QUALIFICATION SYSTEM v1.1

## Objetivo

Impedir que un paquete de ejecución QROS sea entregado como validado cuando sólo pasó integridad/hash/análisis estático, y evitar que Candidate3 sea usado como banco de pruebas para defectos del runner o del propio laboratorio.

## Estados

RUNNER_DRAFT -> STATIC_QUALIFIED -> NATIVE_ENV_QUALIFIED -> CANDIDATE_GATE_ELIGIBLE -> CANDIDATE_NATIVE_VALIDATED.

Fallos: RUNNER_REJECTED_STATIC, RUNNER_REJECTED_NATIVE_ENV, CANDIDATE_REJECTED_NATIVE.

PREVALIDATED_ARTIFACT significa sólo R0+R1. NATIVE_ENV_QUALIFIED exige R2+R3 ejecutados en el Windows/MT5 objetivo.

## Gates

R0: CRC ZIP, manifest, SHA/bytes, autoridad congelada, cero órdenes reales, sin CERT/armado.

R1: reglas BLOCKER + mutation tests. Un cambio de un byte del runner invalida R1.

R2: se ejecuta sin Candidate3. Debe certificar PowerShell objetivo, FileShare.None, includes, MetaEditor 0/0, Strategy Tester smoke sin trading, fencing, release/reacquire, restart/persistencia, watchdog, evidencia fail-closed y cero control sobre el terminal activo.

R3: liga el receipt R2 al fingerprint exacto del runner, qualifier, terminal64/metaeditor64, build MT5, PowerShell, includes y rutas aisladas.

R4: Candidate3 sólo puede ejecutarse si el R2 PASS corresponde exactamente al runner y fingerprint vigentes.

## Enmienda D14 — equivalencia de contexto

Strategy Tester sigue siendo válido para compilación y materialización sin trading, pero queda prohibido certificar allí una invariante de exclusión entre instancias de producción.

El fencing de R2 debe ejecutarse en dos terminales portables normales y aislados, iniciando un EA de calificación sin API de trading mediante `[StartUp]`. Debe demostrarse simultáneamente:

- `MQL_TESTER=0` en holder, probe y reacquire;
- `AllowLiveTrading=0`;
- misma `TERMINAL_COMMONDATA_PATH` en ambos terminales;
- raíces `TERMINAL_DATA_PATH` aisladas;
- holder adquiere el mismo `FILE_COMMON` lock usado por Candidate3;
- segundo terminal es rechazado mientras el holder conserva el handle;
- release marker contiene el mismo token del holder;
- un proceso nuevo puede reacquirir después del release;
- restart/persistencia se prueba también en terminal normal nuevo.

Un `HOLDER_READY` emitido desde Strategy Tester no es evidencia suficiente de solapamiento: el backtest puede finalizar y `OnDeinit` liberar el handle antes del probe.

## Fixed point

Cada defecto nuevo debe: registrar causa raíz; añadir detector; demostrar que una mutación defectuosa falla; demostrar que la corrección pasa; reejecutar todas las regresiones previas; y recién entonces permitir una nueva ejecución nativa.

Candidate3 permanece congelado durante R0-R3. `QDB1.EXEC.CERT` permanece 0. No deployment, no armado y no órdenes reales.