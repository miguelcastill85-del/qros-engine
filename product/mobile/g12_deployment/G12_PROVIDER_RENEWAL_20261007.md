# Reanudación G12 — 7 de octubre de 2026

Objetivo: reanudar el despliegue gratuito del backend sintético G12 ya preparado, conservando APK, Android35 y transparencia Rekor válidos.

## Estado auditable

- **VERIFICADO**: rama de producto `product/mobile-g12-renewable-session-jobs-20261002`, PR #78 draft sobre G10. Recuperado checkpoint V5 de `fe2c3eb18532d48926add8c7d0bfcd84e7c1412f`.
- **VERIFICADO**: APK 0.12.3+15, 146668121 bytes, SHA256 `8bf45b7a13d519866d91dcfe72592a5e5cd5933a63a9025a96207f94895be456`. Evidencia CI37310065707, Flutter59/59, Worker7/7, paridad G9 1/1, Android35 PASS conservada. No recompilación ni repetición en esta recuperación.
- **VERIFICADO**: CI Sigstore37313164714 e inclusión Rekor3088220065 conservados. La transparencia de un hash no establece custodia independiente del backend.
- **VERIFICADO**: [preflight37615888665](https://github.com/miguelcastill85-del/qros-engine/actions/runs/37615888665), fuente `255c27622913fe89026f94b22541266814d1bae6`, terminó FAILURE. Pruebas de redacción/fail-closed 5/5 PASS; primera lectura real de Cloudflare devuelve HTTP401/error10000. No escritura al proveedor ni intento de despliegue.
- **VERIFICADO**: artefacto11479935197, 532 bytes, SHA256 `62eee77c25d6fd8a544131d0ea32b3d35cd9c77288babdf553ff4985e7cf79e9`. Único miembro JSON546 bytes, SHA256 `469a34cfa906a3b8c1609a71516bf8fd95d306f0357ce4f9a1cb8358a821bf4e`, descargado y verificado independientemente.
- **VERIFICADO**: navegador de esta sesión muestra un error de verificación de Cloudflare y Sign in deshabilitado. Sin entrada de credenciales ni repetición de intentos.
- **INFERIDO**: caducidad probable, porque la captura histórica del token indicaba 5 de octubre. HTTP401 por sí solo no distingue caducidad, revocación o credencial incorrecta.
- **NO DISPONIBLE**: plan Workers Free actual. `REPORTADO_EXISTING_GITHUB_GATE` en el recibo es una variable histórica, no una lectura actual del plan; “Adelante” autoriza continuar pero no confirma ese hecho.
- **NO DISPONIBLE**: URL HTTPS G12 desplegada y Android físico G12. El origen fijado en la app es candidato: no presentarlo como servicio activo.
- **VERIFICADO**: cero nuevas operaciones económicas, servicios facturables o cambios a main. Main leído: `4ee8a528b5af6109f6cc6fa7a4dea4fee639c828`; MOBILE_PRODUCT_HEAD v11 sin promoción. Frontera científica V259 previa conservada; no nueva validación científica.
- **REPORTADO**: prueba física G9 anterior del usuario, conservada; no constituye aceptación de G12.
- **VERIFICADO**: no jobs de esta recuperación siguen ejecutándose. Impacto portafolio: ninguno; entrega sigue TEST_ONLY con firma debug, sin comercialización habilitada.

## Intervención indispensable: reemplazar el secreto rechazado

No hay capacidad disponible para leer/escribir GitHub Actions Secrets; el navegador no supera la verificación del proveedor. Sólo el usuario autenticado puede completar este paso. La autorización de despliegue previa sigue vigente.

1. En tu propia sesión Cloudflare abre **Manage account → Account API tokens → Create Token**. Usa un token personalizado para la misma cuenta; nombre `qros-mobile-g12-github-actions`, duración **7 días**.
2. En la política de **cuenta**, selecciona únicamente **Workers Scripts → Edit** y **Account Settings → Read**. El resumen puede mostrar `Workers Scripts Write`. Conserva la misma cuenta específica. No agregues política de zonas, Workers Routes, Cloud Connector, Pages, KV, R2, Billing ni Admin.
3. Revisa y pulsa **Create Token**. Copia el valor directamente a GitHub; no lo envíes al chat, capturas, código, APK ni logs.
4. En [qros-engine](https://github.com/miguelcastill85-del/qros-engine), abre **Settings → Environments → qros-g9-test-only → Environment secrets**. Si allí existe `CLOUDFLARE_API_TOKEN`, pulsa **Update/Edit** sobre ese nombre, pega el token y guarda. No cambies `CLOUDFLARE_ACCOUNT_ID`.
5. Si el secreto no existe en ese environment, busca el mismo nombre en **Settings → Secrets and variables → Actions → Repository secrets** y actualiza el existente. Un secreto de environment del mismo nombre prevalece sobre el de repositorio; por eso debes revisar primero el environment. No dupliques ni cambies otros secretos. Si no aparece en ninguno, informa únicamente “No aparece CLOUDFLARE_API_TOKEN”.
6. Comprueba en la misma cuenta que el plan **Workers** muestra **Free**; un plan gratuito de zona/dominio no prueba el plan Workers. No actives upgrades.
7. Cuando sea cierto, responde únicamente: **“Token actualizado; Workers Free activo”**. Si Workers no muestra Free, informa ese estado y mantén el despliegue bloqueado.

No introduzcas el token API de Cloudflare en la app Android. El bootstrap Android corto y de un solo uso será distinto y sólo se emitirá después del gate HTTPS.

## Primera operación automática después de la intervención

Una sola ejecución del preflight existente de sólo lectura con la credencial reemplazada; descargar y verificar el recibo. Si sigue HTTP401, detener esa ruta sin nuevos intentos idénticos. No ampliar permisos para leer el plan.

Con acceso Workers válido y confirmación actual Free, registrar `REPORTADO` en `cost_gate.json` con vigencia de una hora, ejecutar el workflow de despliegue preparado, comparar origen del proveedor con el origen fijado en Android antes de escribir, verificar respuesta HTTPS auténtica externa mediante Node y Python, revocar canarios y guardar recibo/URL real. Después, seguir el procedimiento físico `G12_ANDROID_PHYSICAL_TEST.md` con la APK exacta ya verificada.

## Garantías y límites

El recibo bruto conserva literalmente `provider_access: NOT_CHECKED`: el script no alcanzó una comprobación agregada completa, pero sí registró la primera lectura rechazada. El checkpoint interpreta ese HTTP401 sin alterar el recibo original.

La APK sigue firmada para pruebas. Producción, aceptación física G12 y custodia externa de backend siguen pendientes. No promover MOBILE_PRODUCT_HEAD ni declarar la app comercialmente terminada a partir de la evidencia conservada.

Documentación primaria consultada el 7 de octubre de 2026:
- [Cloudflare account-owned API tokens](https://developers.cloudflare.com/fundamentals/api/get-started/account-owned-tokens/)
- [Cloudflare creación de API tokens](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)
- [Cloudflare permisos](https://developers.cloudflare.com/fundamentals/api/reference/permissions/)
- [GitHub secretos de environment](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
- [GitHub precedencia de secretos](https://docs.github.com/en/actions/reference/security/secrets)
