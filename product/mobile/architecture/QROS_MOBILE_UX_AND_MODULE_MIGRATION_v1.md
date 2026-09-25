# QROS Mobile — Experiencia profesional y migración modular v1
Status: DESIGN_ONLY / 2026-09-25
Input HEAD: MOBILE_PRODUCT_HEAD v3, Git blob e883f7dcc877ebbba5be79513e03893920dfa05a.
No desktop application, live trading, user PnL or customer-paid infrastructure is authorized by this document.

## Navigation in a phone
Primary tabs: Inicio, Hipótesis, Fábrica, Evidencias, Portafolio. Persistent project switcher at top, global project/tenant identity and current scientific state visible. Bell alerts are notifications, never source of scientific truth. A bottom sheet shows latest independently signed HEAD, campaign ID, data coverage, known blocker and exact next admissible action. Offline status always visible.

### Inicio
Mobile dashboard for owned projects, new hypotheses, currently running/blocked/closed campaigns, synthetic jobs, compute quota and dated verified outcomes. Show "no certified strategies" when none exists. Budget/cost estimated versus measured clearly distinguished. One-touch resume jumps into last verifiable checkpoint, not rerun.

### Hipótesis
1. Natural-language idea as untrusted draft; parse into observable events and candidate typed blocks; show model confidence is linguistic only, not predictive market accuracy.
2. Interactive bar/tick timeline with the first instant each input becomes observable; prohibit undefined bar zero, repainting or changing timezone silently.
3. Causal premise, opposing mechanism and disconfirming results side by side; user approves exact interpretation of ambiguous wording before freeze.
4. Drag-and-drop typed cards CONTEXT → SETUP → TRIGGER → ENTRY → RISK → MANAGEMENT → EXIT → SESSION, each with allowed BUY/SELL and timeframe. Typed blocks can compose groups or visually tagged reusable custom blocks with semantic versions.
5. Program IR and readable rules can be inspected; the phone does not accept arbitrary source-code execution.

### Arquitecto del universo
This screen is the primary differentiator:
- Frozen grammar builder; each axis has explicit list/grid and dependently feasible values; impossible combinations greyed out ex ante, not after PnL.
- "Coverage waterfall": symbolic RAW → typable/valid → exact canonical unique → observed signal-mask equivalence classes in a particular dataset → actually backtested → Gate A eligible. Unknown counts remain "uncomputed", never 0.
- Search type selector EXHAUSTIVE / STRATIFIED_RANDOM / GENETIC; only exhaustive can display 100% of a bounded, completed grammar.
- Parameter landscape planner: show adjacency and interpretable parameter blocks, not merely best individual PF.
- A cost budget and scheduler forecast display calibrated uncertainty from measured local workload benchmarks; do not present an unmeasured prediction as verified.
- Multiplicity meter shows number of all attempted births, economic trials and related genealogies, so million-run freedom cannot silently erase selection bias.
- Prescribed "freeze now" action creates a signed request; only the trusted backend can finalize a scientific contract following independently authenticated evidence.

### Fábrica
A durable task DAG: audit → ontology → enumerator parity → DEV → Gate A → authorized holdout → Supergate → MT5 → portfolio. Progress is measured by *verified written bytes/shard receipts*, not an endlessly moving animation. Show total coverage exact/partial, valid results, cached/duplicate counts, worker CPU, retry, corruption, next eligible action, cost ledger and pause budget. Partial failure preserves verified shards; phone process suspension never restarts finished work.

### Evidencias
Three visually distinct sections:
- Registry (all attempts, discarded programs and provenance) in compressed backend storage; phone shows paginated/virtualized groups, never loads millions of rows.
- Candidates (pre-registered gate survivors); show R-based expectancy, trade count, regimes, cost sensitivity, independent parity diff, smoothness and confidence interval with period label prominently attached.
- Rejections and unresolved: first-class searchable records containing failure reason, leak and impact, so users cannot mistake absent winners for unattempted research.
"EXPOSED" is irreversible for a related genealogy. There is no button to reset economic exposure.

### Portafolio
Causal-family graph and heatmap of daily/monthly/per-trade dependence; order-time interference under per-day limit, one-position-per-asset and zero overnight risk in the owner's preset. Monthly frequency, PF/DD and underwater *marginal* contributions require exact portfolio replay. "APPROVED_FINAL" individual cards never imply user should allocate investment capital; client chooses actual risk policy only after its own independent validation.

### Compartir / exportar
Download redacted research manifest, rules, candidate code and independent trade-by-trade reconciliation *only when source and rights allow*. Exported .MQ5 is marked derived and cannot be promoted without original frozen IR and executable MT5 parity. Do not export, copy or sublicense broker tick carriers.

## Interaction conventions
- Professional dark/light themes, typography tabular for quantitative values and explicit token colors for data confidence/status.
- All legal actions visible; disabled scientific actions display the exact failed gate and a link to supporting receipt instead of silently disappearing.
- Filter controls visibly grouped: PRE-RUN STRUCTURAL, DEV-ONLY PRE-REGISTERED, POST-SELECTION VALIDATION, HOLDOUT AUTHORIZED, DIAGNOSTIC EXPOSED. A filter is never silently moved between groups.
- One-hand friendly controls, landscape optional for long charts, zoomed mobile block-editor canvas, performant virtualized result tables and accessibility labels.
- Remote drafts are not automatically frozen. Offline drafts stay local, encrypted when implemented; reconciliation uses versions and conflict resolution. M0 drafts were volatile and do not imply encrypted persistence.
- Collaborator review roles: owner, analyst, read-only auditor and independent approver. Enforcement lives in tenant-scoped backend rather than Flutter.

## Reuse verified engineering rather than rebuilding it
Actual source files read from GitHub at the exact parent M1 commit:
- include/qros/research_contract.hpp Git blob 22a3c994bd291516f64dab636eb26594936f8e14: DataAuditJob, StrategyContract and ResearchJob already encode contract/data/program and execution/cost SHA pins, search_space_sha256, multiplicity_n_tests and holdout partition IDs. **Adapt and version this**, not replace with a disconnected untyped mobile schema.
- include/qros/research_state.hpp Git blob db3e28cd2a0c2d91b991add1b9ada11d07f18b29: scientific state policy exists, but TransitionContext contains bool flags and TransitionActor is publicly constructible. This is a *production authority boundary gap* until validated server-side receipt-to-context binding is implemented. An authenticated user token is never equivalent to QrosCore authority.
- include/qros/research_ledger.hpp Git blob fe22314e0c32b73d7145693f96631b8014fcae4f: TEST_ONLY hash-chained ledger explicitly requires a trusted external head to detect tail deletion; actual external dynamic witness is not operational.
- product/mobile/flutter_app/lib/core/verified_demo.dart Git blob 1e9f2c7e0cacf20ea912db0ce3e345fa04b921d0: Android M1 includes the frozen synthetic fixture and client verifier. It is an integration seam, not actual broker or canonical M2 research authentication.
Repository source search has not established independent feature_graph.hpp or universe.hpp headers; do not invent completed modules. Reuse the actual existing pipeline, audit and execution implementations after a source-line and contract audit in the implementation ticket.

## Concrete API boundaries for future implementation, not current routes
POST /v1/ideas = draft only.
POST /v1/universes/inspect = pure structural finite count estimate, budget and typability audit; never economic test.
POST /v1/campaigns/preregister = server request subject to human-signed contract freeze and valid data authority.
POST /v1/jobs = idempotent job creation only from permitted phase, with budget and immutable input pins; never public unfenced PnL.
GET /v1/jobs/{id}/progress = verified milestone and content-addressed receipt ID, with tenant-level authorization.
GET /v1/evidence/{id} = authorized read-only certified record with signed external head and taint/exposure state.
POST /v1/campaigns/{id}/scientific-transition = NOT EXPOSED TO PUBLIC API; use internal server-only independently authenticated transition orchestrator.
Production token scopes restricted per project, HTTP 403 versus 401 explicit, resourceVersion CAS and per-route quota. Read-only demo from Android M1 is the only presently validated network client, and even that lacks deployed HTTPS ingress and physical-device testing.

## Three demonstration modes, not artificial profitable strategies
SHOWCASE (no credentials): a fully synthetic sample to teach workflow and error conditions.
RESEARCH TEST_ONLY (authenticated opted-in): bounded synthetic generation and future independently tested engine integration; no real account or holdout.
LIVE RESEARCH (not implemented): licensed client datasets, independent immutable dynamic witness, fixed authoritative backend contracts, robust billing and complete security acceptance; never confuse with live trading.

## Delivery roadmap and performance acceptance
Stage UX1: typed mock + UX usability on Android device, display full workflow with one synthetic bounded grammar.
Stage CORE1: deterministic independent Python vs C++ enumeration census on 2–4 toy ontologies; reject invalid/ambiguous temporal blocks, preserve hash receipts and re-run parity.
Stage CORE2: million-birth stress test on specified backend hardware with exact memory/runtime/cost and no backtest PnL. At scale, reporting a million syntactic births is NOT reporting a million unique viable strategies or a million tick-accurate tests.
Stage CORE3: exact chronological simulator parity for one small approved synthetic trade example; all costs and broker timezone documented.
Stage SAFETY1: authenticated receipts, independently administered immutable external witness, tenant isolation, audit logs, fail-closed rollback and rights protections.
Stage PRODUCTION1: Android physical install and TLS+security integration tests, pilot consent, privacy/legal review and measured per-job cloud expense.
No reliability/throughput claims prior to test receipts. Successful prototype tests are engineering milestones only.

## Honest visual states
CAMPAIGN_ACTIVE / PREREGISTERED_NO_RESULTS / DEVELOPMENT_RUNNING / FROZEN_CANDIDATE / APPROVED_RESEARCH / MT5_EXTERNAL_PENDING / APPROVED_FINAL / REJECTED / OBSERVATIONAL_RESERVE / BRANCH_EXHAUSTED / BLOCKED_BY_INFRASTRUCTURE are displayed only when signed by authoritative canonical QROS records, never inferred from chart color or text the user types.
