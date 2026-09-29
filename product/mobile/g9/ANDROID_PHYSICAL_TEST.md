# G9 Android físico — procedimiento y límites de evidencia

La aplicación G9 es TEST_ONLY, sin operaciones económicas. G8 continúa probando
únicamente el antiguo APK G6 en emulador; no demuestra instalación física de G9.
La versión G9 0.9.0+9 fija la raíz Ed25519 y el origen HTTPS en código. El campo de
origen es de solo lectura. El token permanece en memoria y se borra tras cada intento.

## Instalación y arranque (sin credenciales)

1. Descargar `QROS_MOBILE_G9_TEST_ONLY.apk` del artefacto
   `qros-mobile-g9-test-only-android` del run identificado en el checkpoint vigente.
   Extraer el ZIP si se descarga desde GitHub. Comparar tamaño y SHA-256 con
   `QROS_G9_ANDROID_CI_RECEIPT.json` y el checkpoint verificado independientemente.
2. En el Android autorizado, abrir el APK y permitir temporalmente la instalación
   desde esa aplicación de archivos/navegador. No aceptar planes ni servicios.
3. Si Android rechaza la actualización por firma incompatible, detenerse y conservar
   el mensaje. El debug signer puede cambiar entre builds. No desinstalar una versión
   con datos sin antes decidir cómo conservarlos; no presentar ese rechazo como fallo
   criptográfico del recibo.
4. Abrir QROS, entrar en `Verificar snapshot G5 · G9`, comprobar `G9 · TEST_ONLY` y
   el origen fijo `https://qros-mobile-g9-test-only.miguelcastill85.workers.dev`.
5. Sin token, pulsar verificar: debe rechazarse y no mostrar una cadena verificada.
   Registrar versión de Android, versión de app, hora UTC y captura sin información
   personal. Una captura por sí sola se clasifica REPORTADO, no prueba física completa.

## Prueba HTTPS autenticada (pendiente de entrega segura de token efímero)

El token de Cloudflare/GitHub nunca se introduce en la app. El token QROS es distinto,
scoped a tenant_A/project_A/campaign_A, `demo:read`, de un solo uso y como máximo
300 segundos. Los grants del canary anterior fueron borrados. No reutilizar tokens
antiguos, no enviarlos por chat ni almacenarlos en APK, URL, logs o capturas.

1. Preparar con el operador un canal seguro de entrega y una ventana de prueba;
   emitir el token solo cuando el teléfono esté listo. Esta entrega aún no está validada.
2. Introducir el token en el campo oculto y verificar una vez.
3. Debe mostrar tenant_A/project_A/campaign_A, secuencia 1, dos filas y TEST_ONLY.
4. Intentar reutilizar ese mismo token: rechazo (el backend devuelve 409, la UI muestra
   un error genérico). El campo se borra después de cada intento.
5. Con un token nuevo, desconectar la red e intentar verificar: error y ausencia de un
   resultado verificado nuevo. Reconectar después; no inferir éxito de una captura vieja.
6. Con ADB autorizado o un verificador independiente, recoger SHA-256 del APK instalado,
   certificado de firma, versión Android y evidencia de ejecución. Cruzar el recibo con
   los bytes HTTPS y la raíz fijada; no incluir identificadores personales ni tokens.

No hay herramienta de emparejamiento/control del teléfono físico disponible en esta
sesión. Instalación física y recepción autenticada en ese teléfono permanecen NOT_RUN.
Una prueba de emulador no cambia esos estados. La app no exporta todavía un recibo
forense automático del dispositivo: el procedimiento no debe afirmar que lo hace.
