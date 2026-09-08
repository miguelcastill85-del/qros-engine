# Bus protocol Candidate 3

Namespace: Q24.*, intentionally isolated from the live/rejected v2.2.3 QDB1.* namespace.

Per module: exclusive producer file fence + owner/epoch identity + atomic publish mutex. Writer invalidates slot SEQ/VER before payload, writes finite/exact fields, commits VER then SEQ, advances monotonic HEAD, heartbeat/watermark, flushes globals. Reader validates SEQ/VER both before and after payload and binds payload to current owner/epoch. Rollback, torn payload, non-exact doubles or source-token mismatch fail closed.
