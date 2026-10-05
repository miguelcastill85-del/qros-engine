# QROS Mobile — checkpoint 2026-10-05

OBJETIVO — VERIFICADO: continuar Android y backend sintético sin repetir G1–G9 válidos, sin servicios de pago ni acciones científicas.

AUTORIDAD — VERIFICADO: rama `product/mobile-g12-renewable-session-jobs-20261002`, PR78 draft sobre producto G10. Fuente de app `e7c365f7c951e74073e11a21fe876164c6ce2237`; preparación de despliegue a834bc71d3d3659ba9d50739a9ccacce16e8b366. MOBILE_PRODUCT_HEAD v11 se conserva sin promoción. Main observado 4ee8a528b5af6109f6cc6fa7a4dea4fee639c828, pointer V259; no se modifica.

DATOS — VERIFICADO: sólo fixtures sintéticos. APK 0.12.3+15, 146668121 bytes, SHA-256 `8bf45b7a13d519866d91dcfe72592a5e5cd5933a63a9025a96207f94895be456`; firma debug, no firma de producción.

TRABAJO EJECUTADO — VERIFICADO: fijado origen independiente antes de crear transporte; regresiones de servidor falso y sesión almacenada con origen sustituido. Se eliminaron etiquetas nativas duplicadas, se verificó escritura y limpieza con una cadena pública de prueba, y se ligó el origen derivado del proveedor al origen fijado en Dart antes de cualquier despliegue.

RESULTADOS VERIFICADOS — VERIFICADO: CI37310065707 PASS; Flutter 59/59, análisis cero problemas, Worker 7/7 y paridad G9 1/1. Instalación real en emulador Android35, hash instalado igual a APK descargada; etiquetas nativas únicas, bootstrap protegido, campos editables tras foco y vacíos tras limpiar, bootstrap vacío rechazado. Evidencia descargada y rehash independiente PASS. No constituye prueba física.

URL HTTPS REAL G12 — NO DISPONIBLE: no desplegado. El hostname fijado es configuración candidata; no demuestra una respuesta externa. G9 conserva su recibo histórico de HTTPS; no se vuelve a ejecutar ni se extiende su garantía a G12.

GATES — VERIFICADO: preparación CI37310731342 PASS, 75 comprobaciones locales del canary; job de despliegue SKIPPED. NO DISPONIBLE: plan Workers Free actual, HTTPS externo G12, emparejamiento/Android físico G12, firma Android de producción, custodia externa del backend y lanzamiento comercial. Sigstore del nuevo hash pendiente; G9 histórico permanece válido.

PROBLEMAS Y CAUSA RAÍZ — VERIFICADO: Pixel Launcher ANR en infraestructura; recuperado de forma acotada sólo cuando el diálogo observado es de Launcher. Parser SDK no admitía android-35-ext18; corregido y construido. XML omite hintText: se RETIRA la inferencia de etiquetas nativas ausentes, refutada por instrumentación. Los wrappers añadidos duplicaban etiquetas; retirados. Origen HTTPS arbitrario aceptado por gateway: corregido antes de transporte. API de plan devuelve403 por permisos mínimos; navegador bloqueado por verificación aun tras una recarga.

CORRECCIONES — VERIFICADO: incidencias y sus ejecuciones fallidas preservadas en JSON. Las regresiones afectan sólo móvil y su preparación. Se conserva APK0.12.2 como historia, no como entrega actual. Import local del baseline falla por manifiesto ausente en checkout parcial; no se declara import completo ni aprobación científica.

ESTADO CIENTÍFICO — VERIFICADO: main intacto; holdout y GA2 cerrados, cero pruebas económicas, sin MT5/trading/broker. PASS de ingeniería no otorga autoridad científica.

IMPACTO PORTAFOLIO — NO DISPONIBLE: no medido; no se accede a PnL ni se activan operaciones.

APK O ARCHIVOS — VERIFICADO: APK y ZIP de evidencia Android35 guardados; bytes y hashes en G12_CURRENT_CHECKPOINT.json y recibos nuevos. La instalación física G9 previa sigue REPORTADO por usuario y no sustituye la prueba de esta APK.

COMMIT, PR Y CI — VERIFICADO: fuente e7c365f7c951e74073e11a21fe876164c6ce2237; PR https://github.com/miguelcastill85-del/qros-engine/pull/78; build/runtime https://github.com/miguelcastill85-del/qros-engine/actions/runs/37310065707; preparación https://github.com/miguelcastill85-del/qros-engine/actions/runs/37310731342. Checkpoint de evidencia posterior y sin rebuild.

SIGUIENTE ACCIÓN AUTOMÁTICA — hash público del recibo0.12.3 mediante identidad GitHub Actions; verificar Cosign y Python y persistir. Para desplegar, confirmar Workers Free actual en la misma cuenta, guardar fecha/ventana de una hora en cost_gate.json y ejecutar el guard; verificar HTTPS real antes de emparejar el teléfono. No reiniciar los CIs completados.
