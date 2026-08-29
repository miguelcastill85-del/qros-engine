# Encargo para pegar en Codex

Continúa la construcción de QROS ENGINE desde este repositorio. El objetivo es un
runtime cuantitativo propio, nativo C++20, determinista y portable, que podamos usar
después desde chats con herramientas de ejecución. No reinicies el proyecto, no hagas
un fork de Python y no sustituyas el trabajo por una skill o un diseño conceptual.

Lee AGENTS.md y todos los documentos handoff que indica. Antes de editar, verifica la
importación y la base exacta. Recupera el estado de ingeniería; no lo confundas con un
HEAD científico. v0.6 desciende de v0.4; v0.5 no está recuperada.

Primero cierra el hito de correcciones P0 de la auditoría A01/A02/A03/A06/A07 y la
integración gates/Supergate A08. Reproduce cada caso sobre la baseline, incorpora
regresiones con la expectativa corregida a las suites existentes, corrige y prueba
el build nuevo. No declares resuelto aislamiento físico o procedencia MT5 si el host
no permite demostrarlo. Registra ese bloqueo y continúa con el trabajo independiente.

Después completa el IR autocontenido, estados y SL/TP dinámicos necesarios para la
semilla, QDATA/sesiones, ejecución reanudable y distribución de runtime. Continúa por
los hitos de ENGINEERING_BACKLOG.md con checkpoints, dentro de la autorización y
recursos disponibles. Si falta una decisión metodológica, no la adivines ni cambies
resultados para obtener PASS; identifica la pregunta exacta.

Preserva las reglas de trading, datos Darwinex, Bid/Ask, causalidad, holdout, multiplicidad
y gates. Usa fixtures TEST_ONLY durante desarrollo. No abras el holdout, no inicies una
campaña real ni trading live, no actives APIs/servicios/créditos de pago y no subas datos
privados al repo. El oracle Python queda independiente; el runtime final no debe
necesitar una instalación externa de Python para ejecutar backtests.

La entrega debe incluir fuentes/commit, pruebas y recibos del binario exacto, y el ZIP
QROS_RUNTIME_CHAT definido en CHAT_RUNTIME_RELEASE_CONTRACT.md. Demuestra extracción
limpia, ejecución nativa sin Python en PATH, golden parity, límites y reanudación. No
basta entregar EX5, un README o código sin compilar. Si no puedes publicar el archivo
directamente, entrega un empaquetador reproducible probado y especifica cómo recuperar
el ZIP; no afirmes que ya existe un enlace de descarga.

No declares terminado el producto mientras queden criterios obligatorios sin verificar.
Al cerrar cada hito informa: cambios, pruebas realmente ejecutadas, fallos abiertos,
identidades, recursos medidos y siguiente acción exacta. Trabaja mediante cambios
revisables y no reescribas los recibos históricos.
