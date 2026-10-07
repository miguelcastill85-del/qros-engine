# G12 — checkpoint durable V8, 2026-10-07

## OBJETIVO
VERIFICADO: continuar los gates pendientes de QROS Mobile, conservar evidencia válida y preparar la aceptación externa sin abrir trading ni recursos de pago.

## AUTORIDAD
VERIFICADO: rama canónica `product/mobile-g12-renewable-session-jobs-20261002`, PR78 draft con base G10. Fuente de aplicación `463e68af09c2dc9c689160284b70d6fb7458148e`, tree `201813da0f6e0390f894cb233b03e4a996beba88`; padre de este checkpoint `39f36e61c331cba71c6acf16986735d1bc6652fe`. Recuperación desde a0c4da5da2856c0139f175ef6ead91932fc44507 y checkpoint intermedio aab8ed5d508508e1bd62380b5a58fb3e705a58f7. MOBILE_PRODUCT_HEAD v11 sin promoción.

## DATOS
VERIFICADO: APK0.12.4+16 TEST_ONLY, 146668513 bytes, SHA-256 `8093b987a939bd642bdefb5442290fe3db79c0d48f681da99882c7c38c98d7da`. Recibo fuente 690 bytes SHA `1d6f8cc0875fe27d3643d945cd1477845fd739aff9f70107b968caf5f2b740b2`. Recibos0.12.3 y su Rekor preservados con limitación de acuse de revocación documentada.

## TRABAJO EJECUTADO
VERIFICADO: ocho pruebas nuevas de transporte Dart y seis de autenticación real workerd; defecto de revocación reproducido antes de corregirlo. Cliente exige exactamente {"status":"revoked"}; acuse inválido conserva advertencia y elimina sesión local. Binario nuevo compilado sólo por esa corrección real; transferencia de artefacto original dividida y reensamblada sin recompilar. Nueva inclusión Rekor para hash nuevo. Filtro/guard de CI corregido tras activación de una compilación duplicada por metadata.

## RESULTADOS VERIFICADOS
VERIFICADO: CI37619093151 PASS: Flutter59/59, analyze0, Worker7/7, paridad G9 1/1 y cuatro defectos del padre congelado reproducidos. CI37619093177 PASS: transporte8/8 y autenticación6/6. Certificado autofirmado con mismo hostname fijado rechazado antes de peticiones de aplicación; desconexión, redirects, MIME/UTF-8/JSON inválidos, >65536bytes y sesión manipulada fallan cerrado. Expiración access15min y refresh30d con reloj controlado; tenant/proyecto/campaña cruzados tras reinicio rechazados; GET no adelanta jobs. Son pruebas locales/loopback, no aceptación pública. Android35 instala exactamente el hash8093… y verifica interfaz nativa, enfoque/set/clear sintético, contraseña y bootstrap vacío; no es teléfono físico.

VERIFICADO: ZIP original71253986 bytes SHA5ad5ff2c7a68dc27e2c1e6bb359ed6ae76678d75cf71f7cd863dca936ede0674 y APK completos rehasheados localmente; todos los miembros Android referenciados y PNG comprobados. Inspección estática sin bloques PEM privados en APK: prueba acotada, no ausencia universal de secretos. Firma APK DEBUG, no producción.

VERIFICADO: Sigstore CI37620989068 PASS Cosign3.1.3/Python4.5.0 con raíces TUF, identidad GitHub OIDC y commit802863d049c3a45c59d442faefeb60ae1289586b; rechazos de alteración, identidad y commit falsos. Lectura HTTPS externa Rekor guardada y cuerpo exacto verificado; auditoría local independiente SHA/ECDSA/inclusión Merkle PASS. Índice público3131046344 (índice de hoja shard3009142082). Publicado sólo hash de recibo sintético. No acredita custodia independiente de claves/backend.

VERIFICADO: CI37621609252 confirma source/recipe/artefacto iguales y reutiliza build válido; build/emulador skipped con recibo auditable. Duplicado37620988935 cancelado. Cero runs en progreso/en cola observados en rama al cierre.

## URL HTTPS REAL, SI SE DESPLEGÓ
NO DISPONIBLE: no despliegue G12 actual ni respuesta pública G12 verificada. Historia G9 no se reclasifica como G12.

## GATES
| Gate | Clasificación | Estado |
|---|---|---|
| Cliente corregido y regresiones | VERIFICADO | PASS APK0.12.4 |
| Transporte TLS/autenticación local | VERIFICADO | 14/14 PASS |
| Android35 | VERIFICADO | Emulador PASS |
| Hash externo GitHub OIDC/Rekor | VERIFICADO | PASS índice3131046344 |
| Cloudflare credencial actual | VERIFICADO | Último preflight HTTP401/error10000; bloqueado |
| Workers Free actual | NO DISPONIBLE | Requiere hecho actual del usuario/proveedor |
| HTTPS público G12 + aceptación física0.12.4 | NO DISPONIBLE | NOT_RUN |
| Firma de producción / custodia independiente | NO DISPONIBLE | Pendientes |
| Commercial_ready | VERIFICADO | false |

## PROBLEMAS Y CAUSA RAÍZ
VERIFICADO: revoke descartaba cuerpo; CI de metadata disparaba build por glob amplio; descarga original supera límite32MiB del canal. VERIFICADO: credencial proveedor rechazada HTTP401. INFERIDO: posible expiración por fecha de screenshot5oct; causa precisa de token NO DISPONIBLE.

## CORRECCIONES
VERIFICADO: validación estricta de acuse, nuevo APK0.12.4, tests positivos/negativos con expectativa original; transferencia en cinco partes verificadas; filtro reducido y guard de igualdad fail-closed; duplicado cancelado. Renovación del secreto aún requiere usuario autenticado; no se repite preflight fallido sin cambio.

## ESTADO CIENTÍFICO
VERIFICADO: main lectura 4ee8a528b5af6109f6cc6fa7a4dea4fee639c828 sin modificar; pointer histórico V259 preservado, MOBILE_PRODUCT_HEAD v11 intacto. PnL/holdout/GA2/MT5/trading cerrados, economic_tests0. Import local incompleto por HANDOFF_MANIFEST ausente sólo en checkout parcial; no es PASS científico.

## IMPACTO PORTAFOLIO
VERIFICADO: ninguna orden, prueba económica ni servicio de pago activado. INFERIDO: evidencia adicional reduce incertidumbre de ingeniería; no demuestra rentabilidad ni habilita comercialización.

## APK O ARCHIVOS DESCARGABLES
VERIFICADO: nueva APK, ZIP Android35 y ZIP Sigstore/Rekor guardados y bytes auditados; IDs durables en G12_CURRENT_CHECKPOINT.json. No desinstalar la app existente sin exportar borradores locales. La nueva APK conserva etiqueta TEST_ONLY y firma DEBUG.

## COMMIT, PR Y CI
VERIFICADO: fix463e68af09c2dc9c689160284b70d6fb7458148e; transferencia5fed58b36d642eb9bdc93632ea6995112fd19433; firma802863d049c3a45c59d442faefeb60ae1289586b; guard39f36e61c331cba71c6acf16986735d1bc6652fe. PR78 sigue draft, base producto G10. CI válidos37619093151/37619093177/37620278083/37620989068/37621609252. Baseline fallido37618534076 preservado.

## SIGUIENTE ACCIÓN AUTOMÁTICA
NO DISPONIBLE: intervención indispensable del usuario para reemplazar CLOUDFLARE_API_TOKEN en el secreto existente y confirmar Workers Free actual, sin enviar el token al chat. Después: UN preflight sólo lectura; refrescar cost gate <=1h; desplegar Worker ya validado; Node/Python HTTPS externo; bootstrap de un uso; aceptación física de APK0.12.4 y firma de producción según gates. No recompilar APK ni republicar su hash mientras sus inputs no cambien.
