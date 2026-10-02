# QROS — XAUUSD DEV exacto recuperado y auditado (2026-09-22)

**VERIFICADO mediante bytes y ejecución:** ocho archivos de Google Drive originales (IDs en `QROS_SEED0076_XAU_DEV_FIRST8_RECOVERY_RAW_AUDIT_CHECKPOINT_20260922_v1.json`) coinciden con los SHA-256 congelados. Se extrajeron en orden y se verificaron los SHA-256 de sus ocho miembros de datos. Los primeros **151.382.388** registros PACKED17 (2.573.500.596 bytes) reconstruyen exactamente el SHA-256 DEV congelado `3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53`. El constructor implementa checkpoints atómicos por parte, reanudación después de caída y lectura idempotente; la última se probó sobre el archivo completo.

**Auditoría raw ejecutada sobre todos los registros:** cero timestamps retrocediendo, 74 cotizaciones `ask < bid`, 942.184 `ask == bid`, 23 duplicados consecutivos exactos. Todas las anomalías quedan preservadas en el carrier; la verificación NO implica que sus precios sean ejecutables. La zona horaria real de broker, la codificación precisa de flags y las restricciones de stops no fueron inferidas del timestamp numérico. El JSON de auditoría incluye histograma de spreads raw, ejemplos, flags, brechas y límites por cada parte.

**Reanudación en un runner nuevo:** recuperar exclusivamente los ocho ZIP identificados en el checkpoint y comprobar sus SHA; luego ejecutar:

```sh
python qros_xau_dev_first8_rehydrate_v1.py --source-dir RUTA_A_LOS_8_ZIP --out-dir RUTA_ESTABLE
python qros_xau_dev_packed17_data_audit_v1.py --input RUTA_ESTABLE/XAUUSD_DEV_PACKED17_151382388.bin --output RUTA_ESTABLE/RAW_AUDIT.json
```

No mezclar las otras 27 partes ni recomputar shards1–10. Persistir el carrier resultante en almacenamiento durable cuando el destino lo soporte, sin sustituir la evidencia de los ZIP originales.

**CIENCIA:** `PREREGISTERED_NO_RESULTS`. Sin PnL, sin holdout, sin MT5. Falta recuperar las 303.572 máscaras exactas XAU BUY M1, la hora de broker y las condiciones de ejecución sobre ticks anómalos antes de abrir el primer gate. La ausencia de un artefacto pesado no constituye una estrategia rechazada.
