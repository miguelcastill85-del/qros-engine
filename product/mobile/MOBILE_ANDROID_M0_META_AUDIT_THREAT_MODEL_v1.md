# QROS Mobile Android M0 — META-AUDIT y modelo de amenazas v1

Alcance: primer APK Flutter Android TEST_ONLY, datos sintéticos y borradores volátiles. Este documento NO certifica seguridad de producción.

## Límites verificables del prototipo

- Flutter sin dependencias de red en código Dart y sin conexión con brokers, motores QROS, MT5 ni servicios de pago.
- Fixture DEMO-001 declarada SIMULATED_SAMPLE; los proyectos nuevos son LOCAL_DRAFT_NOT_FROZEN y viven solo en memoria.
- Cero mutaciones científicas: no existen transiciones, API ni campos de actor privilegiado en el cliente.
- Cero promesas de rentabilidad, estadísticas económicas reales, recibos autenticados o aprobación automática.
- El APK debug puede incluir permisos de desarrollo de Flutter; no equivale a una release endurecida.

## Riesgos y mitigaciones obligatorias antes de activar conectividad

| Riesgo | Ataque adversarial | Control de salida |
|---|---|---|
| Escalada del móvil | App adulterada envía QROS_CORE, PASS o flags falsos | API admite solo solicitudes tipadas; actor autorizado exclusivamente en el servidor |
| Sustitución de recibos | Resultado fabricado conserva hash propio coherente | Recibos ligados a dataset, programa, build y genealogía; firma/MAC autenticados con gestión de claves de servidor |
| Retroceso del HEAD | El servidor presenta una cadena válida pero truncada | Ancla externa independiente y monotonía; detección fail-closed |
| Fuga de datos | Proyecto o JSON copiado a portapapeles del SO | M0 limita a datos ficticios; en producción consentimiento explícito, contenido acotado y redacción de secretos |
| Mezcla entre clientes | IDs ajenos accesibles por query adivinable | Authn/Authz por recurso, pruebas IDOR y aislamiento de almacenamiento |
| Falsa certificación | Etiquetas PASS o métricas de fixtures parecen económicas | Etiquetas TEST_ONLY visibles, prueba de UI y auditoría de lenguaje |
| Corrupción offline | Borradores desaparecen tras reinicio y se presentan como persistidos | M0 avisa de estado volátil; persistencia cifrada posterior si se acepta |
| APK alterado | Instalación desde una fuente no autorizada | SHA-256 de artefacto, firma de distribución y verificación del origen |
| Dependencia externa | Descarga de paquetes cambia build sin trazabilidad | Fijar versión SDK y registrar lockfiles, SHA de APK y commit exacto |
| Cargos imprevistos | Jobs o cómputo sin límites | CI acotada; no activar facturación, backend ni jobs pesados en M0 |

## GATES

M0-A: Flutter analyze + pruebas modelo/widgets = PASS en runner real.
M0-B: APK debug existe, tamaño y SHA-256 registrados por CI.
M0-C: instalación/prueba Android real o emulador = prueba separada. Un build PASS no equivale a instalación PASS.
M1: autenticación cliente-servidor y autorización server-only; contratos/recibos independientes.
M2 backend: external HEAD durable y semántica de evidencias antes de habilitar backtesting remoto.
COMERCIAL: evaluación de licencia/datos, privacidad y facturación antes de cualquier cliente de pago.

## Invariantes del proyecto

Autoridad científica main y holdout permanecen intactos. Windows-first está archivado y no forma parte del producto comercial móvil. El motor Linux solo es una dependencia futura del móvil.
