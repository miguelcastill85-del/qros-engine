# Ensayo DEVELOPMENT observado: Sol y Astra

Se lanzaron dos subagentes con las rutas solicitadas gpt-5.6-sol y gpt-6-astra, esfuerzo medium e historial no heredado. Recibieron el mismo paquete de 12 microcasos sin las respuestas esperadas. Los dos finalizaron; sus respuestas se conservan literalmente y el corrector congelado las puntuó por igualdad JSON tipada.

| Ruta solicitada | Aciertos | Fallos críticos del corrector |
|---|---:|---:|
| gpt-5.6-sol | 12/12 | 0 |
| gpt-6-astra | 12/12 | 0 |

Las respuestas son idénticas. Esto cierra el ensayo básico del pipeline; el efecto techo impide separar capacidad. No se compararon SOL_CURRENT_QROS ni SOL_QRCEL y no se midió ganancia de arquitectura.

La interfaz confirmó dos tareas finalizadas; no expuso snapshot interno del modelo, tokens, tiempo comparable ni una traza independiente de herramientas. Los modelos fueron instruidos a no usar herramientas, pero eso no equivale a aislamiento impuesto por el host. Se registra la ruta solicitada separadamente de la identidad interna desconocida. No se calcula significancia o no-inferioridad con un batch por ruta.

Los doce casos ya eran DEVELOPMENT_EXPOSED. Sus eventos de exposición quedan ligados a QRCEL_ROOT para toda la genealogía declarada. Ninguno puede reutilizarse como sealed. El scorer sigue etiquetando su resultado como submitted-bytes-only; el recibo de colaboración documenta aparte la ejecución realmente observada, sin modificar el scorer para que certifique modelos.

`NEXT_BENCHMARK_DESIGN.json` describe las familias de tareas y los controles que faltan para una evaluación informativa. Paridad: INSUFFICIENT_EVIDENCE; promoción QRCEL: no autorizada por este ensayo.
