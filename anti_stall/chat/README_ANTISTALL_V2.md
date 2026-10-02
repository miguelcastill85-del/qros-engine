# QROS Chat Anti-Stall v2 — regla operativa permanente

Este control corrige el bucle observado en los chats: recuperar → fallar → volver a diagnosticar → repetir la misma ruta → agotar el turno → pedir otra intervención del usuario.

## Regla central
Una ruta dispone de **dos intentos como máximo sin progreso medible**. El segundo fallo equivalente cierra esa ruta durante el turno. Una tercera repetición está prohibida. Se debe persistir lo aprendido y cambiar a una ruta independiente válida.

## Qué es progreso
Solo cuenta un cambio verificable: nuevo SHA/commit legítimo, nuevo shard/receipt validado, checkpoint/WAL/puntero durable avanzado, o eliminación comprobada de un bloqueo. Volver a leer lo mismo, crear otro plan o repetir una búsqueda no cuenta.

## Presupuesto de estancamiento
- 2 intentos por operación/ruta sin progreso.
- 2 repeticiones de la misma huella de fallo.
- 2 llamadas idénticas como máximo sin progreso.
- 4 eventos seguidos sin progreso fuerzan cambio de ruta.
- 8 eventos sin progreso en el turno fuerzan checkpoint y fin de la exploración de esa vía.
- Una sola recuperación de autoridad por mensaje «continúa».
- Cero repetición de trabajo ya cerrado.

## Continuidad
«Continúa» significa recuperar una vez el último checkpoint durable y ejecutar la siguiente acción. Una ruta cerrada no se reabre salvo que haya cambiado materialmente la autoridad o el prerrequisito que la bloqueaba.

## Alcance
Controla el comportamiento del chat. No cambia alfa, datos, PnL, Gate A, holdout, GA2 ni MT5 y no promete ejecución en segundo plano.
