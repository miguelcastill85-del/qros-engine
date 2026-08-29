# QROS ENGINE v0.6.0 — desarrollo verificable

Motor nativo **C++20**, descendiente del paquete v0.4 recuperado y verificado. No es una reconstrucción de la fuente v0.5, que no se recuperó.

**Esta entrega ejecuta el flujo de software con datos `TEST_ONLY`. No está terminada ni habilitada para investigación productiva, holdout económico o trading real.** Las capas pendientes no se sustituyen por aprobaciones automáticas.

## Qué incorpora

| Capa | Implementación disponible | Límite actual |
|---|---|---|
| Lenguaje y compilador | DSL declarativo cerrado, comprobación de tipos, DAG e IR con SHA-256 | No ejecuta código arbitrario ni fija la ontología científica del proyecto |
| QDATA | Lectura secuencial CSV5/PACKED17, huellas sobre todos los bytes, sesiones y contratos de shards | No demuestra por sí sola procedencia externa ni cobertura completa del carrier padre |
| Indicadores | 26 operadores, ventanas, EMA entera y OHLC de barras ya cerradas | Exportación de features acotada; no es todavía un almacén masivo indexado |
| Ejecución | Bid/Ask, siguiente registro, SL/TP, BE, trailing, costes y cierre de sesión | Un contrato; slippage fijo adverso; política conservadora explícita |
| Universo y minería | Ejes finitos perezosos, alias, exclusiones causales y N_TESTS bruto | Sólo universos de prueba; recursos y cohortes limitados |
| Resultados | Bloqueo local, fencing, compare-and-swap, bloques inmutables y recuperación | Una máquina y filesystem cooperativo; no un coordinador distribuido |
| Gates | Métricas, BH/BY y prueba de signos por bloques anuales | Screening configurado; supuestos estadísticos no aprobados automáticamente |
| Supergate | Comprobación de huellas y alcance de evidencias | Faltan validadores científicos completos y contrato detallado congelado |
| Holdout | Denegación en desarrollo y consumo único de una autorización | No aislamiento físico ni ejecución económica de holdout |
| Portfolio | Asignación determinista de operaciones, límites y PnL liquidado | Diagnóstico: no replay conjunto ni drawdown mark-to-market |
| MT5 | Exportación MQ5 para tester y comparación exacta de ledgers normalizados | No hay EX5 compilado, terminal ejecutado ni importador automático de deals brutos validado |

## Ejecutar una demostración

El binario incluido es Linux x86-64 estático. Ambos ejemplos son **sintéticos**, aunque sus símbolos sean NQX y XAUUSD.

```bash
./bin/qros capabilities
python3 scripts/run_demo.py --example nqx --out /tmp/qros-demo-nqx-nuevo
python3 scripts/run_demo.py --example xau --out /tmp/qros-demo-xau-nuevo
```

El adaptador sólo calcula huellas y llama al binario: compilación del programa, indicadores, minería, pausa y reanudación, ledger y screening ocurren en C++. Usa un directorio de salida nuevo. No se queda ningún trabajo en segundo plano.

Los archivos `examples/pipeline/*/program.qros` muestran la gramática real; `dataset.qdata` y `vault.policy` contienen los contratos correspondientes. Los umbrales de la demo ilustran el software; no son un contrato científico aceptado ni una recomendación de estrategia.

## Compilar y verificar

Entorno realmente utilizado: GNU g++ 13.3.0, Linux x86-64, C++20, warnings tratados como errores. El adaptador no descarga dependencias.

```bash
python3 scripts/build_native.py --out build-local --static --jobs 3
python3 scripts/verify_software.py --build build-local --out /tmp/qros-verificacion-nueva
```

El verificador comprueba las huellas de fuentes, binarios, pruebas y referencias antes y después de ejecutar las suites. Genera las fixtures sintéticas que faltaban en el archivo v0.4. Los receipts históricos de `evidence/parent` no se presentan como pruebas del binario nuevo.

```bash
python3 scripts/build_native.py --out build-local-asan --sanitize address --jobs 3
python3 scripts/verify_software.py --build build-local-asan --out /tmp/qros-asan-nuevo
```

En este entorno LeakSanitizer no pudo leer `/proc/.../task`. Para comprobar **accesos a memoria**, se repitió ASan con `--leak-check disabled`; esto no demuestra ausencia de fugas. Véanse los logs y la limitación en la auditoría. UBSan se ejecutó separadamente. CMake/CTest están configurados, pero CMake no estaba instalado aquí y no se afirma haber ejecutado esa ruta.

## Semántica de ejecución

- `seq` gobierna la causalidad: timestamps iguales no autorizan usar un registro futuro. La entrada siempre ocurre después del registro de señal.
- BUY entra a Ask y sale a Bid; SELL entra a Bid y sale a Ask. Los gaps se liquidan a la cotización observada, no al nivel teórico.
- Se evalúan protecciones anteriores antes de actualizar BE/trailing. Las nuevas protecciones entran en efecto en la siguiente cotización.
- Spread cero se conserva y audita, pero no ejecuta órdenes. Las cotizaciones cruzadas bloquean el replay.
- Se usa el cierre declarado en el mapa de sesiones. EOF no inventa un cierre. Sin una cotización ejecutable posterior a la entrada, la operación queda sin resolver.
- Máximo una posición, una entrada por barra y 3 o 5 entradas por activo/sesión según contrato. No hay overnight.
- Precios y PnL son enteros int64 con detección de desbordamiento; R usa el riesgo inicial. `net_u` descuenta una comisión total por operación. Estadísticas derivadas usan `long double`.

## Integridad y reanudación

`mine` recibe huellas explícitas del programa, dataset y política de acceso. Al reanudar, también exige el mismo ejecutable y raíz de fuentes. No resuelve «último archivo» ni cambia de rama científica.

Los bloques contienen cada nacimiento, sus alias/exclusiones y todas sus operaciones. Se verifican orden, cantidad, identidad, contabilidad, SHA-256 y cadena de commits antes de avanzar `HEAD`. Un commit ya durable cuyo `HEAD` quedó atrasado se recupera de la siguiente secuencia exacta. Un proceso que perdió el lock/fence no puede escribir válidamente.

Esto protege de errores e interrupciones dentro del protocolo. No constituye aislamiento contra un administrador que pueda editar archivos, ni firma criptográfica de un broker.

## Darwinex y los archivos históricos

Se conserva tu confirmación de que **NQX y XAU proceden de Darwinex y usan su horario**. La inspección de los convertidores recuperados muestra que construyen fecha + hora sin restar un offset; la evidencia nueva tiene alcance de código, no de un nuevo barrido de todos los ticks.

La regla horaria publicada por Darwinex distingue GMT+2/GMT+3 según el horario de verano de Estados Unidos. La conexión exacta entre esa regla, las sesiones y los bytes de cada carrier sigue requiriendo evidencia del periodo. [Horario de MetaTrader en Darwinex](https://help.darwinex.com/metatrader-time).

No se reactivó ninguna autoridad RAR antigua. Los ZIP activos, sus receipts históricos y el estado científico previo permanecen separados de las pruebas de software.

## Qué hace falta para cerrar el software completo

1. Recuperar el contrato científico detallado y congelado del chat original; implementar y validar sus pruebas OOS, robustez, walk-forward/CPCV y Supergate. Las arquitecturas recuperadas nombran esas capas, pero no equivalen a una especificación ejecutable completa.
2. Conectar y validar la autoridad de datos y sesiones reales, incluido el tratamiento explícito de las cotizaciones cruzadas ya registradas en los carriers. No basta con eliminar el bloqueo `TEST_ONLY`.
3. Construir el holdout con aislamiento y registro de exposición, y el portfolio mediante replay conjunto y riesgo mark-to-market con contratos monetarios explícitos.
4. Compilar el MQ5 en MetaEditor, completar la automatización del tester/importación y comprobar paridad contra un terminal MT5 real. No se entregan resultados MT5 fabricados ni un EA autorizado para live.

La auditoría, el checkpoint y los informes vinculados al binario se incluyen en `docs/`, `control/` y `evidence/verification/`.
