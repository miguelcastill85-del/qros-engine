# QRCEL — investigación arquitectónica, DEVELOPMENT v1

Se ha ejecutado un experimento de **mecanismos de continuidad**, previo a cualquier selección de la arquitectura cognitiva completa. Se precisa la ontología de 24 capacidades y se entrega un conjunto de 12 microcasos DEVELOPMENT con scorer determinista. No se realizaron llamadas a Sol/Astra.

## Resultado experimental

Las variantes usan el mismo cálculo sintético, las mismas identidades y la misma batería. El worker calcula por recurrencia; el scorer usa una fórmula cerrada independiente. Cada interrupción termina un proceso con `os._exit(75)` y la reanudación ocurre en un proceso nuevo.

| Escenario | Reiniciar todo | JSON atómico por nodo | Transacción SQLite por nodo |
|---|---:|---:|---:|
| Sin fallo: cálculos | 48 | 48 | 48 |
| Interrupción después del nodo 16: cálculos totales | 64 | 48 | 48 |
| Interrupción antes de confirmar nodo 16: cálculos totales | 64 | 49 | 49 |
| Output durable alterado | Rechazado | Rechazado | Rechazado |
| Input cambiado | Rechazado | Rechazado | Rechazado |
| Confirmaciones de resultados, sin fallo | 1 | 48 | 48 |
| Bytes de artefactos al finalizar, sin fallo | 6.337 | 7.230 | 14.571 |

Los 15 pares escenario-variante dieron el resultado esperado. Estos son 15 casos de software, no familias independientes para inferencia estadística. `commit_count` cuenta confirmaciones lógicas de resultados; excluye schema/metadatos de SQLite, logs instrumentales y publicación de output final. Los bytes incluyen spec, logs y outputs. Los tiempos son mediciones de una sola repetición, dominadas por el proceso/I/O/instrumentación; no sirven para declarar que un backend sea más rápido.

**Conclusión acotada:** en este trabajo, guardar progreso por nodo evita repetir entre 15 y 16 cálculos ante la interrupción probada, a cambio de más confirmaciones. JSON y SQLite empatan en corrección y recomputación. No se ha demostrado un ganador general ni se ha elegido el Minimum Viable Cognitive Stack completo. La omisión de checkpoints intermedios está representada por REPLAY_ALL; una ablation controlada adicional del stack cognitivo sigue pendiente.

Fuentes: `continuity_development/PREREGISTRATION.json` y `continuity_development/run_001/RESULTS.json`. La preregistración se escribió antes de observar resultados y el receipt liga sus bytes y ambos programas por SHA-256. No se cambió ningún gate de trading.

Reproducir en Linux con Python y biblioteca estándar, desde el repositorio:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 cognitive/research/continuity_development/run.py --output cognitive/research/continuity_development/review_run_001
```

El directorio debe ser nuevo. Los workers sólo se ejecutan sobre directorios temporales creados por el harness y datos sintéticos. El script no es un dispatcher QROS ni una implementación endurecida para producción. No cubre fallos eléctricos, corrupción rehasheada por un host, múltiples escritores, red, exactly-once remoto, todos los puntos de interrupción ni DAGs arbitrarios. Un output anterior conservado tras un rechazo no debe reutilizarse por su mera existencia; el consumidor debe comprobar el resultado y la identidad de la ejecución.

## Ontología y arquitecturas completas

`CAPABILITY_ONTOLOGY_v2.json` define observables y límites por capacidad. Las diferencias empíricas Astra–Sol siguen nulas/desconocidas. `ARCHITECTURE_REVIEW_v2.json` conserva cuatro alternativas: orquestador único, especialistas, grafo transaccional y núcleo mínimo sobre QROS. Propone fusionar roles sólo como hipótesis hasta ablation.

No se declara `COGNITIVE_ONTOLOGY_FROZEN` ni `RISE_FIXED_POINT`: hay dos revisiones de método diferente con hallazgos, no dos rondas completas con delta cero. La suficiencia de la ontología, el alcance legacy de autoridad y la independencia de evaluación siguen abiertos. Los tres mecanismos medidos son componentes posibles de esas alternativas; no sustituyen la comparación de tres stacks LLM completos.

## Benchmark de modelos preparado

`model_development/CASES.json` contiene 12 microcasos expuestos; cubren propiedades puntuales de recuperación, dependencias, evidencia, causalidad, cálculo, debugging, herramientas, continuidad y contradicciones. No son una medida completa de razonamiento, programación o investigación abierta. El scorer recibió tres pruebas de software con fixtures y todas pasaron.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 cognitive/research/model_development/score.py --responses respuestas.json
```

Formato de respuesta: objeto JSON indexado por DEV-01..DEV-12, con las claves que solicita cada caso. El scorer conserva casos omitidos como incorrectos, distingue booleanos de enteros y rechaza IDs desconocidos o duplicados. No ejecuta código ni deduce que un modelo respondió por recibir un archivo: siempre etiqueta `SUBMITTED_BYTES_ONLY`, `model_execution_verified=false` y `INSUFFICIENT_EVIDENCE`.

`EXECUTION_PROTOCOL.json` conserva los tracks NATIVE/SYSTEM, condiciones emparejadas, identidad observable y el requisito de evidencia real del proveedor. No se ha configurado ni activado una API de pago o un runner de modelos. Los campos desconocidos deben quedar null. No hay casos VALIDATION/SEALED ni custodio aislado en esta entrega.

## Próxima etapa

Resolver la suficiencia y las interfaces de la ontología antes de elegir arquitectura final; materializar un ejecutor de modelos bajo los recursos autorizados, con referencias/scorer separados; obtener respuestas DEVELOPMENT observadas en condiciones comparables y después fijar validación/sellado. Preservar la autoridad V189 hasta una transición autorizada real. El trabajo científico, los holdouts y el PR de reparaciones #15 permanecen separados de esta rama de investigación.
