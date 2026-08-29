# QROS ENGINE — arquitectura v0.2

Estado: `DEVELOPMENT_RUNNING`.

## Núcleo

C++20, standard library, sin runtime Python ni librerías cuantitativas externas. Python se conserva como oracle independiente de referencia.

## Flujo objetivo

`QDATA Authority → QROS IR → Causal/Event Compiler → Execution Kernel → Universe Compiler → Result Store → Gate/Supergate → Holdout Vault → Portfolio → MT5 Bridge`

## Separación de responsabilidades

- **QDATA Authority:** identidad, provenance, timezone/DST, escala, sesión y completitud.
- **QROS IR:** estrategia declarativa, tipada, sin `eval`.
- **Causal compiler:** garantiza frontier y disponibilidad temporal de features.
- **Execution kernel:** Bid/Ask, gaps, SL-first cuando proceda, sesión, costes/latencia bajo policy versionada.
- **Universe compiler:** masks/records/grafos compactos y deduplicación semántica.
- **Result store:** artefactos inmutables, content roots, receipts, CAS/fencing.
- **Holdout Vault:** separación física/capability de OOS.
- **Reference implementations:** Python + MT5, independientes del kernel rápido.

## Decisión de dependencia

Arrow/Polars/DuckDB/NumPy/Numba pueden existir como adaptadores opcionales de ingestión, ETL, diagnóstico o aceleración exploratoria. Ninguno define la semántica científica del ledger final.
