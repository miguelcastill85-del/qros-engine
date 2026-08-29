# Execution Policy v1

Semántica congelada del kernel v0.3:

- BUY entry = Ask observado.
- BUY exit = Bid observado.
- SELL entry = Bid observado.
- SELL exit = Ask observado.
- entrada estrictamente después de `signal_seq`.
- fill con spread cero = prohibido.
- mercado cruzado = error de datos.
- gap = primer quote ejecutable realmente observado.
- SL/TP ambiguos en un mismo tick = SL primero.
- cierre intradía = último quote ejecutable observado a o antes de `session_close_seq`, siempre posterior a la entrada.
- EOF no equivale a cierre de sesión.
- si no existe quote ejecutable posterior a la entrada = `UNRESOLVED_CLOSE`.

SHA-256 actual:

`20fae56be4a5e2d936f8af11f22ccf4092dea88185d4c8129535cf869c6580be`
