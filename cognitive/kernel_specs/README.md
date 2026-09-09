> Actualización 0.3.1: el bloqueo V190 descrito abajo fue reconciliado en V191 y sus recibos se conservan. Para la entrega actual, consultar ../releases/0.3.1/README.md. El ejemplo 0.3.0 siguiente permanece histórico.

> Final readback: main advanced to V190 and its frozen official validator returned AUTH_SOURCE_MISMATCH:head:None. Current integration is FAIL_CLOSED. The CLI example below belongs to historical engineering commit 70e7ecabe4e96eaa68dfc70430672e66feb720f9 and V189; its manifest anchor must not be reused for this updated delivery or current QROS authority. See ../checkpoints/authority_drift_v190/CHECKPOINT.json.

# Núcleo local QRCEL 0.3.0 — alcance implementado

Este núcleo ejecuta planes JSON explícitos con dos operaciones permitidas: `EXACT_SUM` y `CHECK_DAG`. Aporta coordinación local, verificación y continuidad a un host que ya pueda formular las tareas. No contiene un solver LLM, no opera estrategias ni selecciona la arquitectura cognitiva final.

## Flujo implementado

El CLI verifica la integridad del paquete mediante un blob externo, valida el plan y sus inputs, observa el manifest científico y sus tres delegados y recomputa una capacidad local de SQLite. La ejecución se liga al hash canónico del plan, las fuentes del núcleo/validador y el manifest científico observado. Un cambio de identidad exige un nuevo run; no se reutilizan silenciosamente resultados.

Para cada tarea: comprobar padres y autoridad; clasificar profundidad; resolver la operación; verificar según nivel; confirmar juntos output, evidencia y evento COMPLETE en una transacción SQLite. Las tareas completadas se reutilizan sólo tras validar su integridad y su correspondencia con el ledger. El kernel continúa con tareas independientes cuando una operación devuelve un error; conserva ERROR/UNFIXED y bloquea sus descendientes. Un error determinista ya registrado no se reintenta silenciosamente con el mismo plan/código.

El checkpoint exporta plan, task graph, evidence graph y ledger encadenado por hashes. Es un derivado rematerializable de la base local; SQLite contiene el estado operacional del run, nunca autoridad científica. No hay punteros desde HEAD/STATE/RUN_QUEUE hacia esta base.

| Nivel | Comportamiento del núcleo |
|---|---|
| L0 | Operación determinista y comprobación mínima; claim SUPPORTED |
| L1 | Solver y verificador de representación/algoritmo distinto; claim acotado VERIFIED |
| L2 | Lo anterior más falsificador acotado: eliminación de cada operando o autociclo en cada nodo |
| L3 | BLOCKED: no hay autorización de ejecución científica en este núcleo |

La suma se resuelve con Fraction y se contrasta mediante enteros y denominador común. El DAG usa el Kahn existente y se contrasta mediante DFS. Esto es independencia de métodos para esas propiedades; no implica independencia LLM ni un RISE completo. Un dominio vacío no obtiene un PASS de falsificación L2.

## Uso

Desde un checkout confiable de esta versión, recuperar por el canal autorizado el blob de `cognitive/COGNITIVE_MANIFEST.json` y el de la autoridad científica vigente. El primero verifica el paquete; el segundo verifica la autoridad observada. No derivarlos de archivos no confiables que se pretenda autenticar.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m cognitive.kernel \
  --repo-root . \
  --release-blob BLOB_DEL_MANIFEST_COGNITIVE_VERIFICADO \
  --authority-blob BLOB_DEL_MANIFEST_CIENTIFICO_VERIFICADO \
  --plan cognitive/kernel_specs/EXAMPLE_PLAN.json \
  --plan-sha256 SHA256_CANONICO_DEL_PLAN_VERIFICADO \
  --run-id ejemplo_001
```

El plan se hashea con `runtime.canonical(plan)` (JSON ordenado, separadores compactos y newline), según DATA_CONTRACTS. Los valores de la ejecución de ejemplo se guardan con sus receipts; no copiar el epoch de un chat anterior para una sesión científica nueva.

Repetir la llamada con el mismo run-id y mismas identidades verifica y reanuda; no repite tareas confirmadas. Cada proceso nuevo genera y observa su propia capacidad. Los archivos operacionales quedan bajo `cognitive/runs/<run-id>/`, excluidos de Git. Exportar el checkpoint y su SHA a un soporte durable autorizado antes de perder el runtime; no basta con conservar la ruta temporal.

Restaurar en un run-id vacío agregando `--restore CHECKPOINT_JSON --checkpoint-sha256 SHA_VERIFICADO`. Deben coincidir plan, fuentes y autoridad. La restauración es atómica; un checkpoint inconsistente deja el destino sin tareas restauradas. No sobrescribe runs con progreso válido. El siguiente run reconstruye el estado exclusivamente de estos artefactos y las identidades requeridas, sin memoria conversacional.

## Límites y riesgo residual

- Los inputs son JSON del plan; no hay lectura de PnL, shell, red ni API de modelos. La etiqueta NON_SCIENTIFIC_LOCAL no detecta por sí sola el significado económico de números suministrados por un host; la frontera aquí es ausencia de efectos científicos y accesos externos.
- La clasificación usa riesgo congelado por el host. No hay clasificador semántico que descubra automáticamente si el host etiquetó mal la tarea.
- Los hashes detectan corrupción y contradicciones respecto de anclas confiables. No protegen frente a un host malicioso que pueda sustituir simultáneamente código, base y anclas. El directorio del run debe pertenecer a un host confiable; el chequeo de symlinks no es un sandbox contra modificaciones hostiles concurrentes del filesystem.
- SQLite serializa escritores cooperativos del mismo run. La atomicidad probada es local. No se ofrecen garantías de exactly-once para herramientas o servicios remotos; no hay ejecución remota en esta versión.
- El checkpoint es una instantánea verificable. No se garantiza que se pueda escribir antes de toda terminación involuntaria: ante crash se recupera la transacción local ya confirmada; ante pérdida total del disco se necesita el checkpoint persistido previamente.
- Cualquier claim VERIFIED se limita a la operación exacta y los inputs ligados. No verifica la redacción libre del objetivo ni promociona evidencia científica.
- Se mantienen límites de tamaño, tareas, operandos, fracciones y eventos. Alcanzarlos bloquea la operación; no altera el problema ni declara rechazo científico.
- No se certifican ontología completa, RISE_FIXED_POINT, calidad del razonamiento nativo, paridad Sol–Astra, promoción científica ni funcionamiento en segundo plano.

## Integración y rollback

Se reutilizan los inspectores existentes, el DAG y el manifest científico. El backend SQLite se usa como experimento operacional reversible porque ambos mecanismos de checkpoint pasaron el piloto; no se declara ganador general frente a JSON ni se reemplazan los controladores QROS congelados. Cambiar de backend exige migración explícita y pruebas.

No hay integración automática con las campañas. Para revertir, dejar de usar `cognitive.kernel` o volver al commit padre de esta entrega; los artefactos científicos permanecen válidos. Los runs de distintas fuentes no se migran silenciosamente. Las acciones adicionales y los adapters científicos siguen requiriendo contratos/gates reales.
