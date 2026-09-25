# QROS Anti-Stall — modo ChatGPT Android, por turno

Este es el modo **sin PC**. El usuario usa la aplicación ChatGPT Android dentro del proyecto «Trading algoritmico». El agente usa sus herramientas disponibles **durante cada respuesta**; GitHub y la Biblioteca conservan los checkpoints entre chats.

**La aplicación Android no ejecuta scripts de este repositorio ni los activa automáticamente por recibir un commit.** El contrato se hace efectivo cuando las instrucciones del proyecto mandan leer el puntero vivo al retomar un trabajo y el chat que responde dispone de las herramientas necesarias. Fuera de un turno activo no hay continuidad ininterrumpida garantizada.

1. Recuperar `main/control/QROS_ANTI_STALL_ACTIVE_GOVERNANCE_POINTER.json` y comprobar su pin al protocolo `governance/QROS_ANDROID_CHAT_TURN_ANTISTALL_V1.json`.
2. Recuperar desde la rama científica el puntero `control/QROS_SEED0076_DIRECT_CURRENT_CHAT_HANDOFF.json` y sus `target` y `last_closed_remote_anchor_path`, verificar el Git blob SHA-1 **independientemente**.
3. Confrontar los shards cerrados con recibos y SHA-256 de Biblioteca/Drive. En W5 v33 nunca reiniciar los 261 shards cerrados ni los resultados económicos V28.
4. Ejecutar en el turno los fragmentos pendientes originales y solo rutas causalmente equivalentes precongeladas. Si datos o conectores no están disponibles, seguir por auditorías independientes legítimas; no marcar PASS un bloqueo.
5. Después de **cada** fragmento legítimamente completado: verificar hashes y evidencia, guardar recibo inmutable, escribir handoff y CAS del puntero GitHub y comprobar lectura de retorno. Si hay concurrencia: detener escritura, recuperar y reconciliar el nuevo HEAD.
6. Al finalizar la respuesta, conservar la siguiente acción precisa para que «continúa» en cualquier otro chat de este proyecto no repita trabajo terminado.

`qros_android_turn_preflight_v1.py` verifica los bytes de las fuentes recuperadas por el conector; el caller debe pasar hashes obtenidos **del GitHub vivo**, nunca autoasignados. Es una comprobación de entrada: no envía llamadas a GitHub, no ejecuta los 504 fragmentos, no certifica MT5, no persiste el puntero y no instala nada en Android. Esas acciones las realiza el agente activo con las herramientas del chat y sus pruebas correspondientes.

## Instrucción mínima del proyecto

«QROS Android chat mode: en cada nuevo turno de continuación recupera y valida el puntero Anti-Stall de `main`, el protocolo Android y el puntero científico vivo de la rama correspondiente. Ejecuta el delta autorizado ahora con tus herramientas, no repitas shards PASS; verifica y persiste recibos y CAS del puntero antes de finalizar. No prometas trabajo después del mensaje, no dependas de Windows ni abras holdout, Gate A o GA2 sin sus gates.»
