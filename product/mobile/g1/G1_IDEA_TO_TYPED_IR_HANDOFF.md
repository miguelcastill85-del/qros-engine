# QROS Mobile G1 — actualización funcional Idea → IR tipado → universo sintético

Classification: TEST_ONLY / DEVELOPMENT_RUNNING. Product scope: Android mobile; backend Python oracle is **infrastructure**, not desktop software. Exact base: design branch commit `809ddd3f6696177e3c20abaa7094ab94d0df748a`, mobile verified M1 commit `3bb3ebf843e61fd5722664310a9907745f556ae7`.

## Qué cambia en la app
- Navegación móvil Inicio, Hipótesis, Fábrica, Evidencias y Portafolio; Proyectos/Historial/Seguridad heredados están en el menú superior sin perder su funcionalidad.
- Hypothesis Studio: texto de tesis separado del IR no congelado; ejes tipados visibles y editables de contexto, señal, BUY/SELL, M5/M15, stop racional y salida.
- Previsualización real del producto cartesiano con validación de 144 nacimientos sintácticos para el ejemplo completo (no 144 estrategias viables). La Fábrica muestra el último borrador y su SHA-256, y permite exportar únicamente JSON de prueba.
- Portafolio es una pantalla honesta explícitamente pendiente: cero módulos aprobados, cero asignación de riesgo.
- Los mecanismos heredados de lectura de demostraciones firmadas de M1 se conservan y se someten a regresión.

## Núcleo reproducible G1
- `UniverseBlueprint` en Dart y `universe_contract.py` en Python: implementaciones independientes del esquema `QROS_TYPED_UNIVERSE_DRAFT_V1`.
- Ordenación canónica de mapas y dominios, SHA-256 y enumeración explícita del corpus sintético 144. La fixture JSON se genera en Python **antes** de ejecutar los tests Dart y queda versionada.
- Contrato futuro deriva nombres del verdadero `include/qros/research_contract.hpp` de QROS; IDs de dataset/ejecución/firmas y programHash permanecen `null` hasta que se verifiquen los bytes. Tesis libre se mantiene fuera del hash sintáctico porque todavía falta definir normalización Unicode y firma humana; por ello no existe capacidad de congelación científica.
- Rechazo temprano de símbolos no sintéticos, dominios vacíos/duplicados, valores ilegales, velas actuales/futuras, overnight, más de 3 entradas/día y esquemas con campos privilegio en backend.
- La enumeración local v1 está limitada a 10.000 sintaxis y solo cuenta IDs; millones de combinaciones requieren G2+G4 con streams/chunking, benchmark y datos autorizados.

## Limitaciones y gates
- Sin conexión a ticks ni al motor C++20 de ejecución. No se simula PnL, M1 sigue siendo firma sobre fixture de prueba, no recibo de investigación real.
- El título y tesis se conservan exclusivamente en la sesión en RAM; no existe persistencia cifrada ni restauración tras cierre, ni un sistema de equipos o cuotas comercial. La firma que ve el móvil no concede autoridad científica.
- El análisis sintáctico no demuestra equivalencia semántica ni cierre del universo causal real. Los filtros arbitrarios, editor libre de gramática, plugin SDK, recursos de clientes y optimizadores quedan fuera de G1.

## Siguiente gate
Una vez superada la CI Android y backend: G2 enumeración de universos finitos y dedupe independiente sobre varias ontologías; G3 conexión con motor sintético exacto; infraestructura TLS/testigo externo con autorización independiente antes de datos reales o mutaciones remotas. No ejecutar los 50 shards pendientes del main científico.
