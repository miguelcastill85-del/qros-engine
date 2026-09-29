**OBJETIVO — VERIFICADO PARCIAL.** Cerrar la integración de ingeniería TEST_ONLY entre Cloudflare y Android; quedan gates físicos y de transparencia pública.

**AUTORIDAD — VERIFICADO.** Repositorio miguelcastill85-del/qros-engine; rama product/mobile-g9-cloudflare-android-20260926; PR 74 contra G8. Código probado fe0a850719fe54b283b2152a56d95e749a863e02. MOBILE_PRODUCT_HEAD v11 y recibos G1–G8 preservados. No promoción científica ni merge.

**DATOS — VERIFICADO.** Solo recibos sintéticos tenant_A/project_A/campaign_A, secuencia 1. Clave pública Ed25519 fijada fuera de la respuesta; custodia de firma del mismo operador. No se presenta como custodia independiente. Workers Free: REPORTADO por el usuario; no activación de servicios pagados en este trabajo.

**TRABAJO EJECUTADO — VERIFICADO.** Recuperación sin repetir G1–G8; descarga y rehash de la APK previa; fijación estricta del origen antes de crear el cliente HTTP; campo URL de solo lectura; borrado del token tras cada intento; nueva versión 0.9.0+9; CI con instalación del mismo artefacto en emulador Android 35; preservación de incidentes, bytes y recibos.

**RESULTADOS VERIFICADOS.** Flutter analyze: cero incidencias; 30 pruebas aprobadas. Paridad: 25 pruebas Node, una Workerd, oracle Python 1 positiva/3 negativas, 3 regresiones Python G6 y 8 pruebas Dart. Descargados y rehashados ZIP/APK, siete componentes de paridad y PNG/XML del emulador. Captura inspeccionada: QROS y TEST_ONLY visibles; interfaz real, no splash. Verificación Python independiente del recibo del Worker contra la raíz fijada.

**URL HTTPS REAL — VERIFICADO.** https://qros-mobile-g9-test-only.miguelcastill85.workers.dev/v1/demo-snapshot . Canary autenticado 36486469141: éxito firmado 200; controles de scope, expiración, replay/concurrencia, CORS y cuota aprobados. Probe externo 2026-09-29: 401 sin credenciales, TLS validado. Los grants de canary se borraron al finalizar; no hay token de usuario distribuido.

**GATES.** VERIFICADO: firma inválida, payload alterado, origen falso antes de enviar bearer, certificado autofirmado sustituido y desconexión en pruebas controladas, controles sintéticos en Worker vivo, compilación e instalación/arranque/render en emulador. NO DISPONIBLE: instalación física, pairing HTTPS en Android, publicación Rekor, custodia independiente y firma de release. Escaneo de secretos limitado al código y marcadores/archivos de APK; no se declara auditoría universal del proveedor.

**PROBLEMAS Y CAUSA RAÍZ — VERIFICADO.** Intentos anteriores: fixture ausente; salto de línea añadido al transferir JSON canónico; directorio de trabajo incorrecto para Workerd. Además, la app anterior dejaba editar el origen antes de enviar bearer. Identidad de repositorio privado se haría pública con Sigstore. No hay herramienta de control de teléfono expuesta.

**CORRECCIONES — VERIFICADO.** Regeneración exacta desde raíz del repositorio, conservación de fallos, pin estricto de origen con regresión que exige cero creación de clientes ante sustitución, limpieza del token y nueva APK. La compilación válida anterior no se borró ni se confundió con la final.

**ESTADO CIENTÍFICO — VERIFICADO.** Main consultado en lectura: V259, PREREGISTERED_NO_RESULTS. Sin cambios a main, PnL, holdout, GA2, MT5 ni trading real. Sin backtests económicos nuevos.

**IMPACTO PORTAFOLIO — VERIFICADO.** Ninguna operación de cartera ejecutada. No se infiere rentabilidad ni mejora económica de un PASS de ingeniería.

**APK O ARCHIVOS DESCARGABLES — VERIFICADO.** QROS_MOBILE_G9_TEST_ONLY.apk, 141624110 bytes; SHA-256 60107772a5b60f63a2b7e5d5ec24452ca9a52b05c886fcf15c8e859135074b01. Debug TEST_ONLY. Guía Android, recibos y evidencia del emulador acompañan la entrega. El certificado de firma APK no se extrajo localmente; instalación física aún pendiente.

**COMMIT, PR Y CI — VERIFICADO.** Código: fe0a850719fe54b283b2152a56d95e749a863e02. PR https://github.com/miguelcastill85-del/qros-engine/pull/74, abierto y draft. Android/emulador https://github.com/miguelcastill85-del/qros-engine/actions/runs/36512616737 SUCCESS. Paridad https://github.com/miguelcastill85-del/qros-engine/actions/runs/36512616736 SUCCESS. El commit posterior de checkpoint solo conserva evidencia/documentación y no requiere recompilar.

**SIGUIENTE ACCIÓN AUTOMÁTICA.** Recuperar G9_CURRENT_CHECKPOINT.json y validar evidencia del teléfono cuando el usuario instale la APK; preparar entrega segura de token QROS efímero antes del pairing. Para Rekor se necesita autorización puntual para publicar permanentemente usuario GitHub, nombre del repositorio y ruta/ref del workflow junto con el hash sintético. Nunca publicar código, datos privados, credenciales o claves. Una inclusión Rekor no sustituye custodia independiente ni demuestra ejecución física.

Fuentes de la limitación Sigstore: https://docs.sigstore.dev/quickstart/quickstart-ci/ ; https://docs.sigstore.dev/about/security/ ; https://docs.github.com/en/actions/concepts/security/artifact-attestations . La integración pública está preparada pero no ejecutada ni validada con dos clientes.
