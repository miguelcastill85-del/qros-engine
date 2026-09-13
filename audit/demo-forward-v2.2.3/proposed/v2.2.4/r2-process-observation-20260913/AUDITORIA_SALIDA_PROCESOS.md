# Adjudicación y reparación de observación de procesos

Entrada: QROS_COMPONENT_EVIDENCE_8452e09a594e4d80bc1d5f32057bef65.zip.
SHA-256: `18aed649ebaf3eb02c4d9bc4eceb209cd079331bc34136ba80689f733cebe456`.
Siete entradas, CRC íntegro; el receipt liga exactamente el diagnóstico
`facbc5740172aa99fda4ca6909680b0962b4490bbd963031d47e2dd40647f3a7`
y lector `1f22699be0652f0d9a14f741405da44fd5c05f4a9ad6e050e84b9450daa1150b`.
Autoridad de software: `b986a9dbc74ece1ed28125355e5a52054ffb8754`, rama de hardening.

## Evidencia conservada

Windows PowerShell 5.1.22621.6133; ocho casos del lector PASS.
`stale_then_fresh_different_process` falla con WRITER_FAILED y
`two_process_exclusive_release_reacquire` con HOLDER_EXIT_FAILED.
Ambos stdout/stderr están vacíos. ready/released coinciden en RunId, token,
PID, epoch e identidad física declarada por el helper. No hay LOCK_OBSERVATION.json.

Por el flujo del código exacto, WRITER_FAILED implica que la lectura de la fila
nueva y WaitForExit ya habían terminado; HOLDER_EXIT_FAILED implica que habían
pasado las comparaciones iniciales y el intento recibió error 32. Son inferencias
del flujo, no observaciones brutas conservadas. No se elevan a fencing PASS.
La readquisición no llegó a ejecutarse: estaba después de HOLDER_EXIT_FAILED.

## Defecto demostrado y causa aún no demostrada

La prueba anterior evaluaba `$p.ExitCode -ne 0` sin guardar valor ni tipo.
Así un código no disponible y un código real no nulo compartían la misma etiqueta
de fallo. La prueba tampoco conservaba la fila nueva ni el intento de lock antes
de la comprobación de salida. Esa pérdida de información es un defecto del
diagnóstico que preparó el asistente, no evidencia contra la estrategia.

La hipótesis de ExitCode no disponible en el objeto de Start-Process es compatible
con estos archivos, pero **no está demostrada**: los códigos originales no existen
en el ZIP. No se afirma que los helpers salieron con 0 ni se cambia el FAIL histórico.

## Cambios conjuntos del componente

Se usa System.Diagnostics.Process.Start con el mismo objeto y handle desde el
inicio. No se recuperan procesos por PID. Cada observación escribe código bruto,
tipo, wait_completed, has_exited, stdout/stderr y error antes de decidir.
La lectura de streams es asíncrona para evitar bloquearse con tuberías llenas;
esperas y drenado son acotados. El validador rechaza explícitamente null, string,
booleano, código no esperado, streams sin completar y error de observación.

Los controles 0, 7 y timeout prueban el lanzador antes del escritor y lock.
El control 7 exige observar exactamente 7 y rechazarlo cuando se espera 0.
Un fallo de los controles impide lanzar las pruebas dependientes. Se conserva
la evidencia parcial antes de cada decisión y se incluyen filas y logs al fallar.
Los ocho casos nativos cerrados no se vuelven a contar como trabajo nuevo.

Se revisó el circuito completo: creación, retención del objeto, espera, streams,
tipos, controles negativos, orden de las decisiones, cleanup y ZIP. No se modifican
el lector con ocho casos aprobados, las primitivas MQL ni las fuentes del runner. Esto es un
diagnóstico de componentes, no un parche/release incremental del qualifier.

La documentación oficial exige confirmar la salida para leer ExitCode; el
handle conserva información del proceso terminado hasta cerrar el objeto.
[Process.WaitForExit](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.waitforexit?view=netframework-4.8).
La documentación respalda el diseño, no demuestra retrospectivamente el valor perdido.

## Validación y límite

Verificación ejecutada aquí: integridad de entrada, vínculo de hashes, revisión
estática del componente y reapertura/hash del ZIP entregado. Los nuevos controles
PowerShell y su mutation testing están escritos pero NO ejecutados en este Linux.
No se presenta una prueba Python equivalente como ejecución de PowerShell.
Los 44 casos offline del contrato anterior no se repiten porque no cambió.

R2 permanece NOT_QUALIFIED. Candidate3 FROZEN_CANDIDATE; CERT sin cambios;
sin acceso al terminal ni órdenes. Siguiente acción: verificar el ZIP de este
diagnóstico y su paquete exacto, adjudicar primero los controles del lanzador y
sólo después las dos pruebas pendientes. Continúan abiertos los defectos de
integración del qualifier y la captura física nativa MQL/Tester.
