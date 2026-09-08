# v2.2.4 Candidate 3 — reparación Compile-Only del 2026-09-08

- Fuente recuperada por identidad exacta del paquete físico y checkpoint e395c07.
- Executor completo: las dos dimensiones estáticas pasan de `const int =32` a
  `#define ... 32`; ningún otro byte de su lógica cambia.
- Siete sources restantes intactos; los tres emitters conservan alfa y parámetros
  frente a los emitters congelados v2.2.3 (diff de infraestructura documentado).
- Reproducción nativa de los errores 203 en 145:21 y 146:22; reparación compilada
  con MetaEditor 6182: seis componentes 0 errores / 0 advertencias, seis EX5 nuevos.
- Gate Compile-Only aislado en el proyecto, MetaEditor portable oculto, incluye
  hashes y conserva logs de fallo/éxito. Sin terminal, tester ni órdenes.
- Regresión de reparación 77/77; F01–F18 preservados a nivel de source.
- Bloqueada la reejecución de 62/62, 80/80 y 25/25: faltan los scripts originales
  en ambos ZIP verificados. Sus resultados anteriores siguen siendo históricos.
- Estado DEVELOPMENT_BLOCKED / COMPILE_ONLY_PASS_OFFLINE_REVALIDATION_BLOCKED.
  Sin FROZEN_CANDIDATE, APPROVED_FINAL, deployment ni cambios de QDB1.EXEC.CERT.
- Riesgo 0.50%, reserva 1.00%, tres entradas/día, XAU > NQX > DIV3, Q24.*, arm token,
  BUY/SELL, G30 y holdouts conservados. Gates nativos posteriores pendientes.

Detalle, evidencia, límites y hashes: [REPAIR_REPORT.md](REPAIR_REPORT.md).
