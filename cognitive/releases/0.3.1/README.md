# QRCEL 0.3.1 experimental

Implementa inspección V191 y corrige el arranque concurrente de SQLite. QRCEL no ejecuta investigación científica ni modelos LLM. EXACT_SUM y CHECK_DAG son las únicas operaciones locales.

## Verificación y uso

Recuperar primero la autoridad activa de main y sus identidades; no seleccionar la fixture histórica ni copiar un hash del chat como autoridad vigente. Recuperar el blob del manifiesto cognitive de este commit por un canal confiable.

```bash
python3 -B -m cognitive.verify_release --repo-root . --manifest-blob "$COGNITIVE_BLOB"
python3 -B -m cognitive.validate_candidate --run-name review_031 --authority-root . --authority-blob "$ACTIVE_AUTHORITY_BLOB"
python3 -B -m cognitive.shadow --repo-root . --manifest-blob "$ACTIVE_AUTHORITY_BLOB"
python3 -B -m cognitive.kernel --repo-root . --release-blob "$COGNITIVE_BLOB" --authority-blob "$ACTIVE_AUTHORITY_BLOB" --plan cognitive/kernel_specs/EXAMPLE_PLAN.json --plan-sha256 e273e50dc088d4b1b3eebe48c0e1bff97c37c2c663429b052fcd14d6d064b591 --run-id example_031
```

El adaptador V191 reconoce exclusivamente la cola inicial congelada, con 33.094 configuraciones F03–F12 y F13 excluido. Un progreso o cambio de autoridad no contemplado exige otro adaptador verificado. La etapa general de HEAD/STATE y la subtarea de RUN_QUEUE son campos distintos; no se inventa una equivalencia de IDs ni un DAG científico ejecutable.

## Evidencia y límites

Las 128 pruebas de `checkpoints/v191_integration_031_final` pasaron. El intento anterior se conserva: encontró SQLITE_BUSY durante la inicialización de WAL. La corrección reintenta sólo contención de SQLite durante una ventana acotada; una base corrupta falla. Los commits de resultados siguen siendo transacciones serializadas.

Fixtures V189 y V191 son evidencia histórica para tests. No son autoridad ni autorizan ejecución. `validate_candidate` exige ahora el hash de autoridad de entrada; no reutiliza implícitamente V189.

La identidad de código cambió: los checkpoints 0.3.0 no se importan silenciosamente a 0.3.1. Se conservan con su versión; usar un run ID nuevo. Para rollback de software, recuperar el paquete previo 434e3e15ce673e6265f075d5ae1d23a7e81f88a5, conservar sus registros y no revertir la autoridad científica. Ese paquete carece de adaptación V191 y no debe emplearse para inspección vigente.

No hay paridad Sol–Astra demostrada, evaluación sellada, canary ni promoción QRCEL. La ontología completa y RISE fixed point siguen pendientes. Los PASS aquí son de ingeniería e inspección, no de rentabilidad, holdout o MT5.
