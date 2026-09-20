# QROS/RISE — Auditoría de arquitectura, rendimiento y deriva de complejidad
Fecha: 2026-09-20
Estado: INFORME / NO IMPLEMENTACIÓN

## OBJETIVO
Determinar por qué el proyecto pasó de campañas de minería relativamente directas y productivas a una ejecución dominada por control-plane, shards, receipts, hashes, leases, reconciliaciones e infraestructura; separar rigor científico necesario de complejidad accidental; y definir una arquitectura futura que recupere velocidad sin perder causalidad, reproducibilidad ni protección del holdout.

## AUTORIDAD
- main HEAD al crear este informe: e94b275e1c9032613bd38d0a681eb991ce604318
- Frontier científico vigente: V257
- Campaña: PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA
- Universo congelado: 48,280,320 signal configs
- Shards científicos: 60
- Configuraciones por shard: 804,672
- Shards cerrados: 8
- Shard activo: #9 NQX/BUY/M15
- PnL económico: cerrado
- GA2: cerrado
- holdout: cerrado

## CONCLUSIÓN EJECUTIVA
QROS no se volvió lento principalmente porque ahora investigue más configuraciones. Se volvió lento porque el control-plane pasó de proteger la investigación a ocupar la mayor parte del trabajo operativo.

Los 60 shards NO son el problema principal. Son una partición natural y defendible de 2 activos x 2 lados x 15 timeframes. El problema es que cada shard se transformó en una cadena extensa de materialización, grupos, SQLite temporal durable, compresión, hashes, receipts, merge, oracle, maskpack, compaction, cleanup, handoffs y reconciliaciones.

El motor científico contiene buenas optimizaciones (bitsets, caches, memmap, dedupe de event masks, factorization de management), pero todavía conserva cuellos de botella evitables y su hot path quedó rodeado por una cantidad excesiva de control-plane.

La arquitectura futura debe separar completamente:
1. HOT PATH científico de alto rendimiento.
2. CHECKPOINT/PROMOTION PATH de evidencia durable.
3. CONTROL PLANE mínimo.

GitHub no debe estar en el inner loop del backtest.

## QUÉ HICIMOS BIEN

### 1. Factorización científica
El universo evita el scoring económico ciego de:
48,280,320 signal configs x 3,710 management x 3 execution x 7 stress
= 3,761,519,731,200 pruebas brutas.

La arquitectura actual separa GA1 (event masks, sin PnL), GA2 (signal alpha), management y stress. Esto evita aproximadamente 77,910 overlays económicos por cada signal config antes de demostrar señal.

DECISIÓN: CONSERVAR.

### 2. Event-mask dedupe antes de PnL
Ejemplos verificados:
- NQX BUY H4: 804,672 configs -> 58,647 máscaras distintas; 746,025 aliases.
- NQX BUY M10: 804,672 -> 253,230 distintas; 551,442 aliases.
- NQX BUY M12: 804,672 -> 248,010 distintas; 556,662 aliases.

La reducción es científicamente valiosa porque N_TESTS debe partir de hipótesis/event masks distintas, no de aliases.

DECISIÓN: CONSERVAR, pero acelerar radicalmente su implementación.

### 3. Causalidad y semántica
Se congelaron reloj, sesiones, DST, Ask/Bid, disponibilidad causal, retest windows, opposite-break semantics y no-lookahead antes de PnL.

DECISIÓN: CONSERVAR.

### 4. Holdout firewall y multiplicidad
La separación de GA1/GA2/holdout y la prohibición de usar management para rescatar señales evita overfitting estructural.

DECISIÓN: CONSERVAR.

### 5. Sharding científico
60 shards por asset/side/timeframe aíslan fallos, permiten reanudación y no cambian el universo.

DECISIÓN: CONSERVAR LOS 60 SHARDS COMO IDENTIDAD CIENTÍFICA; NO CONFUNDIRLOS CON CHUNKS OPERACIONALES.

## QUÉ HICIMOS MAL / COMPLEJIDAD ACCIDENTAL

### 1. El control-plane pasó a dominar el proyecto
Snapshot verificado:
- control/: 968 archivos top-level.
- governance/: 79 archivos.
- scripts/: 170 archivos.
- Clasificación heurística de los últimos 100 commits: 93 control/infraestructura, 4 ejecución científica, 3 otros.

Esto es un indicador de deriva arquitectónica: la mayor parte de la actividad dejó de producir señales, event masks, trades o resultados y pasó a administrar el proceso que administra el proceso.

DECISIÓN: REDUCIR.

### 2. Checkpoint demasiado fino
Cada shard tiene 24 grupos internos. Los receipts de merge muestran 72 artefactos por shard. Si este patrón se mantiene:
60 shards x 24 grupos = 1,440 ejecuciones de grupo.
60 shards x 72 artefactos = 4,320 artefactos de grupo, antes de packs, índices, mappings, receipts y compaction.

Los 24 grupos son una decisión operacional, no una identidad científica. Se convirtieron de facto en unidades de gobernanza.

DECISIÓN: desacoplar shard científico de chunk operativo. El chunk debe ser adaptativo y reemplazable sin cambiar la ciencia.

### 3. I/O y serialización excesivos
M12 produjo:
- maskpack global sin comprimir: 2,590,887,817 bytes.
- index: 28,769,160 bytes.
- config-to-class: 51,499,008 bytes.
- maskpack comprimido final: 683,104,903 bytes.
- artefactos de grupos originales: ~2.591 GB; comprimidos: ~322 MB.

El hot path genera, comprime, descomprime, hashea y vuelve a empaquetar grandes cantidades de bytes.

DECISIÓN: el resultado final debe ser durable; los temporales no necesitan el mismo nivel de durabilidad.

### 4. Durabilidad en el lugar equivocado
qros_seed0076_ga1_shard_worker_v223 usa SQLite temporal con:
- journal_mode=DELETE
- synchronous=FULL
- commits cada 20,000 config IDs

Ese DB es scratch temporal y se elimina al final. Pagar fsync/durabilidad fuerte dentro del scratch es contrario al diseño de checkpoints: la durabilidad debe estar en el límite del chunk, no por cada lote interno.

DECISIÓN: sustituir por scratch no-durable/recomputable + checkpoint atómico final.

### 5. Trabajo repetido por grupo
En modo --only-group-index, el worker todavía:
- reconstruye filter_packages;
- reconstruye package_partition;
- calcula el ordered config root recorriendo las 804,672 configuraciones del shard;
- construye structural cache para todas las ventanas/tie policies;
- abre/finaliza una DB por grupo.

Con 24 grupos, parte de este trabajo fijo se repite 24 veces.

DECISIÓN: todo lo invariante al shard debe construirse una sola vez y compartirse por mmap/content-addressed cache.

### 6. Bug de rendimiento concreto
En group_packages_exact():
- se calcula zlib.compress(p.tobytes(),1) y el resultado no se utiliza.
- p.tobytes() se genera repetidamente.

Es CPU/copia inútil en un loop de paquetes.

DECISIÓN: eliminar inmediatamente en la futura optimización, después de parity tests.

### 7. Hash criptográfico demasiado dentro del inner loop
SHA-256 es necesario para identidad final, pero no para cada operación temporal.

DECISIÓN:
- hash rápido/no criptográfico o fingerprint vectorial para agrupamiento provisional;
- confirmación byte-exact contra colisiones;
- SHA-256 solo para artefactos/promoción final.

La autoridad científica final sigue siendo SHA-256.

### 8. Dedupe demasiado tarde
Los shards muestran 68-93% de aliases exactos en ejemplos ya cerrados. Estamos pagando gran parte del costo para descubrir redundancia después.

DECISIÓN:
- semantic canonicalization antes de ejecución;
- common subexpression elimination;
- mask algebra;
- exact data-dependent dedupe después.

No se debe intentar predecir event-mask equality cuando depende de datos; sí eliminar equivalencias lógicas antes de ejecutar.

### 9. Capas de continuidad superpuestas
Actualmente existen DEK, CWS, anti-freeze, external-call budget, heavy-job supervisor, fenced lease, persistent-chat protocol y extended-work bridge.

Cada una nació para cerrar un incidente real, pero la composición aumentó superficie de fallo, stale metadata y reconciliación.

DECISIÓN: consolidar en una única capa de ejecución durable con tres primitivas:
- JOB
- CHUNK
- CHECKPOINT

El resto debe convertirse en invariantes internos, no en subsistemas visibles separados.

## POR QUÉ ANTES SENTÍAMOS MÁS VELOCIDAD
VERIFICADO:
El proyecto histórico produjo módulos completos con robustez de segunda capa, portfolio integration y MT5 pending. Eso demuestra que el flujo antiguo podía convertir hipótesis en resultados útiles sin este volumen de control-plane.

INFERIDO:
La velocidad inicial provenía de una combinación de:
- menos gobernanza por transición;
- ejecución más directa en memoria;
- menos serialización de event masks intermedias;
- menos revalidación de bytes ya certificados;
- búsqueda/vectorización enfocada al resultado en vez de persistir cada micro-etapa.

No existe en las fuentes recuperadas una medición homogénea de wall-clock antiguo vs actual, por lo que no se afirma un factor exacto de slowdown.

## ARQUITECTURA FUTURA PROPUESTA — QROS FAST RESEARCH CORE

### L0 — Immutable Data Plane
Auditar cada carrier una sola vez.
Crear cache content-addressed:
DATA_SHA -> DEV prefixes -> bars -> indicators -> atomic masks.

Regla:
si los hashes de input y código coinciden, NO rehash pesado y NO rematerializar.

### L1 — Causal Compiler
Entrada: hipótesis y ontología congelada.
Salida:
- canonical operator DAG;
- symbolic dedupe;
- common subexpressions;
- frozen config stream/root;
- atomic feature/mask plan.

No PnL.

### L2 — Mask Algebra Engine
Precomputar una vez por asset/side/timeframe:
- structural states;
- raw breaks;
- ATR/EMA/RSI/CCI/Stoch masks;
- session masks;
- MTF masks;
- retest transforms.

Representación primaria:
bitsets / packed uint64 blocks.

Combinar configuraciones con AND/OR sobre bitsets, no reevaluar indicadores/config por config.

### L3 — Fast Exact Dedupe
Dos niveles:
1. fingerprint rápido provisional.
2. byte equality exacta dentro de buckets.
3. SHA-256 final solo de clases/promoción.

No comprimir dentro del loop de dedupe.

### L4 — Adaptive Execution Chunks
Scientific shard sigue fijo.
Execution chunk es variable.

Objetivo:
- 2-10 minutos de compute por chunk, o límite de RAM.
- no 24 grupos obligatorios si el runtime soporta más.
- si falla, dividir dinámicamente el chunk sin cambiar config IDs ni universo.

Checkpoint solo por chunk durable.

### L5 — Result Store Minimal
Por shard durante GA1 conservar:
- config_id -> class_id
- representative config
- event_count
- class mask store
- roots

Eliminar artefactos duplicados intermedios después de verificación.

No generar tres representaciones completas del mismo mask si una puede regenerar las demás determinísticamente.

### L6 — Thin Evidence Plane
Persistir en GitHub SOLO:
- ontology/config roots;
- runner/code roots;
- shard completion receipt;
- checkpoint current;
- final gate receipts;
- correction receipts.

No persistir una nueva autoridad por cada diagnóstico o micro-etapa.

Objetivo operativo:
control files O(campañas + shards + gates), no O(tool calls/incidentes).

### L7 — Promotion / Expensive Validation
Solo después de GA1:
- GA2
- multiplicidad
- management
- stress
- holdout
- supergate
- MT5
- portfolio

La evidencia pesada se activa únicamente cuando una señal tiene derecho científico a llegar allí.

## REGLAS DE RENDIMIENTO PROPUESTAS

1. NO_GITHUB_IN_HOT_LOOP.
2. NO_FULL_REHASH_IF_CONTENT_ADDRESS_ALREADY_VERIFIED.
3. NO_FULL_CONFIG_ROOT_RECOMPUTE_PER_GROUP.
4. NO_SYNC_FULL_SQLITE_FOR_EPHEMERAL_SCRATCH.
5. NO_COMPRESSION_IN_DEDUPE_INNER_LOOP.
6. NO_REBUILD_STRUCTURAL_CACHE_PER_GROUP.
7. NO_REBUILD_FILTER_PACKAGES_PER_GROUP.
8. ONE_FINAL_SHA256_PER_PROMOTED_ARTIFACT.
9. SCIENTIFIC_SHARD != EXECUTION_CHUNK.
10. CACHE_ONCE_REUSE_EVERYWHERE.
11. HASH/PARITY GATES AT BOUNDARIES, NOT EVERY INNER STEP.
12. CONTROL_PLANE_MUST_NOT_EXCEED SCIENTIFIC_WORK IN NORMAL OPERATION.

## OBJETIVOS DE PERFORMANCE A VALIDAR
Estos son objetivos de ingeniería, NO resultados actuales:
- Reducir >=90% las escrituras durable/control-plane por shard.
- Reducir 24 ejecuciones fijas/shard a chunking adaptativo, típicamente 2-8 chunks/shard si RAM/tiempo lo permiten.
- Eliminar 23/24 recomputaciones redundantes del config root por shard.
- Construir structural/filter caches una vez/shard.
- Reducir bytes temporales materializados antes de final pack.
- Hacer que una campaña normal dedique >=80% de wall-clock a cálculo científico efectivo y <=20% a control/I/O/verificación.
- Reusar carriers/bars/indicators entre genealogías cuando identidad/semántica coincidan.

## QUÉ NO DEBEMOS HACER
- No volver al sistema antiguo eliminando holdout firewall, causalidad o multiplicidad.
- No borrar hashes/manifests válidos.
- No tratar millones de aliases como evidencia independiente.
- No hacer un nuevo mega-framework de arquitectura para solucionar el exceso de arquitectura.
- No construir primero el production extended worker actual y luego optimizar: eso automatizaría un hot path todavía ineficiente.

## PLAN RECOMENDADO
P0. Congelar nuevas capas de gobernanza. No crear más frameworks salvo necesidad demostrada.
P1. Construir un benchmark reproducible usando un shard YA CERRADO (por ejemplo NQX BUY M12) para medir CPU, I/O, hashes, compression, DB, caches y control-plane.
P2. Implementar FAST_CORE en rama aislada sin cambiar semántica.
P3. Exigir paridad exacta trade/event-mask/config-to-class contra el shard cerrado.
P4. Benchmark A/B contra worker v223/v236.
P5. Solo si la nueva ruta es idéntica y materialmente más rápida, promoverla.
P6. Reanudar M15 con FAST_CORE.
P7. Terminar los 60 shards.
P8. Abrir GA2 después de 60/60 como ya estaba congelado.

## DECISIÓN
No conviene volver completamente atrás.
Tampoco conviene seguir construyendo infraestructura sobre el motor actual.

La ruta óptima es:
PRESERVAR LA CIENCIA + SIMPLIFICAR EL CONTROL + REESCRIBIR EL HOT PATH.

Scientific state: PREREGISTERED_NO_RESULTS.
Este informe no abre PnL, GA2 ni holdout y no modifica el universo.
