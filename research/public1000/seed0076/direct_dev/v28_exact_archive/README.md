# Seed0076 — código V28 recuperado exactamente (archivo de investigación)

Esta carpeta contiene **36 archivos Python originales**, sin modificar, extraídos del ZIP de recuperación de V28 y autenticados contra el manifiesto `SHA256_MEMBERS_MANIFEST.json` incorporado en aquel ZIP. Son 32 fuentes en `SOURCES/`, 3 fuentes congeladas `FROZEN_ORIGINAL_SOURCE/` y un adaptador `MTF_CAUSAL_ADAPTER/`.

- Archivo original: `QROS_SEED0076_W5_V28_MASTER_COMPLETE_22352_RESULTS_AND_REPRODUCTION.zip`
- SHA-256 del ZIP: `b2943f96a8b0eb946a9899b52e63a354d33971c88baa0b29dfd58f8e116a3e62`
- Archivo fuente registrado: `QROS_V28_36_SOURCE_RELEASE_MANIFEST.json`, SHA-256 `933f1eb09ef254d409957171c820cf12363d9c5514bf8f35c46b8a7d19465a8f`
- Cada archivo tiene tamaño, SHA-256 y Git blob SHA-1 exactos. Los archivos `REFERENCE_ONLY_` son referencias, no componentes nuevos de producción.
- Todos los archivos se incluyen como **fuentes archivadas, no desplegadas**; cualquier cambio posterior exige descendiente y validación independiente.

La prueba CI sólo interpreta AST, autentica todos los bytes y ejecuta el test **sintético original** del propio V28 contra su motor independiente con 24 operaciones / 264 campos. No accede a ticks de mercado ni a resultados económicos reales, no repite V28 ni aprueba Gate A, MT5, holdout o GA2. Los diez shards del antiguo plan GA1 quedan fuera de este trabajo.

La rama directa continúa trabajando con V32+ por separado; el ZIP completo original se conserva en Biblioteca con ID `libfile_ec62d620c5a8819188f5b83ebef2d2a0`. Integrar fuentes recuperables en GitHub no certifica por sí solo costes Darwinex 2018–2019 ni los restantes CH0/CH4.
