# QRCEL: recuperación operacional verificada

Recuperar la release y el manifiesto exactos fijados por la referencia QRCEL del Governor o por `control/QRCEL_ENGINEERING_CURRENT.json` verificado. El usuario eligió V191 como referencia de ingeniería. Resolver aparte la autoridad científica vigente; no borrar historia ni exposición.

Antes de importar el paquete, verificar por SHA-256 el lanzador `cognitive/trusted_bootstrap.py` usando el ancla externa del puntero. Recuperar los archivos del manifiesto desde el commit exacto. Leer `HARDENING_050.md` para el modelo de confianza, compatibilidad y recuperación.

```bash
python3 -I -S -B /ruta/verificada/cognitive/trusted_bootstrap.py --repo-root /ruta/verificada --release-blob <blob-externo-del-manifiesto> --entry session -- --objective '<objetivo autorizado>' --depth L2 --save
```

El lanzador verifica y captura las fuentes antes de importarlas, aplica límites al hijo y termina con él. La sesión carga prompts verificados, inspecciona la referencia V191 y mide capacidad local. No autoriza ciencia ni deja un proceso persistente.

Leer `COGNITIVE_STATE.json`, `checkpoints/admission_062/ACCEPTANCE.json` y `checkpoints/admission_062/RUN_QUEUE.json`. No repetir trabajo cerrado. La evaluación completa y la promoción siguen sujetas a sus gates.

Para continuidad durable, publicar cada checkpoint cerrado con su SHA-256 y el `resume_anchor` del kernel en el repositorio autorizado; comprobar lectura remota por identidad. En otro runtime, verificar esas anclas externas antes de restaurar y medir capacidad de nuevo. `--save` crea primero una sesión local: no prueba persistencia remota.

La recuperación con una release distinta requiere migración explícita; no reescribir hashes históricos. No elegir una rama por fecha. La persistencia del software no garantiza activación ni proceso en todos los chats.

Para objetivos descompuestos con requisitos explícitos, usar el contrato descrito en `GOAL_CONTRACT_060.md`. Debe conservarse con su hash externo y mapa al restaurar. No declarar completo un objetivo libre por tener un DAG válido.

Leer `STORAGE_LIMIT_061.md`: límites por archivo compatibles con SQLite/checkpoints. Una sola invocación escritora por run; la concurrencia puede fallar por timeout sin corrupción.

La release 0.6.2 añade admisión local por run en el lanzador: leer `ADMISSION_062.md`, que supersede la limitación Q07 de `STORAGE_LIMIT_061.md` únicamente para esta ruta.
