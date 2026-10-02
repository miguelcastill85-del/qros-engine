# QROS Mobile G12 — Device Sessions + Resumable Synthetic Jobs

Fecha: 2026-10-02  
Padre integrado verificable: G10+G11 `da2b18b1f5ea7c690f72007508a72ed6f6497c43`. Su tree SHA `015700369064217e462653c43648add6d0ddd167` es idéntico al tree SHA de G11 fuente `dfc8a435b9f4bac6166fb97ca056e31c06200c5c` (CI 37014105082 PASS).

## Objetivo
Cerrar los gates 2 y la parte estrictamente TEST_ONLY del gate 3 de G10 sin fingir un motor C++20 en Workers.

## Diseño
- Identidad: cliente opaco generado por servidor y vinculado a un device_id aleatorio guardado en el almacén seguro del teléfono.
- Bootstrap: bearer de un solo uso, duración máxima 300 s y scope session:bootstrap.
- Sesión: access token 15 min; refresh token rotatorio 30 días. El servidor guarda únicamente hashes.
- Rotación: cada refresh invalida access y refresh anteriores.
- Revocación: elimina índices activos y marca la sesión revocada.
- Jobs: trabajo sintético acotado, idempotente por request_id, persistido en Durable Object y reanudable por job_id tras reinicio.
- Fases: PREPARED → VALIDATED → CHECKPOINTED → COMPLETE.
- Resultado: sólo recibo de infraestructura sintética. economic_tests=0, scientific_approval=false, holdout_open=false, ga2_open=false, mt5_executed=false.

## No implementado / no autorizado
- No PnL.
- No carrier Darwinex.
- No C++20 ejecutándose en Cloudflare Workers.
- No transición científica, PASS, freeze, holdout, GA2, MT5 o trading.
- No suscripciones ni cobros.

## Gates
- G12-WORKER-UNIT: pendiente CI.
- G12-WORKER-RESTART-PARITY: pendiente CI.
- G12-FLUTTER-SESSION: pendiente implementación/CI.
- G12-FLUTTER-JOB-RESUME: pendiente implementación/CI.
- G12-DEPLOY-FREE: sólo procede después de CI PASS y verificación de infraestructura/costo.


## Evidencia de ejecución intermedia

- Run 37016679021: `Install and test isolated G12 Worker` = PASS, incluyendo restart/resume en workerd y dry-run del Worker; el run completo fue cancelado por concurrencia al llegar un commit posterior.
- Run 37016718667: cancelado antes de asignar job; GitHub rechazó rerun del run cancelado.
- Estos runs NO califican el HEAD final. Se requiere CI nuevo sobre el commit posterior a las correcciones Dart.


## Corrección CI 2026-10-02

- Run 37017028245 attempt 2 alcanzó `flutter analyze`.
- Causa raíz verificada: `Icons.resume_outlined` no existe en Flutter 3.35.4; generó `undefined_getter` y `const_with_non_constant_argument`.
- Corrección mínima: sustituir exclusivamente por `Icons.play_arrow_rounded`.
- No cambia contrato, sesión, job, ciencia, datos ni seguridad.
- Próximo gate: repetir CI completo sobre este commit.


## Reconciliación canónica 2026-10-02

- PR #78 / `product/mobile-g12-renewable-session-jobs-20261002` es la genealogía canónica por descender del padre integrado G10+G11.
- HEAD previo canónico reconciliado: `fc8065c51eb9c702cb429d69dd8f5e4379fba232`.
- PR #77 / `product/mobile-g12-session-jobs-20261002` queda supersedido como desarrollo paralelo.
- Prueba de equivalencia de base: G11 `dfc8a435...` y merge G10+G11 `da2b18b1...` comparten exactamente tree SHA `015700369064217e462653c43648add6d0ddd167`.
- Se porta el delta más estricto de #77: bootstrap de un solo uso máximo 300 s, device binding, access 15 min, refresh rotatorio 30 días, hashes server-side, GET puro de estado, POST explícito de resume, idempotencia por request_id y recuperación durable tras reinicio.
- El merge de reconciliación conserva como padres el HEAD canónico previo y el HEAD estricto de #77.
- Ningún CI previo califica automáticamente el nuevo HEAD; debe pasar el workflow completo.
- Sin PnL, holdout, GA2, MT5, trading, carrier Darwinex ni autoridad científica.
