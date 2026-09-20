# Requisitos explícitos y persistencia del objetivo — QRCEL 0.6.0

El kernel admite un contrato externo congelado `QRCEL_EXPLICIT_GOAL_CONTRACT_V1`. Cada requisito identifica operación, hash de entradas, dependencias entre requisitos y profundidad mínima. Un mapa explícito vincula cada requisito a una única tarea. El kernel valida el contrato antes de abrir el almacén y lo vuelve a comprobar al reanudar.

Rechaza requisitos omitidos o duplicados, tareas no contabilizadas, reutilización de un testigo para dos requisitos, sustitución de entradas/operación, pérdida de dependencias, reducción de profundidad y cambios del objetivo respecto a su hash externo. Los checkpoints contienen contrato y mapa; restaurarlos requiere el mismo binding y código. Se preservan los límites de 100 tareas y las operaciones EXACT_SUM/CHECK_DAG.

API: suministrar juntos `goal_contract`, `goal_sha256` y `goal_mapping` al constructor de Kernel. CLI del kernel: `--goal-contract <json> --goal-sha256 <sha256-de-json-canonico> --goal-mapping <json>`. El lanzador aislado y las anclas de release siguen siendo obligatorios. El hash del contrato debe venir de una fuente externa a quien descompone el trabajo, no recalcularse para aceptar una propuesta modificada.

La comprobación acredita cobertura de requisitos explícitos, no que una descripción en lenguaje natural sea completa o correcta. El autor del contrato sigue siendo responsable de especificar todos los requisitos. `natural_language_adequacy_verified` permanece false. Sin contrato explícito el kernel conserva la ejecución local existente y devuelve `NO_EXPLICIT_GOAL_CONTRACT`; no declara satisfecho un objetivo libre.

Un requisito SCIENTIFIC conserva el bloqueo L3 y queda pendiente. El contrato no concede autoridad científica ni permite shell, herramientas externas o trading. La cobertura se deriva de resultados locales ya verificados por el kernel; llamar a una función auxiliar de proyección con datos inventados no constituye una atestación.

Validación: omisión, sustitución, duplicación, dependencias, profundidad, cambio del objetivo, mutación del objeto del llamador, recuperación en un proceso nuevo y preservación de bloqueos científicos. La validación del sistema completo, comparación de modelos, custodia sellada y promoción siguen abiertas. Los recibos de la release 0.5.0 se conservan sin modificaciones y sus hashes de código permanecen históricos.
