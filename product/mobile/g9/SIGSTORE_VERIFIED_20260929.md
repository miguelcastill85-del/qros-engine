**VERIFICADO — G9: publicación y comprobación externa completadas.**

El recibo Android sintético congelado conserva SHA-256 `282ef82d1935afc4e9d07082f2c669d6e587025c1fd4afc71e7c33fa4c66df9f`. Solo se firmó su hash textual con identidad GitHub Actions; no se publicaron en Rekor código, tokens ni claves privadas.

CI 36564211889: SUCCESS. Cosign 3.1.3 y sigstore-python 4.5.0 verificaron identidad exacta, issuer y transparencia. Se rechazaron un archivo alterado y una identidad incorrecta. Una consulta externa al API público de Rekor coincide byte por byte con el cuerpo del bundle. El certificado verificado contiene el SHA del commit de firma `1944d46b817494bd9810b35f817fc2377ba185e8`.

Entrada Rekor: índice `2999110427`; identificador `108e9186e8c5677a520c0695718569daac94f2bc5a93490b98f91741e9ab1d07bed7b2bbb0d51e50`.
Consulta: https://rekor.sigstore.dev/api/v1/log/entries?logIndex=2999110427
CI: https://github.com/miguelcastill85-del/qros-engine/actions/runs/36564211889

El intento 36514779414 falló antes de firmar: el instalador antiguo buscaba una firma .sig ya ausente. Se corrigió usando el instalador oficial v4.1.2 fijado por SHA, conservando sus verificaciones criptográficas. No se omitieron gates de seguridad.

**Autoridad y alcance.** Solo rama de producto G9, PR 74 contra G8. APK y pruebas Android anteriores intactas; MOBILE_PRODUCT_HEAD v11 preservado. Sin cambios a main científico, PnL, holdout, GA2, MT5 ni trading. Impacto de portafolio: ninguno. Repositorio público verificado. No se contrataron planes ni se usaron runners premium; el saldo/facturación histórica de la cuenta no se auditó.

**NO DISPONIBLE / pendiente.** Instalación y pairing HTTPS en teléfono físico; custodia independiente del backend; firma de release. Sigstore acredita firma, identidad y registro externo, no veracidad científica, ejecución física ni supervisión independiente del operador.

**Siguiente acción exacta.** Instalar y abrir la APK ya verificada en el Android autorizado; SHA-256 `60107772a5b60f63a2b7e5d5ec24452ca9a52b05c886fcf15c8e859135074b01`. Preparar entrega segura de un token QROS efímero antes de probar recepción autenticada. No usar el token Cloudflare. No repetir firma, compilación ni pruebas aprobadas.
