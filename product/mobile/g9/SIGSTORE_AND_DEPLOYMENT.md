# G9 — frontera de despliegue y testigo externo

## Estado y garantías

Solo TEST_ONLY, datos sintéticos. No aprobación científica. `main` no se modifica.
El Worker emite el esquema G5 y Ed25519/canonical JSON verificable por G6 con una
raíz nueva. La APK G6 congelada lleva una raíz de fixture con semilla pública:
NO puede autenticar de forma segura este servicio. No reutilizar esa clave.
No se ha construido todavía una APK con la raíz real de G9.

Autenticación del canary: bearer aleatorio de un solo uso, hash SHA256 en secreto
TOKEN_GRANTS_JSON, TTL máximo 300 segundos, ámbito tenant/proyecto/campaña y
solo demo:read. NO es OIDC. Consumir token antes de enviar respuesta significa
que una desconexión exige otro token; no reintentar el mismo ni relajar replay.
Durable Object SQLite único: consumo transaccional, 10 éxitos/minuto globales,
máximo 100 grants. Los rechazos previos a autenticación consumen cuota del plan
Cloudflare pero no generan filas; no se afirma protección ilimitada contra DoS.
Sin CORS, sin logs de headers ni secretos, sin endpoints administrativos.

La respuesta es un snapshot fijo secuencia 1, no un ledger dinámico ni una prueba
de frescura. `external_independent_custody=NOT_DEPLOYED` sigue siendo obligatorio.
Dos claves del mismo operador no son custodia independiente.

## Cloudflare: preparar, no declarar desplegado

La cuenta y Workers Free deben comprobarse en el panel antes de cualquier deploy.
El 2026-09-26 el navegador cloud quedó en verificación antibot tras una recarga.
No se han obtenido Account ID, API token ni URL workers.dev. No se ha activado plan.

Wrangler 4.141.0 y dependencias en lockfile. El canary queda ENABLED=false.
Para habilitarlo, después de acceso autorizado y comprobación del plan gratuito:
1. Crear token Cloudflare de duración limitada, Account/Workers Scripts Edit solo
   para la cuenta objetivo. No añadir permisos de DNS, zonas ni facturación.
2. Guardar CLOUDFLARE_ACCOUNT_ID y CLOUDFLARE_API_TOKEN en Secrets de Actions
   por mecanismo seguro. El conector actual no expone la API de Secrets.
3. Generar clave Ed25519 aleatoria exclusivamente en backend autorizado y guardar
   PKCS8 base64 como Worker Secret SIGNING_PKCS8_B64. No copiarla a repo/logs/APK.
4. Fijar SIGNING_PUBLIC_B64 por canal independiente en una nueva build Android;
   verificar fingerprint fuera de la respuesta del servidor. El Worker no devuelve
   ninguna clave pública ni acepta claves remitidas por el cliente.
5. Configurar PUBLIC_ORIGIN con workers.dev observado, variables no sensibles,
   y grants de token con nbf/exp actuales mediante Worker Secrets. ENABLED=true
   solo tras desplegar con configuración revisada y prueba local verde.
6. Desde un segundo entorno, TLS normal sin bypass, GET autenticado, guardar
   respuesta y comprobar firma/hash con Python y Dart. Exigir 409 al repetir token.
7. Conservar URL, versión Cloudflare, commit, recibos, certificado observado y APK SHA.

`wrangler deploy --dry-run` solo valida empaquetado, no red ni TLS del proveedor.

## Sigstore/Rekor: investigación vigente

Fuentes oficiales consultadas el 2026-09-26:
- https://docs.sigstore.dev/quickstart/quickstart-ci/
- https://docs.sigstore.dev/cosign/signing/signing_with_blobs/
- https://docs.sigstore.dev/cosign/verifying/verify/
- https://github.com/actions/attest (privados usan instancia privada GitHub)
- https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/
- https://developers.cloudflare.com/durable-objects/platform/pricing/

Cosign permite firma keyless desde OIDC GitHub Actions y bundle verificable con
issuer `https://token.actions.githubusercontent.com` e identidad exacta del workflow/ref.
Rekor prueba inclusión de una firma/identidad en un log externo. NO certifica que el
resultado científico es verdadero, el teléfono ejecutó una APK, existe custodia
independiente del backend o que un head es el más reciente.

Un registro público incluye certificado/identidad del workflow (nombre del repositorio
privado y cuenta GitHub). No contiene contraseña, token ni clave privada, pero esa
identidad quedará pública. Antes de publicar hay que resolver expresamente esta
frontera con la restricción de no publicar información personal/privada. Se prepara
workflow desactivado, sin publicación automática. No se afirma registro Rekor.
No usar actions/attest para atribuir transparencia pública a un repo privado.

Después de autorización de esa exposición mínima: firmar SOLO hash de recibo sintético,
conservar bundle; verificar con Cosign y segundo cliente sigstore-python, raíces TUF,
issuer e identidad fijados. No usar opciones que omitan log/SCT/firma. Si una verificación
falla, no promocionar testigo ni borrar evidencia.
