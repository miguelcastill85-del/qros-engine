# Event Phase Contract v1

Contrato hashado por QROS ENGINE:

1. `MARKET_DATA_ACCEPTED`
2. `FEATURE_STATE_UPDATED`
3. `SIGNAL_COMMITTED`
4. `ORDER_INTENT_COMMITTED`
5. `NEXT_RECORD_EXECUTION_ELIGIBLE`
6. `POSITION_MANAGEMENT`
7. `SESSION_SETTLEMENT`

Invariantes:

- ninguna entrada ocurre en el mismo registro que comprometió la señal;
- `seq` es la autoridad causal primaria;
- timestamps pueden empatar pero no retroceder;
- el intent liga exactamente `signal_seq + signal_ts_ns + signal_session_day`;
- `session_close_seq` debe ser el cierre autoritativo de la sesión;
- el replay no puede usar información posterior a la frontera causal para decidir la entrada.

SHA-256 actual del contrato:

`dbb5a921f9239424b780f8fd73f95ae08239746da58a3627efe4368f7bf42465`
