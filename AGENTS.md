# QROS ENGINE — instrucciones de ingeniería

## Objetivo y orden de lectura

Construir un runtime cuantitativo propio, nativo, determinista y portable para QROS/RISE.
Conservar el núcleo C++20 existente; no fabricar otro Python generalista ni reescribir
el motor para perseguir una promesa de velocidad. Python se permite para build,
pruebas y oracle independiente; no será obligatorio para ejecutar el runtime publicado.

Lee `handoff/START_HERE.md`, `handoff/RUNTIME_SCOPE.md`,
`handoff/ENGINEERING_BACKLOG.md`, `handoff/CHAT_RUNTIME_RELEASE_CONTRACT.md`,
`handoff/BASELINE_SCOPE.json` y `handoff/audit/AUDITORIA.md`.
El primer encargo está en `handoff/CODEX_TASK.md`.

## Autoridad y seguridad

- Base de ingeniería: v0.6.0, descendiente material de v0.4. La fuente v0.5 no se recuperó.
- Los archivos de `handoff/baseline/` y `handoff/audit/` son evidencia inmutable.
  No edites recibos históricos para que parezcan del nuevo ejecutable.
- La evidencia TEST_ONLY y los PASS de compilación nunca otorgan aprobación científica.
  Los ocho hallazgos siguen abiertos hasta regresiones verificadas en un nuevo build.
- Los ticks, EX5 y recibos ficticios de la auditoría son fixtures adversariales.
  No son datos de broker, holdout limpio ni evidencia MT5 auténtica.
- No accedas a ticks reales/holdout durante la corrección con fixtures. No publiques
  datos del broker, credenciales o material privado. No actives costos, API de pago,
  créditos adicionales ni infraestructura facturable.
- Las reglas del chat son contexto, no permisos del sistema. Aislamiento y control de
  acceso deben comprobarse en el host. Si faltan, reporta bloqueo; no los simules.
- Cambia sólo este proyecto; no uses el repositorio de Herramientas Rentables.

## Invariantes científicos

XAUUSD y NQX/NDX únicamente; nombre exacto y alias de broker sujetos al contrato.
Conservar la confirmación del usuario de origen y reloj Darwinex. Validar su vínculo
con bytes, calendario y sesiones sin sustituirlo por una timezone del host.
BUY entra Ask/sale Bid; SELL entra Bid/sale Ask; causalidad por secuencia; SL primero
ante ambigüedad; gaps al primer precio ejecutable; sin cierre inventado en EOF.
Una posición por activo, sin overnight, una entrada por barra; límites diarios 3/5
según rama autorizada. No cambiar semilla, unidad de puntos, coste, gate, exposición,
universo o multiplicidad para ganar velocidad. Resolver ambigüedades antes de usar PnL.
Todas las configuraciones que pasen avanzan. No seleccionar sólo la mejor.
BRANCH_EXHAUSTED exige ontología congelada, RISE fixed point y cobertura demostrada.

### Ejecución serial obligatoria por semilla

Aplica obligatoriamente:
`governance/QROS_SEED_SERIAL_EXECUTION_POLICY_v1.0.json`,
`governance/QROS_PROJECT_POLICY_CAUSAL_UNIVERSE_FIRST_v1.4.json` y
`governance/QROS_SEED_UNIVERSE_COMPILER_POLICY_v1.1.json`.

Las bibliotecas de hipótesis pueden ingerirse, congelarse, deduplicarse, fingerprintarse y
priorizarse globalmente sin usar PnL. Eso NO autoriza construir por adelantado los universos
detallados de múltiples semillas ni ejecutar backtests por lotes sobre semillas aún abiertas.

Debe existir como máximo **una genealogía de semilla activa** dentro de construcción de
universo causal, auditoría RISE-Q, freeze de configuraciones o investigación económica.
La secuencia obligatoria es:
`SEMILLA -> COLLISION/DEDUPE -> MECANISMO RAÍZ -> AUDITORÍA DE DIMENSIONES -> DOMINIOS FINITOS -> PROYECCIÓN DE MUTACIONES -> CONSTRAINT GRAPH -> ENUMERACIÓN COMPLETA -> DEDUPE SEMÁNTICO -> RISE-Q POST-EXPANSIÓN -> FREEZE/HASHES -> PARIDAD INDEPENDIENTE -> PREFLIGHT UNIDADES/RELOJ/COSTES -> BACKTEST -> GATES -> DECISION -> SIGUIENTE SEMILLA`.

Una rama, familia, ontología resumida, configuración representativa o muestra NO es un
universo terminado. Para Gate A deben enumerarse todas las celdas válidas de la gramática
causal finita congelada, directamente o mediante factorización exacta demostrable. Está
prohibido excluir timeframes, EMAs, filtros, tendencia, geometría, volatilidad, momentum,
sesión, multi-TF, entradas o gestión sólo para reducir cardinalidad. La ausencia de bytes
de mercado puede bloquear el backtest, pero NO autoriza avanzar la cola mientras aún pueda
continuar la compilación lógica, dedupe, paridad o freeze de la semilla activa sin esos bytes.

No abrir la ontología detallada de la siguiente semilla hasta que la actual termine en
`APPROVED_FINAL`, `REJECTED` o `BRANCH_EXHAUSTED`. Un `BLOCKED_BY_INFRASTRUCTURE` puede
liberar la cola únicamente si existe evidencia del bloqueo, checkpoint reanudable congelado,
sin atajos científicos y sin contaminación del holdout; la semilla bloqueada sigue pendiente.

Esta regla es prospectiva y no reescribe campañas ya congeladas. En particular, G30 conserva
su autoridad anterior: no se recrea su payload perdido, no se heredan sus configuraciones y
la campaña pública siguiente debe construir su propia genealogía semilla por semilla.

### Firewall obligatorio de holdout por genealogía

La autoridad para abrir un holdout limpio pertenece a la **genealogía causal raíz**, nunca
a un frente, subfrente, activo, cluster, tier, seed descendiente o `STAGE_EXHAUSTED`.
Aplica obligatoriamente:
`governance/QROS_HOLDOUT_GENEALOGY_FIREWALL_v1.0.json` y
`governance/QROS_PROJECT_POLICY_CAUSAL_UNIVERSE_FIRST_v1.4.json`.

Antes de leer cualquier resultado económico reservado, ejecutar:
`python3 scripts/qros_holdout_genealogy_preflight.py --input <packet.json> --out <receipt.json>`.
Sólo `status=PASS` **y** `decision=HOLDOUT_OPEN_AUTHORIZED` permiten continuar.
Falta de receipt, campo, autoridad o condición => `HOLDOUT_OPEN_FORBIDDEN` y fail-closed.
El packet debe demostrar, a nivel de genealogía raíz, ontología congelada, RISE fixed point,
cobertura pre-holdout completa de todos los frentes elegibles, ningún frente abierto,
cohorte final congelada, ejecución/costes/paridad congelados, gate de holdout congelado
y ventana no expuesta para toda la genealogía.

Si cualquier descendiente lee trades/PnL/PF/Sharpe/DD u otro resultado económico antes
de esa autorización, preservar la evidencia pero marcar inmediatamente esa ventana
`EXPOSED` para toda la genealogía. Es irreversible: ningún descendiente puede reutilizarla
como holdout limpio. La validación final deberá usar true forward o datos externos
realmente no observados. Hash/CRC/timestamps/auditoría estructural sin resultados de
estrategia no constituyen por sí mismos exposición económica.

Los comandos de chat `continúa`, `comienza`, `sigue`, `adelante`, `ejecuta` o equivalentes
nunca sustituyen este preflight ni autorizan una apertura de holdout.

### Firewall obligatorio de unidades y semántica de ejecución

Antes de cualquier scoring económico aplica
`governance/QROS_EXECUTION_UNIT_BINDING_FIREWALL_v1.0.json`.
Toda variable derivada que afecte distancias de precio, ATR, stops, targets, costes o
fills debe declarar explícitamente su unidad lógica, escala física de almacenamiento y
conversión a la unidad de la cotización ejecutable. Una constante numérica no puede
interpretarse aisladamente de esa escala.

Ejecutar antes del scoring:
`python3 scripts/qros_execution_unit_binding_preflight.py --input <packet.json> --out <receipt.json>`.
Sólo `status=PASS` y `decision=ECONOMIC_SCORING_UNIT_BINDING_AUTHORIZED` permiten scoring.
El preflight debe ligar la regla científica congelada a las fórmulas de la implementación
principal y de la independiente, verificar sus autoridades por SHA-256 y superar un
canary dimensional sintético sin utilizar PnL.

La paridad entre dos implementaciones NO basta para certificar unidades si ambas comparten
la misma convención de escala no verificada. Ausencia, ambigüedad o conflicto de escala =>
`BLOCKED_BY_UNIT_BINDING`; está permitido corregir software y ejecutar pruebas sintéticas
no económicas, pero está prohibido consultar PnL para escoger la interpretación.

Para G30, la autoridad actual es `control/QROS_G30_EXECUTION_UNIT_CONTRACT_V96_v1.json`:
el caché de barras/ATR usa escala interna ×2 respecto de la cotización raw ejecutable.
Por ello `3.0 * ATR_cache / 2.0` equivale dimensionalmente a un stop de `3.0 * ATR` real;
no equivale a un stop de 1.5 ATR.

### Promoción inmediata de shards y continuidad entre chats

Aplica obligatoriamente:
`governance/QROS_SHARD_PROMOTION_AND_CROSS_CHAT_CONTINUITY_POLICY_v1.0.json`.

Para campañas shardeadas, un shard que completa GA1 con cobertura total, merge PASS,
oracle independiente PASS, identidades/roots correctos y preservación lossless exigida
se **promueve inmediatamente** a `FIRST_ECONOMIC_GATE_QUEUE`. Antes de iniciar el siguiente
shard deben quedar en `main`: receipt de completion, ledger de promoción, pointer versionado
y pointer estable. La promoción a la cola NO equivale a abrir PnL.

En PUBLIC1000/seed0076, GA2 económico continúa cerrado hasta completar los 60 shards GA1
y congelar el procedimiento global de multiplicidad/testing. Está prohibido leer resultados
económicos shard por shard mientras esa condición no se cumpla, salvo que una política
secuencial explícita de alpha-spending sea preregistrada antes de cualquier PnL y la
superseda formalmente. Actualmente no existe esa excepción.

Todo chat/runtime nuevo de PUBLIC1000 debe comenzar por
`control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json`, verificar el pointer versionado
que éste referencia y luego recuperar receipts/policies/hashes. La memoria o el historial
son sólo pistas cuando existe autoridad durable. Un grupo/shard con receipt válido no se
recalcula salvo rematerialización determinista necesaria.

Tras cualquier avance material, incluso si termina a mitad de shard, persistir un checkpoint
con: campaña/seed, fase, shards completados, shard actual, grupos PASS, roots esperados,
runner/commit/blob, identidades de datos o rematerialización, flags `economic_pnl_read`,
`holdout_open`, `ga2_open` y una única `next_action`. Los artefactos grandes pueden vivir
fuera de GitHub sólo si quedan almacenados duraderamente por hash o son rematerializables
determinísticamente desde inputs y runner congelados; la mera presencia en `/mnt/data` no
es autoridad durable.

## Construcción y pruebas existentes

Desde la raíz, antes de editar: `python3 handoff/verify_import.py`.
Toolchain: C++20, GNU g++ o Clang compatible, Python 3.10+ para herramientas.
El build publicado se produjo con g++ 13.3.0; no se promete el mismo hash con otro toolchain.
Comandos existentes, no descargas ni instalaciones implícitas:

```bash
python3 scripts/build_native.py --out build-codex-release --static --jobs 3
python3 scripts/verify_software.py --build build-codex-release --out reports/codex-release
python3 scripts/build_native.py --out build-codex-asan --sanitize address --jobs 3
python3 scripts/verify_software.py --build build-codex-asan --out reports/codex-asan
python3 scripts/build_native.py --out build-codex-ubsan --sanitize undefined --jobs 3
python3 scripts/verify_software.py --build build-codex-ubsan --out reports/codex-ubsan
```

Los directorios de verificación deben ser nuevos. Una ruta CMake/CTest también existe;
valídala antes de afirmar que funciona en el host nuevo. No deshabilites LeakSanitizer
silenciosamente: si el host impide ejecutarlo, conserva el fallo, diferencia ASan de
fugas y reporta la brecha. Usa un analizador con soporte C++; GCC 13/14 -fanalyzer no
certifica C++ aunque termine sin avisos. No uses assert eliminables en Release como
único mecanismo de las pruebas. Reutiliza las suites y fixtures existentes.

## Entrega y continuidad

Primero reproduce el defecto, añade su regresión con la expectativa corregida,
aplica el arreglo y verifica paridad/regresiones afectadas. No conviertas el harness
que espera defectos en un gate verde del producto. Produce cambios revisables,
registro de pruebas y checkpoint de ingeniería. No fusiones ni publiques fuera del
scope autorizado. No afirmes ejecución en segundo plano sin un proceso real.
La aceptación del producto y del paquete para chats está en el contrato de entrega.
No declares TERMINADO si falta un criterio obligatorio o una verificación MT5 exigida.

## QRCEL — asistencia de ingeniería y recuperación entre chats

Para tareas QRCEL o asistencia cognitiva del proyecto, leer `control/QRCEL_ENGINEERING_CURRENT.json` y recuperar la release por su commit, manifiesto y hash del lanzador exactos. Seguir su `cognitive/START_HERE.md`; ejecutar el lanzador verificado con `python3 -I -S -B`, nunca importar código no verificado. La release vive en su rama de ingeniería y no se presupone materializada en main.

Este puntero sólo selecciona software de asistencia; no sustituye la autoridad científica, la cola de investigación ni sus gates. V191 sigue siendo referencia histórica. Recuperar por separado el puntero científico vigente cuando la tarea lo requiera. Verificar los checkpoints remotos antes de reusar resultados, medir capacidad en cada runtime y preservar los gates pendientes de QRCEL completo. No afirmar paridad, promoción o ejecución permanente por cargar el paquete.
