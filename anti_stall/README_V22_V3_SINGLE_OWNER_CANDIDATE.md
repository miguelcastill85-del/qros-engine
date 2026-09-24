# QROS/RISE — v2.2 + v3 stateless single-owner (candidato aislado)

## Resultado real

Base exacta: main `1b0cc42ceb977fcfbb7125edf767903f66dd5dd1`; PUBLIC1000 V259 y Anti-Stall v2.2 **sin modificación**. CI de GitHub en la rama de ingeniería: **15/15 pruebas sintéticas nuevas + 45/45 regresiones de v2.1/v2.2 = 60/60 PASS**. [Ejecución real](https://github.com/miguelcastill85-del/qros-engine/actions/runs/36062935032). No hay PnL, operaciones reales, MT5 ni validación Windows.

## Propiedad única de procesos

Se creó un **candidato distinto** que utiliza el esquema congelado v2.1 y la cola v2.2, pero **el proceso se inicia directamente desde una sola función** `run_bounded_single_owner`. No anida el controlador v3 ni el watchdog v2.2. Se incorpora un comprobador v3-style *sin capacidad de iniciar ni reiniciar procesos*, encargado de confirmar cada salida física con el SHA-256 y tamaño congelados, rechazar enlaces simbólicos, cotejar identidad de trabajo y dejar un recibo determinista.

Para cada etapa opt-in, `stateless_guard` fija el SHA-256 de su contrato, del runner candidato y del validador, el archivo de prueba y los límites de memoria/log y tiempo inactivo. El mismo contrato se incluye físicamente y con hash en los inputs de la etapa. Si falta cualquiera de estas identidades, no comienza la ejecución. El recibo de guardia forma parte de los outputs de la etapa: ninguna salida sin prueba obtiene PASS.

## Validaciones

El CI también comprueba que los archivos originales v2.1 y v2.2 **conservan exactamente sus Git blobs**. Las pruebas nuevas cubren salidas exactas, idempotencia, falso exit 0, identidad falsificada, bytes alterados, symlinks, exceso de logs, inactividad y conservación de parcial, contrato alterado, cambio de autoridad, ruta que intenta anidar controladores, salida PASS adulterada, ruta alterna congelada y dos ataques contra la identidad del código.

Se preserva el primer fallo de CI como evidencia negativa: dos problemas de pruebas/normalización fueron identificados y reparados antes del PASS de 60 casos; no se reescriben los resultados anteriores.

## Límites que prohíben la fusión o activación automática

La bandera `direct_worker_no_detached_descendants=true` es una condición congelada pero **no** constituye prueba de aislamiento. Un proceso malicioso podría lanzar descendientes en otro grupo: siguen siendo necesarios cgroups/job objects o una prueba equivalente de contención. Windows no se ejecutó y el candidato falla cerrado allí. No hay prueba sobre los ticks de Darwinex, no se revalidó el motor económico V5 ni los regresores históricos M2/M12/M15. La protección externa de bytes remotos continúa dependiendo de readback independiente.

Este PR debe permanecer **draft**. Nada cambia en main científico, no se abren shard11, GA2 ni holdout, ni se atribuye alfa o aceleración real a estas pruebas. El único siguiente DELTA autorizado de ingeniería es demostrar contención del árbol completo y después paridad no económica contra anchors históricos reales.

Receipt durable: `anti_stall/control/QROS_V22_V3_SINGLE_OWNER_CHECKPOINT_20260924_v1.json`.


## Certificación Linux integrada posterior (24-09-2026)

Se implementó la ruta opt-in `linux_containment` en el runner de propietario único: lanza el worker con `seccomp` (no fork/vfork/clone de proceso, no setsid/setpgid) y hace que el proceso padre compruebe `/proc/<pid>/status` (`Seccomp=2`, `NoNewPrivs=1` y grupo propio) **antes de autorizar el exec del worker**. La ruta requiere contrato, runner, validador, helper y launcher ligados a SHA-256; el recibo de kernel se incorpora a los outputs de la etapa. En cualquier fallo se detiene sin promover el stage.

**GitHub Actions real:** [73/73 PASS](https://github.com/miguelcastill85-del/qros-engine/actions/runs/36070386732) = 19 pruebas integradas + 9 pruebas independientes de seccomp + 45 regresiones originales. Ninguna prueba Linux seccomp se omitió. Comprobaciones generales `freeze-source`, `validate` y `meta-audit` también PASS.

**Sin prueba Windows por petición expresa:** el candidato queda limitado a Linux x86_64; Windows falla cerrado, no se declara soportado. Es un mecanismo para **workers fiables de proceso único**, no una sandbox de código adversarial ni aislamiento de red/ficheros. Un worker que necesite `fork`, subprocesos o ejecución de MT5 fuera de Linux no puede usar esta ruta sin rediseño/revalidación.

**Permiso científico:** esta evidencia autoriza como máximo fusionar el código de ingeniería **opt-in**; todavía NO autoriza ejecutar shards nuevos, consultar resultados económicos, desplegar al broker ni declarar mejora de backtest histórico. Antes de adoptar en un flujo real: exactos M2/M12/M15 sin PnL, dependencia/arquitectura de workers, linaje del reloj broker y recibos de paridad independientes. Preserva el checkpoint inicial de 60 pruebas como evidencia histórica y usa el nuevo recibo `anti_stall/control/QROS_LINUX_ONLY_V22_V3_ENGINEERING_CERT_20260924_v1.json` como autoridad de integración.
