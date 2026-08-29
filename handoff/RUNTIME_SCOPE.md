# Objetivo, separación de funciones y límites

## Producto que queremos

Un runtime cuantitativo propio para QROS/RISE: recibe datos y una estrategia declarativa,
valida sus contratos, ejecuta sus reglas causalmente, registra resultados y permite
reanudar por checkpoints. El resultado económico no depende de cómo un chat describa
la estrategia ni de una instalación externa de Python.

El núcleo sigue siendo C++20. No se encarga un lenguaje general superior a Python.
Se busca corrección, autonomía de distribución y eficiencia medidas en cargas QROS.
El oracle Python permanece independiente. Empaquetar CPython para herramientas sería
una opción posterior; no sería eliminar Python ni demostrar más rendimiento.

## Qué pertenece a cada lugar

| Componente | Responsabilidad | No debe hacer |
|---|---|---|
| Repositorio y Codex | Corregir, construir, probar, revisar y versionar software | Reescribir reglas científicas para producir mejores resultados |
| Paquete de runtime | Ejecutar contratos y emitir resultados verificables | Depender de una conversación o descargar código sin autorización |
| Chat QROS | Formalizar hipótesis, preparar trabajos, invocar motor y analizar evidencia | Sustituir la ejecución por una narración o un CSV inventado |
| Datos y estado de investigación | Carriers, permisos, exposición, candidatos y checkpoints | Entrar indiscriminadamente al repo de ingeniería |
| Host MT5 | Ejecutar MetaEditor/tester y devolver evidencia auténtica | Reemplazarse con dos ledgers copiados |

Git será la fuente de verdad del software una vez importado. Las campañas fijarán un
commit/build y un hash de release; no se actualizarán silenciosamente al cambiar main.
Los datos y el HEAD científico son autoridades separadas del HEAD de software.

## Semilla humana: contexto a preservar, no sustituto del contrato completo

BUY M15: EMA9 > EMA50 en la última vela cerrada anterior a vela 2. Vela 1 roja es
referencia, salvo vela 0 roja que la contenga (High1 <= High0 y Low1 >= Low0), en cuyo
caso se usa vela 0. Vela 2 barre el mínimo y recupera; entrada al primer toque de
recuperación. TP en el máximo de referencia; SL inicial a igual distancia (RR 1:1).
Si vela 2 cierra dentro de la referencia, SL a Low(2) menos 2 puntos. Al alcanzar el
60% del objetivo, BE a entrada más 2 puntos. Cierre en el mismo día.

SELL espejo y las variantes son ramas separadas. Los puntos, redondeos, disponibilidad
de precios y la diferencia entre orden prearmada y señal detectada en el mismo tick
requieren contrato explícito; no deben adivinarse viendo ganancias. Las demos de EMA
no implementan por sí solas esta semilla. La especificación científica exhaustiva
no ha sido recuperada en esta entrega; no se inventan umbrales de aprobación.

## Datos y exposición

Se preserva la confirmación del usuario: NQX y XAU son Darwinex y usan su reloj.
Sólo se entregan referencias de autoridad y datos de prueba. No se copian carriers
reales al repo ni se hace minería nueva. Los carriers activos son ZIP (28 NQX, 35 XAU),
no los antiguos RAR. Su presencia en recibos no prueba disponibilidad en un nuevo chat.
Para la fase real se necesita un corpus de desarrollo explícitamente autorizado y
separado físicamente del holdout; un hash o etiqueta no proporciona aislamiento.

## Definiciones de terminación

1. **Hito de ingeniería completo:** requisitos acotados implementados, regresiones
   verificadas y pendientes explícitos; no aprobación de estrategias.
2. **Runtime aceptado para el entorno de chats probado:** paquete extraído desde cero,
   preflight, fixtures, paridad y reanudación comprobados bajo ese entorno.
3. **Producto completo para investigación real:** además, contratos científicos,
   datos/sesiones, evidencia MT5 exigida, holdout y portfolio validados según alcance.

Si MT5 o aislamiento no están disponibles, esa parte queda bloqueada. Se puede seguir
con los arreglos independientes, pero no entregar un estado de producto terminado.
