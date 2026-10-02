# G10 — preparación comercial, checkpoint 1
Fecha: 2026-09-30. Padre: cb6ea5426b92769cb8fb32d5f54be4f9ef871ad5.
La orden del usuario autoriza desarrollar la app para comercializar. No elimina las restricciones de costo, seguridad, datos ni autoridad científica.

## Delta implementado
Respaldo JSON y recuperación voluntaria de proyectos de borrador desde Evidencias. Importación atómica, idempotente, campos permitidos, límites de tamaño/cantidad y estados exclusivamente locales. No exporta muestra, credenciales ni recibos; contiene los textos del usuario sin cifrar. No incluye todavía los contratos del editor de universos ni guardado automático.

## Gates concretos restantes para el producto contratado
1. Persistencia cifrada automática de proyectos y universos; edición/borrado, recuperación y migración.
2. Identidad de cliente y sesión renovable: el token de un uso y 299 segundos es un ensayo, no onboarding comercial.
3. Backend de trabajos sintéticos reanudables integrado al móvil; el snapshot G9 fijo no ejecuta investigación solicitada por clientes. El despliegue C++20 requiere capacidad gratuita comprobada, no se presume que Workers ejecute el servidor Python o binario nativo.
4. Autoridad autenticada M2 y testigo dinámico independiente antes de mutaciones científicas. Rekor no sustituye custodia.
5. Firma release custodiada y verificable, instalación/actualizaciones probadas, accesibilidad y errores recuperables.
6. Responsable, canal de soporte, política de privacidad según flujo real de datos y canal de distribución definidos.
7. Piloto con usuarios reales, costos medidos y propuesta de valor contrastada antes de activar suscripciones. Precio, cobro, facturación y soporte no están configurados.
No se afirma producto vendible ni se cobra por una demo.

## Distribución y fuentes oficiales consultadas
- https://support.google.com/googleplay/android-developer/answer/6112435 : registro de Google Play con pago único de US$25; no contratado.
- https://support.google.com/googleplay/android-developer/answer/14151465 : nuevas cuentas personales sujetas a prueba cerrada de 12 testers durante 14 días continuos antes de solicitar producción; tipo/antigüedad de cuenta del operador NO DISPONIBLE.
- https://developer.android.com/studio/publish/app-signing : firma de publicación y custodia de claves.
La distribución directa tampoco se declara exenta de requisitos; se revisará para países/dispositivos objetivo antes de publicar.

## Autoridad y validación
G9 conservado en PR74 draft. G10 es rama descendiente independiente. main, MOBILE_PRODUCT_HEAD v11 y recibos congelados intactos. No PnL/holdout/GA2/MT5/live.
Preflight local verify_import.py falla por HANDOFF_MANIFEST.sha256 ausente en recuperación parcial; limitación preservada. No se ejecuta ni modifica el motor científico.
CI G10 compila APK TEST_ONLY y ejecuta Flutter analyze/regresiones más tests de respaldo y UI. Su resultado debe observarse antes de declarar PASS.
