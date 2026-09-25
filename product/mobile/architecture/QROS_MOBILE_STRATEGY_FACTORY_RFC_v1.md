# QROS Mobile Research Studio — Strategy Factory RFC v1
Date: 2026-09-25
Classification: DESIGN_ONLY_NOT_IMPLEMENTED
Authority: user mobile-only directive and MOBILE_PRODUCT_HEAD v3 at Git blob e883f7dcc877ebbba5be79513e03893920dfa05a
Exact parent commit: 3bb3ebf843e61fd5722664310a9907745f556ae7
Scope: mobile-only Android first / iOS subsequently; Linux backend infrastructure is not a desktop product.
This is a product/engineering proposal. Existing M1 Android is TEST_ONLY signed synthetic read-only; not connected to real research data.

## Product thesis
A phone-controlled quantitative research laboratory converts a human hypothesis into a typed, bounded, pre-registered search universe; enumerates or samples millions of configurations on remote, authorized computing workers; evaluates realistic execution against licensed historical data; and yields traceable, independently verified evidence and portfolio-level incremental value. Do not optimize the largest nominal PF. No live trading, customer alpha redistribution, or scientific promotion by the AI.

## Reference and differentiation
StrategyQuant X official documentation covers Builder random/genetic generation, AlgoWizard and custom blocks/templates, Retester, Optimizer, databanks, Custom Projects, Monte Carlo and walk-forward crosschecks and Portfolio Master.
QROS adopts functional ideas, not proprietary code or interface assets. Differentiators proposed: hypothesis-first causal scope; exact bounded universe and accounting; per-tenant scientific holdout firewall; immutable lineage, semantic alias management and reproducible byte manifests; truthful measured enumeration coverage; transparent worker and compute budget; multi-stage independent execution parity; portfolio marginal orthogonality. All improvements remain hypotheses pending implementation and benchmark.

References:
- https://strategyquant.com/doc/strategyquant/program-layout/
- https://strategyquant.com/doc/strategyquant/how-does-strategyquant-work/
- https://strategyquant.com/doc/strategyquant/custom-blocks/
- https://strategyquant.com/doc/strategyquant/introduction-to-custom-projects/
- https://strategyquant.com/doc/strategyquant/cross-checks-automated-strategy-robustness-tests/
- https://strategyquant.com/doc/strategyquant/automatic-portfolio-builder/
- https://doi.org/10.2139/ssrn.2460551
- https://arrow.apache.org/docs/format/Columnar.html
- https://duckdb.org/docs/stable/data/parquet/overview

## Ten product modules

1. IDEA LAB: Guided Spanish natural language, structured hypothesis canvas and observability timeline. AI suggests interpretations and asks for human approval of ambiguous mechanics before freezing; cannot invent a trade, dataset, result or scientific PASS.
2. VISUAL STRATEGY STUDIO: Typed drag/drop and mobile cards for context, trigger, entry, risk, management, exit, filters and deployment constraints. Human-readable rules and machine-readable typed IR are side by side. First-party verified block registry and semantic versions, signed extensibility later.
3. UNIVERSE ARCHITECT: One seed/campaign at a time, fixed grammar and bounded parameter domains. Typed restrictions, impossible-combination rejection, exact/syntactic and scoped semantic dedupe, dependency pruning, prospective N_TESTS. Distinguish raw births, valid programs, unique structures, unique observed signal masks and executions.
4. STRATEGY FACTORY: Exhaustive mode for bounded tractable spaces; frozen random stratified and Sobol-like coverage if not exhaustive; genetic/evolutionary exploratory mode with fully accounted trials. Never label sampled or evolved space complete. Structured one-genealogy-at-a-time campaigns prevent retrospective seed selection.
5. BACKTEST ENGINE: Deterministic C++20 exact tick/replay fills after a gated cheap structural preflight; arrays and signal-mask batching for shared pure indicators only; path-dependent SL/TP/BE/trailing executed by chronological event engine. Costs central/conservative/severe with Bid/Ask and first executable gap price.
6. RISE-Q EVIDENCE: Data audit, preregistration, ontology fixed point for declared grammar, independent enumerator, DEV, Gate A, sealed holdout single-use authorization, Supergate, MT5 trade-by-trade parity, source receipt plus independent witness. EXPOSED research cannot be relabeled clean.
7. DATABANK + GENEALOGY: Immutable source manifests and trade/event ledgers; raw trial registry retained durably while mobile shows bounded ranked views. Causal families, descendants, shared fills and similarity graph; failure and rejected candidates stay auditable.
8. PORTFOLIO LAB: Correlation daily/monthly/trade; simultaneous order collisions, session overlap, same-bar and per-day entry limits; independent-vs-alias module attribution and incremental marginal frequency, PF, drawdown and underwater. Default owner research constraints include XAUUSD/NQX, no overnight and max three new positions/day; future tenants require independently frozen execution policies.
9. REPRODUCIBILITY + EXPORT: Frozen typed IR, codegen MQL5 as a derived output, deterministic source/build version, trade-by-trade Python/C++/MT5 independent parity gate, no silent deployment. JSON/CSV research reports exclude non-owned broker tick content.
10. MOBILE OPERATIONS: Android Flutter UX for creating, monitoring, stopping, examining and exporting authorized runs. Push alerts are hints not scientific receipts. Offline draft editing never grants live search; immutable accepted manifests must be reconciled server-side with conflict resolution.

## Architecture / trust boundaries
UI Flutter -> authenticated BFF/API (OIDC, short-lived scoped credentials, TLS) -> tenant/project authorization -> command validation + durable PostgreSQL transaction/outbox -> workflow orchestrator -> independently isolated CPU workers using signed version-pinned C++20 R2/RISE engine -> object-store immutable data and result shards -> independent witness service in separately administered trust domain -> mobile read-only signed evidence views.
Use modular monolith for typed API/domain/control plane at first, not premature microservices; segregate long-running compute workers and witness from day one. Redis may cache derived progress, never authoritative HEAD. PostgreSQL holds durable workflow registry and idempotent CAS commits. Object blobs are content-addressed SHA-256. No infrastructure accounts or subscriptions are enabled by this RFC.

Data plane: owned/licensed data upload or provider-authorized access only -> bytes SHA-256 + license/tenant entitlement -> audit timezone/broker DST, duplicate/order, gaps, Bid/Ask, spread zero/crossed and rolls -> immutable normalized Arrow/Parquet partitions plus preserved raw source -> dataset version and sealed access policy. Columnar Arrow and Parquet support shared contiguous scanning; DuckDB pushdown is suited for selective analytical queries, not a substitute for chronological execution.
Do not centralize customer proprietary broker ticks into a public catalog or redistribute without explicit license. Encrypt per tenant; no customer secrets on device except OS-protected ephemeral credentials.

Control plane: commandId, actorId, tenantId, resourceVersion, frozen configHash and idempotencyKey. CAS update and outbox in one transaction. Worker writes staged shard, flushes/fsyncs, independently rehashes, atomically installs, records receipt, then advances checkpoint. Crash/retry must be idempotent, must not double-count births/trades, and may never turn a deferred/failed job PASS. HEAD anchored outside the mutable worker account; rollback or mismatch blocks access. A mobile-supplied claim of QROS_CORE/approval is always rejected.

Compute plane: CPU exact branch-and-bound structural feasibility and DAG-memoized indicator carriers; pure signal masks vectorized; execution simulator chronological; independent oracle for canaries, sampled batches and every selected finalist; independent second engine backend where possible. Never claim GPU/speedups absent measured benchmark. Per-tenant queue fairness, capped concurrency, memory and CPU budget, immutable result cache scoped by data/license/engine/build/effective conditions, non-duplicate recomputation. Optional dedicated high-compute queue after measured costs.

## Bounded universe v1
The primitive program is a typed AST/IR with separately versioned Context, Setup, Trigger, Entry, InitialRisk, Management, Exit, Session, Data/Execution, PortfolioConstraints. No free-form user Python/SQL/MQL5 execution in shared compute tier. Typed temporal operators encode whether a datum is final/observable at order time; unknown time zone or lookahead candidate is rejected before test. BUY/SELL explicitly separate and symmetric descendants are not presumed independent.
A campaign spec freezes:
- immutable idea/hypothesis and economic narrative plus disconfirming observations;
- asset, direction, timeframe, permitted building blocks, typed domains and dependency constraints;
- DEV/selection/validation/holdout/EXPOSED/forward disjoint interval identities;
- canonical dataset/runner/instrument/commission/spread/slippage identities;
- enumeration mode, random seed where applicable, fixed search budget, multiplicity family, gate thresholds, exhaustion criterion and cost ceiling;
- schema version, deterministic canonicalization and SHA-256 of root campaign.
Raw combinatorial Cartesian count is analytically computed before any PnL. Reject aliases and impossible states before expensive replay; exact/signal-mask deduplication is valid only for the specific frozen dataset and observation universe, and is NOT global causal equivalence. Counter of attempted births, accepted valid programs, exact-equivalent programs, observed signal equivalence classes, executed tests and rejected reasons must never silently decrease. A fixed point is a reproducible closure of the declared finite grammar, not proof that all imaginable profitable strategies were searched.

## Search stages and honest outcomes
STAGE ZERO preregistration: deterministic rule syntax, time observability and cashflow feasibility.
STAGE ONE: canonical grammar generation, constraint propagation, structural hashes and alias dedupe.
STAGE TWO: audit-approved economical preflight of signal feasibility and frequency using training-only observables; do not use PnL-driven post hoc thresholds.
STAGE THREE: shared fixed carriers, cheap DEV-only simulation for eligible unique structures with execution-error canaries; every PnL test increments multiplicity ledger.
STAGE FOUR: exact bid/ask chronological tick execution for all candidates chosen via frozen DEV rules (not by looking at holdout). Trade-by-trade parity and conservative costs.
STAGE FIVE: multilevel Gate A and the strictly authorized clean holdout once, then Supergate tests such as walk-forward, CPCV, MC/bootstrap, cost/slippage/latency shocks, ablations, leave-year-out, perturbation neighborhoods and concentration.
STAGE SIX: export candidate (not an approved strategy) to independent MT5 parity and marginal portfolio evaluation. Individual APPROVED_FINAL does not imply automatically allocate any portfolio capital.
Exhaustive mode: coverage numerator/denominator and integrity manifest required; can declare UNIVERSE_ONTOLOGY_FROZEN and RISE_FIXED_POINT only with documented closure and no valid unexamined births. Sampled/genetic modes: clearly labeled non-exhaustive, report inclusion policy and number of attempted trials, never report exhaustion. Early stopping allowed only via predeclared rules; unknown portion remains unknown.

## Statistical governance
True forward starts only after frozen selection. Log N_TESTS at each generator/optimizer/restart and lineage across related seeds, including discarded candidates. Use BH/BY, DSR, White Reality Check/SPA, CPCV/PBO, permutation or hierarchical family controls as appropriate to the question and dependence structure; no method proves causality automatically. Report uncertainty and limited sample counts. Show stability plateaus, neighborhood and cost stress, risk and calendar concentration, not a universal weighted leaderboard. Keep all failed candidates and tested configurations in an auditably compressed registry separate from the best-N display databank.
No experimental metric, performance throughput, monthly cost or revenue estimate is asserted by this design RFC.

## Mobile UX: five tabs + one research wizard
Tabs: Home (active campaigns, budget, alerts, verified gates); Idea (guided thesis, freeze-ready rule editor and sample timeline); Factory (universe census, DAG preview, budget, progress heartbeat based on independently verified bytes, pause and recovery); Evidence (trade evidence, alias groups, falsification, gate chronology, cost and uncertainties); Portfolio (marginal addition and conflicts). A persistent project drawer gives source datasets, history, access, collaboration and exports.
Wizard: IDEA -> EXPLAIN RULE -> OBSERVABILITY -> CHOOSE DATA -> CAUSAL BLOCKS -> FREEZE SEARCH -> COST/BUDGET PREVIEW -> RUN/PAUSE -> FALSIFY -> AUDIT -> PORTFOLIO. The phone shows a human-readable current pointer, lineage, PENDING/EXPOSED and a signed receipt; it never silently changes research state.
At progressive disclosure level NOVICE a guided, read-only safe default; ADVANCED adds parameter lattices and cross-checks; LAB exposes full typed IR, locked ontology and anti-leak gates; TEAM introduces owner/analyst/reviewer roles with server-side independent approvals. All four levels share exact engine semantics and cannot pay to bypass scientific gates.
A client may submit natural-language drafts and choose enumerator modes but not overwrite frozen manifests. AI cannot sign receipts, access reserved holdout, select unseen profitable runs, alter independent witness, or certify strategies.

## Business and commercial safety
Free tier: synthetic sample, small bounded educational jobs only, no cost guarantee until benchmark; Creator/Pro: higher explicit CPU-hour and storage quotas with on-screen price before each job; Team: collaboration, separate reviewer approval, tenant audit and organizational quota. Meter actual compute/shards/storage and supply immutable per-job invoice determinants. No perpetual unlimited million-config searches at fixed subscription without fair-use, throttling and queue caps.
No business tier or payment service is active. Review data redistribution rights, customer privacy, app-store obligations and risk disclosures before sale. Publish failure reports as first-class user benefits, not only winners.

## Bounded build order / acceptance
G0 DESIGN_FREEZE: approve this new product contract and evidence taxonomy without retroactively editing M0/M1 or scientific main. Owner: product architecture.
G1 IDEA_TO_IR: Android form to typed normalized AST/IR with exact mobile/server parse parity, timing static analysis, typed signals, one synthetic fixture and intentional invalid cases. Zero cloud needed for deterministic contract tests.
G2 UNIVERSE_ENUMERATOR: independent enumerator pair and oracle, exactly versioned count, exact dedupe, serialized checkpoint/shard manifest, deterministic test toy grammar where 100% finite census is feasible. No live PnL.
G3 ENGINE_VERTICAL_SLICE: licensed synthetic bid/ask source, audited timeline, one end-to-end small causal family, trade-by-trade independent parity, realistic costs and false-lookahead canaries.
G4 SCALE_MEASURE: benchmark 10K/100K/1M syntactic births vs unique executable programs on specified hardware; record CPU hours, memory, throughput, data bytes, cache hit and costs. Scale based on measured throughput without compromised fills or semantic drift.
G5 SCIENTIFIC_EVIDENCE: independent external monotonic anchor, authenticated receipts, physical holdout lock and testable one-time approval, adversarial corruption/drift tests.
G6 MOBILE_RELEASE_CANDIDATE: real Android device install, HTTPS tenant auth, background/offline behavior, app crash/upgrade recovery, API IDOR tests, observability, accessibility and privacy.
G7 PILOT + COMMERCIAL: consented testers, licensed external datasets, documented invoices, retention and support; gradual iOS client only after Android feature/receipt parity.

Important sequence: G1 and G2 can progress as TEST_ONLY without waiting for the public M1 HTTPS ingress; G3 external customer data and production mutations remain blocked by G5. Mobile M1 verified baseline stays unchanged; M2 evidence ledger not promoted by this proposal.

## Adversarial META-AUDIT and mitigations
1. Finite raw search may contain infinite effective semantics due to unsized custom grammar: reject unbounded loops, recursion, continuous floats and dynamic code in V1; require rational grids.
2. Deduping by coincident signal masks may hide different behavior in other datasets: scope mask hashes by dataset and session; retain genotype and canonical IR for future independent test.
3. Frozen search may still leak via open-ended AI advice or analyst viewing economic holdout: immutable per-lineage exposure ledger plus explicit exposure taint, locked role separation and reproducible source receipt.
4. Optimizing for max PF across millions produces selection inflation: all trials and multiple testing accounted; selection decisions fixed before gate/holdout.
5. Fast scan cannot emulate limit-order fill precision: cheap scan is structure-only or non-final research diagnostics; final results always pass timestamped Bid/Ask exact simulator.
6. An authenticated mobile token cannot authorize a scientific PASS: independent evidence oracle, server-only transition gate and witness physically separately administered.
7. A static signed demo witness is not dynamic independent external immutability: M1 signed fixture is engineering-only, not production ledger authority.
8. Client-facing unlimited compute can cause denial of service and unpredictable cost: signed per-job budget preview, cap, reserved concurrency, user-facing partial coverage and no negative balance.
9. Microservices and GPU prematurely increase complexity: modular monolith + coarse isolated compute workers and real profiling before optimization.
10. Causal narrative can be persuasive without identification: distinguish motivated hypothesis, historical association, falsification, prospective OOS evidence and genuinely independent forward causal evidence.

## Current evidence and impact
VERIFIED by live GitHub pointer read: Android M1 v3 TEST_ONLY with 23 backend tests, 13 Flutter tests and valid debug APK receipt at exact source commit 4d8d70e5ebb8bfdefaddd2be188b75659ad4c824; independent HTTPS ingress and physical device installation missing. M2 original isolated Linux has prior 17/17 CTest; not a production research service. Main stable pointer V259 unchanged, economic PnL/GA2/holdout closed.
This RFC is DESIGN_ONLY, not a claim of measured speed, implemented Strategy Factory, backtest robustness or qualified research alpha.
