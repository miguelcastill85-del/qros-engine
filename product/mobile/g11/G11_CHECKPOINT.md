# QROS Mobile G11 — Secure Local Persistence

Fecha: 2026-10-02  
Padre verificado: G10 HEAD `dd9d340c34d9e6bd95a5d69f34d1141f74a887dd`  
Estado: DEVELOPMENT_RUNNING · TEST_ONLY

## Objetivo

Cerrar el primer gate restante de G10 a nivel de ingeniería: persistencia automática cifrada de borradores y del último universo sintético, recuperación al reiniciar, migración controlada, edición/borrado y fallo cerrado ante corrupción o error de escritura.

## Autoridad

- Producto: `product/mobile/QROS_MOBILE_ONLY_PRODUCT_CONTRACT_v1.md`.
- Padre: PR #75 / G10, CI `36791428837` PASS.
- Esta rama NO modifica `main`, `control/HEAD.json`, PnL, holdout, GA2, MT5 ni trading live.
- La aplicación continúa sin autoridad para declarar PASS o mutar estados científicos.

## Delta G11

1. `flutter_secure_storage 10.3.4` fijado como almacén seguro de producción; el APK resultante declara Android API 24 mínimo.
2. Hidratación antes de mostrar la app.
3. Escritura durable antes de aceptar en memoria create/edit/delete/import.
4. Esquema local V2 estricto para proyectos y migración determinista V1→V2.
5. Persistencia del último universo sintético con revalidación completa y recomputación de ambos SHA-256 al arrancar.
6. Corrupción, hash mismatch o fallo del secure store no inyectan estado y dejan alerta recuperable.
7. Editar y eliminar borradores desde el expediente.
8. Respaldo manual se conserva como JSON PORTÁTIL EN TEXTO PLANO y se diferencia explícitamente del almacenamiento cifrado automático.
9. Datos persistidos excluyen credenciales, recibos, muestra DEMO y autoridad científica.

## Gates

- G11-CODE: implementado; pendiente CI.
- G11-ANALYZE: pendiente CI.
- G11-TESTS: pendiente CI.
- G11-APK: compilación previa PASS; inspección reveló `sdkVersion:24`; gate corregido a la realidad del manifiesto y pendiente de rerun.
- G11-PHYSICAL-KEYSTORE: NO EJECUTADO. Requiere Android físico.
- G9-PHYSICAL-INDEPENDENT: continúa pendiente y no se reinterpreta como G11.

## Límites honestos

Un build exitoso y tests con un vault en memoria prueban contratos, migración, atomicidad lógica y compilación del plugin. No prueban todavía la custodia real del Android Keystore en un teléfono físico. Ese punto permanecerá NO DISPONIBLE hasta evidencia de dispositivo.

## Siguiente acción automática tras CI PASS

Abrir G12 descendiente para identidad de cliente + sesión renovable y backend sintético reanudable, manteniendo servidor-only authority y cero operaciones económicas.
