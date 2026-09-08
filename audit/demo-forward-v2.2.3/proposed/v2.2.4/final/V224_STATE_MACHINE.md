# QROS v2.2.4 Candidate 3 — state machine

Status: DEVELOPMENT_RUNNING / OFFLINE_CANDIDATE3_PASS_NATIVE_GATES_PENDING.

Entry intent states:
- QI_RESERVED: durable reservation written before broker send.
- QI_SENT_UNKNOWN: request accepted locally but final broker state not yet authoritative.
- QI_WORKING: live working order observed.
- QI_PARTIAL: partial position/order state; residual risk remains reserved.
- QI_FILLED_PROTECTED: position observed with at-least-requested BUY protection.
- QI_CLOSING: risk-reducing close intent remains durable until observed flat.
- QI_CLOSED / QI_REJECTED / QI_CANCELLED: terminal tombstones retained for the server day.

Management intent states:
- QM_PENDING -> QM_ESCALATED -> QM_DONE.
- Modify/close completion requires broker retcode plus observed post-state; boolean return alone is never authoritative.

Safety invariant: unknown/partial broker state never releases risk, asset, timestamp or daily-entry reservation.
