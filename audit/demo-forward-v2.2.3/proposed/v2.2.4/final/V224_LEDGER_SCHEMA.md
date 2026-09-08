# Ledger contract

Session ledger is append-only and checked. Required semantics include server time, uptime, stage/decision/reason, durable intent id/state, module/profile/seq/event timestamp/action, symbol, Bid/Ask, requested/effective volume, SL/TP, order/deal/position tickets, retcode and account/balance context. Critical persistence failure blocks new entries. Ticket persistence uses exact high/low 32-bit halves rather than lossy double conversion.
