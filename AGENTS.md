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


## QROS/RISE Anti-Stall v2.1 — arranque obligatorio para agentes del repositorio

**Antes de cualquier continuación**, identificar primero la línea de trabajo (lane). La ciencia estable de `main` y el backtest directo `research/seed0076-direct-dev-backtest-20260922` son autoridades DIFERENTES; no usar el pointer V259 para retroceder una línea científica distinta. Recuperar `control/QROS_ANTI_STALL_ACTIVE_GOVERNANCE_POINTER.json` y `anti_stall/README_QROS_ANTI_STALL_V2_1.md` cuando estén presentes en la rama activa. Consultar luego la fuente durable del lane (GitHub commit/blob SHA y checkpoint) y los carriers por ID exacto de Google Drive; rehash de bytes antes de promoción de confianza. Prohibido basarse únicamente en resúmenes de conversación o en metadata remota para certificar el ZIP.

El ejecutor `anti_stall/scripts/qros_anti_stall_v2_1.py` procesa UNA etapa preinscrita por invocación, reanuda desde la última etapa PASS y no reitera una etapa cerrada. `anti_stall/scripts/qros_meta_audit_v2_1.py` debe validar los bytes y el estado con el hash fijado fuera del recibo. Ante conflicto de autoridad, divergencia científica o dependencia invalidada, FALLAR CERRADO; ante interrupción operacional, registrar incidente y reanudar sin duplicación. No perseguir cambios ortogonales en `main` durante el lease; reconciliar en premerge.

Este archivo facilita recuperación en nuevos entornos **solo si el agente lee el repositorio**. No habilita ejecución fuera de sesión por sí mismo. Un scheduler externo o GitHub Actions autorizado debe invocar el runner, con política de costos y permisos explícitos. No se modifica la semilla, GA1 histórico, resultados, MT5, holdout ni riesgo.


## QROS/RISE Anti-Stall v2.2 — presupuesto literal y vías alternativas

**Bootstrap vigente para todo trabajo QROS del repositorio:** leer primero `control/QROS_ANTI_STALL_ACTIVE_GOVERNANCE_POINTER.json` de `main`; seguir su `release_anchor_git_blob_sha1` y `anti_stall/README_QROS_LITERAL_NONSTALL_V2_2.md`. Identificar después la rama científica concreta y leer **su** puntero vivo. La rama directa `research/seed0076-direct-dev-backtest-20260922` usa `control/QROS_SEED0076_DIRECT_CURRENT_CHAT_HANDOFF.json`; jamás sustituirlo por una indicación antigua del puntero de gobernanza.

**Límites operativos literales:** toda ruta ordinaria tiene como máximo **120 segundos absolutos**, **45 segundos sin nuevos bytes verificables** (gracia de arranque limitada e incluida en el límite absoluto), presupuesto máximo de **180 segundos por despacho** y **dos rutas causales equivalentes distintas** congeladas antes de observar PnL. Nunca repetir la ruta fallida idéntica. Para trabajos pesados previamente fragmentados y con recibos SHA preinscritos puede autorizarse un máximo explícito de **600 segundos absolutos / 90 segundos sin progreso** en un ejecutor externo; dividir los chunks si el despacho interactivo no puede cubrirlos.

**Anti-estancamiento efectivo:** usar `anti_stall/scripts/qros_progress_watchdog_v2_2.py` para terminar el grupo completo del proceso al agotar su presupuesto; solo un shard nuevo o modificado con tamaño y SHA-256 recalculados puede renovar el plazo de inactividad. Ante fallo, `anti_stall/scripts/qros_continuation_dispatch_v2_2.py` debe cambiar automáticamente a la siguiente ruta **precongelada equivalente**. Si todas fallan, congelar incidente y shards válidos; continuar únicamente una tarea independiente cuyas dependencias estén verificadas, sin ascender ni saltar la etapa fallida. El ejecutor v2.1 y su auditor independiente continúan como base y fuente de recibos de una etapa.

**Firewall:** la rapidez no autoriza cambiar la semilla, reescribir la tesis, duplicar trabajo cerrado, reducir gates, abrir holdout/GA2, reutilizar shards congelados ni atribuir un PASS a una tarea diferida. Error de autoridad o divergencia científica ⇒ FAIL_CLOSED, no selección oportunista de otra fuente o configuración. Se verificaron 45 pruebas locales (37 regresiones v2.1 + 8 adversariales v2.2) y la identidad exacta del paquete en Drive; Windows nativo y CI remoto v2.2 siguen sin certificación. La ejecución fuera del chat requiere scheduler y acceso autenticado expresamente configurados, nunca se presume activa.


## Continuidad efectiva en ChatGPT Android — Anti-Stall chat v1

Al responder «continúa», «adelante» o un encargo de QROS dentro del proyecto ChatGPT «Trading algoritmico», usar `governance/QROS_ANDROID_CHAT_TURN_ANTISTALL_V1.json` y obtener **en este turno** el pointer vigente `control/QROS_ANTI_STALL_ACTIVE_GOVERNANCE_POINTER.json` de `main` con GitHub autenticado. Para la campaña directa W5 obtener su puntero científico vivo en la rama exacta indicada por el protocolo, verificar sus `target`, ancla y hashes Git de forma independiente; otras campañas usan su propia autoridad exacta.

Ejecutar ahora únicamente el delta pendiente con las herramientas accesibles desde el chat. Ante un bloqueo, congelar la rama afectada y continuar solo una acción independiente legitimada. Tras cada fragmento completado, verificar datos/receipts, persistir handoff y CAS del puntero, leerlo de retorno y conservar la siguiente acción; **no** reemplazar hashes por memoria, no repetir fragmentos cerrados ni abrir holdout/GA2/Gate A. No hace falta instalar software en un PC para este modo. Tampoco existe proceso de chat corriendo sin usuario después de finalizar una respuesta: el siguiente mensaje vuelve a activar la secuencia. El código GitHub no instala controles dentro de la app Android, y los chats fuera de este proyecto necesitan las instrucciones correspondientes.


## Anti-Stall GitHub-native V1 — mandato operativo para chats Android, W5 y etapas futuras

**Prioridad superior a instrucciones anteriores que indiquen Library/Drive como checkpoint:** leer primero `control/QROS_ANTI_STALL_ACTIVE_GOVERNANCE_POINTER.json` de `main` y `governance/QROS_GITHUB_NATIVE_SHARD_STORAGE_V1.json`, y después el puntero científico vivo de la rama exacta. El checkpoint W5 V33 446/710 original tiene todos los recibos y plan/runner dentro de un ZIP Git nativo verificado y una representación 16-part Git ASCII independiente; no vuelvas a descargar Library para reconstruir este checkpoint. El puntero científico documenta el commit exacto y los SHA-1/SHA-256. Los ticks grandes de broker permanecen externalizados e inmutables por hash: no se afirma que los 2,57 GB estén dentro de objetos Git.

**Mecanismo ejecutable real:** `anti_stall/chat/qros_github_shard_store_v1.py` comprueba CRC, SHA de todos los miembros, plan 710, integridad de 446 recibos, conteos/campos/trades, gates cerrados y recorre deltas SHA256 encadenados. Ejecutar máximo SEIS fragmentos nuevos originales por transacción, jamás repetir los ya respaldados en Git. Comparar paridad nueva contra las cintas V28 originales antes de considerar PASS; generar `DELTA_<inicio>_<fin>.json` con bytes íntegros de cada recibo y hashes individuales. Crear Git blob/archivo inmutable, releerlo desde GitHub por SHA1 y SHA256, actualizar índice apéndice, handoff y live pointer por compare-and-swap. Si cualquiera de esas acciones falla, congelar trabajo local no promovido sin continuar otra tanda. El protocolo está documentado en `anti_stall/chat/README_GITHUB_NATIVE_SHARD_STORE_V1.md`.

**Almacenamiento:** GitHub para recibos, código, manifest, cola y checkpoint; Library no es almacén científico para resultados nuevos. Solo puede usarse puente TEMPORAL de transferencia si el conector de GitHub no acepta bytes locales; eliminarlo luego de lectura de retorno Git. No borrar evidencia histórica en Library sin autorización. En chats Android el mecanismo se activa durante cada turno con las herramientas disponibles; NO existe daemon después de responder y no se necesita instalar nada en Windows. Hasta certificación del broker, Gate A, holdout y GA2 permanecen cerrados.
