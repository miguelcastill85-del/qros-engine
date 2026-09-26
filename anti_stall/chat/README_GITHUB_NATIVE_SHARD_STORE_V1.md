# QROS/RISE Anti-Stall: GitHub como almacenamiento duradero y mecanismo de ejecución por turnos

**Implementación, no solo instrucciones:** `qros_github_shard_store_v1.py` ejecuta la auditoría byte por byte, detecta recibos duplicados y tareas fuera del plan congelado, prueba integridad de Git ASCII y construye/valida un delta completo de **máximo seis fragmentos originales**. Sus 14 pruebas adversariales independientes utilizan fixtures sintéticos; el archivo auténtico W5 se verificó por separado con 446 recibos y 452 miembros del manifiesto. El script no hace backtesting ni acredita por sí solo la paridad con los ticks; esa validación la ejecuta el oracle original congelado.

## Evidencia recuperable sin Biblioteca

Rama científica: `research/seed0076-direct-dev-backtest-20260922`.

`research/public1000/seed0076/direct_dev/v33_git_native_evidence/BASELINE_446_FULL_VERIFIED.zip` es un *blob Git nativo* con el ZIP original, sin recomprimir. El SHA-256 original es `d424206c8001422f4d9930b23d8eced5e7115009e40d5fe5b2f0e57ee259ec05`; Git blob SHA-1 `688ec3fa2123ec9df900c41487e4f6298b4ceea5`. Para clientes conectados donde el conector no puede decodificar blobs binarios, la misma evidencia está accesible en `ascii_parts/part_000.b64` a `part_015.b64`, con hashes independientes en `BASELINE_446_ASCII_INDEX.json`. La segunda representación es **transporte de solo lectura**, no otra autoridad científica.

Con los 16 archivos recuperados directamente de GitHub, ejecutar:

```bash
python anti_stall/chat/qros_github_shard_store_v1.py restore-ascii \
  --folder ascii_parts --index BASELINE_446_ASCII_INDEX.json \
  --sha256 d424206c8001422f4d9930b23d8eced5e7115009e40d5fe5b2f0e57ee259ec05 \
  --out baseline_446.zip
```

El programa verifica el SHA-1 de **cada blob Git**, el SHA-256 de cada parte, el ZIP completo, CRC, 452 entradas del manifiesto, 446 recibos, las 710 tareas congeladas, los 11 campos comparados y la ausencia de apertura de gates. Si falta una sola parte, falla cerrado. No hay dependencia de la Biblioteca para esta recuperación.

## Delta Git nativo para continuar

Cuando estén disponibles **recibos nuevos verdaderos**, ya comparados independientemente contra los archivos originales de canal:

```bash
python anti_stall/chat/qros_github_shard_store_v1.py build-delta \
  --zip baseline_446.zip --sha256 d424206c8001422f4d9930b23d8eced5e7115009e40d5fe5b2f0e57ee259ec05 \
  --new-dir NUEVOS_RECIBOS_ORIGINALES --out DELTA_447_452.json
```

Para ciclos posteriores, añadir un `--previous-delta` **por cada delta anterior, en orden**. El programa valida parent SHA-256, plan y runner original, identidad de los ordinales, coincidencia de rechazo/trades/campos, rechazo de duplicados y límites máximos; no selecciona resultados económicos. Los bytes completos de los nuevos recibos van dentro del delta con SHA-256, no solo sus nombres. Subir cada delta como archivo Git inmutable, releerlo, crear recibo de Git y actualizar el puntero científico con compare-and-swap. **Sin esa promoción, no comenzar otros seis.**

`verify-chain` reconstruye el estado usando exclusivamente el baseline Git y los deltas Git, identificando el primer fragmento pendiente en CH0 y CH4. Los ZIP completos posteriores a 446 no se regeneran ni suben en cada ciclo: basta el nuevo delta y el índice Git apéndice.

## Barreras reales

GitHub **no** recibe los 2,57 GB de ticks originales del broker en objetos Git convencionales; conserva SHA y rutas de los carriers originales inmutables. Conector ChatGPT GitHub no acepta rutas locales directamente. Si es inevitable usar un puente temporal de texto para transferir los bytes de un proceso local al conector, se elimina después de la comprobación de retorno en GitHub; **no se crean nuevas versiones duraderas de la Biblioteca**.

El modo Android funciona al procesar cada mensaje con herramientas. GitHub y la app Android no suministran un daemon automático al cerrar el turno. No reabrir Gate A, holdout, GA2 ni alterar W5, PnL o broker fees sin los gates originales.
