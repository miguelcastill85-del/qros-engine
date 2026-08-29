# Auditoría adversarial QROS ENGINE v0.1

## Hallazgos y correcciones

### A1 — "crear otro Python" generalista
Severidad: ALTA (riesgo de alcance/maintenance).
Problema: competir con un runtime generalista consume esfuerzo sin aumentar alfa.
Corrección: runtime especializado QROS; Python sólo referencia/adaptador opcional.
Estado: CORREGIDO EN ARQUITECTURA.

### A2 — DSL con código ejecutable/eval
Severidad: CRÍTICA.
Problema: inyección, no reproducibilidad y estrategias capaces de saltarse causalidad.
Corrección: intent/IR declarativo, versión explícita, lista cerrada de claves, sin eval.
Estado: IMPLEMENTADO v0.1.

### A3 — precios/retornos en floating point
Severidad: ALTA.
Problema: diferencias por plataforma/orden de operaciones y fronteras de SL/TP.
Corrección: fixed-point int64 + R como fracción exacta; checks de overflow.
Estado: IMPLEMENTADO v0.1.

### A4 — causalidad por timestamp únicamente
Severidad: CRÍTICA.
Problema: varios ticks pueden compartir timestamp; se pierde orden dentro de la marca temporal.
Corrección: `seq` autoritativo; intent incluye `signal_seq`; entrada exige seq posterior.
Estado: IMPLEMENTADO y testeado.

### A5 — dataset intercambiable silenciosamente
Severidad: CRÍTICA.
Problema: una misma estrategia podía correr contra otros bytes sin evidenciarlo.
Corrección: `data_sha256` obligatorio y receipt de input/intent/ledger.
Estado: IMPLEMENTADO y negative-test PASS.

### A6 — test suite falsa en Release
Severidad: CRÍTICA.
Problema detectado durante la propia auditoría: los primeros tests usaban `assert`; `NDEBUG` los elimina en Release.
Corrección: `REQUIRE` no eliminable + warnings como errors.
Estado: CORREGIDO; Release tests ejecutan condiciones reales.

### A7 — overflow signed en SL/TP
Severidad: ALTA.
Problema: overflow int64 en C++ puede ser undefined behavior.
Corrección: aritmética checked; caso extremo devuelve DATA_ERROR.
Estado: IMPLEMENTADO; sanitizer/test PASS.

### A8 — last-writer-wins en artefactos
Severidad: CRÍTICA.
Problema: dos procesos podían promocionar bytes distintos sobre la misma ruta.
Corrección v0.1: final inmutable; hard-link atomic promotion, `fsync`, conflicto de bytes => error; rerun idéntico => idempotente.
Estado: IMPLEMENTADO para artefactos locales Linux.
Pendiente: lease/fencing/CAS de scope para campañas distribuidas.

### A9 — asumir UTC/DST
Severidad: CRÍTICA científica.
Problema: una normalización prematura puede mover sesiones/eventos.
Corrección: el kernel recibe `session_day` explícito y no infiere timezone.
Pendiente: QDATA Authority debe registrar evidencia de timezone/DST y transformación.
Estado: PARCIAL; no apto aún para ingestión productiva.

### A10 — C++ memory safety
Severidad: ALTA.
Problema: C++ permite UB/memory errors.
Mitigación: núcleo pequeño, RAII/STL, warnings -Werror, ASan+UBSan, parsing sin punteros crudos, fuzz/property tests futuros.
Estado: SANITIZERS PASS en v0.1; riesgo residual existe.

### A11 — optimización que cambia semántica
Severidad: CRÍTICA científica.
Corrección: reference interpreter independiente, golden ledgers, byte-parity y promotion gate.
Estado: ejemplo y randomized parity implementados; ampliar a corpus real.

### A12 — holdout leakage
Severidad: CRÍTICA científica.
Problema: si el mismo proceso puede leer development y holdout, la separación depende de disciplina.
Corrección objetivo: Holdout Vault con capability tokens/paths inaccesibles al miner; recibo de apertura única.
Estado: PENDIENTE. Bloquea uso de QROS Engine para selección OOS real.

### A13 — formato binario prematuro
Severidad: MEDIA.
Problema: optimizar I/O antes de congelar schema puede generar migraciones y corrupción difíciles de detectar.
Corrección: v0.1 usa CSV mínimo sólo como oracle; QDATA binario se diseña después de manifests/golden data.
Estado: DECISIÓN CORREGIDA.

### A14 — skill como fuente de verdad
Severidad: ALTA.
Problema: una skill puede cambiar o ser aplicada de forma incompleta; no debe decidir semántica científica.
Corrección: specs/tests/hashes del repositorio son autoridad; skill sólo orquesta y verifica gates.
Estado: DECISIÓN CONGELADA PARA v0.1.

## Verificación ejecutada

- CMake Release con GCC 14.2 y C++20: PASS.
- warnings estrictos con `-Werror`: PASS.
- unit tests Release: PASS.
- ASan + UBSan Debug: PASS.
- C++ vs intérprete Python independiente en ejemplo golden: BYTE PARITY PASS.
- randomized parity: 20 casos, seed 20260827: PASS.
- SHA-256 propio vs `sha256sum`, vector `abc`: PASS, `ba7816bf...15ad`.
- data authority hash mismatch: negative test PASS.
- immutable output conflict: negative test PASS.
- rerun idéntico: idempotent PASS.
- binario Linux x86-64 estático: construido; `ldd` informa `not a dynamic executable`.
- microbenchmark sintético 1.000.000 filas: C++ ~201.5 M filas/s; Python reference ~2.54 M filas/s; ratio ~79.36x.

El microbenchmark mide un scan/audit/replay mínimo en memoria. NO representa aceleración end-to-end de QROS ni incorpora I/O, features, minería, clustering o Supergate.
