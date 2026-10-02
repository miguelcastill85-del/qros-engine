# QROS/RISE — Delta de auditoría transversal: admisión de solapamientos

**Fecha:** 2026-09-22  
**Campaña:** `PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA`  
**Estado:** prototipo aislado `SYNTHETIC_VALIDATION_ONLY`; **no autoriza backtests económicos ni producción**.

## Autoridad

- `main` V259; SHA-1 pointer `5a88937d571e4bcc938c9ce71570092e0abfae6d`; `PREREGISTERED_NO_RESULTS`.
- Rama aislada `research/seed0076-first-gate10-20260922`, alcance SHA-1 `ab31ded2702f57b54eebc052f1c8aa2737cf2479`.
- Política congelada de solapamiento `690e0b82233b22fb800693741eede53ce223f5c2`.
- Contrato de normalización W09B v1.1 `5d7006c5b54d4647113c7caab5107e8c9229d2bf`.

## Resultado ejecutado

El código nuevo `qros_seed0076_overlap_admission_v1.py` implementa FIFO determinista por candidato; no permite reentrada con trigger igual al timestamp de salida; produce ledger de rechazos; comprueba Bid/Ask indirectamente mediante R y el stop/dirección ya normalizados (no pretende probar los ticks subyacentes); liga los hashes reales de los archivos sintéticos y el recibo de normalizador; detecta inputs inconsistentes; publica un único directorio de salida atómicamente y verifica reanudación byte a byte. **Se probaron 30 casos y 240 comparaciones semialeatorias frente a un bucle de referencia separado; los resultados figuran en el recibo.**

Contraejemplos: el prototipo experimental previo aceptaba `STOP` BUY por encima del stop, así como `R=-99` con entrada 100, stop 90 y salida 105. El nuevo código rechaza ambos. Esto demuestra una carencia en la *validación sintética anterior*, no operaciones reales defectuosas.

## Interfaz todavía insuficiente para producción

El output congelado de W09B solo contiene 14 campos: no expone `session_close_timestamp`, fecha de trading según broker, zona horaria/DST, ni `entry_carrier_sequence` y `exit_carrier_sequence`. Por tanto un downstream que reciba solo `normalized_trades.jsonl` **no puede demostrar por sí solo** el cierre intradía, la selección del primer tick ejecutable ni el orden físico de ticks con timestamps repetidos. No inventar dichos campos ni inferir fechas UTC: exigir prueba adicional de origen y paridad trade-by-trade del normalizador antes de la admisión de producción.

El recibo sintético puede ser internamente coherente sin probar un productor de ticks real; exigir replay independiente con bytes originales, código/runner recuperables, máscaras exactas, sesión congelada, receipt oracle y guard de admisión de PR #56. Este prototipo no abre `GA2`, holdout, shard11 ni despliegue MT5.

## Ejecución local

```bash
python test_qros_seed0076_overlap_admission_v1.py
python qros_seed0076_overlap_admission_v1.py --input RUTA_FIXTURE_SINTETICO --output RUTA_NUEVA_SALIDA
```

Los tests crean sus fixtures temporalmente. El script rechaza el modo `PRODUCTION` incluso si el manifiesto afirma PASS. La ruta de salida debe ser nueva o coincidir exactamente en bytes con un checkpoint completo existente.

## Siguiente acción determinista

1. Ejecutar W09B primaria y oracle **reales** sobre el mismo fixture de ticks sintéticos, verificar paridad de las salidas de 14 campos y pasar el resultado al adaptador. No reutilizar un recibo simulado como certificación de origen.
2. Diseñar extensión de provenance mínima sin modificar la semántica congelada (timestamp de sesión, trading_date broker y secuencias físicas) y falsarla con DST, igualdad temporal y perturbaciones futuras. Congelar prospectivamente antes de producción.
3. Únicamente después, recuperar `XAUUSD BUY M1` DEV `3ddb3c...` y masks exactos, verificar raíces 303572/aliases y ejecutar el gate de los primeros diez según FIFO, BY `q=1/1200`; holdout sellado.
