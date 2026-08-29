# QROS ENGINE v0.2

Runtime cuantitativo experimental nativo para QROS/RISE.

Estado: `DEVELOPMENT_RUNNING`. No es todavía un motor autorizado para selección OOS ni reemplaza MT5.

## v0.2 añade

- señal ligada a un tick autoritativo exacto;
- `session_close_seq` autoritativo: EOF no equivale a cierre;
- `UNRESOLVED_CLOSE` si no existe quote ejecutable posterior a la entrada;
- conteos de timestamp repetido/payload repetido para auditoría;
- `run_id` SHA-256 determinista en receipts;
- `_GLIBCXX_ASSERTIONS` en Release;
- GCC `-fanalyzer -Werror` limpio tras simplificación del parser;
- 10.000 property cases C++ deterministas;
- paridad independiente Python;
- build estático reproducible byte-a-byte en dos directorios limpios.

Véase `docs/EXTERNAL_MODEL_CROSS_AUDIT_v0_2.md` para la auditoría transversal.
