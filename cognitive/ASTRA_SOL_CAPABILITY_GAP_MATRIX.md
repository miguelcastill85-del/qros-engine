# Astra–Sol: matriz de brechas observables

Existen dos tandas DEVELOPMENT por ruta solicitada: 12 casos iniciales y seis ampliados, con respuestas correctas e idénticas en ambos modelos. Son comparaciones descriptivas bajo instrucciones compartidas; no certifican una comparación nativa plenamente controlada ni una brecha general. Las clasificaciones de compensación siguientes siguen siendo hipótesis, no ventajas nativas verificadas. `UNKNOWN` significa brecha general no identificada, no ausencia de respuestas observadas.

| Capacidad | Compensación propuesta | Brecha observada |
|---|---|---|
| REASONING | PARTIALLY_COMPENSABLE | UNKNOWN |
| DECOMPOSITION | PARTIALLY_COMPENSABLE | UNKNOWN |
| PROGRAMMING | PARTIALLY_COMPENSABLE | UNKNOWN |
| DEBUGGING | PARTIALLY_COMPENSABLE | UNKNOWN |
| STATISTICS | PARTIALLY_COMPENSABLE | UNKNOWN |
| CAUSALITY | PARTIALLY_COMPENSABLE | UNKNOWN |
| RESEARCH | PARTIALLY_COMPENSABLE | UNKNOWN |
| PLANNING | PARTIALLY_COMPENSABLE | UNKNOWN |
| CONTINUITY | SYSTEM_COMPENSABLE | UNKNOWN |
| RECOVERY | SYSTEM_COMPENSABLE | UNKNOWN |
| TOOL_USE | PARTIALLY_COMPENSABLE | UNKNOWN |
| ERROR_DETECTION | PARTIALLY_COMPENSABLE | UNKNOWN |
| VERIFICATION | PARTIALLY_COMPENSABLE | UNKNOWN |
| AUTONOMY | PARTIALLY_COMPENSABLE | UNKNOWN |
| FILES | SYSTEM_COMPENSABLE | UNKNOWN |
| GOAL_PERSISTENCE | SYSTEM_COMPENSABLE | UNKNOWN |
| CONTEXT_DRIFT | PARTIALLY_COMPENSABLE | UNKNOWN |
| DEPENDENCIES | SYSTEM_COMPENSABLE | UNKNOWN |
| EVIDENCE_SYNTHESIS | PARTIALLY_COMPENSABLE | UNKNOWN |
| CONTRADICTIONS | PARTIALLY_COMPENSABLE | UNKNOWN |
| NATIVE_REPRESENTATIONS | NOT_CURRENTLY_COMPENSABLE | UNKNOWN |
| COMPLEX_END_TO_END | PARTIALLY_COMPENSABLE | UNKNOWN |
| HARD_RUNTIME_LIMITS | NOT_CURRENTLY_COMPENSABLE | UNKNOWN |
| TRAINING_KNOWLEDGE | PARTIALLY_COMPENSABLE | UNKNOWN |

La recuperación, las identidades, los DAG y la aritmética exacta tienen evidencia de componentes locales. Esos resultados no miden razonamiento general ni equivalencia entre modelos.

También se observaron dos programas declarativos nuevos, uno por ruta, y 30 replays operacionales conformes bajo tres políticas de persistencia. `research/system_development/RESULTS.json` identifica una reducción de recomputación acotada a esos fallos; no identifica una brecha nativa entre modelos ni comparación integral con CURRENT_QROS.

Evidencia acotada: `research/model_development/run_001/RESULTS.json` y `research/model_development/extended_002/RESULTS.json`. El diagnóstico de una función breve no mide reparación de un repositorio; una respuesta sobre recuperación no mide recuperación efectiva del modelo tras perder contexto. El control ejecutado EXACT_SUM tampoco representa por sí solo `SOL_QRCEL`.
