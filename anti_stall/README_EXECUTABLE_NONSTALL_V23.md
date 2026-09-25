# QROS Anti-Stall v2.3 — mecanismo ejecutable, no una instrucción de chat

## El hueco corregido

El despachador v2.2 retorna `ONE_VERIFIED_STAGE_PASS` tras **una** etapa. Si el host no vuelve a invocarlo, QROS se detiene aunque existan más etapas listas. Además, un proceso interrumpido `RUNNING` requería recuperación manual.

`anti_stall/scripts/qros_continuation_engine_v2_3.py` es un controlador **real** de múltiples etapas sobre la cola v2.2 **ya congelada**. Ejecuta el dispatcher repetidamente bajo un presupuesto global, revalida entradas/salidas y receipts antes/después, emite checkpoint con cadena SHA-256 y sale explícitamente si no hay otra etapa legítima. Recupera `RUNNING` automáticamente **solo** con los SHA-256 y tamaños esperados en el plan original; sin esa evidencia, evita la repetición peligrosa. Los dos ejecutores serializan por mutex del directorio de control y la ejecución local conserva la gobernanza del watchdog/timeout existente.

**No modifica** tesis, órdenes ni costes; no hace backtesting económico ni toca W3, el holdout, GA2, MT5 o los 60 shards de QROS. Reusar este mecanismo para los 449 shards todavía pendientes en el último checkpoint de W5 exige antes que un ejecutor autorizado disponga de sus bytes y planes exactos. Los tests con datos sintéticos no constituyen paridad científica W5.

## Ejecutar en PC/servidor con cola y datos legítimos recuperados

Usar exclusivamente cola SHA-congelada con planes/inputs reales y fuente de verdad viva autenticada previamente:

```sh
python anti_stall/scripts/qros_continuation_engine_v2_3.py \
  --queue /ruta/cola-frozen.json \
  --expected-queue-sha256 <SHA256_EXTERNO_EXACTO> \
  --max-seconds 180 --max-stages 5
```

La salida informa qué **procesos locales sí ejecutó**, qué etapas están bloqueadas y dónde está el checkpoint durable. Segunda llamada, incluso en otro chat/host con el mismo volumen persistente y autoridad exacta: continúa sin recalcular `PASS`.

Solo para calificar el mecanismo con workers reales **sintéticos**:

```sh
python anti_stall/examples/qros_v23_actual_execution_canary.py --work /tmp/qros-v23-demo
python anti_stall/examples/qros_v23_actual_execution_canary.py --work /tmp/qros-v23-demo
python -m unittest discover -s anti_stall/tests -p 'test_v2_3_*.py' -v
```

La primera ejecución crea tres trabajos subordinados, fuerza fallo primario del segundo y valida el alternativo; la segunda debe devolver `actually_executed_jobs_this_invocation: []`. El workflow `qros-executable-nonstall-v23.yml` ejecuta estos tests con `workflow_dispatch` o un PR, **sin** descargar datos de bróker ni activar servicios de pago. No está programado periódicamente para consumir minutos de Actions.

## Garantías y límites

- Una sola cola bajo `SHA256` externo; cada plan, input y resultado conserva sus hashes. Cada `PASS` exige archivos efectivamente generados y revalidados.
- Secuencia real dependiente; hasta dos rutas causales equivalentes, **solamente** si ya estaban congeladas. Rama bloqueada jamás aprueba dependientes; otras ramas independientes sí se ejecutan.
- Presupuesto global por llamada, máximo de etapas y timeout por ruta; watchdog de bytes existente disponible para planes que congelen su uso. Un latido sin nuevos bytes no significa progreso.
- Checkpoint y cadena hash durables con rename atómico. Si el proceso cae entre `PASS` y checkpoint del controlador, se reconcilia desde receipts verificables. Si `RUNNING` no tiene resultados previamente pineados, no se relanza ni se marca completado.
- El motor no puede matar llamadas a conectores realizadas por ChatGPT ni permanecer activo al terminar un chat. Para ejecución continua real se requiere programar **este script** con cron, Task Scheduler o un runner self-hosted ya autorizado y con datos accesibles. El workflow público solo califica fixtures; no finge ejecutar backtests W5.
- Pendiente hasta correrse en esa infraestructura: certificación nativa Windows, integración sobre cola W5 V33 completa y comprobación independiente de todos los shards reales. Requerir validación de acceso a fuentes históricas y certificado de costes antes de Gate A.
