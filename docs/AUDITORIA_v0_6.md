# Auditoría y construcción de QROS ENGINE v0.6.0

**Fecha:** 28 de agosto de 2026. **Resultado:** motor nativo ampliado y verificado en alcance de pruebas; **el producto completo aún no está terminado para producción**.

## Alcance real de la auditoría

Se usaron el README adjunto, el paquete físico v0.4, su manifiesto de 70 archivos, la arquitectura v0.3 incluida y los extractos recuperados del chat «Crear Python mejorado». No se obtuvo una transcripción íntegra ni la fuente/binario v0.5. La búsqueda adicional del contrato científico detallado no recuperó evidencia; no se afirma que ese contrato nunca existiera.

v0.6 es un descendiente declarado de la v0.4 verificada. Se volvió a comprobar que los 70 archivos originales permanecen intactos. Las declaraciones antiguas del asistente, los receipts históricos y las pruebas nuevas no se mezclaron como si fueran equivalentes.

## Qué estaba construido y qué se añadió

| Área | Base física recuperada | v0.6 entregada | Lo que continúa pendiente |
|---|---|---|---|
| Lenguaje/IR | Intents de operaciones individuales | DSL cerrado, tipos, DAG, ejes finitos e identidad SHA-256 | Congelar la ontología científica del proyecto |
| QDATA | Auditor CSV y custodia física histórica | CSV5/PACKED17 en streaming; sesiones y raíz de shards vinculadas a hashes; paridad de conversión normalizada | Verificación externa de todos los periodos reales y del origen temporal de las sesiones |
| Feature Graph | Capa futura en arquitectura | 26 operadores, EMA/ventanas, OHLC cerrado, exportación de features y uso compartido por cohortes | Almacén persistente masivo/indexado y benchmarks al volumen real |
| Ejecución | Replay básico | SL/TP, BE, trailing, costes, gaps y límites por sesión/barra | Equivalencia real de llenados, contratos y costes del broker |
| Universe/Miner | Capa futura | Enumeración perezosa, alias, exclusiones causales, cobertura bruta, pausa y reanudación | Activación científica con especificación y datos autorizados |
| Resultados | Ledgers y receipts | Bloques inmutables, lock, fencing, cadena de hashes, CAS y recuperación | Coordinación distribuida si se requiere; no está implementada |
| Gates/Supergate | Capa futura | Métricas, BH/BY, signos por año y agregación de evidencia | Validadores completos OOS/robustez/walk-forward/CPCV según contrato congelado |
| Holdout Vault | Capa futura | Denegación al motor de desarrollo y consumo único de una autorización | Aislamiento físico, registro de exposición y ejecución controlada de validación |
| Portfolio | Capa futura | Asignador diagnóstico, prioridades, límites y liquidaciones simultáneas | Replay conjunto causal, valoración mark-to-market y riesgo monetario real |
| MT5 Bridge | Capa futura | Generador MQ5 limitado al tester y comparador exacto de ledgers | Compilar EX5, automatizar/importar deals brutos y verificar un terminal real |

No se califica una fila como «terminada» sólo porque exista un archivo o una API.

## Correcciones comprobadas

- **Autoridad XAU:** el índice activo contenía una huella antigua. Se corrigió para que coincida con el archivo físico, sin cambiar el perfil ni las autoridades ZIP; se añadió la comprobación que rechaza un perfil alterado.
- **Desbordamiento de PnL:** se sustituyeron restas con posibilidad de overflow por operaciones comprobadas y rechazo explícito; hay regresión con los extremos de int64.
- **Causalidad:** la entrada sucede en un registro posterior a la señal; no se exponen barras abiertas ni se aplica una nueva protección retroactivamente.
- **Cierres:** no se inventa una salida si no hubo cotización ejecutable posterior a la entrada; la operación queda sin resolver y bloquea el screening completo.
- **Integridad de bloques:** cantidades, identidades, contabilidad, cobertura y hash deben concordar antes de avanzar el checkpoint.
- **Shards:** una raíz, sesión, escala o continuidad incompatible se rechaza. Verificar los shards suministrados no certifica cobertura del carrier completo.
- **Portfolio diagnóstico:** los flujos con el mismo timestamp se suman antes de medir drawdown liquidado; no se inventa un orden intermedio entre activos.
- **Gates:** se verifica que riesgo, comisión y demás metadatos del ledger correspondan al candidato; N_TESTS incluye alias y exclusiones. Un screening positivo sigue sin aprobar investigación.
- **Supergate y MT5:** se rechazan identidades de alcance engañosas, observaciones vacías y diferencias de paridad; no se convierten fixtures en pruebas de ejecución externa.
- **Pruebas heredadas:** faltaban sus archivos de entrada en el paquete. Se generaron fixtures nuevas, declaradas sintéticas, y se adaptaron rutas/huellas de los tests sin reconstruir ficticiamente receipts antiguos.

## Verificación efectivamente ejecutada

| Comprobación | Resultado |
|---|---|
| GNU g++ 13.3.0, C++20, warnings como errores | PASS |
| Suites Release | 12/12 PASS |
| Suites AddressSanitizer, comprobación de accesos | 12/12 PASS; detección de fugas desactivada por restricción de `/proc` |
| Suites UndefinedBehaviorSanitizer | 12/12 PASS |
| Pruebas nativas de pipeline | 40 comprobaciones PASS |
| Integración por cada perfil de compilación | 179 comprobaciones PASS |
| Comparación C++/referencia Python separada | 576 operaciones y 74,400 valores de indicadores coincidentes |
| Barrido de propiedades del núcleo heredado | 10.000 casos PASS |
| Dos compilaciones estáticas en directorios diferentes | Tres ejecutables byte-idénticos |
| Interrupción real con SIGKILL, lock y reanudación | PASS; ledger idéntico al de una ejecución sin interrupción |
| Ejemplos empaquetados NQX y XAUUSD | PASS; sintéticos, 96 nacimientos por ejemplo |
| Inspección ELF | Linux x86-64 estático, sin intérprete dinámico |
| CMake/CTest, Clang y terminal MT5 | No ejecutados en este entorno |

La referencia es una implementación de software separada; no es una auditoría de un tercero ni una prueba del comportamiento del broker. Los 12 grupos incluyen preparación de fixtures y comprobación de autoridades; no son 12 backtests financieros. Los logs y huellas se conservan en `evidence/verification`.

**LeakSanitizer:** el intento inicial terminó con un error del entorno al leer `/proc/.../task`. Se conserva ese fallo. ASan se repitió con `detect_leaks=0`, de modo que esta entrega no certifica ausencia de fugas de memoria.

## Darwinex y el horario

Tu confirmación de que NQX y XAU vienen de Darwinex y usan su horario se acepta y preserva. Además, los dos convertidores recuperados construyen `fecha + hora` sin restar offset. Esto respalda que esas rutas de código conservan el reloj fuente; no se volvió a convertir ni recorrer íntegramente los 559.817.687 ticks NQX y 697.060.968 ticks XAU.

La regla GMT+2/GMT+3 publicada por Darwinex y su relación con el horario de verano estadounidense sirven como referencia del broker; por sí solas no enlazan cada archivo histórico con sesiones exactas. [Fuente oficial](https://help.darwinex.com/metatrader-time).

El README v0.4 ya registra cotizaciones cruzadas en ambos carriers. Esta entrega no las elimina ni las transforma en fills: el replay las rechaza hasta disponer de una política explícita y validada. Las autoridades RAR históricas no vuelven a estar activas.

## Límites de uso y siguiente requisito

Se mantienen `research_ready=0`, `holdout_opened=0`, `scientific_head_promoted=0` y `background_running=0`. No se produjo PnL nuevo con datos reales ni se promovió un portfolio. La protección del holdout aquí es lógica en la ruta de desarrollo; no es aislamiento de filesystem frente a un administrador. Los auditores de integridad tampoco constituyen una bóveda física.

Para cerrar el producto completo hace falta recuperar el **contrato científico detallado del chat original** y disponer de un **entorno MT5/MetaEditor accesible**. A partir de esos insumos deben completarse y probarse Supergate, aislamiento de holdout, replay conjunto del portfolio y automatización/paridad MT5. No se debe suprimir el bloqueo `TEST_ONLY` para aparentar que esas capas están terminadas.

MetaQuotes documenta la compilación externa y el arranque del tester, pero conocer esos comandos no demuestra que el MQ5 de esta entrega compile o reproduzca los fills. [Compilador externo](https://www.metatrader5.com/en/metaeditor/help/beginning/integration_ide), [configuración del tester](https://www.metatrader5.com/en/terminal/help/start_advanced/start).

## Identidad de la entrega

- Binario `bin/qros`: `6835ab7e0bfd94019f67edbd15d5e0c9b2ada9c32f6c261e109cdac22ca28f79`.
- Raíz de fuentes del runtime: `d78be57f8e79c0537074019a75e8bf6da36d3c544955cee8e2aa3698a3bdd31a`.
- Contrato de compilación: `1278c2be7ebad5ff78cc29b461e8e3336d4712855344cef724208bc12fa260b9`.
- Paquete padre v0.4: `a5b6bcb5846cce1c0b40690b490ed6d9c23647a8e9212290388e91ba3d5bc313`.

`control/STATE.json` contiene el checkpoint, `control/SOURCE_SCOPE.json` el alcance de evidencia y `MANIFEST.sha256` las huellas de los archivos de la entrega. El README incluye comandos para compilar, verificar y ejecutar los dos ejemplos.
