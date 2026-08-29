# Physical Authorities v0.4

v0.4 materializa y verifica las autoridades ZIP/PACKED17 vigentes. Los RAR históricos quedan únicamente como evidencia supersedida y no son fuentes activas.

## NQX

28/28 archivos ZIP pasaron tamaño y SHA-256, los 28 payloads pasaron SHA-256 y metadata/rangos, y la concatenación lógica reproduce el carrier canónico SHA-256 `6da9cf67310c2c6689bd82c20882e5e8b652196147a458be58796e5103a22608`.

El scan fresco reproduce 559,817,687 registros, 48,325 spreads cero, 162 spreads cruzados, 0 retrocesos temporales y los conteos anuales del manifest.

## XAU

35/35 archivos ZIP pasan tamaño y SHA-256. Cada payload PACKED17 fue extraído y hasheado; la concatenación exacta de los 35 payloads produce `c386dc3028943f7462f6091d1417a9733237be5e25b07aa5732c111ce11f92e4` sobre 11,850,036,456 bytes.

El scan fresco reproduce 697,060,968 registros, 1,691,627 spreads cero, 2,218 spreads cruzados, 0 retrocesos temporales y todos los conteos anuales esperados.

La primera materialización de XAU parte 029 estaba truncada. Se preservó en cuarentena y nunca se utilizó para construir el carrier final. La copia de reemplazo coincide en tamaño, SHA-256, ZIP, metadata y payload con el manifest y fue promovida al nombre canónico.

## Claim boundary

Estas verificaciones demuestran identidad física e integridad estructural del carrier. No demuestran timezone/DST del broker ni convierten automáticamente los datos en `RESEARCH_READY`.
