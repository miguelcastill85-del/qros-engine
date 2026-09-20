# QRCEL 0.5.0: límites de confianza y continuidad

Esta release cierra Q01–Q05 en el alcance de la auditoría del 20-09-2026. Es asistencia de ingeniería experimental, no selección del sistema completo ni paridad de modelos. Mantiene V191 como referencia; ninguna prueba autoriza ciencia, PnL, holdout o GA2.

## Arranque e identidad

El host debe verificar primero el hash SHA-256 de `cognitive/trusted_bootstrap.py` desde un ancla externa (Governor o puntero durable verificado), además del manifiesto exacto. Ejecutar ese archivo por ruta absoluta con `python -I -S -B`; no importar el paquete por `python -m` antes de verificarlo. El lanzador captura las fuentes declaradas y las compila desde esos bytes. Bloquea bytecode, extensiones, archivos .pth y fuentes extra. Un cambio posterior del árbol no altera el código capturado. Python, su biblioteca estándar, el sistema operativo y el lanzador son parte de la base de confianza.

La sesión consume configuración, estado y prompts desde los mismos bytes verificados. La referencia V191 tiene su propia comprobación de identidad. El modo ACTIVE_INSPECTION conserva su contrato de inspección; no se amplía a transiciones científicas ni se selecciona main por recencia.

## Persistencia y recuperación

El kernel vuelve a evaluar los predicados puros EXACT_SUM y CHECK_DAG antes de devolver resultados persistidos. Eso tiene coste computacional: cero tareas nuevas no significa cero trabajo de verificación. El recibo separa `newly_completed` y `semantic_revalidations_this_instance`. Esta ruta no sirve para repetir efectos externos.

Una cadena de hashes escrita junto con la base no autentica su historia. El recibo emite `resume_anchor` con binding, número de eventos y hash del último evento. Guardar esa ancla y el checkpoint fuera del estado modificable; publicar sus hashes en un commit durable y comprobarlos mediante lectura remota. Para reanudar, pasar `--resume-anchor <archivo>` y `--resume-anchor-sha256 <hash-externo>` al kernel. El prefijo esperado debe existir y coincidir: así se detectan retrocesos y reescrituras de la historia ya comprometida. Los eventos nuevos legítimos pueden extenderlo.

Sin ancla externa, la API conserva compatibilidad para tareas puras locales pero declara `UNATTESTED_LOCAL_HISTORY`. Revalidar resultados no prueba que nunca se borró historia. La ruta de recuperación entre chats debe usar el checkpoint con hash externo y el ancla; nunca tomar como raíz confiable un hash editable junto a los datos.

Los checkpoints de versiones anteriores vinculan otros hashes de código. Se conservan como evidencia; no se cambian sus bindings para aceptarlos en esta release. Una migración futura necesita un contrato y prueba de equivalencia explícitos. Se comprobó restauración en otro proceso y directorio, con la misma release, identidad de checkpoint idéntica, cero tareas nuevas y capacidad medida de nuevo.

## Recursos, cancelación y rutas

El supervisor aplica al hijo CPU (20 s), memoria direccionable (512 MiB), tamaño por archivo de salida (1 MiB), descriptores (128) y tiempo total (30 s) por defecto. Los límites son configurables dentro de cotas explícitas. Cierra stdin, reduce el entorno, utiliza un grupo de procesos y recoge el hijo tras timeout o cancelación. Es un supervisor por invocación; no es un servicio permanente ni un límite global de disco. El plan conserva los límites existentes de tareas y operaciones. Una señal KILL al supervisor o un fallo del host no puede ejecutar limpieza en Python: la siguiente recuperación debe verificar el estado durable.

`rational` valida longitud, exponente y cota numérica antes de construir Fraction. Se preserva la aritmética exacta del dominio admitido. Entradas enormes antes aceptadas quedan rechazadas como `DIMENSION_RESOURCE_LIMIT`; esta es una restricción operacional explícita, no un cambio de reglas de trading.

BenchmarkLedger exige Linux/POSIX con `/proc/self/fd`, directorio final propiedad del usuario y no escribible por grupo/otros. Recorre padres sin seguir enlaces, conserva el descriptor y rechaza enlaces/archivos inseguros en SQLite y auxiliares. Se probó sustitución del padre al abrir. No constituye aislamiento contra un administrador o un atacante con el mismo UID y control irrestricto del host. Otros hosts fallan explícitamente; no se promete compatibilidad Windows en esta ruta.

## Completitud y bloqueos

La corrección de cinco hallazgos no cierra los gates de QRCEL completo. Persisten: adaptadores y delegación para contratos científicos actuales; cobertura semántica general/ontología y fixed point; comparación de sistemas con rutas observadas y recursos equivalentes; casos nuevos y custodia sellada; shadow operacional completo, canary y promoción. Los resultados DEVELOPMENT históricos se conservan y no se vuelven a presentar como ensayos de modelos nuevos.

En esta ejecución no hay un evaluador sellado independiente ni una ruta nativa de evaluación comparativa de modelos con presupuesto y configuración verificables. No se activan APIs de pago. Las pruebas de replays ejecutan código local y no llaman a modelos. El puntero de main observado se registra sólo como contexto de integración; no acredita por sí solo sus dependencias ni cambia autoridad.

## Pruebas y entrega

`cognitive/checkpoints/hardening_050/ACCEPTANCE.json` vincula las pruebas a sus fuentes. Los cinco casos de auditoría se ejecutaron primero con expectativas de seguridad sobre el código anterior y fallaron. La suite del producto y las regresiones nuevas pasan después de corregir. Los recibos históricos no se modifican. Los comandos y logs de la nueva release quedan junto a este checkpoint.

`COGNITIVE_STATE.json` conserva `full_qrcel_complete=false`, `promoted=false` y una cola explícita. Las referencias de software son recuperables entre chats donde esté disponible el Governor y el repositorio. Ni un archivo local ni una instrucción garantizan ejecución automática en chats sin esas capacidades.
