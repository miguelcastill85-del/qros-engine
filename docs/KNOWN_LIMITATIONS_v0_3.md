# Limitaciones conocidas v0.3

- Sólo se entrega binario estático Linux x86-64; no es un EA ni un ejecutable Windows.
- El formato de ticks de prueba es CSV; el formato binario/mmap definitivo todavía no está congelado.
- El auditor de spread usa histograma exacto con límite de 1.000.000 de spreads únicos.
- El mapa de sesiones se materializa en memoria; el tick replay ya es streaming.
- No existe todavía un verificador independiente que demuestre que un receipt `VERIFIED` de broker/vendor corresponde a los bytes fuente externos. Por eso `RESEARCH_READY` está bloqueado por código.
- No hay selección de parámetros, holdout, Walk-Forward, CPCV, Monte Carlo ni portfolio en v0.3.
- El benchmark de 1M ticks mide infraestructura sintética, no rendimiento sobre XAUUSD/NQX reales ni velocidad de minería combinatoria.
