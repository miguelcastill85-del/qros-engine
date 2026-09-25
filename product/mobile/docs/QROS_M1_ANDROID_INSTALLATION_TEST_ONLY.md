# QROS Mobile M1 — Instalación Android TEST_ONLY

**Versión**: M1 / Flutter 3.35.4 / Android debug. Solo datos sintéticos. Archivo `QROS_MOBILE_ANDROID_M1_TEST_ONLY.apk`, 141575502 bytes. SHA-256:

`106dfeceb971d26655e93d2d3d87361a96ca321af9233df66593006b4fa74f2d`

**Procedencia**: GitHub Actions privado, ejecución `36095871557`, commit `4d8d70e5ebb8bfdefaddd2be188b75659ad4c824`. Pruebas: 23/23 backend, 13/13 Flutter, análisis estático sin incidencias. El ZIP fuente y el APK exacto también están disponibles como archivos de la conversación; la retención del artifact GitHub expira el 30 de septiembre de 2026.

## Cómo instalar

1. Descarga el APK M1 desde esta conversación a tu móvil Android, preferiblemente sin reenviarlo a terceros.
2. En **Archivos/Descargas**, pulsa el APK. Si Android pregunta, autoriza temporalmente la instalación desde esa aplicación.
3. Si ya instalaste QROS M0 y Android rechaza M1 por firma incompatible, desinstala la versión M0 e instala M1. Los borradores de M0 solo vivían en memoria y no se habían guardado en una cuenta ni en el servidor. No hagas esto si introdujiste información que no deseas perder sin verificar tu dispositivo.
4. Tras instalar, revoca el permiso temporal de instalación externa si lo activaste.
5. Abre QROS Mobile. La navegación **Inicio / Proyectos / Historial / Seguridad** funciona offline; los proyectos son una fixture ficticia y tus nuevos borradores permanecen solo en memoria.
6. En **Seguridad → Consultar demo firmada** está la interfaz HTTPS con token temporal. Por seguridad, **no hay un servidor HTTPS público configurado todavía**; no introduzcas claves de MT5/Darwinex ni tus contraseñas reales. Esta pantalla todavía no puede completar una consulta remota desde tu teléfono.

## Qué NO demuestra esta versión

No prueba todavía instalación real en tu modelo de Android, rendimiento del teléfono, funcionamiento de un gateway público HTTPS, rentabilidad, estrategias reales, ni trading automático. El JSON firmado de demostración solo certifica la procedencia de datos **TEST_ONLY**.

La siguiente fase debe completar un canal HTTPS autenticado de pruebas, ancla externa dinámica independiente y pruebas con un dispositivo Android real, manteniendo en todo momento los controles científicos de QROS/RISE.
