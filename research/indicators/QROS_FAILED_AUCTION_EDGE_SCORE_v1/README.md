# QROS Failed Auction Edge Score v1 (QFAES)

Estado científico: **PREREGISTERED_NO_RESULTS**.

## Qué intenta predecir
Si una ruptura del máximo/mínimo del día broker anterior en XAUUSD es una subasta fallida y el precio rechazará el nivel en sentido contrario.

## Lo que está congelado antes de resultados
- Sólo PDH/PDL en v1.
- BUY y SELL separados.
- Score 0–100 con cinco componentes causales y pesos fijos.
- Umbral primario de score alto = 70.
- Stop estructural más 0,05 ATR14.
- Objetivo = 1R.
- Horizonte máximo = 90 minutos y sin overnight.
- Desarrollo = 2018–2019.
- Holdout = sellado.
- No se optimizan pesos para PF.

## Interpretación
El score NO es todavía una probabilidad calibrada. Es un ranking causal preregistrado.
Sólo se promoverá a indicador con ventaja estadística demostrada si el score alto supera
el baseline con permutation test, bootstrap de lift, estabilidad anual y monotonía por bins.

## Artefactos
- `QROS_FAILED_AUCTION_EDGE_SCORE_v1_PREREG.json`
- `qros_failed_auction_edge_score_v1.py`
- `test_qros_failed_auction_edge_score_v1.py`
- `MANIFEST_SHA256.txt`
