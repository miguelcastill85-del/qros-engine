# QROS ENGINE v0.4

Runtime cuantitativo nativo experimental para QROS/RISE.

Estado: `DEVELOPMENT_RUNNING`.

v0.4 cierra la **custodia física y carrier PACKED17** de las autoridades activas NQX y XAU, pero mantiene `research_ready=0` hasta demostrar de forma independiente la autoridad timezone/DST del reloj fuente.

## Autoridades físicas activas

### NQX
- ZIP: 28/28 verificados físicamente.
- Carrier: 559,817,687 registros; 9,516,900,679 bytes.
- SHA-256 carrier: `6da9cf67310c2c6689bd82c20882e5e8b652196147a458be58796e5103a22608`.
- out_of_order: 0; zero_spread: 48,325; crossed_spread: 162.
- Estado: `ACTIVE_PHYSICAL_AUTHORITY_CUSTODY_AND_CARRIER_VERIFIED`.

### XAU
- ZIP: 35/35 verificados físicamente.
- Comprimido total: 3,988,985,549 bytes.
- Carrier: 697,060,968 registros; 11,850,036,456 bytes.
- SHA-256 carrier: `c386dc3028943f7462f6091d1417a9733237be5e25b07aa5732c111ce11f92e4`.
- out_of_order: 0; zero_spread: 1,691,627; crossed_spread: 2,218.
- Parte 029: la copia truncada (45,072,384 bytes, SHA `76d24e...1281a`) quedó en cuarentena; la copia válida (124,142,300 bytes, SHA `5ae00d...c3040`) fue promovida al nombre canónico.
- Estado: `ACTIVE_PHYSICAL_AUTHORITY_CUSTODY_AND_CARRIER_VERIFIED`.

## Binario

- Linux x86-64 estático: `bin/qros`.
- SHA-256: `15a69d9f8f32082985267d4e8c65d526f9e290278666c8dca8336e4a6194dc6a`.
- `ldd`: `not a dynamic executable`.
- source_root: `de32d1c1e45e63f6a808ff9a867f9722f1d89257b15fd5137193988dc63af5d9`.
- build_contract: `539a6e57c5230416a996f63f30c3164981ca568d93e8fc56c7f4d1943037e3ac`.

## Gates de implementación

- GCC 14.2 Release warnings-as-errors: PASS.
- Clang 17 Release warnings-as-errors: PASS.
- CTest Release: 2/2 PASS.
- ASan: PASS.
- UBSan: PASS.
- Clang Static Analyzer, incluidos `text_snapshot.cpp` y `main.cpp`: PASS.
- Dos builds Release limpios byte-idénticos: PASS.
- Dos builds estáticos limpios byte-idénticos: PASS.
- Autoridades RAR legacy activas: 0.

## Límite científico

`PHYSICAL_CUSTODY_AND_CARRIER_PASS` no equivale a `RESEARCH_READY`.

Pendiente obligatorio: demostrar `Time Authority` mediante evidencia independiente que vincule el reloj servidor con UTC/DST y las sesiones reales. Hasta entonces v0.4 no autoriza minería productiva dependiente de sesión, apertura de holdout, Supergate productivo ni PnL nuevo basado en una timezone asumida.
