# QRCEL: recuperación operacional

El usuario eligió V191 como referencia de ingeniería. No usar resultados negativos de otras versiones para borrar exposición, evidencia o autoridad científica.

Recuperar este paquete desde el commit y el hash del manifest fijados en la referencia QRCEL del Governor instalado. Verificar los bytes antes de importar código. No elegir una release por fecha o nombre.

Ejecutar desde una copia verificada:

```bash
python -B -m cognitive.session --repo-root <checkout> --release-blob <anclaje-externo> --objective '<objetivo autorizado>' --depth L2 --save
```

Por defecto se usa `REFERENCE_ONLY`: valida la referencia completa V191, carga sólo módulos pertinentes, mide capacidad local y crea un checkpoint de sesión. El recibo no autoriza trading ni activa un proceso persistente. Publicar los checkpoints cerrados en el repositorio usando las herramientas autorizadas del agente; un archivo local por sí solo no demuestra durabilidad remota.

Para inspeccionar autoridad activa, suministrar explícitamente `--mode ACTIVE_INSPECTION --active-root <snapshot> --active-blob <anclaje>`. Una discrepancia bloquea esa inspección; no impide ingeniería sintética independiente.

Leer `COGNITIVE_STATE.json` para trabajo pendiente y `research/evaluation_readiness/COMPLETION_AUDIT.json` para gates no cumplidos. No repetir benchmarks cerrados. Las pruebas de arranque no equivalen a fixed point global ni a paridad Astra–Sol.
