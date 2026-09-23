# QROS/RISE — Arranque entre chats, proyecto y ejecutores (v2.1)

Para cualquier nueva conversación del proyecto *Trading algoritmico* sobre QROS/RISE:

1. Leer primero el puntero activo `control/QROS_ANTI_STALL_ACTIVE_GOVERNANCE_POINTER.json` de `miguelcastill85-del/qros-engine` en `main`, verificar el commit y la release `anti_stall/README_QROS_ANTI_STALL_V2_1.md`.
2. Identificar el **lane** solicitado antes de leer checkpoints: para la campaña pública histórica rige `control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json` en `main`; para el backtest directo rige `research/seed0076-direct-dev-backtest-20260922` con sus anclajes exactos. Nunca usar el V259 histórico para reiniciar el backtest directo.
3. Recuperar Git blob, sha256/bytes y ZIP de Google Drive por ID fijado. El SHA256 de un recibo generado por sí mismo NO certifica autenticidad. La metadata de Drive no sustituye descargar y verificar bytes al promover resultados.
4. Leer el último checkpoint CERRADO del lane y ejecutar solo la **primera unidad pendiente** bajo el plan congelado. El motor anti-stall ejecuta exactamente UNA etapa por invocación, con outputs inmutables, rutas de recuperación limitadas, estado durable y Meta-Audit independiente.
5. Para backtest directo seed0076, el último checkpoint recuperado (2026-09-23) cerró 6 ventanas XAUUSD M1 W3…W13, 103.548 configuraciones y 42.894 máscaras físicas. La siguiente celda preregistrada fue `W3 STRICT_ALL_NEIGHBORS BUY/SELL`, salvo que la rama ya tenga un checkpoint MÁS NUEVO; comprobarlo siempre. Histórico DEV 2018–2019 económicamente EXPUESTO, no reutilizable como holdout. No reabrir los 60 shards congelados ni abrir GA2/holdout.
6. Persistir todos los resultados binarios en Google Drive, y el código, puntero y SHA externos en GitHub. Si hay interrupción, recuperar desde el checkpoint real y documentar el incidente. No prometer actividad entre chats si no existe un scheduler autorizado y un runner persistente.

## Enlace durable y adopción

- Código integrado: `anti_stall/scripts/qros_anti_stall_v2_1.py`.
- Auditor externo: `anti_stall/scripts/qros_meta_audit_v2_1.py`.
- Tests: `python -m unittest discover -s anti_stall/tests -p 'test_v2_1_*.py' -v`.
- CI comprobado en PR #57, ejecución `35914901370`, 37 tests. Windows nativo pendiente.
- ZIP Drive: `1QujX1rPY9wIfcnXjLeJICSq6lOg9si2o`, SHA256 `1c60482e73bc4a589e3a04b27bc8465552ec7cef6c3066f91ad95c485f30068d`.
- Carpeta Drive: `1lfMh7r2SJiu2pIm6kSCAHmvKqLBFHNOG`.

### Texto breve para las instrucciones persistentes del proyecto ChatGPT

> Al iniciar o continuar cualquier tarea QROS/RISE, recupera primero desde GitHub `miguelcastill85-del/qros-engine/main/control/QROS_ANTI_STALL_ACTIVE_GOVERNANCE_POINTER.json` y sigue `control/QROS_CHAT_PROJECT_BOOTSTRAP_v2_1.md`. Identifica el lane antes de buscar. Recupera el último checkpoint y hashes con GitHub/Drive y ejecuta únicamente el delta. Nunca repitas etapas cerradas ni mezcles el puntero V259 antiguo con el backtest directo. Usa Anti-Stall v2.1 y Meta-Audit, conserva cortafuegos científicos y no presupongas ejecución autónoma fuera de la sesión.
