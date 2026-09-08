# Candidate 3: reparación de compilación nativa (2026-09-08)

Compilación **6/6 PASS, 0 errors / 0 warnings** con MetaEditor **5.0.0.6182**.
Estado de entrega: **DEVELOPMENT_BLOCKED / COMPILE_ONLY_PASS_OFFLINE_REVALIDATION_BLOCKED**.
No se declara FROZEN_CANDIDATE ni APPROVED_FINAL: falta reejecutar las suites originales,
cuyos scripts no están incluidos en ninguno de los dos paquetes físicos verificados.

## Causa raíz y reparación

El código **31 corresponde al runner**, en su rama `COMPILE_NOT_0_0`; no es un error
nativo de MetaEditor. El log original del executor contiene exactamente:

| Archivo | Línea | Columna | Diagnóstico |
|---|---:|---:|---|
| QROS_DEMO_PORTFOLIO_EXECUTOR_v2_2_4.mq5 | 145 | 21 | error 203: invalid index value |
| QROS_DEMO_PORTFOLIO_EXECUTOR_v2_2_4.mq5 | 146 | 22 | error 203: invalid index value |

Las declaraciones `g_intents[QROS_INTENT_SLOTS]` y `g_mgmt[QROS_MGMT_SLOTS]` usaban
variables `const int` como dimensiones de arrays estáticos. MetaEditor 6182 rechazó
ambas. Se reprodujo el mismo fallo con los bytes originales y el mismo compilador.

En el **executor completo** sólo se sustituyeron las declaraciones de las líneas 33–34:

```mql5
#define QROS_INTENT_SLOTS 32
#define QROS_MGMT_SLOTS 32
```

Ambas capacidades siguen siendo 32. Las funciones completas y todo el resto del
archivo conservan los mismos bytes. No se modificó ningún otro source de Candidate 3.
La declaración de arrays requiere una constante entera de tamaño según la
[documentación de MQL5](https://www.mql5.com/en/book/basis/arrays/arrays_declaration).

## Ejecución y evidencia

1. Se verificaron los ocho hashes del paquete contra su manifest y el checkpoint Git.
2. El ZIP original pasó CRC y se preservó sin modificaciones.
3. `run01-original` reprodujo los dos errores; los tres emitters dieron 0/0.
4. `run02-corrected` produjo seis EX5 nuevos y los seis logs dieron 0/0.
5. Se importaron a `final/MQL5/` los sources completos y los seis EX5 exactos.

Se usó el mismo gate de seis targets, hashes de entrada, logs 0/0 y presencia/hashes EX5.
El runner se derivó de la copia física; se cambiaron sólo su infraestructura de aislamiento
y registro: raíz nueva obligatoria dentro de `reports`, paquete explícito, manifest
actualizado para el executor, copia de los siete includes estándar, `/include` explícito,
MetaEditor copiado byte a byte y `/portable`, ventana oculta y resultados parciales
conservados en caso de fallo. El original se conserva en `validation/authority/candidate3/`.
**No ejecutar ese runner histórico:** apunta a la carpeta operativa del terminal.
La [interfaz oficial de compilación](https://www.metatrader5.com/en/metaeditor/help/beginning/integration_ide)
documenta `/compile`, `/include` y `/log`. No se usó `/s` (sólo sintaxis).

Los códigos de proceso crudos de MetaEditor fueron 1 incluso en compilaciones correctas;
se preservan en `COMPILE_RESULTS.json`. La aceptación deriva del log nativo 0/0 y del EX5
nuevo, como en el gate original. El gate corregido terminó con código 0. El host de
PowerShell que invocó la reproducción mediante `-Command` expuso su fallo como 1;
el runner entró en su rama explícita `Fail(...,31)`.

Ningún terminal se lanzó, cerró ni reinició; no se retiraron EAs, no se ejecutó ningún EX5,
no hubo tester, órdenes, activación, deployment ni escritura de globals/certificados.
Los snapshots del gate observaron cero procesos llamados `terminal64.exe`; no se infiere
con ello el estado de otra máquina o cuenta. `QDB1.EXEC.CERT=0` queda sin tocar.

## Regresión y conservación científica

La nueva regresión ejecutada dio **77 PASS / 0 FAIL**. Es comprobación de sources y evidencia
nativa de compilación; no certifica comportamiento de CTrade. Ver
`../validation/evidence/offline_regression/REPAIR_REGRESSION_RESULTS.json`.

- Los siete sources restantes son idénticos a Candidate 3, incluidos los tres emitters.
- Los ocho sources/wrapper de v2.2.3 coinciden con `FROZEN_SOURCE_RECEIPT.json`.
- La comparación completa con los tres emitters congelados de v2.2.3 sólo permite las
  diferencias revisadas de versión, include del bus, source token, fencing, watermark y
  namespace DIV3. Tras esas diferencias de infraestructura, todo el source es idéntico.
  Los diffs se guardan en `../validation/evidence/offline_regression/`.
- Se conservan riesgo 0.50%, reserva máxima 1.00%, tres entradas/día, prioridad
  XAU > NQX > DIV3, parámetros, alfa, BUY/SELL, G30, namespace Q24.* y arm token v2.2.4.
- Las funciones relacionadas con F01–F18 se identificaron por línea y hash; permanecen
  idénticas a Candidate 3. Es **PRESERVED_SOURCE_ONLY**, no cierre de sus gates nativos.
- No se consultaron ticks, holdouts ni resultados económicos de estrategia.

## Bloqueo de las suites originales

El runtime ZIP de 67215 bytes y el Compile-Only ZIP de 61816 bytes coinciden con los
hashes del checkpoint y pasan CRC. Ninguno contiene los tres scripts requeridos.
Se conservaron sus inventarios, búsquedas y tres intentos de ejecución terminados con
código 2 / `No such file or directory` en
`../validation/evidence/OFFLINE_HARNESS_RECOVERY.json`.

| Script exacto faltante | SHA-256 exigido por el recibo histórico |
|---|---|
| run_v224_candidate3_offline.py | 27a7ccc97b42bea6f558fb043c57ebede74b8990aae648b2144ff04cd28e1790 |
| run_v224_candidate3_static_audit.py | 8dc7357077e1d693be3192d162bf64e140e03c5831716bf41a32e725bc8ba5c6 |
| run_v224_safety_model.py | 3cb16721a1a436bdaf5b11d785160c609eaa7e1ef845a22e6581d03ce86de61d |

Los PASS históricos 62/62, 80/80 y 25/25 se preservan como históricos, **no reejecutados**.
El recibo 80/80 además marcaba las tres comparaciones parent-emitter como
`SKIP_PARENT_NOT_DISTRIBUTED`; en esta reparación sí se recuperaron y compararon los
emitters congelados. Las 77 comprobaciones nuevas no sustituyen aquellas suites.

El preflight inicial `handoff/verify_import.py` se ejecutó con el Python incluido en
Codex tras comprobar que no existen los alias `python3`/`python`. Rechazó el árbol
preexistente con `ValueError: changed file: AGENTS.md`. Ese verificador corresponde a
la importación inicial v0.6; AGENTS.md no fue modificado por esta tarea.

## Gates posteriores separados

CTrade adversarial real; partial/lost ACK; restart con posición y working order;
two-terminal fencing; DST/session cutoff y lead autorizado (sigue en 0); parent-child
trade-by-trade parity; controller 977/977; module certs; combined canary; START_RECEIPT;
y armado CERT=1. Todos siguen pendientes y fuera de esta fase. Ver `V224_BLOCKERS.json`.

## Hashes de sources y EX5

Los hashes completos, tamaños y evidencia están en `V224_MANIFEST_SHA256.json`.

| Source | SHA-256 |
|---|---|
| QROS_DEMO_BUS_v2_2_4.mqh | `db389efd44f02af7ad437a2a49f8b50c88b5e344fa32c964c70812b930324ae5` |
| QROS_DEMO_PORTFOLIO_EXECUTOR_v2_2_4.mq5 | `721b63b96a297c5a0752a34f3439ff5babc7882e624df7c1ceb1d46fcdf99608` |
| QROS_DIV3_R3_DEMO_EMITTER_v2_2_4.mq5 | `8e285c67f2dc1a69ed84496c279bf14b394a6f597930f133bcf8badfdd0e0ffe` |
| QROS_NQX_17_31_DEMO_EMITTER_v2_2_4.mq5 | `2096a36c8ca372265fb688601a82b859615d4b3507256e19cfd7b31c579aa133` |
| QROS_RISK_KERNEL_APPROVED_v15420.mqh | `8af000aac09747b896cef4e8c9263aaf675dab4fefa07b3d9d4b7c1c170ab49f` |
| QROS_V224_MODULE_CERTIFY.mq5 | `5dccb8a5094d024e7f81f811c65e3b1db7f8ee4f7ae66e56dbb10d2422558acf` |
| QROS_V224_RUNTIME_BOOTSTRAP.mq5 | `320b42cc5a5387fed0e2cf708d4f33f5b4f380ba75121468fbbf989242c28fa4` |
| QROS_XAU_M1_DEMO_EMITTER_v2_2_4.mq5 | `e2ee32a59ded624fae32ea8534fcdd6ac234009dfbbd83de41e230a1747e0c61` |

| EX5 | SHA-256 |
|---|---|
| QROS_DEMO_PORTFOLIO_EXECUTOR_v2_2_4.ex5 | `cace12ac64107af418160762ea05348d61616ff9aa0b5d9c2523c76fff4c741f` |
| QROS_DIV3_R3_DEMO_EMITTER_v2_2_4.ex5 | `43811d5e36bd86a7d4d3ac4f1c2f0b7c9843768449a59e634ca5f1b26e177f70` |
| QROS_NQX_17_31_DEMO_EMITTER_v2_2_4.ex5 | `33a9232f7e032fae2c148fdb735e7d1518c5691529502a407800471eb109e821` |
| QROS_V224_MODULE_CERTIFY.ex5 | `4be24f1e89f4962268676206ffb5817057b4b49089297f528018e9eac86a785b` |
| QROS_V224_RUNTIME_BOOTSTRAP.ex5 | `a189509585d868dad8baa055dad6a9334f2475b5f1311e3671d757480b540ea6` |
| QROS_XAU_M1_DEMO_EMITTER_v2_2_4.ex5 | `a5652f2f3b5162bb0ded6ab592523d783c85b6535c9218f70129014469b59f79` |
