# RSI v2 / G1 — Meta-auditoría adversarial (investigación, no promoción)

**Autoridad científica:** `main` V259; **autoridad QRCEL:** 0.6.2-experimental, referencia no promocionada. Esta rama sólo contiene investigación aditiva; ningún archivo científico ni del motor QRCEL activo ha cambiado.

## Descomposición 1: mecanismo y pruebas
Candidata `RSI-G1-E_CONTRACT-SIGNED_OBSERVATION_GUARD`: protocolo canónico fijado por SHA-256, seis brazos (Sol/Astra × baseline/QROS/QRCEL), distribución explícita en siete familias, doce dimensiones, límites de recursos comunes y observaciones firmadas con Ed25519 por claves nominalmente separadas para ejecutor y custodio. Un conjunto de catorce pruebas sintéticas congeladas antes del código pasó 14/14 en el entorno local; no se ejecutaron tratamientos reales de modelo.

## Descomposición 2: modos de fallo e incentivos
**Contraejemplo decisivo:** un mismo operador puede poseer ambas claves y firmar identidades ficticias de proveedor, registros de recursos falsos y una afirmación inventada de corpus sellado. El prototipo sólo demuestra la integridad de bytes respecto de claves fijadas previamente; no verifica la veracidad material de las declaraciones ni la independencia organizacional. Código y tests fueron construidos por el mismo asistente y sus casos son de desarrollo, no de evaluación reservada.

## Alcance de resultados
`RESEARCH_CANDIDATE` de preadmisión técnica. Sin comparación pareada de modelo, sin prueba independiente sellada, sin estimación de beneficio neto y sin `APPROVED_FINAL`. La dependencia `cryptography==46.0.4` añade coste de mantenimiento no cuantificado. El código, tests y prerregistro se conservan en `CORE_SOURCE.tar.gz.b64`; `DURABLE_CHECKPOINT.json` fija sus identidades y los resultados locales.

## Regresión, rollback y parada
No alterar tesis, genealogías, precios Bid/Ask, evaluación económica, MT5, riesgo ni punteros científicos. Conservar V259, GA1 Recovery Root V9/R3 y QRCEL 0.6.2 intactos. Detener investigación opcional; reanudar sólo tras evidencia externa verificable del proveedor/ejecutor, custodia genuinamente independiente, evaluación emparejada de condiciones equivalentes y corpus sellado nuevo. Si el verificador admite atestaciones materialmente falsas o bloquea observaciones reales con frecuencia inaceptable, rechazar/revertir esta candidata.
