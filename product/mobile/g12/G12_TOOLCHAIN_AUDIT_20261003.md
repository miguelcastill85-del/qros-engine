# Auditoría de herramientas G12 — 2026-10-03
VERIFICADO localmente: npm audit registró 3 paquetes afectados (1 high, 2 moderate), derivados de Undici 7.29.0.
Se fija Undici 7.29.1 para todas las rutas transitivas, manteniendo Miniflare y Wrangler fijados.
Primaria: https://github.com/nodejs/undici/security/advisories/GHSA-w293-vg96-wgc3 .
Después: npm audit = 0 avisos y siete pruebas workerd pasan.
La primera modificación limitada a Miniflare dejaba Wrangler usando 7.29.0; se corrigió con override global.
No usar npm audit fix --force ni migrar a una versión mayor para resolver este parche.
Esto califica herramientas de desarrollo/despliegue G12, no la ausencia universal de vulnerabilidades.
G9 conserva su lockfile histórico; sus herramientas requieren parche separado antes de nuevos despliegues con secretos.
CI y artefacto del parche quedan pendientes al commit fuente; no despliega ni utiliza credenciales.
