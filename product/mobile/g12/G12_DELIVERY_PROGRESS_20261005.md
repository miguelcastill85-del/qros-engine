# G12 — recuperación y entrega 2026-10-05

OBJETIVO: cerrar la entrega móvil TEST_ONLY y preparar el siguiente gate legítimo de despliegue/piloto. La comercialización completa conserva sus requisitos originales.

AUTORIDAD — VERIFICADO: PR78, rama product/mobile-g12-renewable-session-jobs-20261002, descendiente de b877474. MOBILE_PRODUCT_HEAD v11 permanece sin promoción. Checkpoint machine G12_CURRENT_CHECKPOINT.json actualizado; los recibos anteriores se conservan.

DATOS — VERIFICADO: APK 0.12.1+13 ya aprobada por CI37126514681, 146666789 bytes, SHA-256 40568dc3f612cb452513b2f933090e4549f2109d7560cfc944fb8f5f84221822. No se reenumeraron ni ejecutaron etapas científicas.

TRABAJO EJECUTADO — VERIFICADO: las credenciales previamente autorizadas en GitHub sí acceden a Workers API (200) en CI37258559675. La vía API legítima permite superar la dependencia del navegador. No se extraen ni muestran secretos; el reporte sólo contiene resultados y códigos. Consulta de suscripciones: 403/10000 por alcance mínimo del token, conservado sin ampliarlo.

RESULTADOS — VERIFICADO: preparación de despliegue CI37259435859 PASS; nuevo canary local contra el Worker inalterado pasa rotación, replay, tenants/clientes, origen/CORS, idempotencia y hash sintético. Configuración dry-run PASS. El deploy está SKIPPED porque falta confirmación actual del plan Free. Este PASS local no demuestra HTTPS público.

PROBLEMA Y CAUSA RAÍZ — VERIFICADO: CI37259211673 instaló exactamente la APK aprobada en Android35 y comprobó el hash instalado. Falló al exigir etiquetas nativas para servidor/ bootstrap. Las capturas demuestran campos visuales; XML indica controles EditText NAF=true sin etiquetas. El fallo se conserva, no se cambia la expectativa.

CORRECCIÓN: Semantics explícito en ambos campos y texto de vinculación futura; nueva versión 0.12.2+14. CI37259618369 está ejecutando análisis, regresiones, compilación y Android35. Se reutiliza el baseline causal de cuatro defectos si session_client y su regresión permanecen iguales; no se reproduce de nuevo trabajo ya verificado.

URL HTTPS REAL G12 — NO DISPONIBLE: aún no desplegado. No usar como prueba la URL derivada del subdominio del proveedor.

GATES: Free actual NO DISPONIBLE por API; el gate previo queda REPORTADO. Basta una confirmación actual del usuario, sin crear token ni ampliar permisos: se registra en product/mobile/g12_deployment/cost_gate.json por una hora y se dispara el despliegue preparado. Después HTTPS externo Node+Python y pairing físico G12. El gate se revalida al ejecutar, rechaza planes pagos, vencimiento, futuro, scope distinto y banderas de costo.

ESTADO CIENTÍFICO — VERIFICADO DEL ALCANCE DE ESTA SESIÓN: sólo archivos producto/workflows; no escrituras en main, no PnL, holdout, GA2, MT5 o trading. Resultado G12 sólo es infraestructura sintética con hash, sin firma asimétrica independiente ni investigación real. La evidencia Rekor G9 previa no se transforma en custodia independiente de G12.

IMPACTO PORTAFOLIO: ninguno evaluado ni autorizado. COMERCIALIZACIÓN: NO DISPONIBLE; siguen abiertos backend de investigación autenticado, custodia/firma de distribución y aceptación de piloto según contrato G10.

SIGUIENTE ACCIÓN EXACTA: inspeccionar CI37259618369, descargar y verificar APK/evidencia, persistir resultado. No reiniciar jobs. No hay investigación en segundo plano; sólo el workflow identificado está activo.

INCIDENTE DE MATERIALIZACIÓN HISTÓRICA: ejecutar handoff/verify_import.py sobre el checkout local parcial falló por ausencia local de HANDOFF_MANIFEST.sha256; el manifiesto y anchor existen remotamente. Esto no invalida las fuentes móviles fijadas y CI; no se declara el checkout parcial importado como baseline íntegro.
