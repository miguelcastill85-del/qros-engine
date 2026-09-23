# DEVELOPMENT ampliado: seis casos, dos rutas

Las respuestas observadas de las rutas solicitadas `gpt-5.6-sol` y `gpt-6-astra`, ambas con esfuerzo medium e historial aislado, obtuvieron 6/6 y cero fallos críticos bajo el corrector congelado. Fueron idénticas. Los seis casos cubren aritmética racional, planificación con recursos, diagnóstico de código, disponibilidad temporal, estadística causal y recuperación de efectos externos inciertos.

`PREREGISTRATION.json` fija casos, packet y fuente del corrector por SHA-256 antes de observar las respuestas, según la ejecución local y el transcript. La publicación remota es posterior. `SOL_RAW_RESPONSE.json` y `ASTRA_RAW_RESPONSE.json` conservan los bytes JSON entregados; los scores se calculan por separado. No se observan revisiones internas inmutables del proveedor, tokens, latencias ni el historial completo de herramientas. La prohibición de herramientas fue una instrucción, sin aislamiento impuesto por el host.

El control prerregistrado ejecutó realmente `EXACT_SUM` L2 contra la autoridad V191 observada, con verificación y checkpoint. Acertó EXT-01. La mejora observada de exactitud frente a ambos modelos en ese caso es cero. Ese control no es una ejecución `SOL_QRCEL`, ni identifica SYSTEM_GAIN.

Estos casos son DEVELOPMENT expuestos para la genealogía QRCEL. Una tanda por ruta no constituye seis observaciones estadísticas independientes. Dos tandas con puntuación perfecta tampoco establecen no-inferioridad, equivalencia ni un ganador arquitectónico. Resultado: `INSUFFICIENT_EVIDENCE`.

Reproducir el scoring sin reescribir entradas congeladas:

```bash
python3 -B -m unittest cognitive.research.model_development.test_extended_development -v
```

Los siguientes ensayos deben evaluar ejecución completa, continuidad y uso observable de herramientas con tratamientos de stack definidos y congelados. Añadir más microcasos de respuesta corta no resuelve la atribución causal entre modelo y sistema.
