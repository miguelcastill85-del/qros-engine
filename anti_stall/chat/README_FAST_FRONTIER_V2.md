# QROS Anti-Stall Fast Frontier v2 — progreso primero, auditoría completa sólo cuando corresponde

**Autoridad recuperada:** `main` → `control/QROS_ANTI_STALL_ACTIVE_GOVERNANCE_POINTER.json`; en la rama científica exacta `research/seed0076-direct-dev-backtest-20260922` → `control/QROS_SEED0076_DIRECT_CURRENT_CHAT_HANDOFF.json` → handoff/anchor y `fast_frontier_v2`.

## Problema científico/operativo corregido

El mecanismo Git-native v1 ya preservó el ZIP completo de los 446 recibos en Git y 16 respaldos ASCII, pero obligaba a reconstituir el ZIP de 1.052.386 bytes y a auditar 446 recibos y 452 entradas de manifiesto **en cada nuevo chat**. Se desperdiciaba el presupuesto de interacción antes de llegar al siguiente fragmento y se hacían tres commits para cerrar un bloque. El costo de reanudación crecía con el histórico.

## Algoritmo en el chat Android

1. **Auditar una sola vez el baseline:** ZIP original Git SHA-1 `688ec3...`, SHA-256 `d42420...`, plan congelado y runner exactos, 452 miembros SHA y 446 recibos; generar índice inmutable de las 710 tareas (81 KB), bitmap completo (89 bytes) y raíz SHA-256 encadenada de recibos por índice del plan. El bootstrap real es independiente del PnL.
2. **Al entrar en cada chat:** recuperar puntero vivo de la rama y su target/anchor; leer frontier inmutable de ~3 KB y **solo el delta más reciente** de 1 a 6 recibos; validar sus Git blobs y SHA-256, raíz del ledger, bitmap, contador y guardas. No descargar ZIP, 16 partes ASCII ni repetir auditoría de 446 recibos.
3. **Ejecutar un único microbloque de 1–6 tareas originales** de un solo canal, en orden exacto no ejecutado, solamente si los ticks y tapes congelados originales están materializados. El índice del plan (~81 KB) se lee sólo si hay ejecución; se prohíbe fabricar recibos desde fixtures.
4. **Una transacción de Git:** `create_blob` para delta, frontier, anchor, handoff y pointer → `create_tree` sobre el tree exacto del último commit científico → `create_commit` de un solo parent → `update_ref(force=false)` → leer SHA de todos los documentos críticos. Si otro chat avanzó, el push no-fast-forward se rechaza y conserva los recibos locales; no simular un CAS exitoso.
5. **Auditoría profunda cada 20 lotes:** volver al baseline Git y todos los deltas, recomputar ledger y bitmap independientemente, persistir un recibo de auditoría y subir el siguiente watermark. Los errores detienen promoción, sin borrar ni contaminar pruebas válidas.

**Separación obligatoria:** el fast frontier da una prueba de integridad de la *continuidad computacional*, no certifica una estrategia rentable, la comisión histórica ni un holdout limpio. W5 sigue `DEVELOPMENT_RUNNING`; Gate A/GA2/holdout permanecen cerrados.

**Riesgo restante:** la app Android no mantiene procesos después de responder. El algoritmo funciona en el turno activo con acceso a GitHub; el hecho de publicar un script en Git no ejecuta el script dentro de ChatGPT. Si faltan datos de mercado, reportar esa dependencia comprobable y continuar sólo tareas independientes. El benchmark local no representa el tiempo de conectores ni garantiza ahorro absoluto de latencia.

## Verificación

`python anti_stall/chat/qros_fast_frontier_v2.py bootstrap --baseline /ruta/ZIP --out-frontier FAST_FRONTIER_0000.json --out-index FROZEN_TASK_INDEX.json`

`QROS_W5_V33_BASELINE_ZIP=/ruta/BASELINE_446_FULL_VERIFIED.zip python -m unittest discover -s anti_stall/tests -p test_fast_frontier_v2.py -v`

La suite de auditoría profunda **requiere el ZIP científico original de GitHub** en la ruta `QROS_W5_V33_BASELINE_ZIP`. No obtiene datos de Biblioteca ni emplea un archivo local fijo del entorno de desarrollo. Su ausencia constituye una falla explícita de preparación, no un PASS automático.

No usar los recibos sintéticos de las pruebas en la rama científica: sólo el bootstrap contra los 446 recibos originales ha sido publicado en Git.
