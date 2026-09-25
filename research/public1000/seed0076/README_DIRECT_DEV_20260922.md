# WEB_SEED_0076 — Backtest directo DEV (prototipo mínimo)

**Los 60 shards antiguos permanecen completamente fuera de esta investigación.** No se han inspeccionado ni reejecutado. Se conserva la misma semilla y los mismos identificadores de dos configuraciones congeladas de muestra.

- Datos: XAUUSD M1, período DEV 2018–2019, 151.382.388 ticks PACKED17, identidad SHA-256 exacta. Barras/EMA M1 reutilizadas del archivo V220 fijado. No se incluye el histórico bruto en este ZIP.
- Mecanismo de las dos pruebas: fractal 3, empate asimétrico, CLOSE_BREAK, un disparo por fractal, EMA9>20>50 para BUY y espejo para SELL, SL fractal opuesto.
- V1 es **INVÁLIDA**: 25 salidas no ejecutables antes del cierre previsto de 23:50, en 7 fechas; las métricas originales de las operaciones parcialmente cerradas no deben utilizarse. Se preservan para trazabilidad.
- V2 es una **corrección exploratoria distinta**, con cierre fijo 19:30 del servidor (basado exclusivamente en cobertura de cotizaciones para limitar el riesgo de cierre anticipado). 1.432 operaciones simuladas, cero salidas pendientes; -491,8867 R y PF 0,6539 (spread real incluido, SIN comisiones; calendario festivo no certificado; no es Gate A ni evidencia de alfa).
- Paridad generadora independiente: un algoritmo NumPy distinto reproduce exactamente las 22.210 señales BUY y 22.082 SELL, fuente e índice de stop, en M1. No acredita otras familias ni el motor económico.
- Siete pruebas sintéticas de semántica y timing pasan para ambas versiones. El barrido de 48.280.320 configuraciones no se ha ejecutado.

**Exposición irrevocable:** DEV 2018–2019 ha quedado observado económicamente para toda la genealogía relacionada; una arquitectura distinta no lo hace OOS. El holdout no se ha abierto aquí.

## Próxima acción mínima

Compartir eventos y filtros sobre una cinta de candidatos, deduplicar máscaras físicas conservando todas las identidades causales y simular cada resultado económico equivalente una sola vez, tras añadir oracle económico independiente y costos del bróker. No optimizar la salida 19:30 usando este DEV.

Archivos de código, pruebas, CSV de operaciones, recibos, auditoría de horarios y hash de cada entrada se incluyen en este paquete. Para reanudar, recuperar los ocho ZIP originales y el carrier congelado M1 y validar los hashes publicados.
