# QROS W5 — continuidad operacional v2.3, validación preeconómica parcial

**Ámbito:** `WEB_SEED_0076`, `XAUUSD/M1/W5/SOURCE_ASYMMETRIC/RETURN_INSIDE_OR_LEVEL_REPLACED/TICK_BREAK`, BUY y SELL. Congelado V209: 11.176 paquetes por lado, 22.352 hipótesis, DEV 2018–2019 ya expuesto. Los 13 frentes de siete familias anteriores permanecen cerrados; nueve W3 están diferidos por instrucción expresa. Ni holdout ni GA2 se abren.

**Causa raíz operacional:** la gobernanza v2.2 estaba en `main`, pero W5 no tenía cola/planes ejecutables con identidad SHA ni transporte conectado de sus datos. El despachador cerraba una etapa por invocación, el CI de Anti-Stall ejecutaba solo v2.1 y ningún runner externo estaba configurado. Esto no se corrige con más prompts ni llamando PASS a una cola vacía.

**Corrección ejecutada:** `qros_w5_pipeline_v23.py` enlaza un único plan local QROS v2.1 y un plan externo *no acreditado* a una cola SHA-congelada v2.2, con watchdog de 42 s/28 s, presupuesto global de 110 s, dos backends precongelados (Numba y CPython). Reinvoca automáticamente el despachador dentro del presupuesto, reutiliza PASS validado, recupera tras interrupción **solo** si todos los outputs y entradas coinciden con tamaño y SHA publicados fuera del estado, y jamás asciende una dependencia externa sin evidencia real. Un segundo lanzamiento no vuelve a correr el stage PASS.

**Corrección científica previa al backtest:** el V221 original usa `searchsorted(..., side='left') - 1` para el TF superior: en el primer tick de una barra nueva descarta indebidamente la barra superior recién terminada. El adaptador `qros_w5_mtf_causal_adapter_v1.py` implementa `side='right' - 1` con tests de borde y no-lookahead. No muta el V221 histórico. El V220 original barre solo Bid sin validar Ask; los oráculos `guarded_raw_oracle` excluyen ticks no positivos, spread cero o cruzado, antes de cruces/rearme. **Falta implementar e independizar este guard en un carrier vectorizado real** y verificar RETEST_ENTRY, BREAKOUT_BUFFER y toda la cadena de diez familias en DEV antes de autorizar PnL. Las suites de ahora son sintéticas y de inventario, no trades reales.

## Ejecutar sobre los bytes congelados

Requisitos locales: Python con NumPy y Numba, sin depender de red para los ensayos sintéticos. Instalar o utilizar el entorno aprobado de QROS; no exige compra. El directorio del ZIP ya contiene `anti_stall/`, `legacy/source_pins/`, `v209/` y scripts.

```bash
python qros_w5_pipeline_v23.py bootstrap --root ./QROS_W5_RUN
python qros_w5_pipeline_v23.py run --root ./QROS_W5_RUN --budget 110
python qros_w5_pipeline_v23.py status --root ./QROS_W5_RUN
```

**Antes de bootstrap real:** el operador conectado debe comparar `main/control/QROS_ANTI_STALL_ACTIVE_GOVERNANCE_POINTER.json` con su identidad vigente, el puntero de la rama científica contra el blob `8370decb2c8e033c4b60662e72f03b22516ae899` y el prerregistro contra el blob `40275ce4fc0454759a181d9e3d7e8757630134da`. Si la rama avanza, reconciliar desde HEAD; **no ejecutar la cola vieja**. `bootstrap` por sí solo no consulta GitHub ni valida que el puntero siga vigente; el host/ChatGPT debe hacer esa lectura autenticada previamente.

`W5_QUEUE_EXTERNAL_PIN.json` contiene el SHA-256 exacto de cola y planes, además del SHA previsto del único receipt permitido. Un archivo no materializado no significa un nuevo DEV aprobado. El plan de datos real permanece externo y sin attestation hasta recuperar y rehashear el carrier oficial.

## Reanudación del carrier real

Se requieren bytes originales **exactos**: packed17 de 2.573.500.596 bytes y SHA-256 `3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53`, barras M1 SHA `35a8644644daab5fc04a218d5527c3839b5248471801f8a56bbb8a71a7457f59` y cache de indicadores M1 SHA `f30da86f6c11b5a6573b3571ffd3c3621bbe4d51134258c89d956d6f9ab115b5`. Cuando estén disponibles en la misma máquina:

```bash
python qros_w5_realdata_preflight_v1.py --ticks /ruta/XAUUSD_DEV_PACKED17_151382388.bin --bars /ruta/XAUUSD_M1_BID_BARS.npy --indicators /ruta/XAUUSD_M1_INDICATORS.npz --out ./W5_REALDATA_QUOTE_AUDIT.json
```

Este programa recalcula los tres SHA, audita 151.382.388 ticks por shards, orden temporal, spreads inválidos y alineación barra-indicador. No da aprobación para PnL hasta demostrar el calendario/zonas de Darwinex, paridad causal de guardas de Bid/Ask y RETEST_ENTRY/MULTI_TF real. El ZIP actual **no contiene** el carrier de 2.57 GB. La búsqueda en Drive por el nombre packed17 no devolvió el archivo; existen ZIPs multipartes históricos cuya reconstrucción permanece pendiente, no se han declarado irrecuperables.

## Evidencia / límites

Pruebas: 37 de v2.1, 8 de v2.2, 21 del W5 estructural, 12 de integración v2.3 y 5 de preflight negativo = **83 PASS**. Smoke real de cola local: `ONE_VERIFIED_STAGE_PASS` sintético seguido de `EXTERNAL_PROOF_REQUIRED_SAFE_SKIP`; segunda ejecución: 0 stages repetidos. En GitHub el archivo de source mirror y esta release deben vincularse a un receipt inmutable. CI remoto, Windows nativo, MT5 y toda ejecución con ticks reales **siguen sin verificar**. Sin scheduler configurado no existe trabajo autónomo posterior al chat.
