# Llevar QROS a Codex y devolver el runtime a los chats

**Entrega preparada el 28 de agosto de 2026. Alcance: transferencia de ingeniería.**
No contiene una nueva versión corregida del motor ni una aprobación científica.

## Respuesta corta

Sí: la ruta recomendada es un repositorio privado del software para Codex y una
release portable del runtime para los chats de investigación. Codex desarrolla;
el runtime calcula; el chat organiza y analiza. Son funciones separadas, aunque
Work/Codex también permita hacer desarrollo en este mismo tipo de entorno.

No es necesario «migrar toda la conversación». Hay que transferir código, contratos,
pruebas, auditoría y estado verificable. Codex no debe depender de recordar este chat.

## Qué contiene esta entrega

- Carpeta `qros-engine/` preparada para importar a un repositorio: los 167 archivos
  de la release v0.6 se conservan sin cambios de contenido.
- `AGENTS.md`: instrucciones del proyecto que Codex puede leer al iniciar el trabajo.
- `handoff/CODEX_TASK.md`: encargo completo para pegar en Codex.
- Objetivo, backlog de fallos, contrato del ZIP final y alcance de la base.
- Auditoría con sus ocho hallazgos, logs y reproducción sintética.
- ZIP original v0.6 inmutable en `handoff/baseline/` para reproducir el antes.
- Verificador de importación y manifest de esta entrega.

Los recibos antiguos siguen siendo históricos. El estado `production_research_ready=0`
se mantiene. No se ha corregido el código, no se ha creado un repositorio remoto y no
se ha enviado una tarea a Codex como parte de esta entrega.

## 1. Crear o elegir el repositorio del motor

Usar un repositorio **privado y exclusivo de QROS**, por ejemplo `qros-engine`.
Es un nombre propuesto, no un repo ya creado. No usar Herramientas Rentables.

Descargar y descomprimir el ZIP de transferencia. Importar **el contenido de la carpeta
qros-engine**, no solamente el ZIP como un único archivo. AGENTS.md, src/, tests/ y
CMakeLists.txt deben quedar en la raíz del repo. Conservar baseline y evidencia.
Si ya existe un repo QROS, comparar su commit y autoridad antes de importar: no pisarlo.

Para preparar una carpeta local con Git, sin publicar todavía:

```bash
python3 handoff/verify_import.py
git init -b main
git add .
git commit -m "Import verified QROS v0.6 and engineering handoff"
```

Estos comandos se ejecutan desde qros-engine. Requieren Git y su identidad de autor
configurados. El remoto privado se crea o selecciona en tu cuenta y se vincula con
autenticación autorizada; no pegar tokens en chats ni en archivos. Esta entrega no
ejecutó esos comandos ni creó un remoto. Subir fuentes no sustituye configurar acceso
al repo en Codex. Desde móvil, Codex web evita instalar un entorno C++ en el teléfono;
la importación de la carpeta puede requerir un ordenador o una acción autorizada desde
un entorno con Git.

No subir carriers completos ni holdout. La base sólo contiene fixtures pequeñas y
referencias de autoridad. El .gitignore ayuda a evitar errores, pero no es una frontera
de seguridad: revisar el diff antes de publicar.

## 2. Conectar Codex y configurar el entorno

Abrir [Codex](https://chatgpt.com/codex), iniciar sesión con la misma cuenta y conectar
GitHub. Dar acceso sólo al repositorio QROS elegido. Crear el entorno de ese repo y
seleccionar su rama/commit. La documentación oficial describe ese flujo de repositorio,
entorno, tarea y revisión. [Guía oficial de Codex cloud](https://learn.chatgpt.com/docs/cloud).

El entorno de construcción necesita compilador C++20, herramientas de sistema y Python
3.10+ para build/tests/oracle. El ejecutable publicado no debe necesitar ese Python.
La baseline se construyó con g++ 13.3; fijar toolchain para comparar builds reproducibles.
El setup no debe cargar datos reales, secretos MT5 ni iniciar minería. Mantener la red
del agente restringida salvo necesidad justificada. Codex permite configurar entorno
y ejecutar comandos/pruebas en un contenedor. [Entornos cloud](https://learn.chatgpt.com/docs/environments/cloud-environment).

AGENTS.md fija objetivo, comandos e invariantes al arrancar; sus instrucciones no
sustituyen pruebas ni controles de permisos. [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

Usar el acceso incluido en tu plan. No configurar clave API, créditos adicionales,
Actions con gasto ni recursos facturables. El plan Plus incluye acceso a Codex, pero
con límites de uso: no garantiza ejecución ilimitada ni terminar el software en una
sola tarea. [Disponibilidad y límites](https://learn.chatgpt.com/docs/pricing).

## 3. Dar a Codex un encargo ejecutable

Pegar el contenido de `handoff/CODEX_TASK.md` en la tarea del repositorio seleccionado.
Se puede empezar con este texto breve:

> Lee AGENTS.md y handoff/CODEX_TASK.md. Continúa QROS ENGINE desde la base verificada.
> Primero reproduce y corrige los P0 y la integración gates/Supergate, con regresiones.
> Conserva el núcleo nativo y el oracle Python independiente. Después cumple los hitos
> y el contrato de distribución para chats. No alteres reglas científicas, no abras
> holdout ni actives costes. Entrega código revisable, evidencias y un ZIP ejecutable,
> sin declarar terminado lo que siga bloqueado o sin comprobar.

No pedir sólo «termina todo»: la matriz de aceptación y el backlog evitan que un
resumen favorable se confunda con una implementación terminada. Cada hito conserva un
checkpoint. Revisar el diff y las pruebas antes de incorporar cambios al repo.

## 4. Archivo que debe devolver Codex

El contrato exige un `QROS_RUNTIME_CHAT_vX.Y.Z_linux_x86_64.zip`: ejecutable nativo,
contratos, ejemplos de prueba, manifest/hashes, licencias, evidencia y guía. Este nombre
es una especificación futura, **no el archivo de transferencia que se entrega hoy**.

No basta un .py, un .exe de Windows, un EX5 de MetaTrader o un informe. El código fuente
y los scripts de construcción también deben quedar guardados. En cloud, revisar el
diff/PR no equivale automáticamente a obtener un binario descargable; Codex debe
construir el ZIP y hacerlo recuperable mediante una ruta autorizada, o dejar un
empaquetador reproducible probado. No se activa publicación pública ni gasto de CI.

## 5. Usar la release de vuelta en los chats

1. Adjuntar o seleccionar la release exacta y su hash.
2. Verificar y extraer el paquete en el entorno de ejecución, con límites de archivo.
3. Comprobar SO/CPU/permisos/recursos y ejecutar sus self-tests y golden.
4. Aportar los datos de desarrollo y el checkpoint autorizado, por identidad exacta.
5. Generar trabajos declarativos; el chat invoca el motor nativo y lee sus resultados.
6. Guardar resultados/receipts y checkpoint al terminar cada bloque para reanudar.

Mensaje de arranque sugerido para **cuando la release esté construida y aceptada**:

> Usa esta release de QROS. Verifica su manifest, identidad y compatibilidad con este
> entorno. Ejecuta las pruebas de aceptación incluidas. Después recupera el checkpoint
> autorizado y continúa sólo la RUN_QUEUE compatible; conserva los gates y no abras
> holdout. Si falta capacidad o evidencia, indica el bloqueo y no simules resultados.

El runtime y el estado de investigación se entregan por separado. En una nueva sesión
se vuelven a comprobar capacidad e identidades. No se presupone que un ZIP adjunto
quede instalado para siempre ni que todos los chats compartan filesystem.

## Límite que no puede resolver un ZIP

Un chat necesita herramientas que permitan lanzar el ejecutable. Aquí se volvió a
probar la baseline en Linux x86-64 con PATH vacío; capabilities y las dos pruebas
nativas terminan. Eso demuestra una capacidad acotada del entorno actual, no la de
cualquier chat de Android o de cualquier modo de ChatGPT.

La app del teléfono es la interfaz; no tiene que ejecutar el ELF en Android. Un chat
sin terminal/ejecución no puede correrlo sólo por recibirlo. Se necesitaría usar un modo
Work/Codex con esa capacidad u otro host autorizado disponible. La documentación del
terminal integrado describe ejecución en la app de escritorio; no la generaliza a
todos los chats. [Terminal integrado](https://learn.chatgpt.com/docs/integrated-terminal).

Tampoco el binario aporta RAM, CPU, tiempo ilimitado, almacenamiento persistente o MT5.
Campañas grandes necesitan límites, fragmentos y checkpoints; no prometer que cientos
de millones de candidatos cabrán en una única sesión. La validación MT5 auténtica exige
un host con MetaEditor/tester; si falta, se mantiene ese bloqueo.

## Lo que queda pendiente tras esta transferencia

Elegir/importar el repositorio y conectarlo a Codex; ejecutar las correcciones y los
hitos; construir la release; verificarla en el chat receptor; habilitar investigación
real sólo con sus contratos y evidencia. No se ha lanzado una campaña ni alterado el
HEAD científico. La programación diaria solicitada anteriormente tampoco se ha creado:
estaba bloqueada por el límite de tareas y es independiente de esta transferencia.
