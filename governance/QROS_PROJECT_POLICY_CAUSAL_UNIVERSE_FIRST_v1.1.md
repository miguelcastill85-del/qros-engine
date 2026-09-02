# QROS PROJECT POLICY — CAUSAL UNIVERSE FIRST v1.1

**Estado:** ACTIVE_PROJECT_INVARIANT  
**Adopción:** 2026-09-01  
**Sustituye prospectivamente:** `QROS_PROJECT_POLICY_CAUSAL_UNIVERSE_FIRST_v1.0`  
**Conserva:** todos los receipts y resultados históricos; no reescribe evidencia anterior.

## Corrección incorporada en v1.1

La versión 1.0 impedía entrar a desarrollo antes de congelar suficientemente el universo causal, pero no contenía una barrera explícita que impidiera a un **frente o subfrente** abrir por sí mismo un holdout mientras la **genealogía causal raíz** seguía teniendo frentes elegibles pendientes.

Ese hueco queda cerrado.

## Regla dura de holdout

**El holdout pertenece a la genealogía causal raíz, no al frente, subfrente, activo, cluster, tier, seed descendiente ni perfil que llegue primero.**

Un `STAGE_EXHAUSTED`, una cohorte local congelada, un activo terminado o la ausencia temporal de supervivientes en otros frentes **NO autoriza** a abrir el holdout.

Antes de cualquier lectura económica del holdout deben cumplirse simultáneamente:

1. `UNIVERSE_ONTOLOGY_FROZEN = TRUE`.
2. `RISE_FIXED_POINT = TRUE`.
3. `ONTOLOGY_SUFFICIENCY_AUDIT_RECEIPT = PASS`.
4. `PREDEVELOPMENT_UNIVERSE_COVERAGE_RECEIPT = PASS`.
5. Todos los frentes elegibles de la genealogía han terminado investigación pre-holdout o fueron excluidos causalmente con evidencia.
6. Existe `ROOT_GENEALOGY_PRE_HOLDOUT_COVERAGE_RECEIPT = PASS`.
7. No queda ningún `OPEN_ELIGIBLE_FRONTIER`.
8. Selección, deduplicación y clustering de toda la genealogía están terminados.
9. La cohorte final de candidatos de la genealogía está congelada.
10. BUY y SELL permanecen separados.
11. Semántica de ejecución, costes y paridad independiente están congelados/verificados.
12. La ventana propuesta como holdout sigue sin exposición económica para **toda la genealogía**, no sólo para el candidato actual.
13. El gate de aceptación del holdout está congelado antes de leer resultados.
14. `scripts/qros_holdout_genealogy_preflight.py` devuelve simultáneamente `status=PASS` y `decision=HOLDOUT_OPEN_AUTHORIZED`.

Si falta cualquiera, el estado obligatorio es:

`HOLDOUT_OPEN_FORBIDDEN`

La ejecución falla cerrada y no puede leer trades, PnL, PF, Sharpe, drawdown u otros resultados económicos del periodo reservado.

## Qué NO cuenta como apertura económica

Auditar bytes, tamaños, SHA-256, CRC, timestamps, continuidad estructural o construir infraestructura sin consultar resultados de estrategia **no expone económicamente** el holdout.

En cambio, leer operaciones, PnL, PF, Sharpe, DD, win rate, expectancy o cualquier veredicto económico de una estrategia sí produce exposición.

## Propagación irreversible de exposición

Si un holdout se abre prematuramente en cualquier descendiente:

- se detienen nuevas lecturas económicas;
- los resultados ya observados se preservan, nunca se borran ni se maquillan;
- la ventana observada se marca `EXPOSED` para **toda la genealogía raíz**;
- ningún descendiente puede volver a llamarla holdout limpio;
- la validación final limpia deberá usar `TRUE_FORWARD` o datos externos realmente no observados.

La exposición es irreversible.

## Relación con etapas internas

Una campaña puede tener desarrollo, confirmación interna, validación y otras etapas prospectivamente congeladas. Esas etapas no adquieren por ello autoridad para abrir el **holdout final limpio** de la genealogía.

El holdout final se abre una sola vez después de terminar y congelar la investigación pre-holdout de la genealogía completa.

## Autorización automática

Las órdenes `continúa`, `comienza`, `sigue`, `adelante`, `ejecuta`, `prosigue` o equivalentes **no constituyen autorización de holdout**. Antes de ejecutar cualquier lectura económica reservada, el sistema debe comprobar el firewall de genealogía.

El artefacto normativo es:

`governance/QROS_HOLDOUT_GENEALOGY_FIREWALL_v1.0.json`

El preflight obligatorio es:

`scripts/qros_holdout_genealogy_preflight.py`

## Mensaje humano irreversible

Cuando el preflight autorice realmente la apertura, la interfaz debe mostrar:

**HOLDOUT ABIERTO — ESTE PERIODO YA NO ES DESCONOCIDO PARA TODA LA GENEALOGÍA.**
