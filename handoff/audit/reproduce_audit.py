#!/usr/bin/env python3
"""Read-only audit of the released QROS v0.6 binary using new synthetic inputs.

No real carrier, live terminal, or economic holdout is accessed. Expected
vulnerable behavior is recorded as FINDING_REPRODUCED, never as engine approval.
The output directory must not already exist.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import time
import zipfile


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fields(magic: str, values: dict) -> str:
    return magic + "\n" + "".join(f"{key}={values[key]}\n" for key in sorted(values))


def parse(text: str) -> dict:
    return dict(line.split("=", 1) for line in text.splitlines()[1:] if "=" in line)


def require(condition: bool, label: str) -> None:
    if not condition:
        raise RuntimeError(label)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    project = args.project.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    binary = project / "bin/qros"
    commands = []
    findings = []
    original = {}
    with zipfile.ZipFile(args.archive) as package:
        require(package.testzip() is None, "release ZIP CRC")
        for item in package.infolist():
            require(not item.is_dir(), "expected only payload entries")
            relative = Path(item.filename).relative_to("QROS_ENGINE_v0_6")
            require(".." not in relative.parts, "package traversal")
            original[str(relative)] = digest(package.read(item))
            require(digest((project / relative).read_bytes()) == original[str(relative)],
                    f"workspace differs from release: {relative}")

    def put(name: str, text: str) -> Path:
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        require(not path.exists(), f"immutable audit fixture exists: {name}")
        path.write_text(text, encoding="utf-8")
        return path

    def sha(path: Path) -> str:
        return digest(path.read_bytes())

    def command(label: str, argv: list, expected: int = 0, executable: Path = binary) -> str:
        # PATH intentionally empty: a directly invoked native executable must not
        # find Python or shell helpers. The audit driver itself uses Python.
        env = {"PATH": "", "LANG": "C", "LC_ALL": "C", "TZ": "UTC", "TMPDIR": str(out)}
        started = time.monotonic()
        result = subprocess.run([str(executable), *map(str, argv)], cwd=out, env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=35)
        log = put(f"logs/{label}.log", result.stdout)
        commands.append({"label": label, "argv": [str(executable), *map(str, argv)],
                         "returncode": result.returncode, "expected_returncode": expected,
                         "elapsed_seconds": time.monotonic() - started,
                         "log": str(log.relative_to(out)), "log_sha256": sha(log),
                         "PATH": "", "synthetic_only": True})
        require(result.returncode == expected, f"unexpected returncode {label}: {result.stdout}")
        return result.stdout

    def make_data(name: str, prices: list[tuple[int, int]], exposure="SYNTHETIC", quantum=10):
        day = 20240104
        base = 1704326400000000000
        tick_text = "seq,ts_ns,session_day,bid_u,ask_u\n" + "".join(
            f"{index},{base + index * 1000000},{day},{bid},{ask}\n"
            for index, (bid, ask) in enumerate(prices, 1))
        ticks = put(f"{name}/ticks.csv", tick_text)
        session = put(f"{name}/sessions.csv",
            "session_day,open_seq,close_seq,open_ts_ns,close_ts_ns,utc_offset_seconds\n"
            f"{day},1,{len(prices)},{base + 1000000},{base + len(prices) * 1000000},0\n")
        spec = {"authority_id": "AUDIT_SYNTHETIC_BYTES", "symbol": "NQX",
                "purpose": "TEST_ONLY" if exposure == "SYNTHETIC" else "RESEARCH",
                "format": "CSV5", "source_clock": "SYNTHETIC", "exposure": exposure,
                "broker_origin": "SYNTHETIC", "ticks_path": ticks.name,
                "ticks_sha256": sha(ticks), "sessions_path": session.name,
                "sessions_sha256": sha(session), "rows": len(prices), "first_seq": 1,
                "first_day": day, "last_day": day, "tick_size_u": quantum,
                "point_size_u": 10, "price_decimals": 1,
                "parent_carrier_sha256": sha(ticks), "session_fragment_sha256": sha(session)}
        spec["shard_contract_root"] = digest(fields("QROS_SHARD_CONTRACT_V3", spec).encode())
        dataset = put(f"{name}/dataset.qdata", fields("QROS_DATASET_V3", spec))
        policy = {"dataset_spec_sha256": sha(dataset), "data_sha256": sha(ticks),
                  "development_first_day": 20200101, "development_last_day": 20251231,
                  "holdout_first_day": 20260101, "holdout_last_day": 20261231,
                  "exposure": exposure, "authorization_id": "SYNTHETIC_AUDIT_ONLY"}
        vault = put(f"{name}/vault.policy", fields("QROS_VAULT_POLICY_V1", policy))
        return dataset, vault, spec

    def program(name: str, **changes) -> Path:
        spec = {"name": "SYNTHETIC_AUDIT", "symbol": "NQX", "purpose": "TEST_ONLY",
                "seed_sha256": digest(b"synthetic audit fixture, not a real strategy"),
                "side": "BUY", "signal": "sig", "signal_mode": "RISING",
                "stop_u": 20, "target_u": 20, "be_trigger_ppm": 0, "be_offset_u": 0,
                "trailing_u": 0, "daily_limit": 3, "commission_u": 0, "slippage_u": 0,
                "bar_ms": 1, "expiry_records": 10, "node.bid": "BID",
                "node.zero": "CONST:0", "node.sig": "GT:bid:zero"}
        spec.update(changes)
        return put(name, fields("QROS_PROGRAM_V1", spec))

    command("core_baseline", [], executable=project / "bin/qros_tests")
    command("pipeline_baseline", [], executable=project / "bin/qros_pipeline_tests")
    command("native_without_python_path", ["capabilities"])

    data, vault, data_fields = make_data("grid", [(100,110),(100,110),(120,130),(140,150)])
    config = program("grid/program.qros", slippage_u=1)
    grid_run = out / "grid/run"
    command("off_grid_fill", ["backtest", config, sha(config), data, sha(data), vault, sha(vault), grid_run])
    trades = list(csv.DictReader(io.StringIO((grid_run / "final/trades.csv").read_text())))
    require(len(trades) == 1, "one grid demonstration trade")
    off_grid = {name: int(trades[0][name]) for name in ["entry_price_u", "exit_price_u"]}
    require(any(value % 10 for value in off_grid.values()), "off-grid fill finding no longer reproduces")
    findings.append({"id": "A01", "status": "FINDING_REPRODUCED", "title": "Fill quantum not enforced",
                     "input_tick_size_u": 10, "slippage_u": 1, "observed_fills": off_grid,
                     "engine_result": "TEST_STAGE_COMPLETE", "fixture": "grid"})

    sealed, sealed_vault, sealed_fields = make_data("sealed", [(100,110),(100,110),(120,130),(140,150)], "HOLDOUT_SEALED")
    candidate = trades[0]["candidate_id"]
    denied = command("sealed_development_denied", ["vault-check", sealed, sha(sealed), sealed_vault,
                      sha(sealed_vault), candidate], expected=1)
    require("HOLDOUT_ACCESS_DENIED" in denied, "sealed development denial control")
    audit_text = command("sealed_audit_reads_bytes", ["data-check", sealed, sha(sealed), out / "sealed/audit.receipt"])
    require("integrity=PASS" in audit_text, "structural read did not complete")
    findings.append({"id": "A02", "status": "FINDING_REPRODUCED", "title": "Audit command outside vault authorization",
                     "vault_check": "HOLDOUT_ACCESS_DENIED", "data_check": "integrity=PASS",
                     "scope": "aggregate structural observation of SYNTHETIC bytes labelled sealed; no economic opening"})

    grant = put("sealed/grant", fields("QROS_HOLDOUT_GRANT_V1", {
        "policy_sha256": sha(sealed_vault), "data_sha256": sealed_fields["ticks_sha256"],
        "candidate_sha256": candidate, "authorization_id": "SYNTHETIC_AUDIT_ONLY",
        "action": "FIXED_CANDIDATE_HOLDOUT", "expires_unix_seconds": int(time.time()) + 86400}))
    common = ["vault-consume", sealed_vault, sha(sealed_vault), grant, sha(grant)]
    command("grant_first_store", [*common, out / "sealed/store_a"])
    same_store = command("grant_repeat_same_store", [*common, out / "sealed/store_a"], expected=1)
    require("HOLDOUT_CAPABILITY_ALREADY_CONSUMED" in same_store, "same-store denial")
    new_store = command("grant_repeat_different_store", [*common, out / "sealed/store_b"])
    require("status=CAPABILITY_CONSUMED" in new_store, "grant replay finding no longer reproduces")
    findings.append({"id": "A03", "status": "FINDING_REPRODUCED", "title": "Grant single-use local to chosen result directory",
                     "same_store_second_use": "DENIED", "different_store_same_grant": "CAPABILITY_CONSUMED",
                     "economic_data_opened": False})

    alias_program = program("alias/program.qros", **{"axis.duplicate": "1,1", "stop_u": "$duplicate"})
    alias_run = out / "alias/run"
    alias_common = ["mine", alias_program, sha(alias_program), data, sha(data), vault, sha(vault), alias_run, 1, 1]
    command("alias_first_cohort", [*alias_common, 4])
    reread = command("alias_second_cohort_low_row_budget", [*alias_common, 1], expected=1)
    require("graphs=0" in reread and "RESOURCE_ROW_BUDGET_EXCEEDED" in reread, "alias read finding no longer reproduces")
    command("alias_second_cohort_normal_budget", [*alias_common, 4])
    findings.append({"id": "A04", "status": "FINDING_REPRODUCED", "title": "Alias-only cohort still traverses data path",
                     "active_graphs": 0, "reduced_row_budget": "RESOURCE_ROW_BUDGET_EXCEEDED",
                     "scope": "resource behavior, not scientific-invalidity finding"})

    compiled_ir = out / "grid/candidate.ir"
    command("compile_identity_ir", ["compile", config, sha(config), 0, compiled_ir])
    ir = parse(compiled_ir.read_text())
    require("graph_sha256" in ir and not any(key.startswith("node.") for key in ir), "IR representation changed")
    findings.append({"id": "A05", "status": "GAP_CONFIRMED", "title": "Exported IR contains graph digest, not executable graph",
                     "graph_sha256": ir["graph_sha256"], "graph_nodes_serialized": False,
                     "scope": "not a corruption; self-contained IR runtime remains unimplemented"})

    # The next two fixtures deliberately contain invalid 'external' evidence.
    # They are generated solely to test validation, clearly marked as fake.
    external_dir = out / "claimed_external"
    expected = put("claimed_external/expected.csv", (grid_run / "final/trades.csv").read_text())
    observed = put("claimed_external/observed.csv", expected.read_text())
    provenance = {"purpose": "EXTERNAL_MT5", "candidate_id": candidate, "frozen_spec_sha256": sha(config),
                  "terminal_build": 1, "tester_agent_build": 1, "broker_server": "SYNTHETIC_AUDIT_NOT_A_BROKER",
                  "mode": "EVERY_TICK_BASED_ON_REAL_TICKS"}
    for role in ["mq5", "ex5", "set", "symbol_spec", "observed_ticks", "raw_deals"]:
        path = put(f"claimed_external/{role}.txt", f"SYNTHETIC_AUDIT_PLACEHOLDER_NOT_VALID_{role.upper()}\n")
        provenance[role + "_path"] = path.name
        provenance[role + "_sha256"] = sha(path)
    provenance["expected_ticks_sha256"] = provenance["observed_ticks_sha256"]
    provenance_path = put("claimed_external/provenance", fields("QROS_MT5_PROVENANCE_V1", provenance))
    plan = put("claimed_external/plan", fields("QROS_MT5_PARITY_PLAN_V1", {
        "candidate_id": candidate, "frozen_spec_sha256": sha(config), "expected_path": expected.name,
        "expected_sha256": sha(expected), "observed_path": observed.name, "observed_sha256": sha(observed),
        "provenance_path": provenance_path.name, "provenance_sha256": sha(provenance_path)}))
    parity = command("fake_external_artifacts", ["mt5-parity", plan, sha(plan), external_dir / "result.receipt"])
    require("status=EXTERNAL_RECORDED_PARITY_PASS" in parity and "research_approved=0" in parity,
            "external evidence finding no longer reproduces")
    findings.append({"id": "A06", "status": "FINDING_REPRODUCED", "title": "External-recorded parity accepts hash-consistent placeholders",
                     "observed_status": "EXTERNAL_RECORDED_PARITY_PASS", "research_approved": False,
                     "mt5_actually_executed": False, "scope": "missing semantic provenance verifier; no scientific promotion"})

    fake = put("supergate/placeholder.receipt", "SYNTHETIC_INVALID_RECEIPT\n" +
               f"candidate_id={candidate}\nfrozen_spec_sha256={sha(config)}\nstatus=FAIL\n")
    super_fields = {"candidate_id": candidate, "frozen_spec_sha256": sha(config)}
    for role in ["gate", "oos", "robustness", "holdout", "forward", "mt5"]:
        super_fields[role + "_path"] = fake.name
        super_fields[role + "_sha256"] = sha(fake)
    super_plan = put("supergate/plan", fields("QROS_SUPERGATE_PLAN_V1", super_fields))
    summary = command("invalid_supergate_evidence", ["supergate", super_plan, sha(super_plan), out / "supergate/result.receipt"])
    require("status=READY_FOR_SCIENTIFIC_REVIEW_NOT_AUTOMATIC_APPROVAL" in summary and "research_approved=0" in summary,
            "Supergate evidence finding no longer reproduces")
    findings.append({"id": "A07", "status": "FINDING_REPRODUCED", "title": "Supergate aggregates invalid and failed receipts without semantic validation",
                     "provided_status": "FAIL", "observed_status": "READY_FOR_SCIENTIFIC_REVIEW_NOT_AUTOMATIC_APPROVAL",
                     "research_approved": False, "scope": "integrity aggregator, not an implemented scientific gate"})

    gate_program = put("gate_bridge/program.qros", config.read_text())
    gate_completion = put("gate_bridge/completion.receipt", (grid_run / "final/COMPLETED.receipt").read_text())
    gate_ledger = put("gate_bridge/trades.csv", (grid_run / "final/trades.csv").read_text())
    gate_policy = put("gate_bridge/gates.policy", fields("QROS_GATE_POLICY_V1", {
        "program_path": gate_program.name, "program_sha256": sha(gate_program),
        "completion_path": gate_completion.name, "completion_sha256": sha(gate_completion),
        "min_trades": 1, "min_pf_ppm": 0, "max_dd_u": 1000000, "max_negative_years": 10,
        "min_positive_years": 0, "alpha_ppm": 999999, "n_tests": 1, "correction": "BH",
        "repetitions": 99, "rng_seed": 12345, "method": "YEAR_BLOCK_SIGN_FLIP_V1"}))
    actual_gate = out / "gate_bridge/actual_gate.receipt"
    command("generate_actual_gate", ["gates", gate_ledger, sha(gate_ledger), gate_policy, sha(gate_policy), actual_gate])
    actual_super_fields = {"candidate_id": candidate, "frozen_spec_sha256": sha(config),
                          "gate_path": actual_gate.name, "gate_sha256": sha(actual_gate)}
    for role in ["oos", "robustness", "holdout", "forward", "mt5"]:
        actual_super_fields[role + "_path"] = "UNAVAILABLE"
        actual_super_fields[role + "_sha256"] = "0" * 64
    actual_super = put("gate_bridge/supergate.plan", fields("QROS_SUPERGATE_PLAN_V1", actual_super_fields))
    mismatch = command("actual_gate_to_supergate", ["supergate", actual_super, sha(actual_super),
                       out / "gate_bridge/supergate.receipt"], expected=1)
    require("SUPERGATE_EVIDENCE_SCOPE:gate" in mismatch, "gate to Supergate contract mismatch no longer reproduces")
    findings.append({"id": "A08", "status": "GAP_CONFIRMED", "title": "Native gates output is not directly accepted by native Supergate",
                     "gate_generation": "SUCCESS", "supergate_error": "SUPERGATE_EVIDENCE_SCOPE:gate",
                     "scope": "missing per-candidate receipt transformation/schema integration"})

    unchanged = all(digest((project / name).read_bytes()) == hash_value for name, hash_value in original.items())
    require(unchanged, "released source or artifact changed during audit")
    report = {"schema": "QROS_ORIGINAL_DESIGN_AUDIT_PROOFS_V1", "intent": "AUDIT_INTENT",
              "source_scope": "Released v0.6, direct original-chat excerpts, synthetic adversarial probes",
              "project": str(project), "archive_sha256": sha(args.archive), "binary_sha256": sha(binary),
              "release_files_verified": len(original), "release_unchanged_after_audit": unchanged,
              "driver_sha256": digest(Path(__file__).read_bytes()), "commands": commands,
              "findings": findings, "real_carriers_accessed": False, "economic_holdout_opened": False,
              "mt5_executed": False, "implementation_changed": False,
              "interpretation": "Reproduced findings are not approvals. Fixtures are synthetic, even when labels intentionally claim otherwise."}
    put("AUDIT_PROOFS.json", json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"release_files_verified": len(original), "commands": len(commands),
                      "findings": [{"id": f["id"], "status": f["status"]} for f in findings],
                      "report": str(out / "AUDIT_PROOFS.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
