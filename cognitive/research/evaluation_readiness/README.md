# Evaluación: implementación y límites

`cognitive.evaluation.BenchmarkLedger` conserva exposiciones del benchmark de forma transaccional e idempotente; una exposición en cualquier descendiente contamina la raíz declarada, hermanos y versiones futuras. No comparte estado ni periodos con trading. La ausencia de registro no certifica secreto. El host debe declarar toda la genealogía real y conservar el archivo SQLite; un registro borrado no es evidencia de limpieza.

`paired_statistics` calcula intervalos simultáneos por dimensión sobre datos suministrados. Exige protocolo ligado externamente por SHA-256, n fijo, IDs de cluster únicos y las doce dimensiones. Se orientan puntuaciones a mayor-es-mejor antes de ingresarlas según una rúbrica prerregistrada. Un veto impide el resultado condicional favorable. La función no autentica proveedores, independencia, ejecución o sellado; por eso no emite paridad ni promoción.

Se usa la cota de Hoeffding para variables independientes acotadas y unión de eventos entre dimensiones ([notas de CMU](https://www.cs.cmu.edu/~15850/notes/lec11.pdf)). La evaluación de tamaño fijo no admite elegir cuándo detenerse después de ver resultados; para inferencia secuencial se requieren otros límites ([investigación sobre límites adaptativos](https://ai.stanford.edu/~ermon/papers/adaptive_bounds_nips2016.pdf)). Estas fuentes sustentan el cálculo, no prueban que nuestras tareas satisfagan sus supuestos.

`promotion_inventory` expone qué recibos faltan. Ni una tabla de PASS ni un hash autoriza promoción. El protocolo científico existente conserva esa autoridad.

La configuración numérica de los tests es sintética. No está prerregistrada como umbral de paridad real. Todavía no hay ejecutor observable de Sol/Astra, muestras selladas, juicio independiente ni ensayos comparables para seleccionar definitivamente una arquitectura completa. No se sustituyen por nuestros resultados de componentes.
