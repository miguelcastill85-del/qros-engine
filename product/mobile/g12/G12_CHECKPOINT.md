# QROS Mobile G12 — sesión renovable + trabajo sintético reanudable
Fecha: 2026-10-02
Padre: `da2b18b1f5ea7c690f72007508a72ed6f6497c43`.
Estado: DEVELOPMENT_RUNNING · TEST_ONLY.
Objetivo: cerrar G10 #2 y la porción Worker-sintética de #3.
Diseño: pairing de un uso (hash servidor), access 15 min, refresh 7 días rotatorio, tokens locales en secure storage, jobs idempotentes/tenant-scoped con cursor Durable Object en chunks de 256. Respuestas: scientific_authority=NONE, economic_backtests=0, holdout=false, GA2=false, MT5=false.
No afirmado: OIDC productivo, onboarding público, C++20 remoto, despliegue público G12, Android físico, firma release o autoridad científica.
Gates CI: WORKER_TEST, FLUTTER_ANALYZE, FLUTTER_TEST, APK. REMOTE_DEPLOY queda pendiente sin credencial GitHub verificable.
