# QROS/RISE — ANTI-STALL / INCIDENT MAX v2.1 — EVIDENCE-NATIVE

**Alcance:** gobernanza y control de ejecución. No modifica algoritmos de trading, resultados, MT5, GA1, GA2, holdout, datos ni parámetros económicos. Se entrega en rama de gobernanza aislada; no mezclar con el puntero científico V259 de `main`.

## Diagnóstico trazable

1. **Control declarativo sin enforcement completo.** El governor v1 existente implementa *leases* de ramas y caducidad, pero su política de liveness se aplica solo parcialmente. No registra por unidad de trabajo los bytes de entrada/salida ni asegura la reanudación desde la última unidad cerrada.
2. **Autoridades entrelazadas.** `main` conserva el puntero V259 de la investigación histórica, mientras `research/seed0076-direct-dev-backtest-20260922` ha cerrado W3…W13 y auditado sus seis ventanas. Usar el puntero de `main` para reiniciar el backtest directo induce trabajo duplicado. El snapshot integrado reconcilia la rama específica, la identidad Git y la metadata de Drive.
3. **Prueba de procedencia insuficiente.** El prototipo local v2.0 empleaba un hash del estado generado por el propio estado y aceptaba un JSON local con `verified_remote_readback=true`. Un atacante que modifique ambos puede forjar el resultado. v2.1 exige un plan con SHA externo y, para etapas externas, la coincidencia exacta con un Git blob fijado de antemano y un contraste independiente de metadata de Drive.
4. **Problemas operacionales reales en el prototipo.** Bloqueo `fcntl` solo Linux, espera indefinida por lock, `subprocess.run` sin garantía de matar descendientes, journal separado del estado que podía divergir tras un corte. v2.1 incorpora bloqueo de duración limitada Linux/Windows, eliminación del grupo de procesos al agotar tiempo (certificación Windows todavía pendiente), journal integrado con escritura atómica y reconciliación desde la unidad cerrada.

## Componentes

- `scripts/qros_anti_stall_v2_1.py`: ejecutor de **una sola unidad por invocación**, plan y código de entrada fijados por SHA, salidas verificadas byte a byte, reintentos solo por rutas equivalentes congeladas (máximo dos), persistencia `fsync`+`os.replace`, manejo de interrupciones sin ejecución implícita duplicada. Sin dependencias externas de Python.
- `scripts/qros_authority_reconciler_v2_1.py`: reconcilia un snapshot construido **con lecturas frescas de GitHub y Google Drive**; exige SHA del snapshot fijado externamente, árbol Git de la rama vigente, cadena cronológica, contadores y readback de Drive. Separa explícitamente ciencia `main` de la rama del backtest.
- `scripts/qros_meta_audit_v2_1.py`: verificador separado, sin importar el ejecutor. Calcula sus propias huellas, comprueba el estado/cadena/eventos/bytes, contratos de entrada, identidad de la rama y blindajes científicos. Para certificar una etapa externa necesita bytes del anclaje Git y metadata de Drive recuperada por vía independiente.
- `tests/`: pruebas unitarias adversariales y de regresión. `scripts/qros_anti_stall_v2_0_prototype_REFERENCE_ONLY.py` permanece solo para contraste; NO usarlo para producción.
- `control/QROS_SEED0076_DIRECT_RECOVERED_LANE_SNAPSHOT_20260923_v1.json`: snapshot recuperado del backtest directo. El W11 confirmado sirve de línea base; W13 y auditoría final son las dos etapas cronológicas siguientes. `next_automatic_action` apunta a W3 `STRICT_ALL_NEIGHBORS` ya preregistrado. El snapshot **no** reabre el holdout.

## Ejecución local

```bash
python scripts/qros_authority_reconciler_v2_1.py \
  --snapshot control/QROS_SEED0076_DIRECT_RECOVERED_LANE_SNAPSHOT_20260923_v1.json \
  --snapshot-external-sha256 <SHA256_PUBLICADO_EN_GITHUB> \
  --live-branch-tree-sha <ARBOL_GIT_REAL_DE_LA_RAMA>

python -m unittest discover -s tests -p 'test_v2_1_*.py' -v

python scripts/qros_anti_stall_v2_1.py init \
  --work <CARPETA_DE_TRABAJO> --plan <PLAN_CONGELADO.json> \
  --expected-plan-sha256 <SHA256_DEL_PLAN_FIJADO_EN_GITHUB>
python scripts/qros_anti_stall_v2_1.py status \
  --work <CARPETA_DE_TRABAJO> --plan <PLAN_CONGELADO.json> \
  --expected-plan-sha256 <SHA256_DEL_PLAN_FIJADO_EN_GITHUB>
```

Para ejecutar un lote local, `run` procesa **exactamente la próxima etapa**. `recover` solo promueve una etapa interrumpida cuando sus hashes y tamaños de salida estaban fijados de antemano en el plan. Las etapas `external` precisan un Git blob remoto fijado y un readback de Drive; el estado local no confiere esa prueba por sí mismo.

**No ejecutar `run` repetidamente si devuelve HALTED.** Un fallo de infraestructura deja recibo reanudable; una discrepancia científica falla cerrado y se investiga desde el último punto válido. Cuando expire el contexto de conversación, se recupera el snapshot de la rama vigente y se verifica el *live branch tree*; jamás se regresa a W13 si el snapshot prueba que ya se cerró.

## Meta-Audit y alcance de los PASS

- 37 pruebas locales automatizadas: reanudación sin duplicación, captura de procesos excedidos, contención de locks, preservación de entrada y plan, alteración de archivos y recibos, cambios de rama, progreso inventado, CSV/ZIP fuera del contrato y comparación independiente. El detalle está en `governance/QROS_META_AUDIT_CONTRAST_20260923_v1.json`.
- Prueba operativa actual: snapshot real W11→W13→auditoría final reconciliado en `103.548` configuraciones y `42.894` máscaras físicas. Esta auditoría de autoridades no implica una auditoría económica ni equivale a verificar todas las operaciones de trading.
- **Limitaciones expresas:** la API de Drive devuelve metadata, no SHA-256 nativo para cada ZIP; verificar `size` y un hash previamente fijado en Git **no demuestra** que el Drive actual conserve esos mismos bytes sin descargarlo y rehashearlo. Un JSON presentado como readback puede falsificarse; solo debe generarse a partir del conector y volverse a leer de manera independiente. El mutex Windows y la terminación del árbol en Windows son candidatos diseñados, no probados en ese SO. No se promete continuidad autónoma de un chat tras expiración de sesión sin disparador externo; se garantiza checkpoint reanudable.

## Persistencia y activación

La fuente primaria de archivos binarios es Google Drive y la de código/punteros/hashes es GitHub. El ZIP completo lleva `FILE_MANIFEST_SHA256.json`, `PACKAGE_SHA256_EXTERNAL.txt` se entrega por separado a GitHub y el readback de Drive registra su ID y tamaño. Solo declarar gobernanza global **ACTIVA** después de que el código y manifiesto estén publicados, el Meta-Audit y tests pasen, y el puntero activo se instale en `main` mediante reconciliación terminal.
