# RISE Transversal Audit — QROS ENGINE v0.3

## Fallos encontrados y corregidos durante v0.3

1. Test esperaba receipt para `first_ts_ns=0`, pero el contrato exige rechazo temprano del manifest. Se separó en dos tests: extent inválido y timestamp interno no positivo.
2. Replay QDATA materializaba todo el tick history. Sustituido por streaming de una pasada con hash hasta EOF incluso después de TP/SL.
3. `source_root` no distinguía flags de compilación. Añadido `build_contract_sha256`.
4. Evidencia de timezone/procedencia estaba sólo hashada, no ligada semánticamente. Convertida en receipts estructurados y cross-checks.
5. Datos sintéticos podían parecer `RESEARCH_READY`. Se añadió `purpose=TEST_ONLY|RESEARCH` y gate productivo fail-closed.
6. El campo `source_sha256` era ambiguo: en realidad era el hash del receipt de procedencia. Renombrado a `source_evidence_sha256`.
7. SHA-256 generaba texto hexadecimal mediante streams y locale. Sustituido por codificación hexadecimal byte-a-byte.
8. La comparación idempotente de artefactos usaba `ostringstream`; sustituida por lectura binaria exacta.
9. Clang detectó índice `int`→`size_t` implícito en SHA-256. Corregido usando `std::size_t`; warnings no fueron relajados.
10. `__int128` usado inicialmente para percentiles/ppm violaba `-Wpedantic`; eliminado mediante límites aritméticos explícitos y `uint64_t`.
11. GCC `-fanalyzer` dejó de completar `qdata.cpp` dentro de la ventana de ejecución tras crecer la lógica. Se registra como inconcluso; Clang Static Analyzer se ejecutó completo y pasó.

## Invariantes preservados

- fixed-point integer prices;
- BUY Ask/Bid y SELL Bid/Ask;
- SL-first;
- gaps al primer precio observado;
- no fill artificial con spread cero;
- señal y ejecución causalmente separadas;
- cierre intradía con frontera de sesión explícita;
- outputs inmutables;
- hashes y build identity en receipts.

## Riesgos que siguen abiertos

- verificador productivo de procedencia/timezone contra bytes broker/vendor reales: NO IMPLEMENTADO;
- importador QDATA real desde RAR/CSV/BIN de XAUUSD/NQX: NO IMPLEMENTADO;
- feature graph/universe compiler: NO IMPLEMENTADO;
- multiprocessing/scheduler con leases/fencing/CAS: pendiente de integración con Execution Governor;
- holdout vault físico: NO IMPLEMENTADO;
- Supergate nativo: NO IMPLEMENTADO;
- bridge MT5 trade-by-trade: NO IMPLEMENTADO en este engine;
- validación en Windows/MT5 host: pendiente;
- GCC `-fanalyzer` completo sobre el TU QDATA actual: inconcluso por límite de ejecución.

## Decisión

`DEVELOPMENT_RUNNING`.

v0.3 se acepta como checkpoint de infraestructura y corpus de pruebas, no como motor científico productivo.
