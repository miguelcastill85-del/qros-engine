# G12 — recuperación del cliente, 2026-10-03

Autoridad inicial: 0055c99aad927d7c847c662240f5db4f044f4825, PR 78.
VERIFICADO: CI 37070189148 completó exitosamente sobre esa fuente. No repetir los gates previos.

## Corrección propuesta y gate reproducible
- Serializar inicialización, enrollment, renovación, ensureAccess y cierre: evita consumir dos veces el refresh y resucitar una sesión después del cierre.
- Guardar request_id y vínculo cliente/origen/universo antes de enviar createJob; recuperarlo al reintentar después de reiniciar.
- Serializar operaciones de jobs; preservar datos ilegibles; impedir sustitución de job/input o retroceso de fase en sync/resume.
- Verificar fase/progreso, vínculo de resultado y SHA-256 recalculado en Dart. Fixture calculado por Python: 582e593602593454d76ac3a5a911ac6c69deecbbefb0e279dcd6325f2dfa2b18.
- Cierre de sesión informa fallo de almacenamiento y libera la interfaz en finally; pantalla lee el estado vigente dentro del listener.

CI debe primero reproducir cuatro fallos en el padre con las nuevas regresiones y después aprobar todos los tests contra la corrección. Estado al commit de implementación: PENDIENTE_CI, no promoción.
El hash G12 detecta corrupción y enlaza el resultado; no prueba identidad independiente ni sustituye la firma G9.
Una pérdida de respuesta durante rotación de refresh aún requiere recuperación/revinculación; no afirmar renovación infalible ante crash.
El app sigue TEST_ONLY, debug, sin piloto G12 físico ni despliegue G12 público.
Próxima acción exacta: verificar CI de este commit, descargar el artefacto, cotejar SHA/bytes con el recibo y persistir resultado antes de preparar despliegue.
MOBILE_PRODUCT_HEAD y main científico no se modifican. economic_tests=0; holdout/GA2/MT5/live cerrados.

Revisión previa al gate: un trabajo anterior no puede borrar el request_id pendiente de otro universo. Se añade una cuarta regresión. Se conserva el intento inicial de CI 37125776941.

Incidente VERIFICADO: CI 37125776941 reprodujo tres fallos del padre y se detuvo en flutter analyze por tres avisos de interpolación en las pruebas nuevas. Se corrigen las expresiones, sin desactivar el analizador ni reducir gates.
