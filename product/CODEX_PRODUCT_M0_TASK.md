# QROS Research Studio — Codex task M0

## Objective

Verify and harden only the first productization slice already present on branch
`product/qros-research-studio-mvp-v1` without reopening scientific research or rebuilding QROS.
This task is deliberately narrow to minimize Codex credit consumption.

## Authority

- Repository: `miguelcastill85-del/qros-engine`
- Branch: `product/qros-research-studio-mvp-v1`
- Scientific `control/HEAD.json` is read-only for this task.
- Do not open holdout, run real strategy mining, access broker carriers, use MT5, or activate paid services.
- Read `AGENTS.md`, `handoff/RUNTIME_SCOPE.md`, `handoff/ENGINEERING_BACKLOG.md`,
  `product/QROS_RESEARCH_STUDIO_MVP_CONTRACT_v1.md`,
  `product/contracts/QROS_AI_AUTHORITY_FIREWALL_v1.json`, and `product/PRODUCT_HEAD.json`.

## Scope to verify

New/modified product files:

- `include/qros/research_contract.hpp`
- `src/research_contract.cpp`
- `src/product_main.cpp`
- `tests/test_product_contract.cpp`
- `CMakeLists.txt`

The implementation must preserve these properties:

1. AI/natural language has zero authority to grant scientific states.
2. `DataAuditJob` is separate from strategy-bound `ResearchJob`.
3. Strategy contracts are hash-bound, frozen, genealogy-bound, data-authority-bound and carry N_TESTS.
4. Research jobs bind exact Strategy Contract, DataSpec, Program, execution policy and cost policy.
5. Symbol, purpose and data authority must agree across bound objects.
6. `multiplicity_n_tests` cannot undercount `Program.births`.
7. Advanced phases (`HOLDOUT`, `SUPERGATE`, `MT5_PARITY`, `PORTFOLIO`) cannot use `authority_ref=NONE`.
8. Policy file names are resolved only through the safe relative-path guard and their bytes must match their declared SHA-256.
9. Product validation receipts explicitly state `scientific_gate_pass=0` and `scientific_state_mutation=0`.
10. `qros_product` is part of deterministic source identity.

## Execution order

1. Confirm clean checkout and exact branch.
2. Run `python3 handoff/verify_import.py` before edits. If this fails because the product branch legitimately changes files tracked by an old import manifest, classify the cause precisely; do not rewrite historical evidence to make it pass.
3. Configure/build a fresh C++20 tree using the repository-supported build path. Do not reuse a stale build directory.
4. Compile `qros`, `qros_product`, `qros_tests`, `qros_pipeline_tests`, and `qros_product_contract_tests` with existing warnings-as-errors.
5. Run `qros_product_contract_tests` and `qros_product capabilities` first.
6. Run existing non-economic regression suites/CTest that can execute with TEST_ONLY fixtures and no external data.
7. If a new product file causes a compile/test failure, reproduce it, make the smallest product-scope correction, add/adjust a regression, and rerun the affected tests.
8. Do not fix unrelated historical P0/P1 findings in this task. Record them separately as inherited blockers.
9. Do not edit `control/HEAD.json` or scientific campaign artifacts.

## Adversarial checks required

Add or retain tests proving rejection of at least:

- unfrozen strategy contract;
- `N_TESTS=0`;
- N_TESTS lower than Program births;
- development/holdout partition collision;
- program hash mismatch;
- data authority mismatch;
- execution-policy hash mismatch;
- cost-policy hash mismatch;
- data audit disguised as a ResearchJob;
- advanced phase without authority;
- zero/unbounded resource limit;
- policy path traversal or missing policy file;
- policy bytes whose hash differs from declared hash.

Do not fabricate PASS receipts. A parser/unit-test PASS is not a scientific gate PASS.

## Deliverable

Create `product/evidence/M0_BUILD_TEST_RECEIPT.json` containing only observed facts:

- tested commit SHA;
- compiler/toolchain and OS;
- build commands;
- build result;
- test names and exit status;
- `qros_product capabilities` output hash;
- source-root and build-contract identities emitted by the binary;
- any failures and whether they are introduced by this slice or inherited;
- `scientific_state_mutated=false`;
- `holdout_accessed=false`;
- `broker_data_accessed=false`;
- `paid_services_used=false`.

Do not mark M0 accepted unless build/link and required product tests genuinely pass.
