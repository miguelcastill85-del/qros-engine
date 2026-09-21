# QRCEL 0.6.1 — compatibilidad de almacenamiento

Q06: el supervisor 0.6.0 limitaba cada archivo a 1 MiB, mientras el kernel admite checkpoints de hasta 4 MiB. Un plan válido de 883.579 bytes y 100 tareas provocó `disk I/O error` al crecer SQLite; quedaron 68 tareas confirmadas. El checkpoint completo mide 2.009.506 bytes en la prueba.

El entrypoint kernel usa ahora 8 MiB por archivo, compatible con el caso probado y con la rotación usual del WAL; session y verify_release conservan 1 MiB. La respuesta aceptada sigue limitada a 1 MiB. CPU, memoria, tiempo, cierre y verificación de código se conservan. Los archivos temporales stdout/stderr del hijo kernel pueden alcanzar 8 MiB cada uno: no confundir esta cota con un límite agregado de disco. No se amplían planes, operaciones ni gates científicos.

La validación incluye ejecución y restauración del plan grande en directorios/procesos nuevos, cero tareas repetidas, ancla externa e igualdad del checkpoint. Las pruebas del supervisor verifican que siguen activos cancelación, timeout, memoria y rechazo de salida excesiva. Las pruebas sintéticas no certifican fallos eléctricos físicos ni rendimiento de backtesting.

Q07 sigue abierto: cuatro escritores concurrentes pueden agotar los 2 s de espera de SQLite. Se conservaron 100 resultados exactos y 200 eventos; se validó un reintento después de liberar el bloqueo, sin repetir tareas. Usar una única invocación escritora por run. Esta regla documental no implementa un coordinador distribuido, una cola justa ni reintentos automáticos.

Se preservan los recibos históricos y las cinco barreras de evaluación completa. El kernel y sus hashes de identidad no cambian; aun así, cualquier recuperación debe comprobar sus bindings y anclas. QRCEL continúa experimental y sin promoción científica.
