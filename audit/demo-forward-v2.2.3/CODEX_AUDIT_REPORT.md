# Auditoría offline Darwinex-Demo v2.2.3 congelado

Decisión: **CRITICAL_REPLACEMENT_REQUIRED** (`INFERRED`, recomendación de ingeniería apoyada en defectos `STATIC_PROVEN` y contraejemplos `TEST_PROVEN` de alcance sintético).

No se ha demostrado un incidente en el forward activo. El terminal operativo permanece fuera de la auditoría. La decisión exige reemplazo corregido y certificado; no autoriza instalar la propuesta parcial, detener/reiniciar el terminal ni desplegar. No concede aceptación científica ni live.

## Alcance, identidad y método

`TEST_PROVEN`: rama `audit/demo-forward-v2.2.3-frozen-20260907`, HEAD inicial `3c92d2ca50fb08d3b51d19f6f042f328797460e4`, árbol limpio antes de crear artefactos. Cuatro fuentes centrales coinciden en longitud, SHA-256 y Git blob SHA-1 con FROZEN_SOURCE_RECEIPT. Se conservan los seis archivos frozen/, tres documentos iniciales v2.2.3 y evidencia histórica. `evidence/INTEGRITY_FINAL.json` registra comparación final contra Git.

`STATIC_PROVEN`: el recibo identifica ZIP de 134189 bytes y SHA-256 `6e732d59808b768d84ad3a1f734a08a608262192c1f78b2e7143141b461fccde`. El ZIP no está presente: ese hash NO se verificó contra sus bytes. Executor, bus, kernel, bootstrap y autoridades congeladas se leyeron íntegramente, además del handoff/AGENTS requerido. El encargo actual no se sustituye por la antigua construcción C++.

`BLOCKED_PENDING_EXACT_SOURCE_IMPORT` (`BLOCKED`): tres emisores, wrapper, package/EX5/SET/templates, Trade.mqh/dependencias 6182, START_RECEIPT/evidencia de activación y oráculos exactos. No se usó fuente aproximada, main ni directorio del terminal. La declaración del usuario de forward activo se conserva; PREREG histórico no es receipt de activación actual.

`TEST_PROVEN` significa ejecución real del banco offline: traducción acotada y revisable de los cuerpos del executor/bus/kernel, siete funciones bootstrap y su bloque de offset a Node, con fronteras API programadas. Se retienen código generado, stdout JSON, stderr y recibos. No se ejecutó EX5, MetaEditor, Trade.mqh, broker ni dos terminales. Booleano/retcode, posiciones/deals, crashes y cotizaciones son fixtures adversariales explícitas. No se calcula rendimiento ni se consultan datos económicos.

`INFERRED`: la traducción conserva flujo/formulas del subconjunto inspeccionado; no prueba equivalencia formal MQL5. Enteros JS son exactos hasta 2^53−1; T51 estudia doubles de globals, no overflow long MQL. Stubs de archivo, reloj, profit y visibilidad modelan supuestos declarados. Ninguna observación se convierte en resultado MT5. CTrade exacto 6182 queda bloqueado. No se consultó web durante la auditoría offline. Los recibos originales de traducción guardan hash del texto UTF-8 LF antes de escribir CRLF en Windows; TRANSLATION_HASH_VERIFICATION.json verifica ese hash y agrega el hash de archivo real sin reescribir evidencia. ARTIFACT_MANIFEST liga los bytes finales.

`TEST_PROVEN`: `handoff/verify_import.py` falló en AGENTS.md, ya distinto del handoff original antes de auditar. python3 no estaba en PATH; se repitió el mismo script con Python bundled. No se reescribió manifest para ocultar el resultado. No se estableció C++/WSL utilizable ni se instalaron herramientas. Suites C++ v0.6 no validan este executor MQL5 y no se presentan como evidencia de él.

## Resultados ejecutados

`TEST_PROVEN` de fuente traducida: **87 escenarios, 38 PASS y 49 FAIL** en v2.2.3. La matriz añade **16 BLOCKED** de fuentes o ejecución nativa. Cada FAIL compara con expectativa segura, nunca con la expectativa de reproducir un defecto. Exit 0 sólo indica observaciones serializadas; no es gate verde. Errores iniciales del harness se conservan separados en HARNESS_ATTEMPTS.json.

`TEST_PROVEN` de propuesta parcial: **49 PASS y 38 FAIL**, once expectativas mejoradas sin perder los 38 PASS originales. No equivale a compilación/paridad MT5. Reconciliación, recovery y bus conservan defectos críticos.

Resultados: CODEX_AUDIT_TEST_MATRIX.json, `evidence/frozen-final/stdout.json` y `evidence/proposal-final/stdout.json`. FUNCTION_REVIEW_INVENTORY.json enumera cada función revisada. No se afirma MC/DC, fuzzing exhaustivo ni cobertura de todo schedule concurrente.

## Trazado completo del núcleo exacto

`STATIC_PROVEN`: emisor exacto [bloqueado] → QrosBusPublish (payload → SEQ → HEAD) → PollBus. ENTRY → AddPending → SortPending/ProcessPending → SendEntry → símbolo/magic → fault/recovery/CERT/HB/spread → día/cupo/timestamp/activo → normalización/sizing → reserva → arm → CTrade.Buy → bool/retcode → contador, DAY/LASTEV y ledger. Falta reconciliación posterior orden/deal/posición/volumen/barreras.

`STATIC_PROVEN`: MODIFY_SL/CLOSE saltan buffer y buscan primera posición por símbolo/magic. Modify sólo eleva SL; Close intenta ticket. Ambos descartan intención tras CTrade y usan bool para EXECUTED. ForceNoOvernight recorre posiciones y compara fechas, normalmente en timer después de RefreshDay. g_fault salta esas rutas en ciclos futuros. OnInit descarta todos los records hasta HEAD, pone CERT=0 y recovery lock sólo si hay posiciones.

`STATIC_PROVEN`: bootstrap pone CERT=0, valida cuenta/flat, cierra otros charts, limpia HB/STATE, aplica templates, espera nombres/READY/HB/ticks/series/arm/offset/flat, pone CERT=1 si ExpectedArmed==1, intenta receipt y termina. Aunque no tenga order API, CloseOtherCharts/ChartApplyTemplate mutan el terminal: nunca se ejecutó este script aquí.

## Hallazgos

Los números de línea pertenecen a frozen/, no a la propuesta.

| ID | Severidad | Clasificación de fuente | Hallazgo |
|---|---|---|---|
| F01 | Critical | STATIC_PROVEN | Solicitudes pendientes y fills no reconciliados escapan de reservas y exclusión de activo |
| F02 | High | STATIC_PROVEN | Modify/Close confunden booleano de envío con ejecución y pierden intención de reintento |
| F03 | Critical | STATIC_PROVEN | g_fault persistente abandona la gestión posterior de posiciones |
| F04 | Critical | STATIC_PROVEN | Recuperación no reconstruye protección/intenciones y el lock nunca se libera |
| F05 | High | STATIC_PROVEN | HistorySelect fallido habilita contador diario cero |
| F06 | High | STATIC_PROVEN | No overnight actúa después de medianoche y OnTick puede adelantar entradas |
| F07 | High | STATIC_PROVEN | Lector acepta payload nuevo con SEQ viejo durante sobrescritura del ring |
| F08 | High | STATIC_PROVEN | Publicación y ejecución carecen de exclusión de instancia |
| F09 | High | STATIC_PROVEN | Persistencia del bus y commits de estado no se verifican |
| F10 | High | STATIC_PROVEN | Buffer individual y dispatch inmediato CLOSE rompen orden causal global |
| F11 | High | STATIC_PROVEN | Sólo se deduplica último timestamp y no hay validación de edad de evento |
| F12 | High | STATIC_PROVEN | Reserva usa SL actual y faltan finitud/conciliación del precio efectivo |
| F13 | High | STATIC_PROVEN | Frescura puntual no protege envío tras degradación de conexión/ticks |
| F14 | High | STATIC_PROVEN | CERT no acredita executor saludable, identidad exacta ni evidencia durable |
| F15 | High | STATIC_PROVEN | Offset estable no valida UTC+2/+3 ni DST después de certificar |
| F16 | High | STATIC_PROVEN | Ledger sobrescribible y errores de escritura/timer ignorados |
| F17 | Low | STATIC_PROVEN | Globals double sin límite de precisión de secuencia |
| F18 | Medium | STATIC_PROVEN | Barra, referencia y barreras efectivas carecen de contrato completo en núcleo |
| F19 | High | BLOCKED | Fuentes y activación incompletas impiden certificación integral |


### F01 — Solicitudes pendientes y fills no reconciliados escapan de reservas y exclusión de activo

Severidad: **Critical**. Semántica: `execution-semantic`.

Ubicación exacta: `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:199` `ReservedRiskUsd`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:176` `AnyPositionOnAsset`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:295` `SendEntry`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:340` `SendEntry`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:467` `OnInit`.

`STATIC_PROVEN` — Se cuentan posiciones visibles; no se enumeran órdenes ni existe registro de intención pendiente, reconciliación de transacciones, ResultVolume/ResultPrice o validación del SL/TP resultante. PLACED y DONE_PARTIAL avanzan contador/LASTEV y registran EXECUTED; timeout/rechazo no conserva reserva de incertidumbre.

Escenario/reproducibilidad: Stub: balance 10000, tres intenciones de 50 USD, dos sobre NDX, con PLACED sin posición visible. Se aceptan las tres y quedan 150 USD reservados. Con medio fill visible y remanente pendiente vuelve a ocurrir. Timeout con orden viva permite otra solicitud del mismo activo. Casos: T17, T18, T19, T20, T21, T22, T76, T78. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: El contrato de 1% máximo y una posición por activo no queda garantizado. Visibilidad tardía, fill real distinto o posición sin protección pueden quedar sin detección; una cancelación deja un contador inexacto. Que Darwinex produzca cada combinación debe probarse en host aislado. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Intención durable antes de enviar, reserva de riesgo/activo/cupo hasta desenlace confirmado; reconciliar órdenes, deals, posiciones, volumen y barreras. REPLACEMENT_CONTRACT puntos 1–5. La propuesta parcial NO corrige F01.


### F02 — Modify/Close confunden booleano de envío con ejecución y pierden intención de reintento

Severidad: **High**. Semántica: `execution-semantic`.

Ubicación exacta: `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:358` `HandleModify`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:372` `HandleModify`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:376` `HandleClose`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:385` `HandleClose`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:410` `ForceNoOvernight`.

`STATIC_PROVEN` — El branch EXECUTED de modify/close depende únicamente del bool. ResultRetcode sólo informa algunos fallos booleanos; no hay verificación de estado ni cola durable de cierre/modificación. ForceNoOvernight omite el retcode incluso en el texto de fallo.

Escenario/reproducibilidad: Inyectar bool=true, retcode=10006 y posición intacta: se registra EXECUTED. DONE_PARTIAL con remanente abierto también. Con bool=false y posterior recuperación, sin nuevo evento del módulo no se reintenta la intención durante el mismo día. Casos: T23, T24, T25, T26, T39, T77, T80. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: La protección/cierre solicitado puede no aplicarse y el ledger puede afirmar éxito. El par booleano/retcode real de Trade.mqh build 6182 sigue BLOCKED; el defecto de control de flujo es verificable estáticamente. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Comprobar retcode y resultado reconciliado; persistir la intención hasta confirmación. La propuesta parcial elimina éxito falso en los casos probados; aún no añade reintento durable.


### F03 — g_fault persistente abandona la gestión posterior de posiciones

Severidad: **Critical**. Semántica: `execution-semantic`.

Ubicación exacta: `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:106` `SetFault`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:123` `ArmGate`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:488` `OnTimer`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:499` `OnTick`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:421` `PollBus`.

`STATIC_PROVEN` — SetFault es sticky. OnTimer publica HB/ARMED y retorna antes de ForceNoOvernight, PollBus y ProcessPending; OnTick tampoco los ejecuta con fault. El fault se activa por overflow/torn slot, riesgo desconocido o permisos temporales. Dentro del primer PollBus que falla pueden procesarse otros módulos; los ciclos posteriores quedan omitidos.

Escenario/reproducibilidad: Posición QROS abierta del día anterior, SetFault por bus y OnTimer: cero intentos de cierre. Un evento CLOSE posterior no se consume. Deshabilitar temporalmente TERMINAL_TRADE_ALLOWED en HandleClose y restaurarlo deja la misma situación. Casos: T27, T28, T29, T64, T87. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: Pérdida determinista de la ruta central de gestión y del fallback diario mientras subsista la posición. SL/TP del broker, si existen, son la única protección remanente demostrable desde este núcleo. Esto basta para rechazar seguridad incondicional del runtime. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Separar bloqueo de entradas de gestión de inventario reconciliado. La propuesta conserva el cierre diario con fault, pero NO recupera gestión intradía ni procesa un bus de integridad dudosa.


### F04 — Recuperación no reconstruye protección/intenciones y el lock nunca se libera

Severidad: **Critical**. Semántica: `execution-semantic`.

Ubicación exacta: `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:458` `OnInit`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:467` `OnInit`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:475` `OnInit`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:302` `SendEntry`; `frozen/MQL5/Scripts/QROS_V223_RUNTIME_BOOTSTRAP.mq5:317` `OnStart`.

`STATIC_PROVEN` — OnInit detecta sólo posiciones por magic, pone g_recovery_lock=true y fija consumed=HEAD para todos los tipos de evento. No reconstruye estado del módulo ni órdenes/SL/TP; no existe asignación de liberación del lock. El bootstrap requiere cero posiciones para certificar.

Escenario/reproducibilidad: Reiniciar con SL=0: init retorna éxito, lock=true y no hay reparación/close en timer del mismo día. Un CLOSE anterior al restart se descarta. Flat + CERT=1 tampoco libera lock. Control: un CLOSE nuevo sí se procesa aun con lock y CERT=0. Casos: T30, T31, T32, T33, T34, T65, T78. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: Una posición puede quedar sin protección o sin la gestión que existía antes del reinicio. No se afirma que toda posición protegida se abandone: cierre nuevo y fallback diario sano funcionan. La reconstrucción específica de emisores permanece BLOCKED_PENDING_EXACT_SOURCE_IMPORT. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Reconstruir inventario de órdenes/deals/posiciones y estado por generación/módulo; conservar manejo independiente durante recovery. Liberar sólo tras flat real, ausencia de órdenes, historial completo y recertificación. No parchear emisores aproximados.


### F05 — HistorySelect fallido habilita contador diario cero

Severidad: **High**. Semántica: `execution-semantic`.

Ubicación exacta: `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:223` `RebuildDailyCount`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:257` `RefreshDay`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:308` `SendEntry`.

`STATIC_PROVEN` — g_day_entries se pone a cero antes de HistorySelect; false retorna sin fault. La reconstrucción exitosa deduplica DEAL_POSITION_ID, no intención/orden de entrada. No hay contador durable de reservas pendientes.

Escenario/reproducibilidad: Con tres entradas históricas, HistorySelect=false y señal fresca, el stub acepta una cuarta entrada. Con historial completo y tres position IDs distintos, sí bloquea; fills divididos con un mismo ID cuentan una vez. Casos: T12, T35, T36, T40. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: Máximo tres entradas por día deja de garantizarse durante indisponibilidad de historial/restart. Netting o múltiples entradas en un mismo POSITION_ID pueden subcontar; la forma real del historial depende de MT5/broker y sigue BLOCKED. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Fallo de historial bloquea nuevas entradas y exige reconstrucción autoritativa por intención. La propuesta agrega fault y relectura de fault tras RefreshDay; contabilidad durable pendiente.


### F06 — No overnight actúa después de medianoche y OnTick puede adelantar entradas

Severidad: **High**. Semántica: `execution-semantic`.

Ubicación exacta: `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:389` `ForceNoOvernight`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:401` `ForceNoOvernight`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:493` `OnTimer`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:502` `OnTick`.

`STATIC_PROVEN` — ForceNoOvernight sólo cierra cuando la fecha de apertura difiere de ServerDayKey actual. OnTick procesa entradas sin ForceNoOvernight. No hay deadline previo al fin de sesión ni calendario de negociación.

Escenario/reproducibilidad: A las 23:59:59 la posición sigue abierta; el primer timer del día siguiente sano intenta cerrar. OnTick del día nuevo puede aceptar NDX mientras queda XAU del anterior. Rechazo/desconexión prolonga la posición. Casos: T37, T38, T39, T40, T74, T81. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: No se garantiza el contrato literal de no cruzar el día. No se sustituye por liquidación posterior a medianoche. Un emisor podría cerrar antes: esa protección adicional queda bloqueada hasta importar sus bytes. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Vincular deadline previo a sesiones/calendario autorizado y política de contingencia; comprobarlo antes de cualquier entrada. No inventar cutoff, precio de EOF ni ejecución en mercado cerrado.


### F07 — Lector acepta payload nuevo con SEQ viejo durante sobrescritura del ring

Severidad: **High**. Semántica: `execution-semantic`.

Ubicación exacta: `frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh:101` `QrosBusPublish`; `frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh:104` `QrosBusPublish`; `frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh:115` `QrosBusPublish`; `frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh:127` `QrosBusRead`; `frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh:143` `QrosBusRead`.

`STATIC_PROVEN` — El escritor no invalida SEQ antes de modificar payload. El double-check sólo detecta cambios en SEQ; un SEQ viejo estable no acredita que el payload viejo siga intacto.

Escenario/reproducibilidad: Publicar 1..32; pausar 33 tras escribir payload del slot 1 y antes de SEQ. Leer seq=1: ambas comprobaciones ven 1, pero event_ms=33. No requiere dos productores ni HEAD que ya marque overflow. Casos: T41, T42, T43, T44, T86. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: Datos de eventos distintos pueden mezclarse o aplicarse bajo identidad/orden causal incorrectos; también afecta CLOSE/SL. La triage previa sobre coherencia garantizada con un productor debe corregirse. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Invalidar/reservar slot antes de payload y usar versión/época con publicación verificada; rechazo de escritura concurrente, propiedad de productor y recuperación durable.


### F08 — Publicación y ejecución carecen de exclusión de instancia

Severidad: **High**. Semántica: `execution-semantic`.

Ubicación exacta: `frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh:101` `QrosBusPublish`; `frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh:38` `QrosBusKey`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:458` `OnInit`; `frozen/MQL5/Scripts/QROS_V223_RUNTIME_BOOTSTRAP.mq5:234` `RuntimeFailure`.

`STATIC_PROVEN` — HEAD+1 no usa compare-and-swap ni lease. Namespace QDB1 no incorpora cuenta/época/propietario. OnInit no verifica otro executor; bootstrap sólo verifica nombres de tres emisores en charts creados.

Escenario/reproducibilidad: Dos publicaciones del mismo módulo intercaladas tras leer HEAD=0 completan con HEAD=1. Módulos diferentes mantienen cabezas independientes. Dos inicios flat pasan en el stub. Dos espacios de terminal aislados aceptan bajo snapshots de cuenta retrasados. Casos: T46, T47, T66, T75. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: Pérdida de eventos o doble solicitud. T75 prueba sólo snapshots independientes; no ejecuta dos terminales reales ni afirma que compartan globales. El wrapper puede imponer exclusión externa: BLOCKED_PENDING_EXACT_SOURCE_IMPORT. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Propietario/fencing por cuenta y época, productor exclusivo por módulo. Verificar despliegue exacto; no suponer que un mutex local cubre otro terminal.


### F09 — Persistencia del bus y commits de estado no se verifican

Severidad: **High**. Semántica: `execution-semantic`.

Ubicación exacta: `frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh:104` `QrosBusPublish`; `frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh:132` `QrosBusRead`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:420` `PollBus`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:352` `SendEntry`.

`STATIC_PROVEN` — GlobalVariableSet se ignora en payload, SEQ, HEAD, DAY y LASTEV. No hay GlobalVariablesFlush ni protocolo durable de época/recuperación. QrosBusRead sólo exige existencia de SEQ; PollBus no detecta HEAD regresivo.

Escenario/reproducibilidad: Falla escribir HEAD después de SEQ: Publish retorna true con HEAD=0 y no se consume. HEAD baja de 10 a 2: no hay fault. Borrar SL con SEQ válido: lector acepta SL=0. Casos: T33, T41, T45, T48, T55, T79. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: Pérdida de intención, bloqueo hasta vieja cabeza o estado diario/timestamp inconsistente tras caída. Durabilidad real de globals en Windows/MT5 permanece BLOCKED; no se simula fsync ni crash real. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Comprobar escrituras, commit atómico/versionado, flush validado, snapshot y rechazo de rollback; no usar ausencia como cero autorizado.


### F10 — Buffer individual y dispatch inmediato CLOSE rompen orden causal global

Severidad: **High**. Semántica: `execution-semantic`.

Ubicación exacta: `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:275` `Before`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:431` `PollBus`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:439` `ProcessPending`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:378` `HandleClose`.

`STATIC_PROVEN` — SortPending ordena timestamp/prioridad/perfil, pero cada entrada madura según su propio received_uptime. CLOSE/MODIFY se ejecutan durante PollBus y ENTRY se difiere. Gestión sólo se vincula por símbolo/magic.

Escenario/reproducibilidad: NDX llega primero; XAU del mismo ms llega 100ms después. A +300ms XAU sigue inmaduro y NDX se envía. ENTRY luego CLOSE sin posición: close no hace nada y la entrada aparece después. Close viejo cierra nueva generación con mismo magic. Casos: T13, T14, T52, T53, T85. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: Prioridad y relación orden→posición→gestión no garantizadas fuera del lote ideal. Los emisores exactos podrían restringir secuencias, aún bloqueados. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Arbitraje por cohorte completa/watermark, identidad de intención/generación y cancelación de entradas pendientes ante close causal. Conservar orden confirmado close→entry que pasa T85.


### F11 — Sólo se deduplica último timestamp y no hay validación de edad de evento

Severidad: **High**. Semántica: `execution-semantic`.

Ubicación exacta: `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:310` `SendEntry`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:269` `AddPending`; `frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh:134` `QrosBusRead`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:251` `RebuildDailyCount`.

`STATIC_PROVEN` — LASTEV guarda sólo última aceptación; compara igualdad, no frontera causal ni conjunto durable. entry_ref y publish_uptime_ms se transportan pero no se validan al enviar. Skip de replay inicial se limita a HEAD existente.

Escenario/reproducibilidad: Tras entradas A y B y quedar flat, volver a publicar A con secuencia nueva lo acepta. Evento del día anterior en nueva secuencia también se envía con tick actual. Casos: T15, T33, T41, T49. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: Posible duplicación económica de timestamp, señal caducada y cupo atribuido al día de procesamiento. Monotonía completa debe probarse con emisores exactos. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Identidad/deduplicación durable, día/época y frontera causal por emisor; frescura autorizada sin umbrales científicos inventados.


### F12 — Reserva usa SL actual y faltan finitud/conciliación del precio efectivo

Severidad: **High**. Semántica: `execution-semantic`.

Ubicación exacta: `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:210` `ReservedRiskUsd`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:218` `ReservedRiskUsd`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:327` `SendEntry`; `frozen/MQL5/Include/QROS_RISK_KERNEL_APPROVED_v15420.mqh:84` `QrosRiskSize`; `frozen/MQL5/Include/QROS_RISK_KERNEL_APPROVED_v15420.mqh:122` `QrosRiskSize`.

`STATIC_PROVEN` — Reserva=abs(OrderCalcProfit(open, SL_actual, volumen)), sin riesgo inicial guardado. SL en BE da cero; SL por encima puede contar beneficio como riesgo. No se comprueba finitud de p/total. Ambas cotas monetarias admiten 0.01 USD de tolerancia.

Escenario/reproducibilidad: Posición inicial de 50 USD reporta cero al mover SL a entrada. Stub de slippage +2 produce riesgo efectivo de 150 tras sizing de 50. p=NaN con bool=true deja pasar el cap. Barrido de 36 casos finitos en rejillas normales pasa. Casos: T07, T08, T09, T10, T21, T67, T68, T83, T84. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: Reserva no es riesgo inicial. La garantía previa no cubre fills distintos. NaN es prueba defensiva, no afirmación sobre OrderCalcProfit real. Un centavo tampoco equivale a límite matemático exacto. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Separar riesgo inicial durable, actual y pendiente; conciliar fill/barreras y finitud. No cambiar kernel/tolerancia sin contrato y paridad. Propuesta sólo rechaza p no finito.


### F13 — Frescura puntual no protege envío tras degradación de conexión/ticks

Severidad: **High**. Semántica: `execution-semantic`.

Ubicación exacta: `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:160` `PositiveSpread`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:303` `SendEntry`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:123` `ArmGate`; `frozen/MQL5/Scripts/QROS_V223_RUNTIME_BOOTSTRAP.mq5:99` `TickState`.

`STATIC_PROVEN` — Executor valida precios/spread y HB de módulos, no edad de tick ni TERMINAL_CONNECTED. Bootstrap valida frescura una vez. Cuenta demo/servidor/USD se valida en init, no directamente en SendEntry.

Escenario/reproducibilidad: Con CERT y heartbeat fresco, tick positivo de hace una hora llega a Buy. connected=false también llega a Buy en el stub. Casos: T05, T06, T54, T57, T82. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: Solicitud con referencia obsoleta o ACK perdido. T82 no demuestra fill real desconectado, sólo ausencia de gate local. Cambio de cuenta puede provocar reinit de MT5: comportamiento exacto BLOCKED. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Validar cuenta/sesión/conexión y tick por solicitud con reloj autorizado; reconexión requiere reconciliación antes de entradas.


### F14 — CERT no acredita executor saludable, identidad exacta ni evidencia durable

Severidad: **High**. Semántica: `execution-semantic`.

Ubicación exacta: `frozen/MQL5/Scripts/QROS_V223_RUNTIME_BOOTSTRAP.mq5:249` `RuntimeFailure`; `frozen/MQL5/Scripts/QROS_V223_RUNTIME_BOOTSTRAP.mq5:267` `RuntimeFailure`; `frozen/MQL5/Scripts/QROS_V223_RUNTIME_BOOTSTRAP.mq5:432` `OnStart`; `frozen/MQL5/Scripts/QROS_V223_RUNTIME_BOOTSTRAP.mq5:166` `WriteState`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:132` `RuntimeCertified`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:490` `OnTimer`.

`STATIC_PROVEN` — RuntimeFailure valida nombres de emisores y HB/ARMED del executor, no su nombre/build/hash/fault, conexión ni permiso de trading. HB se publica con g_fault. CERT=1 precede WriteState, cuyo fallo de FileOpen no lo invalida. RuntimeCertified acepta 1.5 por cast entero.

Escenario/reproducibilidad: Con fault y HB fresco RuntimeFailure devuelve RUNTIME_READY. También con conexión/permiso false. CERT=1.5 habilita SendEntry. Receipt no escribible no revierte latch según OnStart/WriteState. Casos: T03, T04, T56, T58, T59. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: Readiness falso o sin receipt verificable. Nombre no es hash de EX5/SET; wrapper/START_RECEIPT adicionales bloqueados. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Certificado ligado a identidad, salud, época, cuenta y binarios; receipt durable antes del latch. Propuesta sólo exige double exacto 1.0.


### F15 — Offset estable no valida UTC+2/+3 ni DST después de certificar

Severidad: **High**. Semántica: `execution-semantic`.

Ubicación exacta: `frozen/MQL5/Scripts/QROS_V223_RUNTIME_BOOTSTRAP.mq5:365` `OnStart`; `frozen/MQL5/Scripts/QROS_V223_RUNTIME_BOOTSTRAP.mq5:279` `RuntimeFailure`; `frozen/MQL5/Scripts/QROS_V223_RUNTIME_BOOTSTRAP.mq5:445` `OnStart`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:76` `ServerDayKey`.

`STATIC_PROVEN` — Acepta cualquier offset a <=10 segundos de una hora integral tras diez observaciones. No restringe 7200/10800 ni calendario US DST. Después de CERT retorna; executor no reobserva offset.

Escenario/reproducibilidad: UTC, UTC+1 y UTC-5 se estabilizan como +2/+3. Transición +2↔+3 durante precheck reinicia conteo correctamente; después de CERT no invalida latch. Casos: T69, T70, T71, T72, T73, T74. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: Reloj certificable fuera de contrato, sin garantía central sobre DST durante operación. No se midió reloj host/broker ni se sustituyó Darwinex por America/Santiago. Calendario/sesiones y API 6182 bloqueados. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Vincular fecha/sesión al calendario Darwinex US DST autorizado, offsets permitidos y renovación tras cambio; conservar evidencia observada, no asumir UTC.


### F16 — Ledger sobrescribible y errores de escritura/timer ignorados

Severidad: **High**. Semántica: `infrastructure-only`.

Ubicación exacta: `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:91` `LogRow`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:460` `OnInit`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:481` `OnInit`; `frozen/MQL5/Scripts/QROS_V223_RUNTIME_BOOTSTRAP.mq5:166` `WriteState`; `frozen/MQL5/Scripts/QROS_V223_RUNTIME_BOOTSTRAP.mq5:435` `OnStart`.

`STATIC_PROVEN` — Ledger abre FILE_WRITE sin append/lectura previa ni nombre único. Ignora FileWrite/Flush. Bootstrap reabre FILE_WRITE y SHARE_READ/WRITE, cabecera+fila sin publicación atómica. EventSetMillisecondTimer no se comprueba.

Escenario/reproducibilidad: Stub de apertura truncante pierde fila al reiniciar. FileWrite fallido deja envío sin fila ni fault. Timer=false retorna INIT_SUCCEEDED. FileOpen fallido sí bloquea executor. Casos: T60, T61, T62, T63. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: Pérdida/lectura parcial de evidencia y ausencia del ciclo autoritativo sin fallo explícito. I/O real y parser wrapper BLOCKED; no se bloqueó CSV operativo. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Append-only o ledger por sesión, fallos I/O observables, receipt atómico y timer comprobado. Propuesta sólo resuelve timer.


### F17 — Globals double sin límite de precisión de secuencia

Severidad: **Low**. Semántica: `infrastructure-only`.

Ubicación exacta: `frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh:67` `QrosBusHead`; `frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh:101` `QrosBusPublish`; `frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh:115` `QrosBusPublish`.

`STATIC_PROVEN` — Seq/event_ms se almacenan double y recuperan long sin rango finito/integral ni rotación de época.

Escenario/reproducibilidad: 1788782400123 ms pasa intacto. En double, 2^53+1 coincide con 2^53; publish declara éxito sin avanzar HEAD. Casos: T50, T51. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: No es agotamiento inminente normal; sí corrupción/persistencia sin rechazo. No se probó overflow long nativo MQL ni se certifica con JS Number. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Límites de entero exacto double y secuencia positiva/monotónica; protocolo de época.


### F18 — Barra, referencia y barreras efectivas carecen de contrato completo en núcleo

Severidad: **Medium**. Semántica: `execution-semantic`.

Ubicación exacta: `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:167` `GridNormalize`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:313` `SendEntry`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:364` `HandleModify`; `frozen/MQL5/Include/QROS_DEMO_BUS_v2.mqh:23` `QrosBusEvent`.

`STATIC_PROVEN` — Entrada normaliza SL/TP al tick más cercano (fallback point), exige SL<Ask<TP y sólo envía BUY. Evento sin barra/generación; entry_ref sin uso. Modify TP=0 conserva anterior y SL no creciente descarta evento entero. No valida stops/freeze levels ni resultado SetTypeFillingBySymbol.

Escenario/reproducibilidad: Geometría de solicitud válida puede tener stop entre Bid/Ask o muy cercano y ser rechazada. Modify sólo de TP se descarta sin subir SL. No se afirma que emisores exactos produzcan esos mensajes. Casos: T05, T07, T11, T26, T83. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: Una entrada por barra, puntos, primer toque/gap y SL primero dependen de emisor/broker exactos. Ausencia de SELL no es regresión sin contrato de módulo que lo requiera. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): Importar emisores exactos y probar paridad dimensional/causal/fills; no retocar unidades/señal/stops/prioridad.


### F19 — Fuentes y activación incompletas impiden certificación integral

Severidad: **High**. Semántica: `infrastructure-only`.

Ubicación exacta: `frozen/MQL5/Scripts/QROS_V223_RUNTIME_BOOTSTRAP.mq5:347` `OnStart`; `frozen/MQL5/Experts/QROS_DEMO_PORTFOLIO_EXECUTOR_v2.mq5:9` `include Trade/Trade.mqh`.

`BLOCKED` — Recibo declara ausentes emisores/wrapper; no hay ZIP deployment, START_RECEIPT, EX5/SET/templates ni Trade.mqh exacto 6182 en el árbol. AUTHORITY es histórico: PREREG MT5_EXTERNAL_PENDING y genealogía DIV3 previo distinto no reemplazan recibo v2.2.3.

Escenario/reproducibilidad: Cuatro espejos comparados en bytes/hash/blob coinciden. Inventario Git MQ5/MQH/ZIP no contiene faltantes; único ZIP listado es baseline v0.6. Casos: X01, X02, X03, X04, X05, X06, X07, X08. Los T son `TEST_PROVEN` en el harness; X son `BLOCKED`.

`INFERRED` — Consecuencia/exposición activa: No se prueba identidad del binario activo ni paridad/certificados de activación/broker. Se conserva afirmación del usuario de forward activo; no se contradice con prereg histórico. Expuesto si ocurre el escenario en el ejecutable vinculado a estas fuentes; no se inspeccionó el terminal ni se demuestra un incidente del forward.

Corrección propuesta (`INFERRED`): BLOCKED_PENDING_EXACT_SOURCE_IMPORT. Importar append-only verificado y gate aislado; no sustituir con main ni inspeccionar terminal activo.


## Controles demostrados y límites

- `STATIC_PROVEN` y T01–T03 (`TEST_PROVEN`): demo, Darwinex-Demo y USD se validan al iniciar; desarmado o CERT=0 no envían Buy. Nombre/arm token de código no autentican EX5.
- `TEST_PROVEN`: spread cero/cruzado bloqueado; kernel usa OrderCalcProfit de 1 lote y volumen efectivo, floor por step y rechazo de mínimo excesivo. Barrido de 36 casos más BUY/SELL del kernel pasa. Executor usa Ask para sizing y Buy(price=0); fill efectivo, Bid de salida, gap y SL primero requieren broker/emisor exactos. No se inventan fills/EOF.
- `TEST_PROVEN`: cupo 3, activo ocupado y reserva visible sobre cap se bloquean sin incertidumbre. Historial completo deduplica fills de igual position ID. No generalizar a pendientes, historia fallida o netting.
- `TEST_PROVEN`: prioridad en cohorte coetánea, consumo único por seq, slot ausente/SEQ que cambia, overflow >32 y skip HEAD inicial. No generalizar a payload sobrescrito antes de commit, rollback o dos productores.
- `TEST_PROVEN`: recovery lock permite CLOSE nuevo; timer sano cierra posición de día anterior. No prueba reconstrucción, no overnight estricto ni unlock.
- `TEST_PROVEN`: bootstrap comprueba nombres de emisores/posición/ticks/series en funciones probadas. HB vencido o estado no READY bloquea entrada, uptime futuro se rechaza y offset cambiado durante precheck reinicia conteo. No certifica continuidad postarranque.

## Escenarios obligatorios D01–D20

X representa bloqueo; diseñar fixture no equivale a ejecutarla.

| Requisito | Escenario | Casos |
|---|---|---|
| D01 | two entries same millisecond | T13, T14, T15 |
| D02 | fourth daily entry | T12, T35, T36 |
| D03 | zero/crossed spread | T05 |
| D04 | stale startup ring | T33, T34 |
| D05 | duplicate/torn sequence | T41, T42, T44, T79, T86 |
| D06 | overflow >32 | T43, T27 |
| D07 | broker rejection | T16, T23, T24, T39, X05, X12 |
| D08 | partial fill | T18, T25, X12 |
| D09 | disconnect before ACK | T19, T82, X12 |
| D10 | stop modification rejection | T23, T80, X05 |
| D11 | restart open position | T30, T31, T32, T34, T65, X01, X02, X03, X11 |
| D12 | persistent globals restart | T33, T45, T48, T55, T78, X11 |
| D13 | server midnight | T37, T38, T39, T40, T74, T81, X13 |
| D14 | US DST transition | T69, T70, T71, T72, T73, X13 |
| D15 | gap SL/TP | T21, X09 |
| D16 | two terminals | T46, T66, T75, X04, X10 |
| D17 | temporary trade forbidden | T29, T59, X12 |
| D18 | terminal auto-update | X06, X14, X16 |
| D19 | locked/partial CSV | T60, T61, T62, X04, X15 |
| D20 | late init/heartbeat expiry | T54, T55, T56, T57 |


## Bloqueos, decisión y propuesta

`BLOCKED`: fuentes faltantes/pruebas nativas tienen observed_result=null. No se inspeccionó MT5 operativo para conseguirlas ni se recuperaron bytes de otro repo/red. La única red para entregar es Git sobre la rama autorizada.

`INFERRED`: F01 y F03 bastan para **CRITICAL_REPLACEMENT_REQUIRED**: faltan reservas de exposición pendiente y existen caminos que suprimen gestión central futura. F04 agrega recuperación insuficiente ante protección/intención perdida. Emisores ausentes bloquean certificación del conjunto, pero no borran defectos del executor exacto. No se estima probabilidad de pérdida ni se afirma que ocurrieran en Darwinex.

`BLOCKED`: ni test count ni compilación bastan para promocionar. Falta importar fuentes exactas y gate completo: compile 0/0, parent-child parity, controller parity, forward module certs, combined canary, START_RECEIPT, armado CERT=1. Contención/contrato se crean únicamente en proposed/v2.2.4/; nada se cambia en frozen/.

## Reproducibilidad y entrega

Desde raíz con Python 3/Node ya disponibles, sin instalaciones:

```text
python audit/demo-forward-v2.2.3/tests/run_offline_audit.py --node <node-executable> --out audit/demo-forward-v2.2.3/evidence/<nuevo-directorio>
python audit/demo-forward-v2.2.3/tests/run_offline_audit.py --node <node-executable> --out audit/demo-forward-v2.2.3/evidence/<otro-directorio> --proposal
```

`STATIC_PROVEN`: runner rechaza hashes diferentes y exige salida nueva dentro de la auditoría. Generated JS/resultados son TEST_ONLY; stubs/scenarios no son runtime publicado ni sustituyen C++.

`TEST_PROVEN`: revisión final compara bytes de todos los paths iniciales de audit/demo-forward-v2.2.3 con Git HEAD y cuatro espejos con recibo. INTEGRITY_FINAL.json guarda resultado; ARTIFACT_MANIFEST liga nuevos artefactos SHA-256. SHA del commit se obtiene después y se comunica desde Git, sin hash autorreferente. Push limitado a esta rama, sin merge a main.
