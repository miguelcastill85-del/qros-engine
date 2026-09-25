# QROS Mobile — Contrato exclusivo de aplicación móvil v1

Fecha de autorización de alcance: 2026-09-25. Estado: CAMPAIGN_ACTIVE; sin autorización de publicación comercial.

## Autoridad y genealogía
Este contrato es un descendiente comercial nuevo del histórico `product/QROS_RESEARCH_STUDIO_MVP_CONTRACT_v1.md`. Sustituye **únicamente su alcance de producto y prioridades de desarrollo**, no sus invariantes científicos, políticas de seguridad o evidencias congeladas. No se modifica `product/PRODUCT_HEAD.json`, `control/HEAD.json` ni la autoridad de `main`. El producto histórico Windows-first queda archivado como antecedente técnico, no como hoja de ruta vigente.

## Objetivo del producto
Desarrollar una aplicación móvil profesional de investigación cuantitativa, inicialmente Android y posteriormente iPhone. Todo flujo del cliente debe poder iniciarse, supervisarse y completarse desde el móvil: creación de proyectos, definición de hipótesis, contratos tipados, ingestión autorizada de datos, backtesting, RISE-Q, seguimiento de trabajos, análisis de portafolio e informes reproducibles.

## Dentro del alcance
- Aplicación móvil Flutter con interfaz y navegación adaptadas a teléfonos; Android como primer dispositivo de aceptación.
- Datos sintéticos TEST_ONLY para el primer vertical slice y demostraciones públicas.
- Un backend mínimo y autenticado para ejecutar el motor determinista C++20 y el registro M2. Esta infraestructura no constituye una aplicación de escritorio comercial.
- Trabajos pesados fuera del teléfono, con límites de recursos, reanudación verificable y transparencia sobre costes.
- Estados científicos separados de las anotaciones de infraestructura, recibos firmados/autenticados, y HEAD externo inmutable antes de autorizar mutaciones remotas.
- Móvil con autoridad de consulta por defecto; cualquier solicitud de transición pasa por autorización **del servidor**, nunca por un actor o bandera suministrado por la app.
- Monetización por suscripción únicamente después de probar seguridad, cumplimiento, costes marginales y uso real.

## Fuera del alcance actual
- Aplicación o interfaz de escritorio, instalador Windows, experiencia Mac, CLI comercial orientada al cliente y flujo Windows-first.
- Certificación Windows nativa como bloqueante del primer lanzamiento móvil si el backend se despliega sobre Linux debidamente validado. La ausencia de certificación Windows seguirá documentada y su ruta local debe fallar cerrada.
- Trading automático live, marketplace de estrategias, redistribución de carriers Darwinex, entrega de alfas privados, promesas de rentabilidad y servicios de pago habilitados sin aprobación.
- Una API pública que permita seleccionar `QROS_CORE`, enviar `TransitionContext` como evidencia o promover etapas sin recibos independientes.

## Orden de ejecución desde este contrato
MOBILE_SCOPE_FREEZE → TEST_ONLY_MOBILE_VERTICAL_SLICE → MOBILE_SECURITY_THREAT_MODEL → SERVER_ONLY_AUTHORITY_AND_AUTHENTICATED_RECEIPTS → IMMUTABLE_EXTERNAL_HEAD → MOBILE_TO_BACKEND_TEST_ONLY_INTEGRATION → ANDROID_DEVICE_ACCEPTANCE → PILOT_CONTROLADO → VALIDACIÓN_COMERCIAL.

M2 Linux ya tiene pruebas de integración; no repetirlas en ausencia de cambios. Resolver la seguridad de mutaciones antes de activar la API remota. No reiniciar ni alterar los experimentos científicos QROS.

## Criterios de aceptación de la primera entrega móvil
1. Se instala o ejecuta una app Android (la maqueta HTML anterior no cuenta como aplicación instalable).
2. El usuario navega por proyectos, crea un contrato de demostración y consulta sus estados con accesibilidad básica.
3. No se envían datos del broker ni secretos a la app.
4. Una ejecución sintética puede verse desde móvil con recibo, identidad de build y estados de validación honestos.
5. El móvil no puede otorgar PASS, abrir holdout, fingir autoridad QROS_CORE ni modificar contratos congelados.
6. Hay un conjunto de pruebas de UI Android y de API autenticada, documentado con plataforma, versiones y logs exactos.
7. No depende de un cliente Windows para operar.

## Separación metodológica
El hecho de aprobar un build móvil o las pruebas M2 no concede aprobación científica ni comercial. Mantener cerrados economic PnL, GA2, holdout y MT5 externo salvo autorización y evidencia específicas.
