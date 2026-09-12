# QROS RUNNER QUALIFICATION SYSTEM v1

## Objetivo

Impedir que un paquete de ejecución QROS sea entregado como “validado” cuando sólo ha pasado
integridad/hash/análisis estático, y evitar que Candidate3 vuelva a ser usado como banco de pruebas
para defectos del runner.

Este sistema separa de forma obligatoria la calificación del **runner** de la validación del
**candidato científico**.

## Estados obligatorios

1. `RUNNER_DRAFT`
2. `STATIC_QUALIFIED`
3. `NATIVE_ENV_QUALIFIED`
4. `CANDIDATE_GATE_ELIGIBLE`
5. `CANDIDATE_NATIVE_VALIDATED`

Estados de fallo:
- `RUNNER_REJECTED_STATIC`
- `RUNNER_REJECTED_NATIVE_ENV`
- `CANDIDATE_REJECTED_NATIVE`

Queda prohibido llamar `validated`, `native validated`, `PASS nativo` o equivalente a un artefacto
que no haya alcanzado `NATIVE_ENV_QUALIFIED` o superior.

## Regla de doble separación

### Gate R0 — integridad
- CRC ZIP.
- manifiesto completo.
- SHA-256/bytes de todas las fuentes.
- autoridad Candidate3 congelada.
- ninguna mutación de `QDB1.EXEC.CERT`.
- ninguna orden real autorizada.

### Gate R1 — análisis estático del runner
Se ejecuta `qros_runner_static_release_gate_v1_1.py`.
Debe:
- pasar todas las reglas BLOCKER;
- pasar todos los mutation tests;
- producir receipt SHA-bound.
Un cambio de un byte del runner invalida R1.

### Gate R2 — calificación nativa del entorno/runner
Se ejecuta **sin Candidate3** y sin órdenes al broker.
Debe certificar en el Windows objetivo:
- versión PowerShell;
- semántica de colecciones con StrictMode;
- lectura/escritura/cierre de CSV con FileShare.None;
- write → close → exclusive read → snapshot;
- copia de includes estándar;
- compilación MetaEditor 6182 `0 errors / 0 warnings`;
- Strategy Tester smoke sin trading;
- FILE_COMMON por RunId;
- fencing de dos procesos con solapamiento real;
- release + reacquire;
- restart/persistencia de un estado sintético;
- watchdog/timeout;
- evidencia fail-closed aun ante excepción;
- que el terminal activo no fue detenido/reiniciado/escrito.

R2 emite `RUNNER_NATIVE_QUALIFICATION_RECEIPT.json`.

### Gate R3 — binding de entorno
El receipt R2 queda ligado a un fingerprint:
- SHA del runner;
- SHA del harness de calificación;
- SHA terminal64/metaeditor64;
- build MT5;
- PowerShell major/minor;
- hash/snapshot de includes estándar usados;
- ruta de clones;
- contrato de servidor demo si aplica.

Cualquier cambio de fingerprint invalida R2 y obliga a recalificar el runner antes de tocar Candidate3.

### Gate R4 — Candidate gate
Sólo puede ejecutarse si existe un R2 PASS cuyo fingerprint coincide exactamente.
Candidate3 nunca vuelve a ser usado para descubrir fallos básicos del runner.

## Regresión obligatoria de defectos históricos

Cada defecto observado se convierte en una prueba negativa permanente. El gate está obligado a
detectar mutaciones que reproduzcan el defecto. Si una mutación conocida deja de ser detectada,
la release del runner falla aunque el paquete real parezca correcto.

Defectos históricos iniciales: D01–D10 en `QROS_RUNNER_DEFECT_LEDGER_v1.json`.

## Regla de fixed point

Después de cualquier defecto nuevo:
1. registrar causa raíz;
2. crear detector/regresión;
3. demostrar que la versión defectuosa falla el nuevo detector;
4. demostrar que la corregida lo pasa;
5. ejecutar nuevamente todos los detectores previos;
6. sólo entonces promover a R1/R2.

No se entrega una corrección incremental al usuario sin que el defecto recién descubierto haya sido
convertido en una regresión automática.

## Regla de mutación única

Una release de runner no puede cambiar simultáneamente:
- Candidate3;
- alfa;
- kernel de riesgo;
- runner;
- harness científico.

Si el objetivo es reparar el runner, Candidate3/harness científico deben permanecer byte-exactos.
Si hay que cambiar dos capas, se abre una genealogía nueva y se invalida toda calificación anterior.

## Regla de repetición

Si la misma familia de fallo aparece dos veces, se prohíben más parches de síntomas.
Se exige auditoría de fixed point de esa capa y una versión mayor del runner.

## Semántica de etiquetas

- `PREVALIDATED_ARTIFACT`: sólo R0+R1.
- `NATIVE_ENV_QUALIFIED`: R2+R3.
- `NATIVE_VALIDATED`: Candidate gate completado después de R2/R3.

Estas etiquetas son mutuamente excluyentes y no pueden usarse como sinónimos.

## Estado de Candidate3

Este sistema no modifica Candidate3. `QDB1.EXEC.CERT` debe permanecer `0`.
No autoriza deployment, armado ni órdenes reales.
