# QROS ENGINE: auditoría del diseño original y del software disponible

**Fecha:** 28 de agosto de 2026. **Base comprobada:** QROS ENGINE v0.6.0.

**Resultado:** auditoría completada; correcciones y capas pendientes identificadas. El producto permanece en desarrollo. Esta revisión no modifica el motor ni concede aprobación científica, acceso económico a holdout o permiso de trading real.

## 1. Dictamen

La evolución hacia un runtime cuantitativo nativo es coherente con el objetivo de QROS. Ya existe una parte útil de esa autonomía: ejecuté el binario directamente, con `PATH` vacío y sin Python en la ruta de búsqueda. El backtest sintético y los comandos auditados funcionan así; su implementación inspeccionada está en C++. Python sigue presente en las herramientas de construcción, pruebas, empaquetado y referencia independiente.

La aspiración defendible es **un entorno especializado que haga el trabajo de QROS de forma más controlable, reproducible y eficiente**. Todavía no hay evidencia para afirmar que QROS completo sea superior a Python, NumPy, Numba u otros motores en cargas equivalentes. Los microbenchmarks citados en el chat original no miden el producto completo ni corresponden al binario actual.

No recomiendo otro cambio general de lenguaje. Recomiendo completar el contrato ejecutable, corregir las fronteras de validación y medir el flujo completo. Tampoco recomiendo eliminar el oracle Python: una segunda implementación es útil para descubrir errores compartidos por el compilador y el kernel nativo.

Si quieres conservar la idea de «Python integrado», cabe ofrecer después una edición de herramientas con CPython empaquetado y versiones fijadas. El usuario no necesitaría instalar su propio Python, pero esa edición seguiría conteniendo un intérprete y sus dependencias. La documentación oficial permite integrar CPython en C++, sin fabricar un fork de Python. Eso resuelve distribución y extensibilidad; no acelera automáticamente el motor. [Integración de Python en otra aplicación](https://docs.python.org/3/extending/embedding.html).

## 2. Qué se verificó y qué queda fuera

| Evidencia | Resultado y alcance |
|---|---|
| Extractos originales aportados en este mensaje | Leídos como requisitos y afirmaciones históricas de v0.1/v0.2. No equivalen al chat completo ni a una especificación científica exhaustiva. |
| README adjunto | Describe v0.4 y autoridades históricas. Sus PASS conservan ese alcance. |
| Paquete entregado v0.6 | CRC correcto; 167 archivos comparados byte a byte mediante hashes contra el árbol de trabajo, sin diferencias. |
| Binario v0.6 | SHA-256 comprobado; ELF sin `PT_INTERP`. Ejecución directa con `PATH` vacío. |
| Pruebas nativas existentes | Reejecutadas: `ALL_TESTS_PASS` y `PIPELINE_TESTS_PASS checks=40`. |
| Pruebas dirigidas nuevas | 17 invocaciones en la ejecución final del harness; ocho hallazgos o brechas confirmados, detallados abajo. |
| Análisis estático exploratorio | Cuatro unidades C++ con GCC 13.3; resultados parciales, no un PASS del programa completo. Se añadió un control mínimo sin QROS. |
| Integridad tras las pruebas dirigidas | Los mismos 167 archivos de la entrega seguían intactos. |
| Recibos Release/ASan/UBSan de v0.6 | Inspeccionados y vinculados al paquete. No se presenta esta lectura como una nueva ejecución de todas esas suites. LeakSanitizer sigue sin estar verificado. |
| Ticks originales NQX/XAU | No se abrieron ni se recalculó PnL real en esta auditoría. |
| MT5 | Sin MetaEditor, EX5 ejecutado o terminal disponible aquí. No hubo paridad externa real. |

Identidades de la base auditada:

```text
ZIP v0.6:
43a95ed3f8e3078db4ab50a3a0e10abfc72b3f363d4867a43483b47a0aa0e20a

bin/qros:
6835ab7e0bfd94019f67edbd15d5e0c9b2ada9c32f6c261e109cdac22ca28f79

source_root v0.6:
d78be57f8e79c0537074019a75e8bf6da36d3c544955cee8e2aa3698a3bdd31a
```

La fuente v0.5 sigue sin estar recuperada. v0.6 se identifica como descendiente de v0.4; no se inventa una continuidad material a través de v0.5.

## 3. Ocho comprobaciones concretas

**P0** significa que debe resolverse antes de habilitar investigación productiva o confianza en esa validación. **P1** bloquea completar o escalar la capa correspondiente. No implica que un sistema productivo ya haya sufrido el problema: el motor continúa restringido a pruebas.

| ID | Prioridad | Comprobación | Resultado observado | Corrección o aceptación requerida |
|---|---|---|---|---|
| A01 | P0 | Quotes válidos con `tick_size_u=10` y slippage de una unidad | El backtest termina y registra entrada **111** y salida **139**, fuera de la rejilla de diez unidades. | Vincular política de ejecución e instrumento; rechazar configuraciones incompatibles antes del replay. Si se quiere representar costes fraccionarios, separarlos del precio ejecutado. |
| A02 | P0 | Dataset sintético marcado como sellado | `vault-check` deniega desarrollo; `data-check` lee los bytes y produce estadísticas sin pedir autorización de vault. | Separar el rol de auditoría de datos del rol de miner. El proceso de investigación no debe tener acceso al carrier sellado. |
| A03 | P0 | Consumir dos veces el mismo permiso | En el mismo directorio se rechaza; en otro directorio se acepta otra vez como `CAPABILITY_CONSUMED`. | Registro de consumo canónico y protegido, independiente de la ruta elegida por quien ejecuta. |
| A04 | P1 | Segunda cohorte compuesta sólo por alias | Declara `graphs=0`, pero entra igualmente en la ruta de datos; falla al reducir el presupuesto de filas. Con el presupuesto normal termina. | Planificar alias antes del replay y reutilizar la validación de una instantánea inmutable; no repetir lectura y hashing completos sin necesidad. |
| A05 | P1 | Inspección del IR generado por `compile` | Serializa la huella del grafo, pero no los nodos ejecutables. | Completar un IR autocontenido, versionado y verificable, o un paquete que incluya y vincule todos sus componentes. |
| A06 | P0 | Evidencias MT5 ficticias pero con hashes consistentes | Acepta texto de prueba como EX5, ticks y deals; con dos ledgers copiados emite `EXTERNAL_RECORDED_PARITY_PASS`. | Validar formatos, procedencia de la ejecución y derivación del ledger a partir de los deals y ticks observados. |
| A07 | P0 | Seis recibos ficticios con `status=FAIL` | Supergate devuelve `READY_FOR_SCIENTIFIC_REVIEW_NOT_AUTOMATIC_APPROVAL` porque sólo comprueba hashes y alcance textual. | Validadores por método, esquema, versión, estado y dependencias; una evidencia fallida no puede contar como validación satisfecha. |
| A08 | P1 | Conectar un resultado real del comando `gates` al comando `supergate` | El primer comando genera su informe; el segundo lo rechaza con `SUPERGATE_EVIDENCE_SCOPE:gate`. | Implementar la transformación a recibos por candidato y un contrato común entre ambas capas. |

**Matiz esencial:** A06 y A07 conservan `research_approved=0`. No se logró una aprobación científica indebida; se demostraron límites de los verificadores y etiquetas que podrían sobreinterpretarse. A02 sólo expuso estadísticas estructurales de bytes sintéticos; A03 no abrió datos económicos. Los artefactos falsos están identificados como fixtures adversariales, no como evidencia externa válida.

### Localización de las causas

| Hallazgo | Código inspeccionado |
|---|---|
| A01 | [backtest.cpp](sandbox:/workspace/scratch/4081d1647557/qros_engine_v0_6/src/backtest.cpp), [pipeline_data.cpp](sandbox:/workspace/scratch/4081d1647557/qros_engine_v0_6/src/pipeline_data.cpp): se valida la rejilla de las cotizaciones, pero el backtest no recibe el tamaño de tick para validar fills o protecciones. |
| A02–A03 | [pipeline_cli.cpp](sandbox:/workspace/scratch/4081d1647557/qros_engine_v0_6/src/pipeline_cli.cpp), [vault.cpp](sandbox:/workspace/scratch/4081d1647557/qros_engine_v0_6/src/vault.cpp): comandos de auditoría fuera de `enforce_vault`; consumo ligado a `store/control`. |
| A04 | [pipeline_cli.cpp](sandbox:/workspace/scratch/4081d1647557/qros_engine_v0_6/src/pipeline_cli.cpp): `walk_data` se invoca en cada cohorte, incluso sin grafos activos. |
| A05 | [universe.cpp](sandbox:/workspace/scratch/4081d1647557/qros_engine_v0_6/src/universe.cpp): `QROS_CANDIDATE_IR_V1` incluye `graph_sha256`, no el contenido del grafo. |
| A06 | [mt5_bridge.cpp](sandbox:/workspace/scratch/4081d1647557/qros_engine_v0_6/src/mt5_bridge.cpp): verifica hashes de archivos auxiliares, sin interpretar su contenido ni reconstruir el ledger desde ellos. |
| A07–A08 | [gates.cpp](sandbox:/workspace/scratch/4081d1647557/qros_engine_v0_6/src/gates.cpp): agregación por búsqueda de líneas; el informe de screening no tiene el mismo esquema por candidato que exige Supergate. |

Estas pruebas se conservan en `AUDIT_PROOFS.json`, sus logs y el harness reproducible del paquete de evidencias. Son pruebas del binario entregado, no de una versión modificada para producir el resultado.

## 4. Corrección de una conclusión del chat original: el análisis estático

El chat daba mucho peso a `GCC -fanalyzer -Werror → PASS` sobre C++20. La documentación de **GCC 13.3 y GCC 14.2** dice expresamente que su analizador es adecuado sólo para C en esas versiones. También advierte que puede emitir falsos positivos, omitir errores y abandonar rutas complejas. Un PASS de esa herramienta no certifica el motor C++. [GCC 13.3](https://gcc.gnu.org/onlinedocs/gcc-13.3.0/gcc/Static-Analyzer-Options.html), [GCC 14.2](https://gcc.gnu.org/onlinedocs/gcc-14.2.0/gcc/Static-Analyzer-Options.html).

La comprobación actual, acotada a 35 segundos por unidad, produjo:

| Unidad | Resultado |
|---|---|
| `backtest.cpp` | Compilación con analizador terminada sin diagnósticos. |
| `vault.cpp` | Compilación con analizador terminada sin diagnósticos. |
| `feature_graph.cpp` | Diagnósticos de valor no inicializado en rutas de `std::deque`; compilación no limpia. |
| `universe.cpp` | Límite de 35 segundos; se detuvo su grupo de procesos. Resultado inconcluso. |
| Control mínimo `std::deque`, sin QROS | Reproduce la misma familia de diagnósticos; seis errores del analizador. |

Esto indica una limitación relevante de la herramienta para este caso. No demuestra que todos los avisos del motor sean falsos, ni permite declarar una vulnerabilidad de memoria confirmada. Conservo los diagnósticos y el control mínimo.

**Mejora:** usar una ruta de análisis que soporte C++, como Clang Static Analyzer, fijar versión y configuración y tratar sus resultados junto con pruebas y sanitizers. No cambiar contenedores sólo para obtener una salida verde de una herramienta inadecuada. Clang no estaba instalado aquí, así que su ejecución permanece pendiente. [Clang Static Analyzer](https://clang.llvm.org/docs/ClangStaticAnalyzer.html).

También falta fuzzing guiado por cobertura para parsers, IR, PACKED17, sesiones y almacén de resultados. Las 10.000 propiedades del kernel histórico no sustituyen ese trabajo ni cubren automáticamente todas las capas nuevas. [Documentación de libFuzzer](https://llvm.org/docs/LibFuzzer.html).

## 5. Qué falta para completar el lenguaje y el runtime

### 5.1 Un contrato semántico único y ejecutable

Existen contratos históricos y políticas dentro del código. Falta consolidar su relación con el pipeline nuevo: versión de lenguaje, operadores, unidades, redondeos, reloj, fases de evento, órdenes y errores. Cada resultado debe identificar exactamente esos contratos.

No basta con llamar al grafo «compilador causal». Deben poder auditarse la información disponible, el estado de la estrategia y la orden producida en cada secuencia. Hace falta una traza opcional que explique una operación desde sus datos y señales hasta el fill.

La regla de siguiente registro y una estrategia descrita como «entrada al primer toque» necesitan una traducción explícita. Una orden armada antes del toque y una señal detectada en ese mismo toque son eventos distintos. Resolverlo es una cuestión semántica; no debe modificarse para mejorar un benchmark.

### 5.2 Estrategias con estado y niveles dinámicos

El compilador actual sólo admite SL/TP como distancias enteras fijas por candidato. No permite que una operación tome su TP del máximo de una barra de referencia, derive su riesgo inicial de ese objetivo y cambie el SL por una condición posterior de la barra de entrada.

La familia de barrido/reclaim necesita estados explícitos: selección de referencia, armado, barrido, recuperación, entrada, gestión y expiración. Debe conservarse la semilla autorizada y separar sus variantes, no sustituirla silenciosamente por un cruce de medias de la demo.

La implementación debería añadir expresiones tipadas para niveles y una máquina de estados declarativa, acotada y sin `eval`. No hace falta convertir el DSL en un lenguaje general. El corpus golden debe cubrir también señales falsas, ausencia de entrada, empates de timestamp, cambio de sesión y casos sin cierre ejecutable.

### 5.3 Unidades y tipos de dominio

`Number` y `Boolean` no distinguen precio, distancia, puntos, tiempo, contratos y dinero. Mantener enteros no impide mezclar unidades. Deben existir tipos o verificaciones equivalentes para esas magnitudes, con conversiones explícitas.

Por ejemplo, «dos puntos» debe convertirse con `point_size_u`; no necesariamente son dos unidades de precio. Debe registrarse el contrato monetario real: tamaño de contrato, lotaje equivalente, moneda, tick value, comisiones y reglas de margen. MetaTrader distingue esas propiedades del tamaño mínimo de cambio de precio. [Propiedades de símbolos en MQL5](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants).

### 5.4 IR, compatibilidad y dos rutas de ejecución

El IR necesita el grafo, estados, acciones y políticas necesarios para ejecutarlo, además de hashes. Debe poder validarse y ejecutarse con una interfaz estable, sin volver a interpretar informalmente el chat.

Una mejora estructural útil sería mantener un intérprete sencillo del IR como referencia semántica y un ejecutor optimizado del mismo contrato. El oracle Python seguiría siendo una implementación separada. Ninguna ruta debe generar sus resultados esperados copiando el ledger de la otra.

## 6. QDATA y Darwinex: qué está resuelto y qué no

**Se conserva tu confirmación:** los ticks NQX y XAU provienen de Darwinex y usan su horario. No se vuelve a cuestionar su origen. La regla pública de Darwinex es GMT+3 durante el verano de Estados Unidos y GMT+2 fuera de él. No debe sustituirse por un calendario europeo de DST. [Horario de MetaTrader en Darwinex](https://help.darwinex.com/metatrader-time).

Lo pendiente es conectar esa autoridad con los bytes y con cada ejecución:

1. **Reloj fuente y UTC:** conservar la marca original y producir una transformación explícita, con versión de calendario y pruebas en cambios DST. Los convertidores recuperados forman fecha y hora sin restar un offset; su inspección no equivale a reconvertir todos los archivos.
2. **Sesiones reales:** vincular horarios, pausas, excepciones y fronteras a los registros. El cierre de un fragmento de archivo no debe convertirse en un cierre de sesión.
3. **Cobertura de shards:** demostrar rangos de bytes y secuencias respecto al carrier padre, sin huecos ni solapamientos. El verificador actual declara correctamente `full_parent_coverage=NOT_ASSERTED`.
4. **Calidad de quotes:** cerrar la política de cotizaciones cruzadas, spread cero y campos heredados. Los recibos históricos registran 162 cruces NQX y 2.218 XAU; el replay ejecutable actual rechaza un cruce. Esos conteos no fueron recalculados ahora. No se puede habilitar todo el carrier quitando una guarda o borrando filas sin autoridad metodológica.
5. **Flags y procedencia por registro:** PACKED17 conserva el byte de flags, pero el nuevo replay no lo incorpora a `Tick`. Hay que definir qué significa para la actualización de Bid/Ask y qué información se mantiene o se descarta. No asumir que todo registro representa una cotización bilateral recién actualizada.
6. **Alias de instrumentos:** la relación entre nombres como NQX/NDX y el símbolo exacto del broker debe formar parte del contrato; la similitud del nombre no demuestra equivalencia.

Hace falta un primer corpus golden de **datos reales de desarrollo autorizados**, pequeño pero representativo, para XAU y NQX. No usar holdout para depurar semántica.

## 7. Holdout: aislamiento real, con un modelo de confianza explícito

Los hashes comprueban identidad e integridad; no son permisos. Un fichero editable que declara `HOLDOUT_SEALED` no impide leer otro fichero disponible bajo el mismo usuario.

La arquitectura pendiente debe separar el almacenamiento sellado del proceso miner, mediante permisos y procesos distintos o un servicio de evaluación que no entregue los ticks al investigador. Las claves y el registro de autorizaciones, si se usan, deben quedar fuera del alcance del proceso de investigación. Un administrador que controla ambos lados sigue estando fuera de esa garantía: hay que declarar el modelo de confianza.

El servicio debe recibir un candidato congelado, verificar autorización y consumo en un registro canónico, ejecutar una evaluación acotada y registrar toda exposición. Una repetición, cambio de carpeta, cambio de etiqueta o migración no debe convertir datos ya vistos en un holdout limpio.

Implementar esta infraestructura no autoriza abrir el holdout. Su apertura económica sigue siendo una acción separada del protocolo científico.

## 8. MT5: completar el puente y comprobar el flujo realmente utilizado

Exportar MQ5 y comparar dos CSV no completa MT5 parity. Faltan compilación, ejecución automática del tester, importación de deals y validación de los ticks efectivamente usados.

La advertencia del chat sobre los ticks reales sigue siendo pertinente: la documentación actual indica que M1 se usa para verificar y corregir la historia de ticks; también contempla generar ticks cuando falta historia para una barra e ignorarlos si no existe la barra correspondiente. La prueba debe conservar diarios y datos observados, no sólo el nombre del modo de tester. [Preparación del tester](https://www.metatrader5.com/en/terminal/help/algotrading/test_preparation), [Ticks reales y generados](https://www.metatrader5.com/en/terminal/help/algotrading/tick_generation).

La documentación del diario describe estadísticas de discrepancias entre ticks y barras. Deben entrar en el verificador automatizado. Esto no demuestra que nuestros archivos tengan esas discrepancias: debe comprobarse en una ejecución real. [Diario del tester](https://www.metatrader5.com/en/terminal/help/algotrading/tester_journal).

Pendientes concretos del puente actual:

- Generar el paquete del tester completo: MQ5, recursos de sesiones, SET, especificación de símbolo, fechas, builds y hashes. La plantilla lee `SessionFile`, pero no resuelve por sí sola su entrega al agente del tester.
- Compilar con MetaEditor y recoger errores antes de ejecutar; automatizar el terminal sin pasos manuales en cada candidato.
- Registrar órdenes, deals, rechazos y razones originales. La plantilla actual convierte razones distintas de SL/TP en `SESSION_CLOSE`; eso puede ocultar una divergencia.
- Resolver deals con timestamps repetidos mediante identidad y orden de eventos, no sólo por milisegundo. El log bruto actual no lleva la secuencia autoritativa de fill.
- Unificar los dominios numéricos. La ruta MQL5 no reproduce de forma completa la aritmética checked del C++.
- Resolver diferencias explícitas de cierre: el C++ puede usar la última cotización ejecutable anterior al cierre declarado; la plantilla MT5 aborta si el tick de cierre tiene spread cero. Si se cambia la política, registrarlo como modificación semántica, no como arreglo invisible.
- Verificar la serie observada completa. Contar llamadas `OnTick` no prueba por sí solo la integridad del flujo: MQL5 documenta que un nuevo evento no se añade cuando ya hay otro en cola o procesándose. La consecuencia exacta en el tester debe medirse; no se afirma que ya se hayan perdido ticks aquí. [OnTick](https://www.mql5.com/en/docs/event_handlers/ontick).

Una ejecución externa puede demostrar discrepancias útiles sin dar PASS. La paridad debe localizar el primer desacuerdo entre datos, features, señal, orden, fill, costes y sesión. No basta con que coincidan el beneficio final o el número de operaciones.

## 9. Escala: el principal trabajo pendiente no es otro lenguaje

El miner comparte grafos **dentro de una cohorte**, pero recorre el carrier de nuevo para la siguiente. Además:

- `committed_chunks` carga todos los chunks anteriores en memoria; la finalización construye un ledger como una cadena grande, limitada a 128 MiB.
- La caché de identidades comprueba el límite de un millón al reconstruirse, pero no aplica una guarda equivalente en cada inserción del bucle; además se copia al empezar cada cohorte.
- `HIGHEST` y `LOWEST` recorren su ventana en cada actualización; una deque monótona puede mejorar el coste, si preserva todos los resultados.
- EMA conserva historial para el warmup aunque su recurrencia sólo necesita estado acotado y un contador. Es una optimización posible, no una mejora medida en esta revisión.
- La reanudación es por nacimientos completos. Falta checkpoint del estado de datos, barras, indicadores, órdenes y posiciones para continuar dentro de una pasada larga sin empezar otra vez el carrier.

### Estimación de amplificación de lectura

Para **un millón de nacimientos por activo**, con cohortes de 2.000, hay 500 pasadas por carrier. Aplicado a los tamaños históricos declarados:

| Carrier | Bytes por pasada | Bytes lógicos en 500 pasadas |
|---|---:|---:|
| NQX | 9.516.900.679 | 4.758.450.339.500 |
| XAU | 11.850.036.456 | 5.925.018.228.000 |
| Total | 21.366.937.135 | **10.683.468.567.500** |

Son aproximadamente **10,68 TB de bytes recorridos y hasheados**, según el bucle actual. Es una estimación derivada del código y tamaños históricos, no una campaña ejecutada ni una medida de tráfico físico de disco: la caché del sistema puede reducir ese tráfico.

### Mejoras que probaría en este orden

1. Planificar alias y exclusiones antes del replay, conservando cobertura y `N_TESTS` según la metodología autorizada.
2. Instantáneas validadas, particiones de datos y caché causal de features reutilizable entre cohortes. Las claves deben incluir datos, grafo, warmup, reloj, política y versión del motor.
3. Almacén de resultados por bloques, índices y finalización en streaming; límites de memoria antes de asignar, no después de concatenar todo.
4. Estado por candidato compacto; separar columnas numéricas y despachar operadores compilados, evitando comparar cadenas de opcode en cada tick.
5. Paralelizar trabajo independiente con orden de commits determinista. No paralelizar una misma secuencia causal sin una prueba de equivalencia.
6. Evaluar bitsets, SIMD o kernels especializados en cuellos de botella medidos. Cambiar a Rust, añadir Numba o introducir JIT sólo si el beneficio justifica el coste y supera la paridad.

El benchmark de promoción debe incluir lectura, validación, hashing, features, candidatos, ledger, checkpoint y recuperación. Registrar tiempo de pared, CPU, pico de RAM, bytes recorridos, número de pasadas y hashes de salida. Comparar varias ejecuciones bajo la misma máquina y distinguir caché fría/caliente. No he generado un nuevo multiplicador de velocidad del producto completo.

## 10. Gates científicos, universo y portfolio

| Capa | Disponible | Falta para cumplir el objetivo |
|---|---|---|
| Universo | Ejes finitos, aliases exactos y exclusiones explícitas | Ontología y genealogía congeladas; cobertura por familia; deduplicación y clustering con reglas claras, sin descartar aprobados por elegir sólo «el mejor». |
| Screening | PF, expectativa, DD liquidado, resultados anuales, BH/BY y signos por bloques anuales | Prerregistro verificable, evaluación de supuestos, particiones IS/OOS y métodos robustos que exija el protocolo. |
| Supergate | Integridad y alcance de referencias | Validadores científicos ejecutables, recibos compatibles por candidato y rechazo de evidencia fallida, sintética, expuesta o de alcance incorrecto. |
| Holdout | Guardas de desarrollo y primitiva de consumo | Aislamiento, autorización confiable, registro de exposición y evaluación controlada del candidato congelado. |
| Portfolio | Asignación determinista de operaciones ya calculadas | Replay conjunto de estrategias, órdenes y límites; valoración de posiciones abiertas, moneda, margen y costes reales. |
| MT5 | Exportador y comparador de ledgers | Compilación y tester automatizados, importador validado y procedencia del replay observado. |

El test de signos por años supone simetría e independencia de bloques; el propio informe reconoce que no se verifican automáticamente. Pocos años implican pocas combinaciones de signos posibles. Aumentar el número de simulaciones no crea información histórica adicional. Con familias muy grandes, hay que diseñar la evaluación antes de mirar qué candidatos pasan, no rebajar la corrección para producir ganadores.

Walk-forward, purga/embargo, CPCV, pruebas de costes, remuestreo, estabilidad de parámetros y métricas de sobreajuste deben implementarse **según el contrato científico aplicable**. No doy por hecho que nombrar todas esas técnicas haga válido un protocolo. Tampoco fijo aquí umbrales nuevos ni una regla de rechazo por un solo año perdedor.

El portfolio actual filtra ledgers obtenidos por separado. Si una operación se rechaza por solapamiento, el estado posterior de la estrategia puede cambiar; filtrar su ledger original no siempre equivale a volver a ejecutarla. Además, el DD de operaciones cerradas no mide el DD de posiciones abiertas. Hace falta un reloj compartido demostrado y un replay conjunto. La etiqueta `SHARED_UTC` del plan no sustituye el vínculo de los timestamps con esa autoridad.

## 11. Qué aprovechar de las referencias externas

Son referencias de diseño, no dependencias que se hayan añadido ni motores que se hayan ejecutado en esta auditoría.

| Referencia | Conclusión aplicable a QROS |
|---|---|
| NautilusTrader | Su core comparte componentes entre simulación y live y ordena los eventos de un nodo en un hilo. Refuerza separar orden causal de servicios auxiliares y paralelizar unidades independientes; no demuestra paridad automática con el mercado. [Arquitectura oficial](https://nautilustrader.io/docs/latest/concepts/architecture/). |
| LEAN | La frontera temporal usa la disponibilidad efectiva de los datos. QROS debe especificar cuándo una barra puede alimentar señales y qué ocurre en gaps y múltiples resoluciones. [Time frontier](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/time-modeling/timeslices). |
| Polars | Streaming es útil, pero algunas operaciones pueden volver al motor en memoria. Debe inspeccionarse el plan y medirse el pico real de RAM; no asumir que toda consulta es out-of-core. [Streaming](https://docs.pola.rs/user-guide/concepts/streaming/). |
| Arrow | La representación columnar ayuda a scans y SIMD. Validar datos serializados es obligatorio; su C Data Interface contiene punteros que no se pueden hacer seguros frente a un productor no confiable mediante una validación genérica. Para productores no confiables, preferir frontera de proceso y formato serializado validado. [Formato](https://arrow.apache.org/docs/format/Columnar.html), [Seguridad](https://arrow.apache.org/docs/format/Security.html). |
| DuckDB | Puede ser auxiliar de consultas y resultados. Su licencia MIT no obliga a adoptarlo ni demuestra que mejore este workload; primero benchmark y dependencias explícitas. [Información oficial](https://duckdb.org/why_duckdb). |

La revisión confirma la cautela con licencias: el repositorio consultado de vectorbt declara Apache 2.0 con Commons Clause; NautilusTrader publica LGPLv3 y LEAN Apache 2.0. Son condiciones diferentes. No los describiría indistintamente como componentes sin restricciones para cualquier futura distribución. [vectorbt](https://github.com/polakowo/vectorbt/blob/master/LICENSE.md), [NautilusTrader](https://github.com/nautechsystems/nautilus_trader/blob/develop/LICENSE), [LEAN](https://github.com/QuantConnect/Lean/blob/master/LICENSE).

## 12. Distribución y seguridad del producto

Un ejecutable estático no carece de dependencias: incorpora bibliotecas del runtime. Se localizaron las bibliotecas estáticas estándar de la toolchain; el paquete actual no contiene un SBOM ni un inventario completo de licencias y componentes de enlace.

libstdc++ usa GPLv3 con la excepción de runtime de GCC, que contempla su uso por módulos independientes bajo condiciones específicas. Eso no sustituye revisar el resto de bibliotecas enlazadas ni sus avisos. No se emite aquí un dictamen de redistribución del paquete. [Licencia del runtime de GCC](https://gcc.gnu.org/onlinedocs/libstdc++/manual/license.html).

Antes de distribuir como producto terminado faltan:

- Toolchain reproducible que vincule también headers, linker y bibliotecas, no sólo el ejecutable del compilador. Dos builds iguales en la misma máquina no prueban reproducción en una instalación distinta.
- Pruebas en plataformas soportadas y empaquetado explícito. Linux x86-64 no significa que el mismo ejecutable funcione nativamente en Windows, donde debe integrarse el tester MT5.
- Límites de memoria, disco y tiempo verificables; errores estructurados; cancelación y reanudación seguras; observabilidad por etapa.
- Contratos de API/CLI estables y un recorrido de usuario completo. Tener varios subcomandos no constituye todavía una aplicación integrada lista para operar.
- Pruebas de dependencias, permisos y recuperación; inventario de componentes y sus avisos. No se debe convertir un hash de una build en garantía general de seguridad.

La skill futura sólo debería ejecutar estos gates y registrar evidencias. No debe decidir semántica, inventar permisos ni convertir una prueba sintética en aprobación. Mantendría la decisión original de posponerla como nuevo producto hasta disponer de contratos y corpus golden adecuados.

## 13. Orden recomendado de construcción y criterios de cierre

| Etapa | Entrega concreta | Criterio para considerarla terminada |
|---|---|---|
| 1. Corregir fronteras actuales | Rejilla de precios, permisos de lectura/consumo y esquemas de evidencias | Las fixtures A01–A03 y A06–A08 reciben el rechazo o transformación correctos; las pruebas válidas existentes conservan sus resultados. |
| 2. Completar contrato e IR | Unidades, estados de estrategia, niveles dinámicos, fases y trazas | La estrategia autorizada se expresa sin modificar su semántica; el IR puede ejecutarse sin reconstruir nodos desde el chat; paridad con oracle independiente. |
| 3. Conectar QDATA real de desarrollo | Reloj Darwinex, sesiones, fragmentos, calidad y corpus golden | Identidad y cobertura verificadas; casos DST y bordes de sesión cubiertos; ningún acceso involuntario a holdout. |
| 4. Cerrar una paridad MT5 pequeña y real | Compilación/tester/importación automáticos | Registro de ejecución y datos observados, con diferencias clasificadas; PASS sólo cuando lo soportan las pruebas. Un caso divergente debe conservarse como golden negativo. |
| 5. Escalar sin cambiar resultados | Cachés causales, resultados en streaming, checkpoints de datos y estado | Paridad exacta al cambiar cohortes/shards/reanudación; presupuesto RAM/CPU/disco medido; cobertura y multiplicidad preservadas. |
| 6. Completar validación científica | Gates y Supergate según contrato congelado | Prerregistro, datos/exposición y familia vinculados; verificadores por método; sin aprobaciones por etiquetas o hashes aislados. |
| 7. Portfolio e integración de producto | Replay conjunto, riesgo abierto, moneda y distribución | Replay causal conjunto, límites correctos, PnL y DD verificables y flujo operativo reproducible. La aprobación live sigue siendo posterior y separada. |

Las etapas independientes pueden desarrollarse en paralelo cuando sus contratos estén definidos. No es necesario esperar el chat completo para corregir A01 o completar los esquemas; sí es necesario resolver las decisiones científicas que cambian el significado de la estrategia o la aprobación.

### Qué no haría ahora

No fabricaría un Python generalista, no reescribiría todo en Rust/C++, no incorporaría todas las bibliotecas por defecto, no crearía un JIT antes de medir el intérprete actual y no declararía terminado el software por tener nombres de todas sus capas.

**Prioridad inmediata:** convertir los hallazgos reproducidos en pruebas de regresión y cerrar el contrato del instrumento y las evidencias. Después, un recorrido pequeño y completo con la estrategia autorizada y paridad externa vale más que otro microbenchmark aislado.

## 14. Estado al cerrar esta auditoría

```text
AUDIT_INTENT: COMPLETED
ENGINE_BASE: v0.6.0, sin modificar
DIRECTED_PROBES: 8 hallazgos/brechas, 17 invocaciones
STATIC_ANALYSIS: PARCIAL; no aprobación C++ con GCC -fanalyzer
REAL_CARRIER_REPLAY: NO
ECONOMIC_HOLDOUT_OPENED: NO
MT5_COMPILED_OR_EXECUTED: NO
RESEARCH_APPROVAL_GRANTED: NO
BACKGROUND_RUNNING: NO
```

Se entregan el informe y un paquete reproducible de evidencias. Los archivos con evidencias MT5 o Supergate deliberadamente falsas dentro de ese paquete son **exclusivamente pruebas negativas sintéticas** y nunca deben promocionarse a autoridad científica.
