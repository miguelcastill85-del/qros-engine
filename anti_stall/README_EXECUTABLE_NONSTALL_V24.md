# QROS Anti-Stall v2.4: EJECUTOR real, reanudable y vigilado por autoridad

**Alcance:** control de procesos. No certifica rentabilidad, comisiones, sesiones, MT5, holdout ni Gate A. No cambia el contrato de la genealogía. El motor cuantitativo no fue reescrito.

## Cadena de ejecución efectiva

- v2.1: ejecuta **un** proceso realmente congelado, verifica inputs/outputs SHA-256, conserva events apéndice y ruta alternativa SOLO si quedó prerregistrada.
- v2.2: watchdog de tiempo e inactividad por **nuevos bytes verificados** y dispatcher dependiente seguro; no confundir log/heartbeat con progreso.
- v2.3: **ejecutor real multi-etapa**, reinvoca el dispatcher, checkpoint durable y reanudación al reiniciar. RUNNING recuperable sin repetición **solo** si los outputs coinciden con SHA/tamaño previstos en el plan original. En caso contrario detiene esa rama y permite continuar otras independientes.
- v2.4: **servicio multicíclico** ejecuta v2.3 varias veces sin que el chat vuelva a llamarlo; antes y después de cada ciclo hace un `git fetch` autenticado en el PC autorizado, comprueba URL exacta de origin, que el commit de cola es ancestro, Git blob SHA-1 del HEAD científico vivo, target y anchor exactos. Un cambio de autoridad pausa la cola: no rebasa ni reescribe el plan automáticamente.
- La cola, los planes, el origen Git, los outputs y el puntero de autoridad tienen pines independientes. Todos los runners son síncronos y con presupuestos; no hay bucles ilimitados para fingir continuidad.

## Activar en una PC Windows que **ya posee** los datos, planes y acceso Git autorizado

**Requisitos locales**: Python 3.11+, `git` autenticado para leer el repo privado, `qros-engine` con rama local y su historial suficientes (`merge-base --is-ancestor`), cola REAL y cada plan ya congelados en la ruta correcta, los ocho archivos originales relevantes con SHA verificado y los workers originales reales. **Este repositorio no descarga automáticamente los datos privados de ChatGPT Library/Drive a la PC ni puede configurar el Programador de tareas a distancia.** Primero debe existir la cola congelada y los bytes correctos; un archivo parecido no sirve.

En PowerShell (usuario de la PC; esto no requiere una suscripción adicional):

```powershell
$repo = 'C:\ruta\qros-engine'
$queue = 'C:\ruta\QROS_W5_COLA_REAL_CONGELADA.json'
# Copiar los SHA exactos de los receipts autorizados de ESA cola y del puntero vivo,
# NO del ejemplo; NO adivinar, NO usar un checkpoint anterior.
& "$repo\anti_stall\hosts\install_windows_task_v2_4.ps1" `
  -RepoDir $repo -Queue $queue -QueueSha256 $SHA256_COLA_REAL `
  -LivePointerSha1 $GIT_BLOB_SHA1_HEAD_VIGENTE -PythonExe 'python.exe' -RunNow
```

La instalación registra **una tarea del usuario interactivo** diaria a las 22:00 de la PC y al iniciar sesión, con política `IgnoreNew` para impedir duplicados. Está limitada a 7 h por activación, máximo 20 ciclos y 6 h operativas en cada activación. La tarea termina si falta el broker original, hay drift de SHA, el puntero científico cambió, faltan credenciales o no queda trabajo legítimo. Los logs se conservan en `QROS_V24_SCHEDULED_LOGS` junto a la cola; v2.3 persiste su checkpoint SHA en `control_root`.

**Limitación física**: si el equipo está apagado, no tiene acceso al broker/Drive/Git o el usuario no inicia sesión, no hay ejecución. `StartWhenAvailable` permite ejecución tardía cuando el equipo se enciende y el usuario entra. Para 24/7 hace falta un host permanente autorizado; ni un chat ni un archivo de instrucciones sustituyen un proceso vivo.

## Ejecutar una sesión de manera inmediata y verificable

```bash
python anti_stall/scripts/qros_continuation_service_v2_4.py \
 --queue /ruta/cola-frozen.json \
 --expected-queue-sha256 SHA256_EXTERNO_DE_ESTA_COLA \
 --git-dir /ruta/checkout-autenticado \
 --pointer-path control/QROS_SEED0076_DIRECT_CURRENT_CHAT_HANDOFF.json \
 --expected-live-pointer-sha1 GIT_BLOB_SHA1_DEL_PUNTERO_ACTUAL \
 --max-cycles 20 --wall-seconds 21600 --cycle-seconds 180 --stages-per-cycle 5
```

Salidas: `ALL_VERIFIED_EXECUTION_COMPLETE` = todos los jobs verificables PASS, 0; `SCIENTIFIC_OR_INFRASTRUCTURE_DEPENDENCY_SAFE_DEFER` = no hay trabajo permitido, 20; `FAIL_CLOSED` = fuente o infraestructura inválida, 3. Los estados del servicio **nunca** representan Gate A o aprobación científica.

## Pruebas de falsación

`python -m unittest discover -s anti_stall/tests -p 'test_v2_3_*.py' -v`

`python -m unittest discover -s anti_stall/tests -p 'test_v2_4_*.py' -v`

`python anti_stall/examples/qros_v23_actual_execution_canary.py --work /tmp/QROS_v24_canary`

Repetir última línea en la misma carpeta: la segunda vez `actually_executed_jobs_this_invocation` debe ser `[]`. Los fixtures producen bytes y procesos reales, **nunca ticks históricos**. GH Actions privado contiene un workflow **solo manual (`workflow_dispatch`)** para no consumir minutos sin autorización; Windows nativo debe calificarse en la PC destino.

## Bloqueo separado de W5

El checkpoint W5 de la rama científica tiene **solo los shards de paridad aún pendientes y las pruebas primarias históricas de comisiones y sesiones**. QROS v2.4 no inventa el plan ni los datos: se instala sin cambiar `research/seed0076-direct-dev-backtest-20260922`, sus 261 shards V33 ya verificados, W3 diferido, holdout cerrado, GA2 cerrado ni el cálculo económico V28. Si las fuentes originales no pueden materializarse, la cola queda suspendida con evidencia y reanuda en cuanto los bytes exactos están montados y la autoridad vuelve a congelarse.
