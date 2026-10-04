# G12 — integración verificada, TEST_ONLY

VERIFICADO: fuente 217cd842cb195fa92e52aa39068b97892752e48e; CI 37126514681 finalizada success. Worker, regresiones Flutter, reproducción de cuatro defectos del padre y compilación Android aprobados. ZIP descargado y APK rehasheada independientemente; identidades completas en G12_CURRENT_CHECKPOINT.json. APK 0.12.1+13, debug, minSdk 24. No se repitió ninguna ejecución aprobada en esta recuperación.

El cliente conserva solicitudes pendientes ante pérdida de respuesta, serializa renovación/cierre de sesión y comprueba continuidad e integridad SHA-256 del resultado sintético. Esto no convierte el hash en firma asimétrica ni prueba investigación real. El endurecimiento del Worker y el parche de herramientas de PR80 están integrados; PR80 cerró como merged.

NO DISPONIBLE: despliegue público G12, prueba física de esta APK, firma de distribución y aprobación comercial. La prueba física G9 permanece REPORTADA por el usuario, con capturas previas; no se reclasifica como prueba de G12. El bloqueo Cloudflare observado fue un formulario de login deshabilitado con error de verificación, no credenciales inválidas demostradas.

Incidente de recuperación: el inspector local esperaba result=error; el JSONL usa result=failure. Se corrigió la interpretación, sin modificar datos ni producto: cuatro fallos visibles del padre. Los incidentes y correcciones anteriores se conservan en G12_CLIENT_RECOVERY_20261003.md y G12_TOOLCHAIN_AUDIT_20261003.md; sus estados pendientes quedan complementados por esta evidencia posterior.

MOBILE_PRODUCT_HEAD v11 y main científico intactos. Sin PnL, holdout, GA2, MT5, datos reales ni servicios de pago. Impacto de portafolio: ninguno evaluado o autorizado.

Siguiente operación exacta: recuperar acceso autenticado Cloudflare y confirmar Free; preparar despliegue aislado G12 y canary HTTPS externo, manteniendo ENABLED=false hasta cumplir configuración y controles. Después, prueba física de G12 con recibo. No desinstalar la app existente para resolver conflicto de firma sin conservar antes sus datos. No hay ejecución en segundo plano ni autorización comercial implícita.
