# QROS Research Studio — MVP Contract v1

Status: PRODUCTIZATION_PREREGISTERED_NO_RESULTS

## Purpose

Convert the existing QROS/RISE runtime into a Windows-first desktop research product without changing scientific rules, reusing the existing deterministic C++20 core and keeping all customer-facing AI outside scientific authority.

The MVP is not a promise of profitable strategies. It is a reproducible quantitative research and adversarial validation workstation.

## Non-negotiable boundaries

1. `control/HEAD.json` remains scientific campaign authority and is not modified by productization work.
2. Existing QROS/RISE scientific contracts, holdout firewalls, execution semantics, multiplicity rules, evidence semantics and MT5 parity requirements remain authoritative.
3. Customer AI may propose hypotheses, translate natural language to a typed draft, explain results and suggest new genealogies. It may not grant PASS, APPROVED_RESEARCH, APPROVED_FINAL, HOLDOUT_OPEN, SUPERGATE_PASS, MT5_PARITY_PASS or portfolio inclusion.
4. All scientific transitions are deterministic state-machine decisions backed by machine-verifiable evidence.
5. Productization must not include proprietary trading modules, private strategy ledgers, broker data, credentials or clean holdout data.
6. No paid API, cloud compute, subscription service or external billing is required by the MVP.
7. Default processing is local. Cloud/LLM integration is optional and replaceable.

## MVP user journey

The first accepted product slice must support this closed loop:

1. Create local project.
2. Import user-provided market data through an explicit adapter.
3. Run data audit and provenance checks before economic scoring.
4. Define or import a typed Strategy Contract.
5. Freeze research contract before development results are used for selection.
6. Run deterministic QROS development/backtest pipeline.
7. Persist candidate genealogy, search-space identity, N_TESTS, execution semantics, cost model and evidence references.
8. Execute RISE-Q gate checks appropriate to the current stage.
9. Return either REJECTED or a candidate eligible for the next authorized stage.
10. Export a Research Evidence Attestation describing exactly what was executed and what remains unverified.

MT5 external parity and final deployment remain later acceptance gates unless a real MT5 host and authentic evidence are available.

## Product modules

### QROS Studio Shell
Desktop UI and local project management. It has no scientific authority.

### QROS Copilot
Optional AI interface for hypothesis drafting, contract explanation and result interpretation. It is explicitly untrusted for PASS/FAIL decisions.

### Strategy Contract Compiler
Converts validated structured input into an immutable, versioned Strategy Contract. Natural-language output must never bypass this compiler.

### Data Authority Layer
Binds files, hashes, symbol aliases, units, clock/session contracts, coverage, Bid/Ask semantics and provenance. Economic scoring is forbidden until required gates pass.

### QROS Core
Existing deterministic C++20 engine for data, features, execution, backtest, gates, result storage and resumable jobs.

### RISE-Q Guardian
Continuous event-driven validator that checks authority, evidence, exposure, genealogy, semantic validity and stage transitions.

### Independent Parity Layer
Independent implementation/oracle with explicit provenance. Shared assumptions and shared code paths must be declared rather than treated as independent evidence.

### Portfolio Lab
Separate post-strategy layer for correlation, overlap, interference, daily entry caps, marginal contribution and portfolio-specific overfitting controls.

### Deploy
Exports research artifacts and, when genuinely validated, MT5/Python deployment packages. Export is not equivalent to APPROVED_FINAL.

## Research states allowed in the product

- CAMPAIGN_ACTIVE
- PREREGISTERED_NO_RESULTS
- DEVELOPMENT_RUNNING
- FROZEN_CANDIDATE
- APPROVED_RESEARCH
- MT5_EXTERNAL_PENDING
- APPROVED_FINAL
- REJECTED
- OBSERVATIONAL_RESERVE
- BRANCH_EXHAUSTED
- BLOCKED_BY_INFRASTRUCTURE

Every transition must be explicit, logged and fail-closed.

## Research Evidence Attestation

The product must never emit a generic profitability certificate. It may emit an attestation containing:

- strategy/campaign ID;
- root genealogy ID;
- software commit/build/hash;
- Strategy Contract hash;
- dataset/snapshot hashes and provenance class;
- development and validation window classification;
- exposure registry state;
- tests actually executed;
- methods not executed;
- costs/execution semantics;
- deterministic result hashes;
- gate decisions and authority sources;
- MT5 parity status;
- portfolio integration status;
- limitations and blockers.

The attestation certifies evidence provenance and executed validation only. It does not certify future profitability.

## Commercial boundary

The public product contains the laboratory, not the project's proprietary alpha. Existing XAU/NDX modules, frozen seeds, trade ledgers and private campaign-specific intelligence must not be shipped in customer builds unless separately and explicitly licensed.

## MVP acceptance gates

The MVP is accepted only when all are demonstrated on TEST_ONLY fixtures and an authorized development sample:

A. Clean installation on supported Windows target.
B. Runtime executes without requiring ChatGPT or an external Python installation in the normal path.
C. Typed Strategy Contract can be created, validated, frozen and hashed.
D. AI cannot directly modify frozen rules or scientific state.
E. Data provenance/unit/session gates fail closed.
F. Development run is resumable with deterministic checkpoint identity.
G. RISE-Q rejects semantically invalid evidence even when hashes are valid.
H. Exposure registry prevents reuse of an exposed period as clean holdout.
I. Independent parity provenance is recorded.
J. Research Evidence Attestation is reproducible from stored artifacts.
K. No proprietary module or broker carrier is present in the distributable package.
L. Existing QROS scientific regression suites remain green for all touched components.

## Explicitly out of MVP

- SaaS multi-tenant cloud execution;
- paid hosted inference;
- mobile native application;
- marketplace of strategies;
- automatic live trading;
- claims of guaranteed profitability;
- proprietary QROS alpha distribution;
- institutional billing/licensing infrastructure;
- unsupported broker-data redistribution.

## First engineering objective

Implement the product boundary and contracts before UI polish. The first code milestone is a local, deterministic `research_job` path that consumes a typed Strategy Contract plus Data Authority packet, invokes existing QROS components and produces a state transition plus Evidence Attestation skeleton without any AI dependency.
