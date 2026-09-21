# QRCEL 0.6.2 — admisión local acotada

El lanzador verificado adquiere un flock exclusivo por repo/run antes de llamar al entrypoint del kernel, incluyendo la apertura de SQLite y la exportación/restauración. La espera predeterminada es 10 segundos; `--admission-wait` admite 0 a 15 segundos, dentro del tiempo total del supervisor. Los procesos de runs diferentes no comparten este bloqueo.

Al agotar la espera, el hijo devuelve KERNEL_ADMISSION_TIMEOUT; el supervisor informa retryable_local_admission=true. No se ejecuta el kernel ni se reintentan tareas automáticamente. Reanudar siempre con el mismo run, inputs, objetivo y anclas; una salida de admisión no autoriza repetir efectos externos. Una cola arbitrariamente grande puede agotar su presupuesto; no se promete FIFO ni ausencia de starvation.

Los locks viven en cognitive/admission, directorio privado 0700, y son archivos regulares 0600 propiedad del usuario, sin enlaces ni hardlinks. Se usan descriptores, O_NOFOLLOW y cierre garantizado. El archivo del lock permanece: borrarlo mientras hay participantes puede dividir la exclusión. La propiedad del flock termina al cerrar o morir el worker, incluso por SIGKILL; no se usa un PID grabado como lease.

La validación bloquea también abreviaturas de argumentos reservados de identidad y de --run-id, para que el objetivo protegido coincida con el usado por el entrypoint. Las opciones del supervisor deben escribirse completas. Esto corrige un desvío reproducido con --repo-r y --run-i en 0.6.1.

Alcance: procesos cooperativos que usan este lanzador sobre el mismo sistema de archivos local POSIX/Linux. No es fencing distribuido, coordinación entre copias de estado, protección contra administradores/same-UID hostiles ni cobertura automática de llamadas directas a Kernel o de versiones antiguas. SQLite conserva sus propias transacciones y timeout; un escritor externo no cooperativo aún puede generar database-is-locked.

Q07 queda cerrado sólo en el alcance del lanzador local probado. Se mantienen los límites de almacenamiento de 0.6.1. Kernel/runtime/goal_contract no cambian de bytes; se siguen comprobando los bindings y anclas antes de recuperar. Ninguna prueba activa ciencia, holdout, PnL, modelos de pago o promoción completa de QRCEL.
