# Contrato propuesto de entrega del runtime para chats

Estado: REQUISITO DE INGENIERÍA A IMPLEMENTAR Y VALIDAR. No describe una release final
ya construida. No cambia por sí mismo la metodología científica de QROS.

## Entregables que Codex deberá producir

1. Commit/patch revisable, fuentes y pruebas completas; identidad de todos los inputs.
2. `QROS_RUNTIME_CHAT_vX.Y.Z_linux_x86_64.zip` (X.Y.Z es un marcador, no una versión existente).
3. SHA-256 del ZIP, manifest del payload y evidencia de extracción/ejecución limpia.
4. Changelog, matriz de capacidades, fallos resueltos y pendientes; instrucciones de
   importación al chat. Si falta un criterio, denominar release de desarrollo, no FINAL.

El ZIP deberá contener:

| Ruta propuesta | Contenido |
|---|---|
| START_HERE.md | Importación, comandos reales, requisitos y límites |
| bin/qros | ELF Linux x86-64 y requisitos mínimos de CPU/kernel explicitados |
| contracts/ | Versiones de datos, IR, ejecución, unidades y jobs |
| examples/test_only/ | Datos, estrategia y resultados golden sintéticos pequeños |
| manifests/ | Inventario con tamaños y SHA-256; origen/commit/toolchain |
| receipts/ | Pruebas ligadas al binario distribuido, no a otro build |
| licenses/ | Licencias de lo redistribuido, incluida biblioteca estática; SBOM |
| optional_tools/ | Adaptadores opcionales, separados del camino nativo |

No incluir ticks completos, holdout, secretos ni resultados científicos ajenos a esta
release. Los datos y el estado de campaña se entregan por separado.

## Independencia y compatibilidad

- El ciclo normal de ejecución no pide instalar Python, NumPy, Numba ni un compilador.
  Puede haber Python en build/oracle sin contradecir esta propiedad.
- Sin descargas, pip, apt, elevación de permisos ni servicios de pago en el arranque.
- Preferir un binario estático portable dentro del target Linux x86-64 probado.
  «Estático» no significa portable a Android/Windows/ARM ni inmune a límites del host.
- No imponer AVX/AVX2/AVX512 por defecto sin declarar requisitos y comprobar CPU.
- No asumir acceso a `/proc`, permisos de ejecución, memoria ilimitada o persistencia.
  Una guarda debe detectar incompatibilidad antes de leer datos científicos.
- Otras arquitecturas sólo se soportan tras construirlas y probarlas. Un EX5 o EXE
  Windows no sustituye al ELF requerido para este entorno Linux.

## Interfaz requerida; nombres nuevos aún propuestos

`capabilities` ya existe. Los comandos de diagnóstico, self-test y job/checkpoint
siguientes son especificaciones de interfaz; no afirmar que v0.6 ya los reconoce.
Codex podrá conservar comandos actuales compatibles y añadir una fachada versionada.

| Operación | Garantía requerida |
|---|---|
| Preflight / doctor | SO/arquitectura, CPU, permisos, recursos, hashes y formatos; sin acceso a holdout |
| Self-test | Casos golden con digest esperado independiente, discrepancias no silenciosas |
| Ejecutar job | Contrato declarativo cerrado; sin eval/shell; inputs exactos y presupuestos |
| Estado y reanudar | Checkpoint íntegro y compatible, sin repetición ni pérdida de identidad |
| Empaquetar resultado | Ledger/metrics/coverage/logs y cadena de commits verificable |

Un job identifica dataset/snapshot, programa/IR, sesión/reloj, política de ejecución,
costes, autorización, rango de candidatos, seed aleatoria si aplica, y presupuesto.
Rutas del host se vinculan a identidades; no se resuelven por glob/latest. Rechazar
versiones incompatibles, rutas que escapen del área de trabajo y archivos mutados.

El checkpoint incluye fuente/binario/contratos/datos, secuencia, rango, exposiciones,
estado de features/barras/órdenes/posiciones cuando se reanude dentro de un replay,
hash de outputs y siguiente acción. Una migración de schema necesita autorización y
prueba de equivalencia. Nunca recomputar resultados esperados copiando el mismo motor.

## Pruebas de aceptación de la distribución

1. Verificar payload y extraer en directorio nuevo; prohibir traversal/symlinks peligrosos.
2. Probar el ELF distribuido con entorno saneado y PATH sin Python, sin red; el harness
   de QA sí puede usar Python para lanzar el proceso, pero eso se declara.
3. Ejecutar fixtures BUY/SELL representativas y comparar con golden/oracle independiente.
4. Pausar y reanudar; obtener ledger/coverage equivalentes a ejecución sin interrupción.
5. Rechazar datos/hash/schema/permiso incorrectos; cero acceso accidental al holdout.
6. Medir RAM, CPU, tiempos y tamaño de resultados en workloads representativos acotados.
7. Repetir desde el ZIP devuelto por Codex en el chat receptor. El PASS del host de
   construcción no certifica el host de destino.
8. Sin P0 abierto ni mensajes de aprobación excesivos. Para declarar producto completo,
   además cumplir validación real MT5/ciencia/portfolio exigidas; no inferirlas de fixtures.

## Cómo se utilizará aquí

Se adjunta o materializa la release, se verifica identidad y capacidad del entorno,
se ejecutan los golden y se restauran datos/estado autorizados. Después el chat genera
jobs declarativos y llama al ejecutable; los cálculos se realizan en el runtime.

Cada sesión guarda resultados y un `QROS_RUN_STATE_<id>.zip` (nombre propuesto) con
checkpoint y referencias exactas. El binario, los ticks y el estado son tres objetos
distintos. Adjuntar el ejecutable no aporta automáticamente los ticks ni una sesión
persistente. No se promete trabajo autónomo después del cierre del chat.

Un chat sin terminal/herramienta que permita lanzar ejecutables no puede usar este
runtime nativo sólo por recibir un ZIP. Debe usarse Work/Codex u otro entorno autorizado
con ejecución, o un host externo ya disponible. No se eluden políticas de la plataforma.
Si no hay RAM, almacenamiento, tiempo o permisos, se reporta capacidad bloqueada y
se conserva el checkpoint; nunca se presenta una simulación narrativa como backtest.
