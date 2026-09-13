# R2: auditoría de bloqueo y contrato ejecutable

Estado: **BLOCKED_BY_INFRASTRUCTURE — R2 NO CALIFICADO**.

Entrada principal: `AUDITORIA_RAIZ.md`; decisión: `DECISION.json`.
No es un nuevo qualifier, no lanza MT5 y no habilita Candidate3.

Desde este directorio, con Python estándar ya disponible:

```bash
python3 test_evidence_contract.py
python3 reproduce_legacy_gate.py
```

El primer comando reproduce 27 mutaciones TEST_ONLY. El segundo verifica el SHA del
gate histórico recuperado y reproduce dos falsos positivos usando cadenas inertes.
No ejecuta las órdenes PowerShell contenidas en esas cadenas.

`evidence_contract.py --plan PLAN.json --packet PACKET.json` sólo comprueba coherencia
offline. Códigos de salida: 2 = rechazado; 3 = coherente pero NO calificado.
Nunca devuelve éxito de calificación ni un certificado R2. Su schema draft se ilustra
en `fixture()` del test, que contiene exclusivamente datos sintéticos marcados.
No hay un collector nativo ni un adaptador al ZIP original en esta entrega.

`R2_NATIVE_RECEIPT.json` es explícitamente un recibo de **no ejecución de esta sesión**.
El FAIL histórico se conserva separado y atribuido a sus fuentes documentales.
`ENVIRONMENT_FINGERPRINT.json` contiene los campos objetivo no observados como null y
`usable_for_R3=false`; sus valores históricos no son un fingerprint certificado.

MANIFEST_SHA256.json vincula todos los archivos de este suplemento salvo el propio
manifest. El commit de publicación queda como ancla externa para evitar autorreferencia.
Ninguna fuente existente del runner, qualifier, Candidate3 o baseline se modifica.

Pendiente: acceso a paquetes originales por hash y host Windows 6182; auditoría completa
del qualifier; pruebas nativas de identidad física/ownership y gates R2/R3 antes de R4.
