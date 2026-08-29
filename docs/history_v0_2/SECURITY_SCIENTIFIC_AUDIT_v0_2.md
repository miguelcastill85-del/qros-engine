# Auditoría adversarial QROS ENGINE v0.2

## Cerrado en v0.2

- parser declarativo sin código ejecutable;
- fixed-point + overflow checked;
- orden causal por `seq`;
- signal boundary exacta;
- session close boundary exacta;
- EOF no equivale a cierre;
- no same-tick fabricated close por datos agotados;
- crossed market fatal, zero-spread no fill;
- input SHA-256 binding;
- output final inmutable/idempotente;
- run ID determinista;
- `_GLIBCXX_ASSERTIONS` Release;
- GCC warnings `-Werror`;
- GCC `-fanalyzer -Werror` limpio;
- ASan/UBSan PASS;
- build estático reproducible en dos árboles limpios.

## Abierto / bloqueante

- QDATA timezone/DST authority;
- validación de gaps/cobertura según calendario real;
- Holdout Vault;
- lease/fencing/CAS a nivel campaña;
- event-phase state machine;
- ExecutionPolicy con costes/slippage/latencia/fallos;
- fuzzing de parser y QDATA binario;
- golden corpus real XAU/NDX;
- MT5 trade-by-trade con provenance completo.

No se autoriza promoción científica mientras estos puntos bloqueantes afecten la campaña correspondiente.
