# Auditoría autónoma R2 — 2026-09-13

**Decisión: BLOCKED_BY_INFRASTRUCTURE. R2 no calificado.**

Candidate3 continúa `FROZEN_CANDIDATE`; su ejecución, CERT, deployment y live permanecen prohibidos. Esta intervención no conectó con el PC, no ejecutó Candidate3, no inició MT5 y no envió órdenes. `QDB1.EXEC.CERT=0` se conserva como requisito; no se afirma haber leído su valor actual en el PC.

Repositorio `miguelcastill85-del/qros-engine`, exclusivamente rama `fix/demo-forward-v2.2.4-hardening-20260907`. Base inspeccionada: `eede23ec274abf27a667e1f9cad1ad226cf05444`; árbol `1a2d1558f03180c2d8a9789eaf1cf1b2b28b6ba5`. Los nuevos archivos son un suplemento de auditoría y un contrato ejecutable offline. No son una nueva release del qualifier ni un reemplazo del runner.

## Conclusión causal y límites

La causa física exacta de `FENCE_SECOND_EXECUTOR_NOT_DENIED` **no está demostrada**. Lo demostrado en las fuentes recuperadas es un conflicto de adjudicación y una brecha de evidencia: el recibo `QROS_RUNNER_R2_NATIVE_ENV_ADJUDICATION_v1.json` afirma que la primitiva no fue exclusiva; `R2_NATIVE_ENV_EVIDENCE_ADJUDICATION_20260911.json` reconoce que el archivo de fallo no contiene HOLDER_READY, resultado del probe, release ni logs del Tester y que el código 52 también puede representar evidencia ausente/ilegible. Son proposiciones con distinto alcance, no equivalentes.

Por ello se retira **como inferencia válida para esta auditoría** la afirmación de que hubo dos aperturas simultáneas del mismo recurso físico. Los recibos históricos se preservan íntegros. Tampoco se afirma que el holder terminó prematuramente: es una hipótesis plausible, no una observación recuperada. No está demostrado un defecto de Candidate3 ni la necesidad de sustituir FILE_COMMON en producción.

El ZIP nativo original y los fuentes del qualifier no están materializados; sus hashes se conocen por la instrucción del usuario y por recibos coincidentes, pero **no se verificaron contra sus bytes**. Esto impide reconstruir el orden real de adquisición/intento/liberación y auditar íntegramente el qualifier. La genealogía siguiente es exacta en identidades documentales recuperadas, no una comparación byte a byte de fuentes ausentes.

## Genealogía documental anterior a cualquier nuevo código

| Etapa | Identidad documentada | Supuesto o defecto consignado | Límite de la evidencia |
|---|---|---|---|
| v1.4 | Paquete `aa27dbff716ec9a8dc44c0c4c183299accdb6fb97e1c0dae50e2ecb7b3f34bac`; evidencia `bf74d91575dd8d69a02e84343e99c8510e1b0ee26b7f4cfa3d35787ad89c261e` | Sustituye esperar la salida de GUI por archivos; holder usa Sleep(90000) en Tester. READY no demuestra handle abierto 90 segundos reales. | Adjudicación y prerregistro recuperados; paquete/harness no recuperados. |
| v1.5 | Paquete `5206cd5c599eef19fb73dfa7924d3aee07149f139eb4ceb3079d94b6203326da`; harness `a482d3305336756c1bb3ef4d7fe6efd7a9e0c11bc6c8ef2ea710c0cc6237aa37` | Cambia a GetTickCount64, 120000 ms. El registro de captura informa exclusión y luego IOException al leer el CSV todavía abierto. | Captura descrita en recibo, no observada de nuevo; no certifica identidad física ni ciclo completo. |
| v1.6 | Paquete `f87ca7c67be2f3625e55e0aeb16abea4d7a76ecd5d98a234973e51f5a6427b3d`; harness `f140a1019b4539e9df819c26f2144d26ad27b0714230a9d0fdb6739d9b50f5c3` | Cerrar RESULTS y publicar RELEASED. Auditoría posterior detecta nombres compartidos, lectura prematura, copias sin cierre y excepciones sin recibo. Se ordena no ejecutar v1.6. | Registro `RUNNER_FIXED_POINT_AUDIT_v1.json`; no fuentes v1.6. |
| RQS / v2 | D01–D10 y separación R0/R1/R2/R3/R4; después D11–D13 | Un PASS estático no prueba Windows/MT5; `.Count`, mutaciones con alias y guardas de procesos requieren pruebas propias. | Gate histórico v1.1 recuperado y ejecutado sobre strings sintéticos. Gate más reciente no recuperado. |
| R1 candidato | Runner v2.2_R1CANDIDATE `17be652ebb5c3745590ceae798a02d136285a2c8dc1c3645f2be578dfa8d8375` | Registro 13/13 + 10/10; Candidate execution false. | SHA declarado, runner exacto no recuperado. |
| R2 v1 FINAL | ZIP `a4dd75c13432ac0f423301e645a9acf3f1d07a4be7c95e9a0a6aa182e0b89bdd`; PS1 `a58de18704ad76c3dce4e09950170462d4bc82442660203b4b8741a840b96f96`; MQL5 `45cad9f9a3fb7a13b032fde417f7cdaa9abf342cb8706545f9c6354a18831347` | 15/15 + 11/11 y pre-delivery 19/19 no detectan toda la ambigüedad nativa. Fallo 52. | Fuentes y ZIP de evidencia ausentes de las superficies recuperables. |
| R2T posterior | ZIP declarado `f65ca9bc2d362ac0ba193e304f2552537b880d5699a3e648e03b7c9c6054fc1b` | Propone terminales normales; su regla “segundo adquirió ⇒ defecto real” todavía necesita mismo recurso físico y ownership simultáneo. | Sólo especificación, reporte estático y post-build; ni fuente ni ejecución nativa recuperadas. No se adopta como solución ya probada. |

Los commits que introdujeron esos registros constan en `SOURCE_SCOPE.json`. No se reutilizaron los resultados históricos de Candidate3 como prueba nueva ni se ejecutó R4.

## Semántica contrastada con fuentes primarias

MetaQuotes documenta un sandbox propio por agente; también documenta expresamente el uso de FILE_COMMON para interacción entre **agentes locales** y terminal. Por tanto, sandbox individual no implica que FILE_COMMON necesariamente apunte a archivos diferentes. `Sleep()` avanza tiempo simulado en Tester; GetTickCount64 mide tiempo transcurrido del sistema, pero una comprobación en eventos no mantiene por sí sola el EA vivo hasta el siguiente evento. [Tester y carpeta compartida](https://www.mql5.com/en/docs/runtime/testing), [GetTickCount64](https://www.mql5.com/en/docs/common/gettickcount64).

Sin FILE_COMMON, FileOpen opera bajo MQL5/Files del terminal o agente; con FILE_COMMON usa la carpeta común. La ruta se obtiene de TERMINAL_COMMONDATA_PATH, agregando Files y el nombre relativo. Es una ruta inferida hasta corroborar el objeto abierto. TERMINAL_PATH, TERMINAL_DATA_PATH y el modo portable no sustituyen esa medición. [FileOpen](https://www.mql5.com/en/docs/files/fileopen), [propiedades del terminal](https://www.mql5.com/en/docs/constants/environment_state/terminalstatus).

En Windows, aperturas de datos incompatibles con el share mode vigente deben fallar con ERROR_SHARING_VIOLATION (32). Acceso a atributos no equivale a una segunda apertura READ/WRITE: puede permitirse aunque ésta esté denegada. La observación externa debe registrar ambos parámetros. Un PID o path textual no identifica por sí solo el recurso; contrastar identidad de archivo por volumen/file ID y resolver alias/reparse points, conservando identidad del proceso y hora de creación. [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew), [identidad por handle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileinformationbyhandle).

## Matriz experimental discriminante — pendiente de Windows

Ninguna fila se marca ejecutada. Repetir el mismo protocolo con PS→PS, PS→Tester, Tester→PS, Tester A→Tester B, terminal normal A→B y A→Tester B. Sólo agentes locales identificados; nunca cloud ni remotos. Intercambiar holder/probe y repetir con identidades de ejecución nuevas. Timeout finito produce FAIL/INCONCLUSIVE y preserva evidencia.

| Hipótesis | Prueba discriminante | Resultado que la distingue |
|---|---|---|
| A: Windows acepta ambas aperturas del mismo objeto | Registrar apertura RW/share-none, vida continua del handle holder, volumen/file ID, y intento RW del probe dentro de ese intervalo; repetir con dos procesos .NET. | Dos adquisiciones reales sobre mismo objeto e intervalo, con flags corroborados. Un acceso sólo a atributos no cuenta. Si PS→PS falla también, aislar filesystem/filtro/flags antes de culpar MT5. |
| B: namespace físico distinto | Capturar common/data/program paths de ambos MQL, identidades externas de proceso y objetos, y challenge aleatorio de la ejecución en el recurso, no sólo en el CSV. | File ID/volumen o destino final diferentes. Rutas textuales iguales no bastan. |
| C: holder cerró prematuramente | Registrar CloseHandle/OnDeinit, razón de salida y ACK de liberación, con reloj monotónico externo. | Cierre anterior al intento. READY persistente no refuta esta hipótesis. |
| D: no hubo solapamiento real | Barrera con token nuevo del runner, ACK sólo mientras el handle está abierto, trazas de apertura/intento/cierre y correlación GetTickCount64. | Intento fuera del intervalo o no correlacionable ⇒ solapamiento no demostrado. PID vivo y heartbeat solos son insuficientes. |
| E: evidencia y lock observados son recursos diferentes | Comparar path final/file ID del handle MQL con el objeto vigilado por PS; archivos de resultados separados y ligados a rol/RunId. | Diferencia de identidad o snapshot de otro RunId. El código 52 debe separarse de evidencia faltante, ilegible o incompleta. |
| F: EA ejecutado por otro proceso/agente | Correlacionar procesos terminal64 y metatester64, ejecutable, inicio, usuario/sesión, puerto/directorio del agente y MQL_TESTER. | Resultado cambia con contexto de agente/usuario/ruta; identifica dónde ocurrió FileOpen sin adjudicar por el PID de la GUI. |
| G: otra causa | Registrar GetLastError MQL y Win32 real; introducir ruta inválida, ACL denegada, flags compartidos, caché vieja, timeout, reparse y PID reutilizado. | Denegación por causa distinta de sharing, retorno temprano, otro archivo o resultado reutilizado; FAIL explícito con razón propia. |

## Instrumentación y protocolo requeridos

Por holder/probe/reacquire: RunId, token propio y token esperado de holder, epoch, nombre lógico, TERMINAL_PATH, TERMINAL_DATA_PATH, TERMINAL_COMMONDATA_PATH, MQL_PROGRAM_PATH, MQL_TESTER, GetTickCount64 de cada transición, flags exactos, resultado y GetLastError. Registrar adquisición, intento, decisión y liberación incluso en OnDeinit. No introducir un PID inventado: obtener PID de terminal y agente desde observación externa y asociarlo mediante un challenge nuevo y la identidad del proceso; ChartID no es PID.

PowerShell debe registrar UTC externa y reloj monotónico, host/boot ID, PID+CreationDate+ExecutablePath+usuario/sesión, proceso creador, paths finales y file IDs observados. Una traza nativa o inspección equivalente de handles debe vincular el holder real al objeto y acreditar que no hubo cierre intermedio. Si no puede obtenerse esa evidencia, el gate falla cerrado. Un heartbeat acredita actividad de código, no demuestra por sí solo un handle exclusivo continuo.

Crear plan esperado independiente ANTES de lanzar procesos. Vincular ambas fuentes a ese plan; no tomar los valores esperados del mismo CSV que se valida. El contrato offline entregado comprueba coherencia entre rol/plan/observación, pero no autentica al productor ni verifica una traza Windows: jamás emite R2 PASS, incluso ante un transcript sintético perfectamente coherente.

Separar HOLDER, PROBE, RELEASE y REACQUIRE; cerrar y hacer snapshot exclusivo de cada evidencia. Congelar manifest de fuentes/includes/EX5/configs y los logs en todos los caminos de salida. La barrera de liberación incluye token y epoch; reacquire sólo después de cierre confirmado. Restart usa otro proceso con identidad de creación distinta y verifica bytes durables, no un booleano `persistence=true`.

Registrar procesos activos y paths protegidos antes/después es necesario; un CSV vacío no demuestra ausencia de procesos inaccesibles o un filtro correcto. La nueva instrumentación debe distinguir inventario completo de acceso denegado. No copiar ni modificar perfiles activos; clones nuevos sin EA de trading, AllowLiveTrading=0, permisos DLL desactivados en MQL. Cleanup sólo procesos creados por esta ejecución, comprobando PID+inicio+path exacto; nunca por nombre global.

## Alternativas de fencing de producción — evaluación, sin cambio de Candidate3

| Primitiva | Garantía y limitación | Condición de aceptación |
|---|---|---|
| Archivo Windows RW exclusivo realmente compartido | OS mantiene exclusión mientras vive el handle; archivo puede permanecer al morir el owner. No depende de GV locales. | Mismo objeto, share-none demostrado, handle retenido hasta fin de ownership; no borrar/recrear el guard. |
| Named mutex Windows | Exclusión entre procesos, propiedad del hilo; muerte produce abandono y exige reconciliación. No es API nativa documentada de MQL5. | Nombre y ACL ligados al scope, manejo de WAIT_ABANDONED; sidecar o importación auditada requerirían calificación adicional. [Mutex Windows](https://learn.microsoft.com/en-us/windows/win32/sync/mutex-objects). |
| Creación atómica de archivo/directorio | Arbitra adquisición inicial; un artefacto huérfano no conserva ownership vivo. Un Test-Path seguido de creación no es atómico. | Operación CreateNew/CREATE_NEW o creación atómica verificada y guard independiente para recuperar huérfanos. [Creación de archivos](https://learn.microsoft.com/en-us/windows/win32/fileio/creating-and-opening-files). |
| Lock scoped por broker/cuenta | El scope debe incluir servidor, cuenta normalizada y dominio de ejecución; RunId no puede fragmentar el lock de producción. | Un guard local coordina sólo ese host/scope. No garantiza exclusión de otro PC operando la misma cuenta; no inventar un lock del broker. |
| Guard durable + token + epoch + heartbeat | Mejor contrato de ownership y recuperación, pero heartbeat vencido no prueba muerte ni autoriza robar el lock. | Adquirir guard OS primero; reconciliar estado y órdenes existentes; aumentar epoch durable bajo exclusión; rechazar mensajes del epoch anterior. |

Si se demuestra inadecuación de FILE_COMMON, una vía legítima sin DLL de MQL sería un coordinador local gratuito que conserve el guard OS y exponga IPC autenticado por token/epoch. Sin embargo, un sidecar que muere mientras el EA conserva permiso para operar produce split-brain. Para producción haría falta interlock obligatorio en la ruta de ejecución y reconciliación, y posiblemente cambiar Candidate3: no basta añadir un heartbeat. No se implementa ese cambio sin demostrar primero su necesidad y repetir los gates invalidados. Stale recovery nunca usa sólo TTL, y un lock file no se elimina mientras otro owner pueda seguir vivo. El protocolo debe rechazar release sin token, epochs repetidos y ABA.

## Pruebas ejecutadas y defectos

* 24 fuentes textuales recuperadas: Git blob SHA-1 recalculado desde bytes exactos, 24/24 coincidencias; SHA-256 en SOURCE_INTEGRITY.json. Esto no incluye fuentes R2 ausentes.
* Gate histórico v1.1: dos entradas sintéticas reproducen aceptación incorrecta 10/10: Stop-Process en nivel superior y envoltura try/catch sólo en comentarios. No se ejecutó ninguna instrucción PowerShell. Script de reproducción incluido, bound al SHA histórico.
* Nuevo contrato offline: 27/27 mutaciones rechazadas, incluidas las 12 solicitadas, más file ID, evidencia externa distinta, handle interrumpido, PID reutilizado, error ACL en lugar de sharing, cambio del runner, CERT y Candidate3. Control positivo coherente permanece sin certificado. Son mutaciones de transcript, no cobertura del qualifier original.
* Import preflight histórico ejecutado: falla por HANDOFF_MANIFEST.sha256 no materializado en esta recuperación parcial. No evidencia corrupción del repositorio. No se modifican fuentes existentes ni baseline para eludirlo.
* No se ejecutó PowerShell/MetaEditor/MT5, two-terminal native, restart nativo ni R4. El static gate completo y el fixed point del qualifier quedan sin ejecutar por falta de fuentes exactas. No se etiqueta esta entrega como qualifier prevalidado.

## Estado final y siguiente gate legítimo

La identidad del runner permanece `17be652ebb5c3745590ceae798a02d136285a2c8dc1c3645f2be578dfa8d8375`; su `STATIC_QUALIFIED` es documental y no se promueve. R2 previo: FAIL según recibos; esta sesión: NOT_RUN_BLOCKED, sin nuevo native receipt PASS. Fingerprint objetivo no observado; se entrega un registro de ausencia con valores históricos separados, no un certificado utilizable.

Se requiere recuperar automáticamente los paquetes exactos mediante una superficie accesible, contrastar hashes, completar auditoría integral del qualifier y sus mutaciones, y ejecutar R2 instrumentado en Windows 6182 aislado sin Candidate3. Sólo tras R2 válido procede R3 y preparar R4 ligado al mismo SHA. Cambiar cualquier byte del runner invalida R1/R2; cambiar qualifier invalida la evidencia obtenida por él. No autoriza despliegue, CERT ni live.

La parada responde a acceso/materialización e infraestructura nativa, no a falta de permiso para las acciones ya autorizadas. No hay ningún proceso investigando en segundo plano.
