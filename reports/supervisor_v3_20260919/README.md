# QROS: corrección del supervisor de procesos

Candidato de ingeniería derivado de `ede867afa821bd7b7ee86e259b87c42ae782f4a3`.
Las versiones congeladas v1/v2, el puntero científico y el PR #51 no se modifican.

## Fallos reproducidos y correcciones

| Fallo | Corrección comprobada |
|---|---|
| Un trabajador colgado mantiene `wait()` indefinidamente | Tiempo máximo obligatorio, medido con reloj monotónico; finalización del grupo y salida operativa 124 |
| Logs ilimitados o un hijo con tuberías abiertas | Límite combinado de stdout/stderr; lectura incremental; deadline también cubre tuberías heredadas |
| `done` de otra especificación se reutiliza como PASS | Verificación del job, SHA de la especificación, SHA del recibo y hashes/tamaños de artefactos |
| PID de otro runtime o lanzamiento incierto permite reintento | Estados UNKNOWN/FOREIGN; rechazo sin afirmar muerte ni iniciar otro intento |
| Bloqueos por directorios pueden ser robados durante recuperación | `flock` no bloqueante sobre inode estable; liberación por el kernel; no borrar el inode |
| Bootstrap repetido puede lanzar otro trabajador | Exclusión por intento y marca de identidad durable; un intento con identidad nunca se vuelve a lanzar |
| Symlink permite validar un artefacto fuera del intento | Rechazo del symlink final y de sus directorios padres |
| Llamada de control sin límite | Adaptador fenced v2: 3 segundos más cleanup acotado; timeout devuelve UNKNOWN sin autorizar relanzamiento |

## Evidencia

- Siete regresiones dirigidas fallaron sobre v1 antes de corregir. v2 delega ese mismo controlador, aunque su bloqueo de directorios tiene un parche propio.
- 20 pruebas del candidato v3, 11 casos del corpus histórico de ciclo de vida y 6 del adaptador: **37 PASS**.
- El corpus histórico se reutiliza sin modificarlo. El adaptador de pruebas añade los presupuestos obligatorios y limpia únicamente el fixture de bloqueo legado.
- Una carga sintética idéntica produce los mismos SHA-256 de artefacto y recibo bajo v1 y v3. Se comprueban adopción de huérfano, concurrencia, reintento acotado y reutilización sin nuevo worker.
- Los logs y `CHECKPOINT.json` contienen tiempos observados e identidades. No son un benchmark de estrategias ni evidencia de mejora de PF/rentabilidad.
- `handoff/verify_import.py` se ejecutó y rechazó la materialización parcial por archivos históricos ausentes. No se certifica el import original ni una release nativa completa. Los 22 archivos recuperados para esta corrección sí se verificaron contra sus Git blob SHA del commit exacto.

## Uso optativo

El job conserva los campos anteriores y exige dos presupuestos explícitos:

```json
{"max_runtime_seconds": 3600, "max_log_bytes": 10485760}
```

Son ejemplos de ingeniería, no parámetros autorizados para una campaña concreta.
Usar una raíz local **nueva y exclusiva para v3**. No mezclar supervisores antiguos
y nuevos sobre el mismo job. No copiar ni borrar claims activos para forzar reintentos.

```bash
python3 scripts/qros_heavy_job_supervisor_tests_v3.py
python3 scripts/qros_heavy_job_supervisor_lifecycle_tests_v3.py
python3 scripts/qros_fenced_heavy_job_supervisor_tests_v2.py
```

Para una cápsula previamente autorizada y ligada a una lease vigente, el nuevo
adaptador es `scripts/qros_fenced_heavy_job_supervisor_v2.py`, con argumentos
`--job-spec`, `--work-root` y `--lease`. Invoca exclusivamente el supervisor v3 hermano.
Su comprobación local de lease no reemplaza el CAS durable de la autoridad.

`FAIL` en estos controladores es un fallo operativo; no significa rechazo de una
estrategia ni agotamiento de una rama. Un timeout deja sus salidas sin promover.
Si el resultado del control es desconocido, recuperar claim/identidad/artefactos antes
de cualquier acción posterior. El watchdog del trabajador depende de que sobreviva
el bootstrap; adoptar un huérfano no restablece automáticamente ese watchdog.

## Frontera y pendientes

El target V255 conserva el blob esperado. El checkpoint operativo actual tiene blob
`bc4064d698d67e48c2a699c3236da88bca528d6c`, pero el puntero estable referencia
`22f1c8fed5dd8bf63f17f72754edf180a734f95e`. Esa discrepancia se registra sin reescribir
la autoridad ni iniciar group11. No se recuperaron ticks ni se abrió PnL, holdout o GA2.

La activación científica exige reconciliar esa referencia y ligar una cápsula exacta
al nuevo ejecutable y presupuestos. P09/P12 del PR #51 no se cierran con estas pruebas.
Linux y filesystem local son el único entorno probado. No se certifican aislamiento
de red/disco, límites de RSS, filesystem distribuido, procesos que escapen de su grupo,
MT5, un backtest real ni resistencia a I/O bloqueado dentro del kernel.

Las pruebas demuestran correcciones acotadas de ejecución e integridad; no que toda
la arquitectura QROS esté libre de fallos. No se hizo merge ni despliegue científico.
