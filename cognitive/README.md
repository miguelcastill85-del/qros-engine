# QRCEL — reparaciones verificadas, candidato 0.2.0

Estado: **IMPLEMENTED_AND_TESTED_SHADOW_CANDIDATE**. Esta entrega añade inspectores deterministas y pruebas bajo `cognitive/`. No instala hooks en los runners ni reemplaza los validadores científicos congelados. No es una promoción de QRCEL ni una demostración de equivalencia Sol–Astra.

## Resultado observado

La ejecución `checkpoints/clean_recovery_020` aprobó 78 métodos de prueba: 40 de la primera versión, 12 adicionales y 26 existentes. Una prueba adicionalmente recorre 200 grafos con semilla fija y contrasta ordenamiento topológico con cierre transitivo independiente. Son casos de software, no 200 observaciones estadísticas independientes. Los ocho escenarios DEVELOPMENT conocidos obtuvieron 0/8 comportamientos esperados en los componentes antiguos y 8/8 en el candidato. F05 evalúa lectura compatible, no ejecución científica equivalente. F02 adapta la representación del packet al nuevo contrato conservando la contradicción dimensional.

Shadow de lectura sobre la autoridad V189: PASS para el manifest y sus tres delegados, con `PREFLIGHT_REQUIRED_NO_DISPATCH`. Se preservaron los 62 archivos de control, scripts, tests, governance y handoff presentes en la copia limpia. La copia incluyó 64 archivos del repositorio, todos contrastados por blob con el árbol remoto fijado. No se afirma haber ejecutado la batería completa del repositorio de 1.079 blobs.

## Cambios posteriores validados

F09 rechaza estados COMPLETED e IN_PROGRESS con dependencias incompletas. F10 normaliza las excepciones de los tipos malformados probados y fija límites de JSON: 1.024 dígitos por entero y profundidad de contenedores 128 (raíz = 0), preservando la reconstrucción exacta dentro del contrato. F11 añade un contrato externo de procedencia y extensión a los checkpoints. Los 12 métodos nuevos prueban controles negativos, positivos y límites. La comparación original 8/8 sigue aprobada; no se convierte en 11/11 porque F11 amplía el contrato anterior.

**Cambio de API en 0.2.0:** `verify_checkpoint` requiere `expected_parent_commit` y `expected_total_count`. Deben provenir del contrato de tarea congelado del host, no copiarse del checkpoint inspeccionado. COMPLETED exige alcanzar el total, PENDING_RESUMABLE exige trabajo restante y todo rango debe estar dentro de la extensión. Esto verifica metadatos y bytes; no sustituye la validación de filas/resultados del dominio. Los consumidores opt-in deben adaptar su llamada antes de usar esta versión. No hay consumidores científicos instalados.

La versión 0.1.0 permanece recuperable en el commit `ecb9139e9e568cdde1b58ba713ebddb396f13ba0`; sus receipts históricos se conservan bajo `clean_recovery_r1`. La nueva evidencia se encuentra bajo `clean_recovery_020`. El baseline observado de F09–F11 está en `followup_baseline/OBSERVED_FAILURES.json`.

## Reparaciones y alcance

| ID | Defecto reproducido | Implementación candidata |
|---|---|---|
| F01 | Hash correcto permite documento FAIL o genealogía incorrecta | Inspección de contenido tipado, estado, claims, ámbito y genealogía |
| F02 | Los números del packet desplazan el contenido del documento | Comparación packet/documento y aritmética dimensional exacta con Fraction |
| F03 | Ruta delegada ignorada | Rutas exactas y ancla externa del manifest; comprobación de blobs |
| F04 | Campos ausentes aceptados por igualdad de valores nulos | Campos y tipos obligatorios, esquema explícito y JSON estricto |
| F05 | Controlador antiguo rechaza la cola V189 | Adaptador V189 de lectura; no inventa prerrequisitos ni despacha |
| F06 | Ciclos sin rechazo | DAG explícito con detección de ciclos y autociclos |
| F07 | Dependencias ajenas a G30 ignoradas | Todos los namespaces se resuelven o fallan cerrados |
| F08 | Hash de output inválido aceptado | Formato y bytes, inputs, identidad de autoridad, rangos y exposición |

Se añaden rechazo de rutas inseguras/symlinks/FIFO, límites de lectura, pérdida de archivos, truncamiento, alteración de outputs, reconstrucción exacta en proceso nuevo y escritura atómica de receipts de ingeniería. La compresión es codificación sin pérdida; no es compresión semántica LLM. La idempotencia probada consiste en no volver a seleccionar tareas completadas y repetir inspecciones sin efectos. No existe todavía un ejecutor de efectos con WAL/exactly-once.

## Reproducción local

Desde un checkout de esta rama, en Linux con Python 3.12 y biblioteca estándar:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m cognitive.validate_candidate --run-name local_review_001
```

El nombre debe ser nuevo. El programa escribe sólo receipts bajo `cognitive/checkpoints/<nombre>`. Los tests usan fixtures sintéticos en directorios temporales. El comparador restaura en memoria el validador baseline desde `control/recovery/qros_control_authority_validator_v2.py.gz.b64`, verificando tamaño y SHA-256 del carrier, gzip y fuente. No necesita que otro chat haya restaurado `scripts/qros_control_authority_validator_v2.py`.

Inspección sin escribir receipts:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m cognitive.shadow --repo-root . --manifest-blob 8e81e70881796288f79abfa0280e73676d19a06f
```

Ese blob corresponde exclusivamente al baseline auditado. En una sesión operacional nueva debe recuperarse primero la autoridad vigente por su fuente autorizada y recomputarse físicamente la capacidad. Nunca derivar el ancla del mismo archivo no confiable que se intenta verificar. Un cambio de epoch exige un adaptador explícito y nuevas pruebas; no seleccionar versiones por fecha o nombres.

## Límites de integración y confianza

`EvidenceContract` es una exigencia suministrada por el host confiable, separada del packet inspeccionado. El inspector compara `authority_manifest_sha256` con ese contrato; **no demuestra que el contrato haya sido delegado por la autoridad científica activa**. Sólo admite el nuevo envelope `QROS_BOUND_EVIDENCE_V1`; documentos históricos necesitan adaptadores respaldados por sus contratos reales. Nunca emitir autorización económica a partir de esta inspección.

`inspect_units` verifica la coherencia de las declaraciones y los hashes de dos fuentes distintas. Diferentes bytes no prueban independencia metodológica ni que el código ejecute lo declarado. La paridad de runners sigue pendiente y separada. `satisfied_external` sólo acepta un conjunto congelado; corresponde al host recomputar y verificar la evidencia de cada capacidad antes de suministrarlo.

El shadow certifica un predicado acotado sobre manifest/HEAD/STATE/QUEUE. No resuelve la ambigüedad histórica de redirects, ni materializa inputs de trading, ni certifica el bootstrap completo. Ningún PASS de este paquete puede promover resultados, cambiar gates o abrir periodos. Las instrucciones dentro de fixtures son datos; la prueba de injection cubre este parser, no todas las rutas posibles de un agente LLM.

## Autoridad observada y continuidad

Repositorio: `miguelcastill85-del/qros-engine`.
Baseline: `c43176df7713f5833b48589a0e86d2ae63ac6700`.
Authority Manifest: `control/CONTROL_AUTHORITY_MANIFEST_v3.json`, epoch 189, blob `8e81e70881796288f79abfa0280e73676d19a06f`.
Campaña: `QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1`.

`COGNITIVE_STATE.json` es un checkpoint de ingeniería subordinado. No es otro HEAD. La clasificación observada sigue siendo `EXPOSED_OBSERVATIONAL_ONLY`; 2022–2026 strategy PnL sigue bloqueado. No se leyó PnL, ejecutó MT5, modificó autoridad o activó infraestructura de pago.

## Decisión arquitectónica

Se implementó únicamente el subconjunto determinista que responde a fallos reproducidos, reutilizando baseline y fixtures existentes. No se ha certificado `COGNITIVE_ONTOLOGY_FROZEN`, `RISE_FIXED_POINT`, superiority, paridad o ganador entre arquitecturas. DEVELOPMENT usa errores conocidos ya expuestos. Faltan validación nueva, evaluación sellada, comparación pareada entre modelos, shadow operacional y canary antes de cualquier promoción completa.

Rollback: el baseline sigue activo y no se añadió ningún consumidor automático. No importar el paquete o retirar la rama candidata revierte su uso experimental sin migrar estado científico. No modificar ni destruir los artefactos congelados.
