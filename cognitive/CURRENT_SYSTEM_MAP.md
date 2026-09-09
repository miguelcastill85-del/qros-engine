# CURRENT_SYSTEM_MAP — alcance observado de QROS/RISE/QRCEL

Mapa de ingeniería subordinado, sin autorización científica. Las identidades exactas están en `research/system_map/SOURCE_INDEX.json`. Una ruta presente en el árbol remoto demuestra presencia; leer una interfaz no prueba ejecución. Este mapa no certifica cobertura exhaustiva del repositorio ni capacidad del próximo runtime.

## Autoridad y separación de capas

La fuente recuperada fue `control/CONTROL_AUTHORITY_MANIFEST_v3.json` en el repositorio canónico. La observación V191 enlaza HEAD, STATE y RUN_QUEUE por blobs exactos, registro V191, registro heredado V190 y siete redirects. Los recibos de reconciliación de V191 y el shadow cognitivo documentan la validación realizada. El checkout parcial de ingeniería contiene también controles V189 históricos: se excluyen explícitamente del bootstrap activo. El núcleo recibe por separado la raíz materializada V191 y el ancla externa.

| Capa | Componente y fuente | Capacidad observada y límite |
|---|---|---|
| A — Modelo | Rutas solicitadas Sol y Astra; receipts de las dos tandas DEVELOPMENT | Se observaron respuestas. Revisión interna inmutable, tokens y trazas completas no expuestos. No hay equivalencia funcional general demostrada. |
| B — Operación | Skill `qros-rise-execution-governor` de esta sesión | Protocolo de recuperación, verificación, ejecución, medida y persistencia. La presencia de la Skill no prueba validación conductual ni constituye HEAD científico. |
| B — QRCEL | `cognitive/runtime.py`, `kernel.py`, `evaluation.py` | Inspectores tipados; EXACT_SUM/CHECK_DAG; transacciones locales, checkpoint y exposición del benchmark. No es un solver LLM general ni runner económico. |
| C — QROS/RISE | Protocolo de universo causal v1.5 y referencias científicas delegadas por HEAD | La enumeración interna no demuestra suficiencia ontológica. El protocolo v1.5 es prospectivo; leerlo no adopta una nueva metodología en la campaña congelada. |
| D — Autoridad | Manifest, HEAD, STATE, RUN_QUEUE, registros y redirects V191 | Única autoridad activa observada. QRCEL conserva un puntero hacia ella y no recibe capacidad de promoción científica. |

## Componentes existentes que deben preservarse

| Área | Fuente identificada | Qué existe | Qué no queda probado aquí |
|---|---|---|---|
| Governor | Skill de sesión; protocolos persistentes del repo | Disciplina de continuidad y límites de autorización | Que cualquier implementación de agentes cumpla siempre la disciplina |
| RISE | `governance/QROS_RISE_PREDEVELOPMENT_UNIVERSE_FREEZE_PROTOCOL_v1.5.md` | Criterios de cobertura y auditoría adversarial, dos rondas sin nuevos hallazgos para el scope | RISE_FIXED_POINT de QRCEL completo |
| HEAD/STATE/cola | Tres roles delegados en manifest V191 | Estado y ruta científica separados del runtime | Inputs y preflights de cada runner disponibles en esta sesión |
| Manifests y hashes | Registro V191 e identidad heredada V190 | Blobs de autoridad y redirects; manifest cognitivo separado | Que un hash autorice leer datos o promueva evidencia |
| Controlador | `scripts/qros_persistent_chat_controller.py` | Validación, lease, heartbeat, fencing y selección de ítems bajo su esquema | Compatibilidad automática con cualquier nueva cola; la incompatibilidad histórica motivó el adaptador cognitivo de lectura |
| CAS y ejecución activa | `scripts/qros_persistent_git_cas.py`, `qros_persistent_foreground_guard.py` | Implementaciones existentes sujetas a sus contratos | Servicio de fondo permanente |
| Checkpoints | `governance/QROS_CHECKPOINT_RECOVERY_CONTRACT_v2.json` | Binding de inputs/algoritmo, continuidad de rangos, estado de commit y recuperación | Que un receipt sin bytes recuperables sea reanudable |
| Ledger local cognitivo | `cognitive/kernel.py` | Commit conjunto de output/evidencia/ledger y reuso idempotente de operaciones admitidas | Exactly-once remoto |
| Ledger del benchmark | `cognitive/evaluation.py` | Exposición propagada por genealogía; ausencia de fila no certifica sealed | Custodia física del corpus o identidad del modelo |
| Software de investigación | `include/qros/pipeline.hpp` en commit fijado | Interfaces de datos, FeatureGraph, programa/candidato, backtest, ledger, ResultStore, gates, portfolio, vault y MT5 | Compilación, exhaustividad de implementación, validez científica o MT5_PASS actual |
| Validadores | Validador oficial V2, preflights de holdout y execution-unit binding | Verificación de contratos existente; recibos históricos y tests identificados | Sustitución de todos los gates por un PASS cognitivo |
| Schemas | Esquemas explícitos en manifest/roles, contratos de ingeniería y parsers | Versionado y comprobación tipada en componentes acotados | Adaptación semántica automática de documentos históricos |
| Rematerialización | `control/recovery/qros_rematerialize_gzip_b64_v1.py` y durabilidad de fuentes | Verifica SHA-256 del carrier y fuente descomprimida; reemplaza output por rename | Disponibilidad de cualquier carrier, límites generales de descompresión o autorización de su contenido |
| Recuperación entre chats | Contrato de durabilidad, código persistente y checkpoints | Exigencia de bytes exactos y reconstrucción desde artefactos | Heredar herramientas o ejecutar después de terminar el runtime |
| Tests | Último receipt 0.3.2 y siete pruebas del corrector ampliado | 142 métodos históricos de componentes; siete adicionales del corrector; dos tandas por ruta | Test suite completa del motor C++ o evaluación sellada |

## Errores y contradicciones relevantes

1. V190 omitía la delegación de autorización en HEAD; la reconciliación V191 preservó el alcance y pasó el validador oficial. No se reutiliza el HEAD local V189 como autoridad vigente.
2. Las reparaciones F01–F12 y la carrera SQLite están descritas en `ERROR_MEMORY.json` y receipts de versiones. Aquí no se vuelven a declarar corregidas sin esos límites de evidencia.
3. El README y la matriz conservaban afirmaciones anteriores a las nuevas implementaciones y ensayos. Se corrigieron comandos sin ancla, la descripción de WAL, el alcance V191 y la supuesta ausencia de ensayos.
4. El audit histórico `docs/RISE_TRANSVERSAL_AUDIT_v0_3.md` declara carencias de aquella entrega; la interfaz actual recuperada contiene FeatureGraph, universe, vault y reportes. No se traslada automáticamente la lista antigua de carencias al estado actual, ni se certifica implementación correcta por ver declaraciones.
5. Dos benchmarks con efecto techo no identifican qué arquitectura mejora los resultados. Una función determinista ejecutada no puede etiquetarse como una ejecución completa de Sol+QRCEL.

## Cuellos de botella y decisión

El cuello de botella observado de esta evaluación es la discriminación y atribución: faltan tratamientos de sistema operacionales, trazas instrumentadas y casos de ejecución completa. La segunda limitación es integrar contratos históricos reales sin crear otra autoridad. La tercera es demostrar continuidad del agente; hoy hay evidencia más fuerte de continuidad del núcleo local.

Se preservan las cuatro alternativas A/B/C/D descritas en `research/ARCHITECTURE_REVIEW_v2.json`. D — QROS existente más inspectores mínimos — tiene implementación de componentes; no es ganador del stack completo. No se justifican agentes especializados adicionales por estas puntuaciones. Se conserva el núcleo mínimo existente, sin promoción ni afirmación de agotamiento de las demás ramas.
