# Android físico — siguiente prueba G12 TEST_ONLY

Estado: PREPARADO. Instalar una APK o ver capturas del emulador no certifica ejecución física. G9 físico previo permanece REPORTADO y no debe repetirse.

1. Usar únicamente la APK que figure como verificada en G12_CURRENT_CHECKPOINT.json. Comparar versión y SHA con el recibo; conservar la APK anterior. Si Android rechaza actualización por firma incompatible, no desinstalar ni borrar datos. Respaldar primero los borradores mediante “Respaldar y recuperar” → “Copiar respaldo portátil” si esa versión lo ofrece.
2. Abrir QROS → Más módulos y seguridad → Seguridad → Vincular dispositivo G12.
3. El único origen permitido es `HttpsSessionGateway.trustedOrigin` del build verificado: https://qros-mobile-g12-test-only.miguelcastill85.workers.dev. Esa configuración no prueba despliegue; no hacer pairing hasta que el checkpoint registre HTTPS externo PASS.
4. Usar exclusivamente un bootstrap QROS de un solo uso y corta duración suministrado por el mecanismo seguro del proveedor. Nunca usar un token de API Cloudflare, una contraseña o una clave privada. No enviarlo por chat ni incluirlo en capturas. La emisión para el teléfono está PENDIENTE.
5. Pulsar “Vincular dispositivo”. Conservar captura de “SESIÓN ACTIVA” con origen, client_id y vencimientos, después de que el bootstrap se haya limpiado. La captura por sí sola constituye evidencia REPORTADA.
6. Hipótesis → guardar universo sintético → Fábrica → Abrir trabajo sintético G12 → Crear trabajo sintético. Avanzar con “Reanudar siguiente checkpoint” hasta COMPLETE/100%. Conservar identificador y SHA del resultado. Esto mide infraestructura sintética; no ejecuta backtests económicos.
7. Cerrar y abrir la app; “Sincronizar estado” debe recuperar el mismo trabajo. Probar sin conectividad y reconectar: no se concede progreso ni aprobación por una respuesta fallida.
8. “Rotar sesión ahora” conserva la identidad de cliente. “Cerrar y revocar sesión” debe eliminar la sesión local; si la app informa revocación remota no confirmada, registrar esa limitación y no afirmar revocación global.

Recibo físico mínimo: versión, SHA realmente comprobado cuando exista herramienta autorizada, modelo/API Android, hora de prueba, identificador/resultado sintético, capturas sin credenciales y clasificación de cada conclusión. El agente no dispone de control autorizado del teléfono en este entorno; la aceptación independiente sigue NOT_RUN.
