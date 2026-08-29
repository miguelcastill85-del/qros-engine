# Decisión sobre skill para construir QROS ENGINE

## Decisión

NO hacer que una skill sea requisito para construir o ejecutar el software.
SÍ crear posteriormente una skill ligera `qros-engine-builder` como capa de gobernanza de ingeniería.

## Motivo

La fuente de verdad debe ser el repositorio versionado: especificaciones, schemas, tests, golden ledgers, hashes y receipts. Una skill es útil para recordar el workflow y obligar a ejecutar gates, pero no debe contener semántica exclusiva ni ser capaz de cambiar reglas científicas por sí sola.

## Responsabilidades permitidas de la skill

- reconstruir HEAD/checkpoint verificable;
- leer las specs del repo antes de modificar código;
- ejecutar build/test/sanitizer/parity/benchmark;
- impedir promoción si cambia un golden ledger no autorizado;
- mantener CHANGELOG, manifests y hashes;
- seleccionar el siguiente cuello de botella por profiler;
- producir código completo y reproducible;
- registrar causa raíz de fallos.

## Responsabilidades prohibidas

- definir por sí sola Bid/Ask, SL/TP, timezone, holdout o gates;
- reemplazar specs/versiones por memoria conversacional;
- aceptar diferencias de ledger para ganar velocidad;
- usar latest/glob como autoridad;
- ocultar fallos del compilador/test suite;
- descargar dependencias o activar servicios de pago sin necesidad/consentimiento.

## Cuándo crearla

Después de congelar `QROS_ENGINE_CONTRACT_v1` y el primer corpus golden real XAU/NDX. Crear la skill antes puede cristalizar errores de arquitectura todavía no descubiertos.
