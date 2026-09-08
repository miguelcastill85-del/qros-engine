# Propuesta parcial v2.2.4 — NO DESPLEGABLE

`INFERRED`: este directorio contiene una propuesta de contención derivada únicamente del executor congelado cuyo SHA-256 es `106d6890542e71dd3a1c6b90838e87664fa1a66fe576e713ceb7b52acce20d43`. No constituye una versión aceptada, compilada ni apta para reemplazar el MT5 operativo.

`TEST_PROVEN` en traducción de fuente con API sintética: 11 expectativas que fallan en la fuente congelada pasan con esta propuesta; las 38 expectativas que ya pasaban siguen pasando. Total: 49 PASS y 38 FAIL de 87. Consulte `../../evidence/proposal-final/stdout.json` y el diff `CHANGES.diff`.

La propuesta exige el valor exacto de CERT, bloquea entradas al fallar HistorySelect, rechaza valoraciones no finitas, comprueba retcode y estado observado en modify/close, conserva el intento de cierre de posiciones del día anterior cuando existe g_fault y comprueba el registro del timer. La última medida de gestión usa inventario de posiciones del broker; no procesa el bus que originó un fallo de integridad.

`BLOCKED`: no se ha compilado MQL5 ni ejecutado Trade.mqh build 6182. La comprobación inmediata de posición/SL/TP puede quedar sin confirmar por retrasos de visibilidad; aún falta la reconciliación durable. Un resultado sin confirmar jamás debe promoverse a ejecución exitosa.

`STATIC_PROVEN`: este candidato conserva defectos críticos sin reparar: reservas de solicitudes pendientes, recuperación de módulos, diario de transacciones, huérfanas sin SL en el mismo día, reintentos de intención close/modify, carreras del bus, deadline antes del cierre de sesión y certificación continua. No intenta inventar la política científica que falta en los emisores exactos.

`INFERRED`: las modificaciones a gestión, certificación y contabilidad son `execution-semantic`; la comprobación del timer y evidencia de retcodes es `infrastructure-only`. Ningún ajuste de señales, riesgo 0.50/1.00, prioridad, universo o cupo diario está propuesto. La compatibilidad con módulos aún requiere paridad.

Antes de cualquier sustitución deben cumplirse todos los requisitos de `REPLACEMENT_CONTRACT.md`, importarse las fuentes exactas ausentes y repetirse el gate completo: compilación 0 errores/0 warnings, paridad padre-hijo, paridad del controlador, certificados de cada módulo forward, canary combinado, START_RECEIPT y runtime armado con CERT=1. Nada en este directorio autoriza despliegue.
