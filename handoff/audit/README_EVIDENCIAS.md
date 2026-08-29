# Evidencias de auditoría de QROS ENGINE v0.6

Fecha: 2026-08-28. Alcance: auditoría de software, sin modificar la entrega.

**ESTE PAQUETE NO ES UN HEAD CIENTÍFICO NI UNA APROBACIÓN.**

Todos los ticks y trades de `synthetic_probes/` son sintéticos. Los archivos
`claimed_external/` y `supergate/` contienen intencionalmente texto que NO es
evidencia MT5, OOS, holdout o Supergate válida. Existen para comprobar los
verificadores. Nunca deben promocionarse ni interpretarse como ejecuciones reales.

## Contenido

- `AUDITORIA.md`: informe, prioridades, limitaciones y referencias primarias.
- `reproduce_audit.py`: harness que regenera fixtures en un directorio nuevo.
- `synthetic_probes/AUDIT_PROOFS.json`: ocho hallazgos/brechas y 17 invocaciones,
  con hashes de logs y del binario. Incluye las comprobaciones de integridad de
  los 167 archivos originales antes y después de las pruebas.
- `static_analysis/`: resultados parciales GCC 13.3, logs y control mínimo de
  `std::deque`. No es una certificación C++ ni prueba de vulnerabilidad confirmada.
- `AUDIT_SCOPE.json`: alcance y límites de esta entrega de auditoría.
- `MANIFEST.sha256` y `MANIFEST.sha256.sha256`: integridad del payload sin
  autorreferencia.

## Reproducir las pruebas dirigidas

Se necesitan el ZIP v0.6 original, su árbol extraído y Python 3 para el harness.
El motor es el ELF Linux x86-64 estático del paquete v0.6. El harness invoca ese
motor con PATH vacío; no cambia sus fuentes ni su binario.

```bash
python3 reproduce_audit.py \
  --project /ruta/absoluta/QROS_ENGINE_v0_6 \
  --archive /ruta/absoluta/QROS_ENGINE_v0_6_SOFTWARE_20260828_R1.zip \
  --out /ruta/absoluta/auditoria-nueva
```

`--out` no puede existir. No uses los ticks reales ni un directorio de resultados
científicos. El harness construye sus propias cotizaciones y permisos ficticios.

El resultado esperado sobre v0.6 es **FINDING_REPRODUCED/GAP_CONFIRMED**. Eso NO
significa que el engine apruebe un gate de calidad: significa que el problema o
límite descrito se reproduce. Para una corrección futura, los casos pertinentes
deben incorporarse a la suite existente con la expectativa corregida. No usar
este harness sin adaptar como gate de promoción de una versión nueva.

Las marcas de tiempo, expiración del permiso sintético, nonces y tiempos de
ejecución cambian entre ejecuciones. Se reproducen las propiedades comprobadas;
no se promete identidad byte a byte de todos los archivos de una nueva corrida.

## Análisis estático

Los comandos exactos y hashes están en `ANALYZER_REPORT.json` y
`CONTROL_REPORT.json`. El primer informe cubre sólo cuatro unidades de traducción.
`universe.cpp` alcanzó el límite de 35 segundos y fue detenido; su resultado es
inconcluso. No se han ocultado advertencias. La documentación de GCC 13.3/14.2
declara su analizador adecuado sólo para C; véase el informe antes de interpretar
sus resultados sobre C++.

## Reanudar el trabajo

Última base: v0.6, SHA del binario
`6835ab7e0bfd94019f67edbd15d5e0c9b2ada9c32f6c261e109cdac22ca28f79`.

Siguiente trabajo propuesto: correcciones de contrato de instrumento y de
verificadores, seguidas de aislamiento de holdout, IR/estados y corpus golden.
Esta auditoría no cambia reglas de estrategia, datasets, multiplicidad o gates.
No deja procesos en segundo plano.
