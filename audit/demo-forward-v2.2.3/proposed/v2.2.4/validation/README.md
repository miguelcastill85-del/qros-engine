# Validación de la reparación Candidate 3

`authority/` conserva bytes históricos exactos: no editar ni ejecutar sus runners
o scripts de activación. `evidence/` separa el fallo original, reproducción,
compilación corregida, regresión y el bloqueo de las suites originales.

`compile_only_isolated.ps1` deriva del runner físico de Candidate 3. Se ejecutó
dos veces con MetaEditor 6182 copiado dentro de `reports`, en modo portable oculto,
includes copiados desde los siete headers listados en el log original, y roots nuevas.
No acepta RunRoot fuera de reports ni reutiliza una ejecución existente. Ejecuta
sólo `/compile` sobre los seis targets del gate; no ejecuta terminal ni EX5.
Los hashes de compilador y headers se conservan en `evidence/TOOLCHAIN.json`.

La regresión offline de esta reparación es reproducible con Python 3.10+:

```text
python validate_compile_repair.py --out <directorio-nuevo>
```

No requiere broker, datos, red, terminal, instalación ni API. Devuelve fallo si se
modifica cualquier componente adicional, cambia alfa fuera de las diferencias
revisadas, o no concuerdan logs/hashes de los seis EX5. No ejecuta MQL. La ausencia
de los tres harnesses históricos se reporta por separado; 77/77 no los sustituye.

Consulte `../final/REPAIR_REPORT.md` para el alcance completo, los comandos del gate
original y derivado, las diferencias de infraestructura y los bloqueos restantes.
