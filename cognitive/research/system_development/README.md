# Ensayo operacional restringido

Sol y Astra produjeron un programa declarativo cada uno. Ambos programas pasaron el contrato congelado y fueron ejecutados por el host bajo tres políticas de persistencia y cinco escenarios: 15/15 por programa. Son dos respuestas de modelos y 30 replays de un caso, no 30 tareas independientes de modelos.

El intérprete admite exclusivamente EXACT_SUM y CHECK_DAG. Un séptimo nodo sintético, S, debía permanecer bloqueado; no hubo intentos de ejecutarlo. No se ejecutó Python generado por los modelos. El host rechazó los probes de aislamiento de procesos; esos fallos están registrados en VALIDATION_RECEIPT.json.

| Escenario | A: snapshot final | B: snapshot por tarea | C: núcleo transaccional real |
|---|---:|---:|---:|
| Normal | 6 | 6 | 6 |
| Interrupción antes de persistir T | 11 | 7 | 7 |
| Interrupción después de procesar T | 11 | 6 | 6 |
| Autoridad alterada | 0 | 0 | 0 |

La tabla cuenta intentos de operación observados, incluida la recuperación; el patrón fue igual para ambos programas. Las tres políticas detectaron la corrupción de outputs y el desacuerdo de autoridad. Repetir una ejecución ya cerrada produjo cero nuevas operaciones.

A y B son referencias experimentales explícitas; **ninguna representa CURRENT_QROS completo**. C usa el núcleo existente. B igualó la recuperación de C en estos casos seriales y ocupó menos bytes de artefactos. No se evaluó concurrencia, por lo que ese resultado no autoriza reemplazar el núcleo ni elegir un ganador global. El beneficio comprobado es evitar recomputación frente al snapshot final en estos fallos concretos. No identifica una mejora general de razonamiento.

PREREGISTRATION.json fija V2 y los hashes de fuentes antes de recibir los programas de los agentes. V1 aceptaba cualquier causa FAIL_CLOSED en los casos negativos; se corrigió para exigir el error esperado. PRE_MODEL_V1_SOURCE_ARCHIVE.json y los receipts iniciales conservan la evidencia previa. Ocho pruebas del contrato/corrector y siete de recuperación pasaron. Los recibos históricos de 142 métodos del núcleo conservan su alcance y no fueron reejecutados por esta entrega.

Las respuestas crudas y los programas adaptados están en sol_001/ y astra_001/. Las trazas cubren cada operación del intérprete ejecutada por los adaptadores, no las herramientas internas del agente. Las revisiones inmutables de los modelos y sus tokens no fueron expuestos. No hay evaluación sellada, recuperación del contexto LLM completo, paridad ni promoción.

Recuperación de evidencia cerrada, sin volver a ejecutar operaciones ni llamar modelos:

```bash
python3 -B -m cognitive.research.system_development.recover --directory cognitive/research/system_development/sol_001 --expected-result-sha e0448e2d5d7860fc7d475191fe32b366f046827209e2acf979b7ba7a2c25d980 --prereg cognitive/research/system_development/PREREGISTRATION.json
```

Este hash identifica el resultado cerrado de Sol y debe contrastarse con el release verificado. La recuperación comprueba bytes, programa, cobertura de escenarios, errores esperados, salidas, interrupciones y trazas. No convierte la autoridad histórica V191 en autoridad vigente. Toda ejecución nueva exige bootstrap y capacidad física nuevos. El recuperador admite recibos completos; no certifica una tanda parcial como terminada.

## Revalidación histórica tras 0.3.3

Para los resultados V2, `recover` requiere ahora `--source-archive cognitive/research/system_development/FROZEN_V2_SOURCE_ARCHIVE.json`, además del hash externo de RESULTS y la preregistración original. El archivo histórico sólo se lee como datos. La ejecución de fuentes actuales con la preregistración V2 falla deliberadamente: se requiere una nueva preregistración DEVELOPMENT, sin volver a considerar sellados los casos observados.

`run` acepta `--stop-after`, `--resume` y `--resume-sha` para el nuevo formato de episodios cerrados. Una reanudación exige autoridad fresca coherente y hashes de código actuales. El formato histórico records-only no se convierte automáticamente en evidencia reanudable.
