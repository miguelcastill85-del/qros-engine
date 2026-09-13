# Continuación desde la recuperación del PC

R2 sigue sin calificar. El bloqueo por fuentes ausentes queda resuelto; el acceso nativo a Windows/MT5 sigue sin estar disponible. Candidate3 permanece congelado, sin cambios ni ejecución. No se ha leído ni modificado CERT en el PC: mantenerlo en 0 sigue siendo requisito.

## Autoridad recuperada

Base remota inspeccionada: `082ae2a5153c226739ae78ed491d8ed4a0b35baa`, exclusivamente en `fix/demo-forward-v2.2.4-hardening-20260907`. No se modifica main ni la evidencia histórica.

Archivo `QROS_RECUPERACION_20260913_013208_b5666249.zip`, SHA-256 `c7cc89e75276fedaf565cdae16a13538cab52046774e02b9904e654162b8502c`: 2.745 miembros y 405.195.615 bytes expandidos. Los 2.739 registros inventariados coinciden en tamaño y SHA-256. La verificación ha leído bytes para hashing, sin analizar resultados económicos ni abrir una nueva investigación.

Paquetes anidados verificados: R2 8/8 entradas y R2T 6/6 entradas. Las fuentes exactas necesarias están preservadas en `sources/`; identidades en `SOURCE_INTEGRITY.json`. No se suben al repositorio el ZIP privado completo, credenciales, datos de broker ni logs de cuenta.

El runner recuperado coincide con `17be652ebb5c3745590ceae798a02d136285a2c8dc1c3645f2be578dfa8d8375`. R2 PS1 coincide con `a58de18704ad76c3dce4e09950170462d4bc82442660203b4b8741a840b96f96` y MQL5 con `45cad9f9a3fb7a13b032fde417f7cdaa9abf342cb8706545f9c6354a18831347`.

## Qué demuestra ahora la evidencia

El archivo inventariado `000069_QROS_R2_r2_20260911_234345_12b72981_FENCE_RESULTS.csv` contiene `R2_FENCE_PROBE,FAIL,SECOND_LOCK_ACQUIRED`, modo Tester=1 y build 6182. Ya no falta el resultado del probe. No contiene tiempos de adquisición/liberación ni identidad física: sigue sin demostrar dos aperturas simultáneas sobre el mismo objeto.

El R2T posterior registra `SECOND_LOCK_DENIED`, error MQL 5004, modo Tester=0, build 6182 y rutas common iguales. `R2T_RELEASED.csv` y HOLDER_READY tienen el token coincidente 481523873744556. El receipt termina `REACQUIRE_FAIL`, código 55, ejecución `20260912_021919_d7245a9c`. No hay un resultado de readquisición capturado que permita atribuir ese FAIL a una apertura denegada.

**Defecto demostrado en el lector:** `First` invoca una sola vez `Read-Rows`. Éste devuelve el primer snapshot legible; si contiene una fila de otra etapa, First devuelve null inmediatamente. El probe y la readquisición reutilizan `IsoB/MQL5/Files/<Prefix>_RESULT.csv`. Por ello el lector puede encontrar el PASS antiguo del probe antes de que arranque el nuevo EA, devolver null y disparar código 55 sin esperar los 60 segundos. La misma falla alcanza las etapas de restart que reutilizan RESULT.csv.

La reproducción determinista demuestra ese camino de fallo sobre el flujo de la fuente exacta. **No demuestra que fuera el único motivo del fallo histórico:** el log y el snapshot del instante de readquisición faltan. No se inventan timestamps, PID, handles ni resultados nativos.

## Genealogía y supuestos corregidos

Se conserva la genealogía documental v1.4 → v1.5 → v1.6 → RQS → R2 del suplemento `r2-autonomous-audit-20260913/AUDITORIA_RAIZ.md`, sin reescribirla. Esta recuperación completa las fuentes R2 y R2T; no convierte retrospectivamente los resúmenes de v1.4–v1.6 en una comparación completa de sus bytes.

* R2 recuperado usa GetTickCount64 y OnTimer, **no Sleep**. No atribuir este fallo a Sleep del Tester. El cierre por OnDeinit antes del plazo sigue siendo hipótesis pendiente de traza.
* CSV legible no significa resultado de la etapa esperada. El timeout anterior protegía la apertura, no la llegada del resultado.
* Cualquier FileOpen fallido no demuestra exclusión mutua. Error MQL 5004 no sustituye la clasificación externa de sharing violation.
* common_path igual, READY y proceso vivo no prueban identidad física ni continuidad del handle.
* El PASS estático R2T histórico 15/15 y 14/14 mutaciones no cubre estos defectos. No se ha recuperado su generador como para recalcular ese score.

## Corrección y validación realizadas

`Wait-QrosStageRow.ps1` implementa un lector independiente: espera la etapa solicitada, usa un único plazo monotónico, limita bytes, cierra siempre el handle, rechaza duplicados y vínculos esperados incorrectos, y devuelve un FAIL auténtico inmediatamente. No transforma FAIL en PASS. Dot-sourcing sólo define la función; no inicia terminales ni cambia configuraciones.

Es un **componente de ingeniería, no una release del qualifier**. No está integrado en el lanzador porque persisten otros defectos del ledger. Los CSV históricos no contienen todos los vínculos que el nuevo lector puede exigir; la corrección completa necesita también instrumentar el productor y separar archivos por etapa/nonce. Una lectura correcta por sí sola tampoco demuestra autenticidad del productor.

`reproduce_stage_race.py`: falso negativo reproducido y 12/12 regresiones del modelo Python aprobadas. Incluye evidencia vieja, snapshot vacío, resultado retrasado, FAIL auténtico, timeout, duplicados, RunId/PID/token incorrectos y status inválido. Esto no es ejecución PowerShell ni mutation score de R2.

`Test-WaitQrosStageRow.ps1`: seis pruebas nativas preparadas, incluida escritura retrasada desde otro proceso PowerShell. **No ejecutadas**: este host es Linux y no dispone de pwsh ni Wine; tampoco existe acceso de ejecución al Windows del usuario. No se instala infraestructura ni se activa gasto.

El preflight histórico `handoff/verify_import.py` se intentó: falla porque esta materialización parcial no incluye HANDOFF_MANIFEST.sha256. No demuestra corrupción del repositorio. No se toca el motor, baseline, código científico ni archivos existentes.

## Auditoría integral y pruebas pendientes

El ledger registra 12 hallazgos con raíz, detector, caso negativo, regresión, arreglo y evidencia. Además del lector: clasificación del fallo de apertura; identidad física; prefijos de rutas; errores de cierre ignorados; compilador sin deadline; contenido de clones; empaquetado antes de cleanup; vinculación del productor; cadena SHA; cierre temprano del Tester; escritura del token sin comprobación completa.

No se declara fixed point: faltan implementación consolidada y pruebas nativas de esos contratos. No se genera una sucesión v1.1/v1.2 para ir descubriendo síntomas en el PC.

La matriz A–G del suplemento anterior sigue vigente. Debe cruzar PS→PS, PS→Tester, Tester→PS, Tester→Tester y terminal normal→terminal normal con objeto físico, identidad de proceso y periodo real de ownership. Rechazar las doce mutaciones exigidas por el usuario sigue siendo obligatorio en el **validador nativo**, no sólo en un transcript sintético.

No hay evidencia suficiente para sustituir FILE_COMMON en Candidate3. Se mantiene la evaluación previa de archivo exclusivo, mutex, creación atómica y guard con token/epoch/heartbeat; cualquier cambio de producción exige demostrar la necesidad y repetir los gates afectados.

Referencias primarias verificadas: [FileOpen](https://www.mql5.com/en/docs/files/fileopen), [GetTickCount64](https://www.mql5.com/en/docs/common/gettickcount64), [TerminalInfoString](https://www.mql5.com/en/docs/check/terminalinfostring). Describen las APIs; no certifican el comportamiento de este host ni sustituyen la evidencia nativa.

## Estado y siguiente acción

Estado: `BLOCKED_BY_INFRASTRUCTURE` para calificación nativa. Recuperación de fuentes completada; defecto de lectura demostrado; componente corregido pendiente de prueba nativa e integración consolidada. R2 histórico FAIL, R2T histórico FAIL, R2 actual no ejecutado. Fingerprint no certificado. R3/R4 bloqueados.

Siguiente trabajo: cerrar la implementación consolidada del ledger, validar el lector y el validador en Windows, instrumentar identidad física y ownership, y ejecutar R2 completo en clones aislados 6182 sin Candidate3. Sólo entonces puede promoverse el SHA exacto del runner. No despliegue, CERT, live ni órdenes. No se afirma trabajo en segundo plano.
