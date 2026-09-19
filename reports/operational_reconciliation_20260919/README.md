# Reconciliación operativa QROS — 19 septiembre 2026

Alcance: consistencia de referencias y etiquetas operativas. No activación de un
supervisor ni ejecución científica.

La discrepancia original del checkpoint 4.16 quedó superada por avances concurrentes
de main. La reparación se aplica sobre `70cff9e16983319ac42d36f69906fb6af7f5e1ce`,
que conserva el checkpoint 4.25 y DEK v3 activo. No restaura versiones antiguas.

Cambios:

- El checkpoint apunta al target científico V255 inmutable; desaparece la dependencia circular del hash del puntero mutable.
- El candidato histórico DEK v3 especifica su commit exacto. Su antiguo hash no se compara contra el archivo activo.
- La autoridad de recuperación del grupo 09 apunta a su estado terminal.
- El último recibo queda en grupo 10 y la siguiente cápsula en grupo 11.
- La etiqueta pendiente conserva los 11 grupos cerrados, sin el texto desactualizado de 9.
- Puntero 6.9, checkpoint 4.26 y recibo se promueven como un único árbol Git.

Validación: 128 referencias de puntero/checkpoint; metadatos de 11 recibos, cuyo total
reportado es 368808 configuraciones; seis pins de fuentes de cápsula; 14 mutaciones
adversariales rechazadas. La reproducción offline genera tres blobs exactos.
Se verificaron bytes de 21 documentos/fuentes recuperados. No se reejecutaron los
workers ni se rehashearon sus grandes artefactos históricos.

Reproducción, en un directorio temporal y sin modificar control del repositorio:

```bash
python3 reports/operational_reconciliation_20260919/reproduce.py
```

El workflow de exportación y su next_action se conservan literalmente. Este trabajo
no comprueba su estado en vivo ni lo relanza. Se conservan DEK v3, el supervisor
congelado, los gates, la exposición y la autoridad científica V255. PR #54 sigue como
candidato de ingeniería sin activar; P09/P12 no se cierran con esta reconciliación.

El snapshot es un registro de referencias seleccionado del árbol base, no un checkout
completo ni una nueva autoridad de datos. El recibo conserva los pins previos como
evidencia histórica y define el alcance de sus verificaciones.
