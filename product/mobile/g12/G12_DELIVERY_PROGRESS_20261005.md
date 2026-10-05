# G12 — recuperación durable 2026-10-05

OBJETIVO: cerrar la entrega Android TEST_ONLY y continuar el despliegue sintético autorizado. No declarar comercialización antes de sus gates.

AUTORIDAD — VERIFICADO: rama `product/mobile-g12-renewable-session-jobs-20261002`, PR78. APK fuente e2c9b0a4404ebdd3d821abc7d9672f547f43f357; harness nativo 76c018fc77c0e5b7b572c07e2c4fd95e2c88ba11. MOBILE_PRODUCT_HEAD v11 conservado; main científico no modificado.

DATOS — VERIFICADO: APK 0.12.2+14, 146666937 bytes, SHA-256 b6250899380e781e0d5b38667d5a6e6f3660cfb458032589c0bc60cbb094ddc4. ZIP11323449351: 71248486 bytes, SHA-256 7a5d1bd630c8f654f4bb2ef2b4a4eebe84a54684677a8857090d900aa33eb0be. Descarga y rehash local completos; firma debug, sin distribución de producción.

RESULTADOS VERIFICADOS: build/análisis CI37259618369 job111603900084 PASS; 57/57 Flutter, 7/7 Worker G12 y 1/1 paridad G9. Baseline causal de cuatro defectos reutilizado porque cliente/regresión no cambiaron. No se repite G1–G9.

PROBLEMAS Y CAUSA RAÍZ — VERIFICADO: emulator CI37259618369 instaló el mismo APK pero Pixel Launcher ANR tapó la app; captura y XML conservados, artifact11323354822 hash8a52c568f36f1ac70242eaca239f38fe28ecbc8553bc285df0c08c62b251ddaa. CI37307731966 superó esa interferencia y llegó a sesión; falló lectura XML de etiquetas, artifact11344790591 hashe516d733c3342a983138ed3397c74dfd651e7e99ba0d1a51bfb862717ed17c95.

CORRECCIÓN DEL DIAGNÓSTICO: NAF=true y text/content-desc vacíos no bastan para declarar etiqueta inaccesible: el volcado no contiene hintText. La inferencia anterior se retira mientras el probe nativo comprueba hintText, editabilidad, acción SET_TEXT y protección password. Expectativas de etiquetas no reducidas. APK no recompilada para este cambio del harness.

TRABAJO ACTIVO: CI37308747783 prueba nativa sobre APK exacta 0.12.2. No hay trabajo científico en segundo plano.

CLOUDFLARE — VERIFICADO: API autorizada 200 mediante secrets existentes en CI37258559675; token no expuesto ni permisos ampliados. Preparación CI37259435859 PASS y ZIP11323833304 rehash local PASS; canary PASS_LOCAL_PROTOCOL_ONLY. Despliegue SKIPPED.

URL HTTPS REAL G12 — NO DISPONIBLE: no desplegado. G9 previo se conserva, no se inventa equivalencia con G12.

GATES: plan Free actual NO DISPONIBLE; endpoint suscripciones API403 por token mínimo y navegador con error de verificación persistente tras una recarga. Se necesita una confirmación actual de Workers Free en la misma cuenta; no un token nuevo. Entonces registrar cost_gate.json REPORTADO con vigencia de una hora y ejecutar deploy + canary externo Node/Python. Pairing físico G12 NOT_RUN; G9 físico sigue REPORTADO previo, sin repetirlo.

ESTADO CIENTÍFICO — VERIFICADO EN ESTE DELTA: sin main, PnL, holdout, GA2, MT5, broker o trading; cero servicios de pago activados. G12 sólo hash de integridad sintético, no firma independiente ni custodia externa. Rekor G9 permanece como evidencia de transparencia histórica.

IMPACTO PORTAFOLIO: ninguno medido ni autorizado. COMERCIALIZACIÓN — NO DISPONIBLE: faltan backend real autenticado, firma/custodia de producción y piloto según contrato; no se promueven estados científicos.

SIGUIENTE ACCIÓN EXACTA: inspeccionar CI37308747783, verificar APK instalado y evidencia nativa, persistir resultado; después resolver únicamente el plan Free actual y desplegar vía preparada.

INCIDENTE DE MATERIALIZACIÓN: handoff/verify_import.py sobre checkout parcial falló por ausencia local de HANDOFF_MANIFEST.sha256; manifiesto/anchor existen remotamente. No se declara baseline local íntegro; no invalida bytes de APK y CI móviles verificados.
