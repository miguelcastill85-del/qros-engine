# QROS Anti-Stall — GitHub WAL v1 (chat Android, sin PC)

**Propósito:** ejecutar estados, no reinterpretar prompts. Para W5 V33 el checkpoint real e inmutable de GitHub contiene 446/710 fragmentos; el SHA-256 del ZIP y sus 452 miembros, los 446 recibos y las 710 unidades congeladas se auditan antes de cualquier transición. El WAL almacena un índice pequeño y eventos inmutables en GitHub. Los nuevos recibos completos se guardan en deltas Git de máximo seis; no se generan ZIP completos de Biblioteca.

## Transiciones legales

`BASELINE → READY → CLAIMED → [BLOCKED] → COMMIT PREPARADO → Git CAS/readback → READY`

- `BASELINE`: audita los 446 recibos originales de GitHub; genera el evento `000000_BASELINE.json` y `control/QROS_W5_V33_GIT_WAL_CURRENT.json` sin avanzar la ciencia.
- `CLAIM`: selecciona las **siguientes unidades exactas** CH0 o CH4 no cerradas, máximo seis, con `work_id` determinista y verificación física SHA-256 del carrier original y ZIP del canal. Se publican **índice y evento CLAIM en una única transacción Git no forzada** *antes* de ejecutar.
- `EXECUTE`: usa exclusivamente el runner, plan y oráculo originales de W5 V33; no lo sustituye el WAL. El runner puede terminar con código 75 al alcanzar el quantum, lo que no equivale a un fallo científico.
- `RECOVER`: consulta el índice Git y los archivos de salida; si hay recibos completos, los valida sin recalcular; si faltan, no repite ciegamente los trabajos con resultado incierto. `BLOCKED` registra el impedimento y permite rutas independientes explícitamente autorizadas.
- `ATTEST`: valida cada JSON original, máscaras/ordinales, hashes congelados, sumas de las 11 comparaciones, flag de rechazo y firewalls; `qros_github_shard_store_v1.py build-delta` verifica adicionalmente toda la cadena Git y genera los **bytes completos de los recibos nuevos**. No permite inventar evidencia ni sustituye la ejecución independiente sobre ticks.
- `COMMIT`: una vez creado y releído el delta y las anclas/hand-offs Git, generar índice y evento COMMIT. **Delta, índice, evento, ancla, handoff y puntero científico deben quedar en el mismo commit final, o la transición no es PASS.** El transporte Git `qros_github_atomic_transport_v1.py` verifica cada blob antes de crear árbol, utiliza `force=false`, después relee HEAD y todos los blobs. Cualquier deriva requiere conciliación, nunca forzar el puntero.
- `ADVANCE`: solo si el commit final y todos los blobs pasan readback, la siguiente tarea vuelve a READY. Repetir `READY` no ejecuta tareas cerradas.

**Límite físico real:** los ticks originales de 2,57 GB y los ZIP V28 de canal están fuera de Git y requieren rehidratación con sus hashes antes de CLAIM. No se emite CLAIM ni PASS si los bytes faltan. El bot de ChatGPT no puede seguir procesando un chat cerrado: cada mensaje reabre el WAL verificando el HEAD de GitHub. La CLI Python/HTTP sirve también a hosts autorizados con `GITHUB_TOKEN`, sin exigir PC ni instalación en Android.

## Comandos básicos

Los archivos de autoridad deben proceder del conector GitHub y validarse contra su Git blob SHA-1; no se consideran fiables copias con el mismo nombre. Con el snapshot Git recuperado:

```bash
python anti_stall/chat/qros_git_wal_v1.py --baseline baseline_446.zip bootstrap \
  --pointer LIVE_SCIENTIFIC_POINTER.json --pointer-blob-sha1 <SHA1_EXACTO_DE_GITHUB> \
  --expected-branch-tip <COMMIT_SHA_VIGENTE> --out WAL_PREPARED

python anti_stall/chat/qros_git_wal_v1.py --baseline baseline_446.zip \
  next --ledger LIVE_GIT_WAL_INDEX.json --last-event LAST_EVENT.json \
  --pointer LIVE_SCIENTIFIC_POINTER.json --pointer-blob-sha1 <SHA1_EXACTO>

python anti_stall/chat/qros_git_wal_v1.py --baseline baseline_446.zip \
  claim --ledger LIVE_GIT_WAL_INDEX.json --last-event LAST_EVENT.json \
  --pointer LIVE_SCIENTIFIC_POINTER.json --pointer-blob-sha1 <SHA1_EXACTO> \
  --channel 0 --raw-ticks XAUUSD_DEV_PACKED17_151382388.bin \
  --channel-zip QROS_SEED0076_W5_V28_CHANNEL_0_FULL_CAUSAL_AND_ECONOMIC_EVIDENCE.zip \
  --expected-branch-tip <COMMIT_SHA_VIGENTE> --out CLAIM_PREPARED
```

Para un runtime con GitHub API autenticada, `qros_github_atomic_transport_v1.AtomicCAS.publish` admite **varios blobs de una sola vez**; desde ChatGPT, las llamadas equivalentes del conector GitHub crean blobs, árbol, commit y CAS, y verifican la lectura remota. En `CLAIM_PREPARED/PUBLISH_PACKET.json` constan rutas y hashes exactos del índice y evento. **No lanzar el worker antes de que CLAIM esté publicado y leído de retorno.**

Una vez que los seis recibos reales estén completos y que el validador original genere el delta Git, `propose-commit` prepara el siguiente evento y ledger. El puntero final debe señalar ancla y handoff ya verificados; no es válido un autopuntero a un commit que aún no existe. La publicación final es atómica e idempotente respecto a los `work_id` congelados.

## Evidencia local verificada y límites

- ZIP W5 original SHA-256 `d424206c8001422f4d9930b23d8eced5e7115009e40d5fe5b2f0e57ee259ec05`; Git blob SHA-1 `688ec3fa2123ec9df900c41487e4f6298b4ceea5`.
- 446 recibos originales; 452 miembros verificados del manifiesto; 710 tareas originales; 169 tareas tienen ordinales no consecutivos por exclusiones ex-ante, preservadas exactamente.
- Pruebas adversariales con **recibos sintéticos etiquetados**, no afirmaciones de nuevos trades. El hardware Windows, los datos de nueva paridad y GitHub Actions remoto requieren pruebas separadas.
- `Gate_A_approved=false`, `holdout_open=false`, `ga2_open=false`; sin nuevos resultados de PnL y sin certificación histórica de comisiones ni horarios especiales.

**Regla de no-estancamiento:** si una tarea reclama el turno sin poder completar el delta antes de terminar la respuesta, registrar la situación real y detener el worker. Recuperar en el siguiente turno desde el evento Git; jamás atribuir PASS o abrir holdout con trabajo local no persistido.
