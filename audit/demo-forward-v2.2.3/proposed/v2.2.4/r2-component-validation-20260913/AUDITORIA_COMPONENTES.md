# Continuación desde la recuperación del PC

Autoridad de partida: commit `680d5752ba08eb18232de77d786c2642ecff98c3`,
exclusivamente rama `fix/demo-forward-v2.2.4-hardening-20260907`.
El checkpoint de `r2-recovery-audit-20260913` es la autoridad de esta reparación;
`control/HEAD.json` describe otra campaña y no se usa para elegir tareas R2.

## Hallazgos verificados

El ZIP recuperado conserva SHA-256
`c7cc89e75276fedaf565cdae16a13538cab52046774e02b9904e654162b8502c`.
La rematerialización exige una nueva comprobación: 2.739/2.739 entradas inventariadas
coinciden en bytes y SHA. El ZIP usa separadores Windows; se normalizan sólo para
resolver nombres, rechazando colisiones y traversal. No se interpretaron datos económicos.

Las fuentes del runner y R2 conservan exactamente los tres SHA declarados por el
usuario. Candidate3 no fue modificado. La carrera del lector ya está documentada
y su componente se reutiliza sin cambios. No se declara otra vez como trabajo nuevo.

El contrato offline histórico acepta identidades vacías coherentemente repetidas
en plan y evidencia. Se reprodujeron, entre otros, identidad física `null`, PID
negativo y token de propietario `null`. No era un falso certificado R2: incluso
esos resultados mantenían `r2_native_qualified=false`. Era una falsa aceptación de
consistencia que podía confundir una futura integración del validador.

El componente endurecido valida también el plan, formas/tipos, identidades no
vacías, PID positivo, tokens distintos por rol, generación del probe, derivación
del nombre físico desde Common/Files y códigos Win32 compatibles con el resultado.
Se conservó byte a byte el validador previo. Las 27 mutaciones heredadas pasan y
las 17 adicionales se rechazan; 16 de estas 17 eran aceptadas por el anterior.
Esto es mutation testing de entradas del contrato, no de MT5 ni del qualifier.

## Diagnóstico Windows entregado

Un BAT lanza pruebas acotadas sin MT5. Nueve casos ejercitan el lector, incluyendo
un escritor real en otro proceso. Un décimo caso compuesto observa dos procesos
PowerShell sobre un archivo temporal: identidad NTFS antes/durante/después, PID y
fecha de creación, token escrito bajo lock, error de compartición 32, liberación,
salida del helper y readquisición con lectura del token. El helper tiene deadline
y no hay comandos para terminar procesos. La señal ready se publica con rename
después de cerrar el archivo de evidencia; no se repite la lectura prematura de
un archivo recién creado pero incompleto.

El resultado y las salidas de los helpers se comprimen en un solo ZIP. La rutina
reabre el ZIP y compara número de entradas, tamaños y SHA de cada archivo. El test
no crea una nueva versión del qualifier y no integra el lector en el runner aún.

## Semántica y límites

MetaQuotes documenta FILE_COMMON como carpeta compartida y el sandbox normal del
Tester como directorio del agente. La documentación no demuestra qué objeto físico
usaron los procesos del incidente. [FileOpen](https://www.mql5.com/en/docs/files/fileopen).

Windows mantiene las restricciones de compartición mientras el handle está abierto.
Una denegación genérica no basta: hay que separar error 32 de ACL, ruta inexistente
y otros errores. [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew).

La consulta de identidad usa volumen e índice de archivo con handle abierto y se
limita a NTFS. No generaliza unicidad a otros sistemas de archivos.
[GetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfileinformationbyhandle).

El diagnóstico PowerShell **no observa handles MQL5**, no prueba continuidad de un
handle del Tester y no resuelve por sí solo hipótesis A–G. No hay base para sustituir
FILE_COMMON en producción todavía. La evidencia histórica no permite concluir que
Windows concediera dos aperturas incompatibles de un mismo archivo.

## Bloqueo y ruta pendiente

Este host es Linux, sin powershell, pwsh ni wine en PATH, y no dispone de acceso al
Windows objetivo. No se lanzaron compilación MetaEditor, pruebas Windows ni MT5.
La clonación Git por HTTPS no dispone de credencial local; se recuperaron fuentes
por el conector autorizado y se verificaron sus blobs. El verificador global de
importación se intentó y falló por HANDOFF_MANIFEST.sha256 ausente en este checkout
parcial; no se usa ese fallo para invalidar el runner ni se afirma baseline global.

Persisten todos los defectos nativos abiertos R2REC-02–12 del ledger de recuperación.
No se declara fixed point del qualifier ni release consolidada. Una vez recibido el
ZIP de componentes, verificarlo y corregir cualquier fallo del componente antes de
integrarlo; luego reparar conjuntamente las guardas de clones, ownership de procesos,
compilación acotada, productores MQL y finalización de evidencia. La prueba MQL exige
captura nativa independiente del recurso/handle; un booleano uninterrupted no la aporta.
R2 completo, R3 y R4 siguen pendientes. Candidate3 continúa FROZEN_CANDIDATE.
