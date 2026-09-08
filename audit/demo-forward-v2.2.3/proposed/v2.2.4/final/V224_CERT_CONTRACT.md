# Runtime CERT contract

Candidate 3 uses Q24.EXEC.CERT only; it never writes QDB1.EXEC.CERT.

CERT=1 is valid only when bound to executor instance, build, login, manifest token, executor source token, Darwinex UTC offset, and each producer owner/epoch/source token. Disconnect/reconnect, producer identity change, offset transition, restart, recovery, entry/bus/management fault or loss of trading permission invalidates certification.

Bootstrap defaults to InpAllowChartProvision=false and therefore does not close unrelated charts or provision templates unless explicitly enabled in an isolated authorized runtime. A durable receipt is written and reopened successfully before the CERT latch.

Current blocker: InpSessionCloseLeadSec=0. RuntimeCertified therefore cannot authorize entries until an authoritative Darwinex native session/latency gate freezes this execution-safety value.
