# G12 — validación independiente y corrección de revocación, 2026-10-07

VERIFICADO: fuente `463e68af09c2dc9c689160284b70d6fb7458148e`, CI37619093177 PASS. Ocho nuevas pruebas de transporte G12 y seis de autenticación durable. Recibos y logs descargados; ZIPs y miembros verificados por SHA-256.

Reproducción inicial CI37618534076: 7 casos PASS y 1 FAIL real. Un HTTP200 con JSON vacío/no revocado era interpretado como éxito porque `revoke()` descartaba el cuerpo. Corrección mínima: exigir exactamente `{"status":"revoked"}`. Si el acuse no es válido, el cierre local borra la sesión y deja `REMOTE_REVOKE_UNCONFIRMED`. Expectativa del test conservada.

VERIFICADO: certificado autofirmado con el mismo hostname fijado rechazado por TLS antes de cualquier petición de aplicación; desconexión, redirecciones, MIME/UTF-8/JSON inválidos, respuesta >65536 bytes y sustitución de sesión rechazados. El proxy es sólo loopback y no desactiva validación TLS. Esta evidencia no es HTTPS público Cloudflare.

VERIFICADO: workerd real sobre dependencias G12 congeladas; bordes de expiración access15min/refresh30d exclusivos; cambio de tenant/proyecto/campaña tras reinicio deniega ambos tokens y conserva el trabajo original; GET no adelanta fases. Reloj controlado de prueba, no espera real de 30 días.

Nueva APK0.12.4+16 necesaria porque se modificó el cliente. Run37619093151 completado PASS; bytes146668513/SHA8093b987a939bd642bdefb5442290fe3db79c0d48f681da99882c7c38c98d7da y Android35 PASS verificados independientemente. APK0.12.3 y Rekor anteriores conservados como históricos, con el defecto de acuse identificado. No repetir esos bytes ni registros; generar evidencia sólo para el binario corregido.

NO DISPONIBLE: acceso válido Cloudflare (último preflightHTTP401), Workers Free actual, despliegue HTTPS G12, prueba física G12 y firma de producción. Autorización anterior preservada. Main científico y MOBILE_PRODUCT_HEAD v11 intactos; PnL/holdout/GA2/MT5/trading cerrados, cero servicios de pago.

Build, Android35 y nuevo hash Rekor3131046344 ya verificados. Siguiente operación: reemplazar secreto proveedor y confirmar Workers Free actual según `G12_PROVIDER_RENEWAL_20261007.md`; luego un preflight de sólo lectura y despliegue condicionado. Ver checkpoint V8; no repetir APK ni hash.
