# Android físico — pendiente, no confundir con emulador

No instalar G6 para atribuir autenticidad a la nueva clave G9: su raíz es diferente.
G6 SHA256 histórico: 2c4053a27fa5692871db717c4c5bb42e1284673b49f13fa41db6a7e2b0b52c97.
No se ha modificado el cliente distribuido ni construido otra APK en este checkpoint.

Después de recuperar Cloudflare y fijar la raíz pública G9 fuera del servidor:
1. Compilar APK TEST_ONLY con raíz y origen HTTPS exactos fijados; CI calcula SHA256.
2. Entregar APK/hash y token efímero por canal seguro. Nunca token en URL, APK o chat.
3. Instalar en teléfono autorizado; abrir snapshot, usar URL fijada y token una vez.
4. Debe mostrar tenant_A/project_A/campaign_A, secuencia 1, dos filas y TEST_ONLY.
5. Repetición: denegación 409; desconexión: error sin mostrar verificación nueva.
6. Exportar recibo del teléfono: APK SHA, certificado de firma APK, versión Android,
   instante, hash del snapshot, resultado criptográfico y URL, sin tokens ni serial.
7. Verificador independiente cruza APK, bytes HTTPS y recibo; screenshot solo no basta.

No existe herramienta de control/emparejamiento Android físico expuesta en esta sesión.
La prueba requiere la intervención física del usuario. No se declara instalación real.
Faltan pruebas TLS adversariales del cliente con certificado sustituido y servidor falso
usando la futura raíz/origen G9. Las pruebas de URL del Worker NO cubren esos ataques.
