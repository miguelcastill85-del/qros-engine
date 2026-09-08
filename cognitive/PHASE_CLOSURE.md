# Cierre de la fase de reparaciones validadas

**Resultado: REPAIR_PHASE_COMPLETE — versión 0.2.1, candidata para revisión.**

Se cerró la implementación y verificación de las reparaciones locales aceptadas después de la auditoría. El proyecto QRCEL completo continúa como hipótesis de investigación: este cierre no certifica una ontología completa, RISE_FIXED_POINT, integración científica, paridad de modelos o promoción. El alcance es software determinista opt-in y shadow de lectura.

## Evidencia final

| Comprobación | Observación y alcance |
|---|---|
| Batería final | 86 métodos aprobados: 60 del candidato y 26 existentes |
| Comparación original | 8/8 casos DEVELOPMENT conservan el comportamiento esperado |
| Grafo de dependencias | 200 grafos con semilla fija contrastados con cierre transitivo independiente; incluidos en un método de prueba |
| Recuperación limpia | 64 archivos originales contrastados con blobs del repositorio; no requiere restauraciones de otro chat |
| Preservación | 62 archivos protegidos presentes en esa copia permanecen idénticos |
| Shadow | Manifest V189 y tres delegados inspeccionados; siguiente item = preflight sin dispatch |
| Integridad de entrega | Verificador nuevo exige ancla externa, hashes, scope cognitive y ausencia de código Python no listado |
| Código y resultados | Commit Git + manifest y receipts; originales congelados conservados |

La fuente de cada resultado es `cognitive/checkpoints/clean_recovery_021/`. Los casos nuevos cubren la alteración de objetos de observación y la integridad del paquete. No se presentan como benchmark de Sol o Astra. El scope de tests no incluye toda la batería C++/MT5 ni datos económicos del repositorio.

## Última corrección: F12

La versión 0.2.0 permitía construir un `AuthorityObservation` modificado y obtener un recibo PASS sin revalidar sus bytes. El caso está preservado en `checkpoints/closure_baseline/OBSERVED_FAILURE.json`. Ahora ambos consumidores (`authority_receipt`, `inspect_active_queue`) vuelven a comprobar manifest y delegados mediante el mismo validador, evitando duplicar reglas.

Un objeto Python nunca representa por sí mismo una prueba de autenticación. El ancla sigue siendo responsabilidad del host, recuperada por el canal autorizado. No es una defensa frente a un host arbitrario que cambie también código y anclas.

## Uso operacional que queda habilitado

1. Recuperar un checkout verificado de la versión candidata y obtener por separado el blob de `cognitive/COGNITIVE_MANIFEST.json` en su commit.
2. Ejecutar `python3 -m cognitive.verify_release --repo-root . --manifest-blob <BLOB_COGNITIVE_MANIFEST>` desde código previamente confiable.
3. Recuperar la autoridad científica vigente por su ruta autorizada y suministrar su blob explícito a `cognitive.shadow`.
4. Usar los inspectores como apoyo de lectura, y repetir la validación del candidato cuando cambien fuentes, runtime o contrato.

El verificador de integridad no ejecuta tests ni hereda capacidad. Tampoco puede establecer su propia confianza antes de ser ejecutado: el checkout y su entrypoint deben verificarse externamente. `verify_checkpoint` exige los nuevos argumentos de 0.2.0; ver README. No se instala un servicio, scheduler, agente de fondo ni consumidor científico automático.

## Integración y rollback

La entrega se prepara como PR borrador. El marcador `[skip ci]` evita activar el workflow de investigación que actualmente escucha pull_request. No se modifica dicho workflow ni se presenta CI omitido como aprobado. La semántica del marcador está documentada por [GitHub](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs). Cualquier gate de merge requerido sigue pendiente hasta ejecutarse de forma autorizada.

Rollback del candidato: volver al commit `1635b8a8fa6ffeab76d26290eefbd40611ea1a45` (0.2.0), o dejar de importar el paquete. El sistema científico actual conserva su baseline `c43176df7713f5833b48589a0e86d2ae63ac6700`; no requiere migración inversa.

## Trabajo distinto que sigue pendiente

Para adoptar QRCEL como capa científica falta resolver el alcance legacy del bootstrap, delegar los contratos de evidencia mediante la autoridad existente, adaptar los schemas históricos, cerrar la ontología/RISE completos y ejecutar los tracks NATIVE/SYSTEM con validación y evaluación selladas, shadow operacional y canary. Ninguna de estas exigencias se reemplaza por 86 tests de software. La arquitectura y la paridad continúan con `INSUFFICIENT_EVIDENCE`.
