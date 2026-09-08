# Recovery protocol

1. Load durable Q24 intent and management slots.
2. Rebuild daily entry count from authoritative history; HistorySelect failure is fail-closed.
3. Enumerate QROS working orders and open positions. Unknown broker inventory creates recovery shells and requires recertification.
4. Unprotected or old-day inventory is scheduled for risk-reducing management; entry faults never disable management processing.
5. Recovery lock remains until positions, QROS orders and nonterminal intents are absent and history is available.
6. A restart always invalidates runtime CERT. External bootstrap must issue a new durable receipt before CERT can latch again.
