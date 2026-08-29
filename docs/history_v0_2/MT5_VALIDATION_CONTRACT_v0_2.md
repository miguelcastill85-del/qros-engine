# MT5 Validation Contract — borrador v0.2

Estado: contrato de diseño; implementación MT5 pendiente.

## Problema

El modo "real ticks" de MT5 es la validación externa preferida, pero la documentación oficial indica que el Strategy Tester compara ticks con barras M1 y puede descartar ticks inconsistentes y generar ticks sustitutos. Si faltan ticks para una barra M1, también puede generar ticks.

Por tanto, `MT5 PASS` sin provenance es insuficiente.

## Receipt obligatorio por validación futura

- `mt5_terminal_build`
- `tester_agent_build`
- broker/servidor/cuenta de validación
- símbolo exacto y propiedades del símbolo
- intervalo solicitado
- modo del tester (`Every tick based on real ticks` requerido cuando aplique)
- timezone/session evidence externa a MT5
- hash del EA/MQ5 fuente
- hash del EX5 compilado si puede obtenerse de forma estable
- hash de parámetros SET
- hash del candidato QROS congelado
- hashes de datos/exportaciones disponibles
- conteo de ticks/barres observado
- detección de minutos con ausencia/discrepancia cuando pueda extraerse
- ledger MT5 normalizado
- hash del ledger
- reporte de paridad trade-by-trade con QROS
- divergencias clasificadas: DATA / SIGNAL / FILL / COST / SESSION / ROUNDING / UNKNOWN

## Regla

MT5 es una implementación independiente indispensable, pero no tiene autoridad para reescribir silenciosamente la especificación QROS. Toda divergencia debe resolverse causalmente; no se ajusta el candidato después de observar MT5 para hacerlo coincidir.
