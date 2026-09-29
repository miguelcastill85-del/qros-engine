# G9 — cierre del checkpoint TEST_ONLY, 2026-09-29

## Objetivo y autoridad
Conectar QROS Mobile a HTTPS sintético autenticado y conservar evidencia auditable. VERIFICADO: rama de producto product/mobile-g9-cloudflare-android-20260926; PR #74 contra product/mobile-g8-emulator-runtime-20260925. MOBILE_PRODUCT_HEAD v11 y genealogía G1–G8 se conservan. Este cierre documental no promueve autoridad.

## Datos y trabajo ejecutado
VERIFICADO: Worker HTTPS, raíz pública fijada fuera de la respuesta, destino exacto del bearer, acceso por tenant/proyecto/campaña, expiración, replay atómico, cuota, CORS restrictivo y fallos cerrados. Paridad Worker/Python/Dart y controles negativos constan en recibos previos.
VERIFICADO: APK 0.9.0+9, 141624110 bytes, SHA-256 60107772a5b60f63a2b7e5d5ec24452ca9a52b05c886fcf15c8e859135074b01.
Fuente Android probada: fe0a850719fe54b283b2152a56d95e749a863e02.
VERIFICADO: 30 pruebas Flutter, análisis limpio e instalación/arranque/renderizado en emulador Android 35.

## URL HTTPS real
https://qros-mobile-g9-test-only.miguelcastill85.workers.dev/v1/demo-snapshot
VERIFICADO previamente mediante canary autenticado y consulta HTTPS externa sin credenciales (401). No se emite ni renueva acceso con este cierre.

## Teléfono físico
VERIFICADO en captura: CADENA SINTÉTICA VERIFICADA; tenant_A/project_A/campaign_A, dos filas, secuencia 1.
VERIFICADO en segunda captura: rechazo antes de caducar la ventana.
REPORTADO: ejecución en teléfono, misma APK entregada, eliminación de QROS_G9_PHONE_TOKEN y cierre del generador.
INFERIDO: conexión autenticada física y rechazo por replay a partir de evidencias correlacionadas; el error genérico no revela HTTP409.
NO DISPONIBLE: medición independiente del SHA de la APK instalada e identidad del dispositivo.
No se repite la prueba funcional ya completada.

## Testigo externo
VERIFICADO: Sigstore/Rekor, run 36564211889, Cosign y sigstore-python con identidad e issuer exactos; negativos de sujeto alterado/identidad incorrecta; lectura pública externa coincidente.
Índice Rekor: 2999110427. Se publicó el hash del recibo sintético congelado, no secretos.
NO DISPONIBLE: custodia independiente de las claves del backend. Transparencia pública no equivale a custodia independiente.

## Gates y límites
VERIFICADO: ingeniería HTTPS/paridad, pruebas de autenticación y firmas, APK/emulador, evidencia pública Rekor.
VERIFICADO: captura positiva y negativa del operador; alcance limitado descrito arriba.
NO DISPONIBLE: firma release de producción, OIDC de producción y custodia independiente. APK debug TEST_ONLY; secuencia sintética fija.
REPORTADO: Workers Free. No se contrataron planes de pago mediante estas acciones; no se certifica la facturación global de las cuentas.

## Problemas, causas y correcciones
VERIFICADO: incidentes Android de fixture/ruta/canonicalización corregidos y conservados en ANDROID_RECOVERY_20260929.json.
VERIFICADO: instalador Cosign antiguo buscaba .sig retirado; corregido con instalador oficial compatible con bundles, sin desactivar verificación.
REPORTADO: copia del token fallaba en el teléfono; causa exacta NO DISPONIBLE. Se añadió campo seleccionable y vías de copia alternativas. Posterior secreto guardado y prueba positiva respaldan la recuperación funcional, sin probar qué vía de copia utilizó.
VERIFICADO: ventana limitada a 299 segundos; artefacto descargado y SHA comprobado. Limpieza del secreto REPORTADA.

## Estado científico e impacto portafolio
VERIFICADO respecto de este trabajo: ninguna modificación de main científico, ningún PnL, holdout, GA2, MT5 ni trading real. Impacto económico del portafolio: ninguno demostrado. No hay promoción científica ni aprobación de producción.

## Archivos y trazabilidad
- APK: artefacto Android 11009517002, run 36512616737.
- Canary: run 36486469141.
- Paridad: run 36512616736; último automático 36628359094 SUCCESS.
- Sigstore: run 36564211889; SIGSTORE_VERIFIED_20260929.json y ZIP base64 durable.
- Teléfono: run 36628359102 SUCCESS; PHONE_WINDOW_36628359102.json y ZIP base64, SHA 4048a648aeb74cbc7be832937e1942cb7246c3fd939824cba75bc3811f45865c.
- Capturas: PHYSICAL_AUTHENTICATED_SCREEN_20260929.json y PHYSICAL_REUSE_SCREEN_20260929.json conservan hashes y observaciones; imágenes personales no publicadas.
- Limpieza: PHONE_CLEANUP_20260929.json.
- Checkpoint: receipts/G9_CURRENT_CHECKPOINT.json.
- PR: https://github.com/miguelcastill85-del/qros-engine/pull/74

## Siguiente acción
Revisión del cierre TEST_ONLY en PR #74. Se conserva el PR abierto como borrador contra G8; no se fusiona ni se modifica main. No quedan ejecuciones automáticas necesarias para este cierre documental. Las garantías de producción pendientes requieren trabajo y evidencia separados.
