# QROS RSI v2 — Evidencia externa E1 mediante PC, sin GitHub Actions

Versión: PC_PORTABLE_E1_v1.0. Alternativa de cero minutos de GitHub.

## Uso

En Windows, descomprime el ZIP y ejecuta `EJECUTAR_G1_EN_PC.cmd`. Requiere **Python 3** con `cryptography==46.0.4` previamente instalado. **No instala dependencias, no conecta con la red, no abre MT5 y no genera cargos.** Si la dependencia falta, falla cerrado con un error explícito. Guarda y posteriormente verifica el archivo creado en `EVIDENCE_OUTPUT/QROS_G1_PC_RECEIPT_*.zip`.

## Integridad

El ejecutor compara SHA-256 del paquete completo G1 original, SHA-256 del TAR interno, hashes individuales de las tres fuentes científicas congeladas, nombres de miembros, CRC del ZIP y 14 pruebas originales sin modificar. El archivo de salida incluye un recibo JSON, log de las pruebas y manifiesto SHA-256. El código del ejecutor debe contrastarse con el blob de GitHub de la rama aislada; de lo contrario su identidad depende sólo del ZIP entregado.

## Límites científicos

`PASS_14_OF_14` sólo prueba el comportamiento sintético del software **en ese entorno**. La máquina es declarada por el script; no constituye prueba criptográfica de equipo independiente. Ni la máquina ni dos llaves locales garantizan una custodia externa auténtica. No se ejecuta un modelo, no se verifica versión inmutable del proveedor, no existe holdout independiente ni se demuestra mejora QRCEL. La autoridad científica V259, GA1 shard11, PnL, holdout y GA2 siguen cerrados.

Para evidencia de infraestructura hospedada externa, usar el workflow de GitHub preparado en la rama de investigación exclusivamente cuando existan garantías verificables de cero cargos adicionales.
