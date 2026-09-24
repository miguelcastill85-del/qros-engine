# QROS/RISE — ANTI-STALL v2.2 — LÍMITE LITERAL, RUTA ALTERNATIVA Y CONTINUIDAD

**Delta respecto a v2.1:** v2.1 ya mata el árbol de procesos al agotar el tiempo del intento, pero devuelve `FAILED_ROUTE_SWITCH_REQUIRED` y el siguiente intento depende de una nueva invocación. v2.2 añade un despachador que continúa automáticamente dentro de la invocación, y un watchdog que detecta ausencia REAL de nuevos bytes validados. No modifica estrategias ni resultados.

## Presupuesto obligatorio

- **Interacción ordinaria:** máximo 120 s por ruta; sin progreso real durante 45 s se termina antes. Presupuesto total del despachador: 180 s. Máximo dos rutas causales previamente congeladas y nunca dos intentos idénticos.
- **Trabajo pesado ya troceado:** hasta 600 s de tiempo absoluto y 90 s de inactividad, solamente si el plan fijado demuestra un sistema de chunks, outputs con SHA y recuperación. En chat, la invocación sigue acotada por el presupuesto total y debe fraccionarse para entrar en él.
- **Progreso válido:** bytes de un shard nuevo o modificado, tamaño exacto y SHA-256 recomputado por el watchdog. Un heartbeat o un archivo de progreso antiguo NO amplía la ejecución. Un hash verificado solo permite continuar ejecutando, no certifica un resultado científico.
- **Ruta alternativa:** primero la siguiente implementación equivalente en el plan original, sin tocar señal, orden, costes ni ventanas. Si ninguna supera los controles, congelar el incidente y continuar una tarea que NO dependa del resultado. No convertir una etapa fallida en PASS.
- **Cambios de autoridad o resultados contradictorios:** falla cerrado. No hay permiso para abrir holdout, GA2, reutilizar shards congelados ni cambiar de semilla para hacer parecer que hubo progreso.

## Piezas y pruebas

1. `scripts/qros_progress_watchdog_v2_2.py`: ejecuta el proceso en grupo aislado, mide reloj monotónico, observa avances SHA y mata el árbol en timeout. Conserva shards parciales, genera razón explícita (`WALL_DEADLINE` / `NO_VERIFIED_BYTE_PROGRESS`). El timeout también incluye la gracia de arranque acotada.
2. `scripts/qros_continuation_dispatch_v2_2.py`: lee **cola y planes congelados por SHA-256 externo**, exige autoridad exactamente igual en los planes, verifica el estado anterior usando el ejecutor v2.1, ejecuta dos rutas equivalentes como máximo y selecciona una tarea independiente solo si todas sus dependencias están en PASS. Se detiene al cerrar UNA etapa por invocación.
3. `tests/test_v2_2_nonstall.py`: pruebas adversariales de alternancia automática, no duplicar trabajo cerrado, dependencias, desvío de autoridad, límite absoluto del plan, timeout por inactividad, progreso real y heartbeats falsificados.
4. Se preserva y ejecuta la suite original de **37 pruebas v2.1** en el mismo árbol. v2.2 agrega **8 pruebas** sin modificar v2.1 ni sus manifiestos.

## Contrato para cada cola

La cola requiere `schema=QROS_BOUNDED_CONTINUATION_QUEUE_V2_2`, `authority` con `base_commit` real, `control_root` y `jobs` congelados. Cada trabajo contiene `id`, `kind`, `work` (carpeta privada de la etapa), `plan` (ruta al plan v2.1 de exactamente una etapa), `plan_sha256`, `hard_route_seconds`, `max_distinct_routes` y `depends_on` con referencias a trabajos ANTERIORES. Todos los trabajos deben compartir la autoridad exacta de su cola. El SHA-256 de la cola se publica externamente en GitHub y se pasa con `--expected-queue-sha256`.

Los `routes.argv` del plan deben usar el watchdog de v2.2 para los procesos largos. Incluir su SHA256 en el contrato de inputs del plan; fijar `timeout_seconds` del plan v2.1 varios segundos por encima de `--wall` del watchdog para que éste pueda matar el árbol y reportar su propio incidente antes del límite exterior.

```
python anti_stall/scripts/qros_continuation_dispatch_v2_2.py \
  --queue ./EXACT_LANE_QUEUE.json \
  --expected-queue-sha256 EXACT_PIN_FROM_GITHUB \
  --budget-seconds 180
```

`NO_STAGE_PROMOTED_SAFE_DEFER` significa bloqueo registrado, no fracaso silencioso ni aprobación científica. No ejecutar sin reconciliar antes el HEAD de la rama viva y el puntero de gobernanza; el despacho local **no consulta conectores por sí mismo**.

## Limitaciones explícitas

El watchdog termina procesos locales, no puede imponer un kill sobre una llamada a un conector hospedado ni seguir ejecutándose cuando termina la sesión de ChatGPT. Los planes han de existir ANTES de ver PnL; se prohíbe inventar una alternativa tras conocer resultados. La implementación Windows hereda el método `taskkill` de v2.1 y exige validación nativa externa antes de certificar Windows. El SHA de metadata Drive no reemplaza una descarga de bytes.
