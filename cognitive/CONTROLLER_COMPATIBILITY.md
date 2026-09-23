# Compatibilidad del controlador V191

El controlador V1 original se conserva. Una fachada explícita permite `validate` y `next` sobre la referencia inicial V191, verificando manifest, identidades delegadas, registros, redirects, población, gates y estado de cola. No cambia schemas ni estados.

```bash
python -B -m cognitive.qros_controller_adapter validate --repo-root <referencia-v191> --manifest-blob 5afce6279994b8625bd79fb2d5d13924e3c561e7
python -B -m cognitive.qros_controller_adapter next --repo-root <referencia-v191> --manifest-blob 5afce6279994b8625bd79fb2d5d13924e3c561e7
```

El arranque `cognitive.session` incorpora esta interfaz automáticamente. La tarea devuelta es una pista histórica para preflight; no es una orden de ejecutar ciencia. V191 no contiene un contrato de leases ni transiciones delegado al adaptador: claim, heartbeat, release, checkpoint transition y dispatch se rechazan. No se inventan esos campos ni una nueva autoridad.

En comparación, compartir esta fachada entre QROS_REFERENCE_COMPAT y QRCEL. Nunca llamar CURRENT_QROS sin modificar al brazo parcheado ni atribuir la compatibilidad a mayor razonamiento del modelo. Evidencia: `checkpoints/controller_adapter_042/RESOLUTION.json`.
