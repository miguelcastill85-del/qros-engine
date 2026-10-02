# QROS/RISE — W09B ↔ solapamiento, integración sintética

**VERIFICADO**: cuatro archivos W09B originales recuperados byte a byte de GitHub y comprobados contra Git blob SHA-1; se reutiliza sin cambios la política congelada de solapamiento. El integrador ejecuta W09B primario y oráculo sobre 13 escenarios idénticos de ticks Bid/Ask con secuencia física compartida; compara el JSONL de 14 campos **byte a byte** antes de admitir eventos con la política FIFO. Resultado: 13/13 paridad, 6 admitidas y 7 rechazadas, 23 pruebas adicionales PASS.

**FALSO PASS DE VALIDACIÓN SINTÉTICA**: ambos módulos originales aceptan `bool` como `int` en algunos timestamps y secuencias; el preflight aislado rechaza el tipo, y el test conserva el contraejemplo. No existen lecturas de PnL histórico de esta ejecución.

**RIESGOS ABIERTOS**: la estrategia de normalización acepta entrada y salida en el mismo tick, stop activado en el tick de entrada y ticks de spread cero. Se observó la **aceptación del código**, no que Darwinex acepte esas órdenes reales ni que los históricos contengan ese problema. No se debe promover a económico sin vincular sesión real, costes, reglas de colocación y fuente de ticks. Una señal disponible en el mismo timestamp que la entrada requiere orden físico independiente: sidecar sintético la pone en cuarentena si falta.

**EJECUCIÓN local del paquete (sin pip):** `python test_qros_w09b_overlap_seam_integration_v1.py`; o `python qros_w09b_overlap_seam_integration_v1.py --output NUEVA_RUTA`. El integrador requiere un directorio de salida nuevo; el ZIP contiene fixtures y receipts reproducibles.

**CIENCIA**: main V259 `PREREGISTERED_NO_RESULTS`; rama PR #56 aislada. No backtest histórico, no holdout, no MT5, no autorización de producción. Próximo delta: carriers DEV/masks exactos XAU BUY M1 y contrato broker de sesión/stop antes del gate.
