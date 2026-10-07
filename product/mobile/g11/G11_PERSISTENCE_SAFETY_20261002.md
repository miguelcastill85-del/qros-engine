# G11 persistence safety follow-up — 2026-10-02
Parent: da2b18b1f5ea7c690f72007508a72ed6f6497c43, already integrated G11, CI37015270543 SUCCESS.
Do not repeat G10/G11 implementation or G9 physical pairing.

Identified from source: concurrent read/modify/write loses one draft and duplicates IDs; save/clear race can resurrect a universe; create without hydration can erase existing projects; read failures/corruption allow overwrite; sequence below stored ID can produce future collisions.

Correction: per-store serialized transactions, hydration before mutation, block writes/deletes after failed load, preserve original corrupt bytes, strict ID-to-sequence binding, migration commit after successful durable write. Write failures leave memory unchanged and do not poison queued retries.

CI first runs seven new tests against frozen parent source and requires six expected failures, restores corrected source, then runs full analyze/test/build. This is TEST_ONLY and not proof of physical Keystore or commercial readiness.

Preflight local handoff/verify_import.py: fails because scoped recovery lacks HANDOFF_MANIFEST.sha256, matching earlier recorded limitation. Scientific files are untouched.

Next: verify CI/artifact bytes, then customer authentication and resumable synthetic job integration. Release signing, actual distribution account and commercial onboarding remain open. No paid resources or private market data authorized.
