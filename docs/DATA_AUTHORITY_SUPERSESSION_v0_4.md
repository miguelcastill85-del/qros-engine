# QROS ENGINE v0.4 — Data Authority Supersession

Estado: `DEVELOPMENT_RUNNING`.

## Cambio autoritativo

Los antiguos RAR multipartes de XAU/NQX ya no existen como fuente operativa y quedan **SUPERSEDED / PROHIBITED_AS_ACTIVE_AUTHORITY**.

Autoridades vigentes:

- NQX: `QROS_NQX_FULL_HISTORY_v2_part001-of-028.zip` … `part028-of-028.zip`.
- XAU: `QROS_XAU_FULL_HISTORY_v2_part001-of-035.zip` … `part035-of-035.zip`.

Ambos usan payload `PACKED17`: `int64 timestamp_ms + int32 bid_scaled + int32 ask_scaled + uint8 flags`.

## NQX

- 28 ZIP.
- Carrier: `NQX_PACKED17_FULL_2018_2026.bin`.
- 9,516,900,679 bytes.
- 559,817,687 records.
- SHA-256: `6da9cf67310c2c6689bd82c20882e5e8b652196147a458be58796e5103a22608`.
- Price unit: 0.1 NDX/NQX.
- Saved catalog: `28_OF_28_SAVED_CATALOG_CONFIRMED` according to `QROS_NQX_ZIP_FILE_INDEX_v3.json`.

## XAU

- 35 ZIP.
- Carrier: `XAU_PACKED17_CENT_FULL_2018_2026.bin`.
- 11,850,036,456 bytes.
- 697,060,968 records.
- SHA-256: `c386dc3028943f7462f6091d1417a9733237be5e25b07aa5732c111ce11f92e4`.
- Price unit: 0.01 XAUUSD.

## Gate científico

La existencia del manifest/catálogo en File Library no equivale a bytes físicamente materializados en el runtime C++ actual. Por ello ambos perfiles permanecen `research_ready=0` hasta:

1. materializar los ZIP exactos mediante una ruta de File Library disponible al runtime;
2. medir tamaño + SHA-256 de cada ZIP;
3. verificar CRC/ZIP member y payload hash;
4. validar continuidad de `start_record`, timestamps y conteos;
5. reproducir el carrier SHA-256 completo por streaming;
6. completar Time Authority sin inferir timezone/DST.

No se volverá a pedir ni buscar el RAR antiguo.
