# Backlog de ingeniería derivado de la auditoría

Estado inicial: todos los hallazgos siguientes están ABIERTOS en v0.6.0.
La prioridad ordena el trabajo, no elimina requisitos ni identidades científicas.
El reporte detallado y su reproducción están en `audit/`.

| Orden / ID | Trabajo | Prueba de aceptación mínima |
|---|---|---|
| P0 A01 | Instrumento, tick size, puntos, slippage y fills | Tick size 10/slippage 1 no produce precios 111/139; rechaza o representa costes separadamente con política explícita. Pruebas BUY/SELL, gaps y overflow. |
| P0 A02 | Control de acceso en todos los lectores y aislamiento de holdout | Proceso miner no puede leer carrier sellado ni estadísticas por otro comando; prueba permisos del host y denegación antes de abrir bytes. |
| P0 A03 | Consumo de autorización independiente de carpeta | Mismo permiso rechazado en segundo uso aunque cambie store, ruta o proceso; carreras y rollback probados en registro canónico protegido. |
| P0 A06 | Procedencia de MT5 y reconstrucción de ledger | Texto falso como EX5/ticks/deals se rechaza; resultado nunca afirma paridad externa sin ejecución verificable y derivación de deals. |
| P0 A07 | Validadores semánticos de evidencia | Recibos FAIL, tipos inválidos, resultados sintéticos/expuestos o dependencias erróneas no satisfacen métodos requeridos. |
| P1 A08 | Contrato gates → Supergate | Salida válida por candidato conecta ambas capas; un screening no se presenta como todos los métodos científicos aprobados. |
| P1 A05 | IR autocontenido y versionado | Grafo, estados, acciones y políticas se pueden validar y ejecutar sin el texto original ni consultas al chat. |
| P1 A04 | Evitar relectura de cohortes sólo alias | Contadores de lectura prueban cero replay adicional de alias sobre snapshot validado; ledger, cobertura y N_TESTS se conservan. |

## Hitos posteriores obligatorios según alcance

### H1. Semántica y corpus golden

Tipos de precio/distancia/puntos/tiempo/dinero; estados sweep → reclaim; referencia
dinámica; TP/SL dependientes de barras; BE/gestión; trazas causales de señal a fill;
orden de fases; igualdad de timestamp con seq diferente; gaps, spread cero/cruzado,
warmup, pausas de sesión y cierre sin cotización válida. Congelar y probar el significado
de primer toque antes de reemplazar next-record. Respetar el contrato vigente mientras
se resuelven cambios metodológicos; no quitar guardas TEST_ONLY para avanzar.

QDATA debe vincular bytes, flags, unidades, alias de símbolo, reloj Darwinex, DST,
sesiones y cobertura de shards. Conservar información fuente; no borrar cruces sin
una política autorizada. Un corpus real sólo puede venir de desarrollo permitido.

### H2. Runtime y distribución para chats

Cumplir `CHAT_RUNTIME_RELEASE_CONTRACT.md`: preflight, job declarativo, ejecución
nativa sin instalación de Python, versión/hash, límites, checkpoints y restauración.
Probar desde una copia limpia y sin red, también con rutas nuevas.

### H3. Escala medible

Reutilizar lectura y features entre cohortes; resultados e índices en streaming;
estado acotado de indicadores/candidatos; checkpoints dentro de pasadas largas;
casos de fallo/carrera; determinismo entre planificaciones permitidas. Benchmark
de flujo completo con I/O, hashing, ledger y reanudación; RAM/CPU/bytes/pasadas y
paridad exacta. No usar el microbenchmark antiguo como velocidad del producto.

### H4. Validación científica y MT5

Implementar sólo métodos y umbrales del contrato científico recuperado/aprobado.
Registrar todas las pruebas y multiplicidad; distinguir desarrollo, OOS expuesto,
holdout y forward. MetaEditor/tester/importador automático; símbolo, build, SET,
recursos, diario y ticks observados; comparar trade por trade y clasificar divergencias.
Si no existe host MT5 real, declarar bloqueada la aceptación externa, no simularla.

### H5. Portfolio y aceptación

Replay conjunto de estrategias, reglas de interacción, posiciones abiertas, valoración
mark-to-market, moneda/tick value, comisiones y margen. Pruebas de límites diarios y
concurrencia. Publicar sólo una release con matriz de capacidades y limitaciones reales.

## Flujo por corrección

Reproducir sobre baseline → regresión con expectativa correcta → patch mínimo →
pruebas afectadas + oracle → sanitizers/análisis C++ → integración → recibo del nuevo
build → revisión. Actualizar estado por ID y conservar antes/después.

El harness histórico `reproduce_audit.py` espera que aparezcan los defectos en la base.
Su salida FINDING_REPRODUCED no es un PASS de calidad. Para usarlo tras un arreglo,
trasladar el caso pertinente a las suites existentes y cambiar su expectativa con razón.
No modificar la evidencia baseline para ocultar la diferencia.
