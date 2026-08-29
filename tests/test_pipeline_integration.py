#!/usr/bin/env python3
"""End-to-end tests. Every generated tick and broker artifact is SYNTHETIC.

The Python oracle consumes declared programs and generated input ticks, never
native IR/feature/ledger output. Test reports are evidence of software behavior,
not investment results, real broker parity, or a scientific campaign.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import random
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))
import pipeline_reference as oracle


def digest(data):
    if isinstance(data, Path):
        data = data.read_bytes()
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def fields(magic, values):
    return magic + "\n" + "".join(f"{key}={values[key]}\n" for key in sorted(values))


def kv(path):
    return dict(line.split("=", 1) for line in Path(path).read_text().splitlines()[1:] if "=" in line)


def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode() if isinstance(text, str) else text)
    return path


def write_csv(path, rows, names=None):
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=names or list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return put(path, text.getvalue())


def fixture(days=(20210104, 20220104, 20230104, 20240104), count=600):
    rng = random.Random(643901)
    ticks, sessions = [], []
    for day in days:
        base = int(datetime.strptime(str(day), "%Y%m%d").replace(hour=9, tzinfo=timezone.utc).timestamp()) * 10**9
        first = len(ticks) + 1
        for i in range(count):
            offset = i - (1 if i % 79 == 0 and i else 0)
            wave = i % 80
            bid = 100000 + (wave if wave < 40 else 80-wave) * 2 + rng.randrange(-2, 3)
            spread = 0 if i % 137 == 0 else 2 + (i % 11 == 0)
            ticks.append(dict(seq=len(ticks)+1, ts_ns=base+offset*200_000_000,
                              session_day=day, bid_u=bid, ask_u=bid+spread))
        sessions.append(dict(session_day=day, open_seq=first, close_seq=len(ticks),
                             open_ts_ns=ticks[first-1]["ts_ns"], close_ts_ns=ticks[-1]["ts_ns"], utc_offset_seconds=0))
    return ticks, sessions


def dataset(folder, ticks, sessions, fmt="CSV5", symbol="NQX", overrides=None, parent=None):
    folder.mkdir(parents=True, exist_ok=True)
    if fmt == "CSV5":
        tick_path = write_csv(folder / "ticks.csv", ticks)
    else:
        tick_path = put(folder / "ticks.p17", b"".join(struct.pack("<qiiB", t["ts_ns"]//10**6, t["bid_u"], t["ask_u"], 6) for t in ticks))
    session_path = write_csv(folder / "sessions.csv", sessions)
    values = dict(authority_id="EXPLICIT_SYNTHETIC_FIXTURE", symbol=symbol, purpose="TEST_ONLY", format=fmt,
                  source_clock="SYNTHETIC", exposure="SYNTHETIC", broker_origin="SYNTHETIC",
                  ticks_path=tick_path.name, ticks_sha256=digest(tick_path), sessions_path=session_path.name,
                  sessions_sha256=digest(session_path), rows=len(ticks), first_seq=ticks[0]["seq"],
                  first_day=sessions[0]["session_day"], last_day=sessions[-1]["session_day"],
                  tick_size_u=1, point_size_u=10 if symbol == "NQX" else 100,
                  price_decimals=1 if symbol == "NQX" else 2,
                  parent_carrier_sha256=parent or digest("synthetic input generator seed 643901"),
                  session_fragment_sha256=digest(session_path))
    if overrides:
        values.update(overrides)
    values["shard_contract_root"] = digest(fields("QROS_SHARD_CONTRACT_V3", values))
    spec = put(folder / "dataset.qdata", fields("QROS_DATASET_V3", values))
    policy = dict(dataset_spec_sha256=digest(spec), data_sha256=values["ticks_sha256"],
                  development_first_day=20200101, development_last_day=20251231,
                  holdout_first_day=20260101, holdout_last_day=20261231,
                  exposure=values["exposure"], authorization_id="SOFTWARE_TEST_ONLY")
    vault = put(folder / "vault.policy", fields("QROS_VAULT_POLICY_V1", policy))
    return spec, vault


def base_program():
    return dict(name="SYNTHETIC_EMA_CROSS", symbol="NQX", purpose="TEST_ONLY", seed_sha256=digest("declared synthetic test seed"),
                side="$side", signal="sig", signal_mode="RISING", stop_u="$stop", target_u="18",
                be_trigger_ppm="$be", be_offset_u="1", trailing_u="$trail", daily_limit="3",
                commission_u="1", slippage_u="1", bar_ms="1000", expiry_records="7", **{
                    "axis.fast":"2,2,4", "axis.slow":"3,5", "axis.side":"-1,1", "axis.stop":"8,12",
                    "axis.be":"0,500000", "axis.trail":"0,6", "require.order":"LT:$fast:$slow",
                    "node.close":"CLOSE:1000", "node.fast":"EMA:close:$fast", "node.slow":"EMA:close:$slow",
                    "node.up":"CROSS_UP:fast:slow", "node.down":"CROSS_DOWN:fast:slow", "node.sig":"OR:up:down"})


def single_program():
    return dict(name="SYNTHETIC_ALWAYS_TRUE", symbol="NQX", purpose="TEST_ONLY", seed_sha256=digest("single fixture"),
                side="BUY", signal="sig", signal_mode="EACH_UPDATE", stop_u="10", target_u="18",
                be_trigger_ppm="0", be_offset_u="0", trailing_u="0", daily_limit="3",
                commission_u="1", slippage_u="0", bar_ms="1000", expiry_records="7", **{
                    "node.bid":"BID", "node.zero":"CONST:0", "node.sig":"GT:bid:zero"})


class Suite:
    def __init__(self, binary, folder, leak_check="enabled"):
        self.binary, self.root = binary.resolve(), folder.resolve()
        if self.root.exists() and any(self.root.iterdir()):
            raise RuntimeError("test output must be new or empty; refusing to overwrite")
        self.root.mkdir(parents=True, exist_ok=True)
        self.leak_check = leak_check
        self.env = dict(PATH="/usr/bin:/bin", LANG="C", LC_ALL="C", TZ="UTC",
                        ASAN_OPTIONS=f"detect_leaks={1 if leak_check=='enabled' else 0}:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
        self.checks, self.commands, self.labels = 0, [], []
        self.started = time.monotonic()

    def check(self, condition, label):
        if not condition:
            raise AssertionError(label)
        self.checks += 1
        self.labels.append(label)

    def command(self, *args, error=None, status=None, timeout=90):
        argv = [str(self.binary), *map(str, args)]
        p = subprocess.Popen(argv, cwd=self.root, env=self.env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            raw = p.communicate(timeout=timeout)[0]
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.communicate()
            raise AssertionError("native test timeout; group killed") from None
        text = raw.decode(errors="replace")
        self.commands.append(dict(args=list(map(str, args)), status=p.returncode, output_sha256=digest(raw)))
        if error:
            self.check(p.returncode > 0 and error in text, f"reject {error}: {text[-300:]}")
        elif status is not None:
            self.check(p.returncode == status, f"exit {status}: {text[-300:]}")
        elif p.returncode != 0:
            raise AssertionError(f"command failed {args}: {text[-3000:]}")
        return text

    def mine(self, program, data, vault, output, chunk=13, max_chunks=100, rows=10000000, **kwargs):
        return self.command("mine", program, digest(program), data, digest(data), vault, digest(vault), output,
                            chunk, max_chunks, rows, **kwargs)

    def run(self):
        ticks, sessions = fixture()
        spec, vault = dataset(self.root/"csv", ticks, sessions)
        packed, packed_vault = dataset(self.root/"packed", ticks, sessions, "PACKED17")
        raw_program = base_program()
        program = put(self.root/"universe.qros", fields("QROS_PROGRAM_V1", raw_program))
        for data in (spec, packed):
            receipt = data.parent/"audit.receipt"
            self.command("data-check", data, digest(data), receipt)
            self.check(kv(receipt)["integrity"] == "PASS" and kv(receipt)["research_ready"] == "0", "data integrity does not promote research")

        resumed, fresh, binrun = (self.root/name for name in ("resumed", "fresh", "binary-run"))
        text = self.mine(program, spec, vault, resumed, chunk=7, max_chunks=2)
        self.check("PAUSED_AT_CHUNK_BOUNDARY" in text and kv(resumed/"control/HEAD")["end"] == "14", "bounded pause at birth 14")
        self.check(not (resumed/"final/COMPLETED.receipt").exists(), "pause cannot claim completion")
        self.mine(program, spec, vault, resumed, chunk=11)
        self.mine(program, spec, vault, fresh, chunk=31)
        self.mine(program, packed, packed_vault, binrun, chunk=96)
        ledger = resumed/"final/trades.csv"
        self.check(ledger.read_bytes() == (fresh/"final/trades.csv").read_bytes() == (binrun/"final/trades.csv").read_bytes(), "ledger identical across chunks, resume, CSV5 and PACKED17")
        before = digest(resumed/"final/COMPLETED.receipt")
        self.mine(program, spec, vault, resumed)
        self.check(before == digest(resumed/"final/COMPLETED.receipt"), "completed rerun idempotent")
        complete = kv(resumed/"final/COMPLETED.receipt")
        self.check(complete["n_tests_raw"] == "96" and complete["aliases"] == "32" and complete["causal_exclusions"] == "16", "raw N_TESTS retains aliases and causal exclusions")
        self.check(complete["unresolved"] == "0" and complete["scientific_head_promoted"] == "0", "complete test stage leaves scientific head unchanged")
        rows = list(csv.DictReader(ledger.open()))
        self.check(len(rows) > 200, "nontrivial synthetic trade coverage")
        by_birth = {}
        for row in rows:
            by_birth.setdefault(int(row["birth"]), []).append(row)
        configs = list(oracle.variants(raw_program))
        compared = 0
        for birth, observed in sorted(by_birth.items()):
            expected, unresolved = oracle.backtest(configs[birth], ticks, sessions)
            self.check(not unresolved and len(expected) == len(observed), f"independent trade count birth {birth}")
            for index, (a, b) in enumerate(zip(expected, observed)):
                for key, value in a.items():
                    if str(value) != b[key]:
                        raise AssertionError(f"independent parity birth={birth} trade={index} field={key}: expected={value} observed={b[key]}")
                compared += 1
        self.check({r["side"] for r in rows} == {"BUY", "SELL"}, "independent parity includes both sides")
        self.trade_parity_count = compared
        print(f"PARITY trades={compared} unique_candidates={len(by_birth)}", flush=True)

        # Every feature opcode is observable through a connected, typed DAG.
        all_ops = single_program()
        for k in list(all_ops):
            if k.startswith("node."):
                del all_ops[k]
        expressions = dict(bid="BID", ask="ASK", spread="SPREAD", zero="CONST:0", one="CONST:1",
                           o="OPEN:400", h="HIGH:400", l="LOW:400", c="CLOSE:400",
                           sum="ADD:o:c", diff="SUB:h:l", lo="MIN:sum:bid", hi="MAX:diff:spread",
                           lag="LAG:c:2", ema="EMA:lag:3", highest="HIGHEST:h:4", lowest="LOWEST:l:4",
                           ge="GE:hi:zero", le="LE:lo:ask", eq="EQ:spread:one", gt="GT:highest:lowest", lt="LT:o:c",
                           up="CROSS_UP:ema:c", down="CROSS_DOWN:c:ema", both="AND:ge:le", inv="NOT:eq",
                           a="OR:both:inv", b="OR:gt:lt", d="OR:up:down", e="OR:a:b", sig="OR:e:d")
        all_ops.update({"node."+k:v for k,v in expressions.items()})
        all_program = put(self.root/"all-ops.qros", fields("QROS_PROGRAM_V1", all_ops))
        exported = self.root/"features.csv"
        self.command("features", all_program, digest(all_program), 0, spec, digest(spec), vault, digest(vault), exported)
        _, expected_features = oracle.feature_table(next(oracle.variants(all_ops)), ticks)
        feature_rows = list(csv.DictReader(exported.open()))
        feature_cells = 0
        for i, row in enumerate(feature_rows):
            for name, value in row.items():
                if name == "seq":
                    continue
                target = expected_features[name][i][0]
                if value != ("NA" if target is None else str(target)):
                    raise AssertionError(f"feature parity row={i} node={name} expected={target} observed={value}")
                feature_cells += 1
        self.check(len({v.split(":")[0] for v in expressions.values()}) == 26, "all 26 native feature opcodes compared")
        self.feature_parity_cells = feature_cells
        self.execution_edges()

        # Conversion verification binds the supplied normalized CSV, not an imagined raw MT5 export.
        normalized = write_csv(self.root/"normalized.csv", [dict(timestamp_ms=t["ts_ns"]//10**6, bid_u=t["bid_u"], ask_u=t["ask_u"], flags=6) for t in ticks])
        conversion = put(self.root/"conversion.contract", fields("QROS_CONVERSION_CONTRACT_V1", dict(
            raw_csv=normalized.name, raw_sha256=digest(normalized), packed17="packed/ticks.p17", packed_sha256=digest(packed.parent/"ticks.p17"),
            rows=len(ticks), clock_domain="SYNTHETIC", timestamp_multiplier=1000000, price_decimals=1, broker_origin="SYNTHETIC")))
        self.command("verify-conversion", conversion, digest(conversion), self.root/"conversion.receipt")
        self.check(kv(self.root/"conversion.receipt")["timestamp_offset_applied_ms"] == "0", "conversion preserves source clock")
        normalized.write_text(normalized.read_text().replace("100000", "100001", 1))
        f = kv(conversion); f["raw_sha256"] = digest(normalized)
        mismatch = put(self.root/"conversion-mismatch.contract", fields("QROS_CONVERSION_CONTRACT_V1", f))
        self.command("verify-conversion", mismatch, digest(mismatch), self.root/"must-not-convert", error="CONVERSION_RECORD_MISMATCH")
        # Shards contain complete synthetic sessions, maintaining absolute causal seq.
        shard_rows = []
        for i, session in enumerate(sessions):
            subset = ticks[session["open_seq"]-1:session["close_seq"]]
            shard, _ = dataset(self.root/f"shard-{i}", subset, [session], "PACKED17")
            shard_rows.append(dict(index=i, manifest_path=f"shard-{i}/dataset.qdata", manifest_sha256=digest(shard), shard_contract_root=kv(shard)["shard_contract_root"]))
        index = write_csv(self.root/"shards.csv", shard_rows)
        self.command("verify-shards", index, digest(index), self.root/"shards.receipt")
        self.check(kv(self.root/"shards.receipt")["rows"] == str(len(ticks)), "all provided shard rows verified")
        mixed, _ = dataset(self.root/"mixed-scale-shard", ticks[600:1200], [sessions[1]], "PACKED17", overrides=dict(price_decimals=2))
        mixed_rows = [dict(row) for row in shard_rows]
        mixed_rows[1].update(manifest_path="mixed-scale-shard/dataset.qdata", manifest_sha256=digest(mixed), shard_contract_root=kv(mixed)["shard_contract_root"])
        mixed_index = write_csv(self.root/"mixed-scale.csv", mixed_rows)
        self.command("verify-shards", mixed_index, digest(mixed_index), self.root/"must-not-mix", error="SHARD_CHAIN_METADATA_MISMATCH")
        shard_rows[1]["shard_contract_root"] = "0"*64
        bad_index = write_csv(self.root/"shards-bad.csv", shard_rows)
        self.command("verify-shards", bad_index, digest(bad_index), self.root/"must-not-shard", error="SHARD_CONTRACT_ROOT_MISMATCH")

        # Negative inputs cannot publish an economic chunk or a passing receipt.
        single = put(self.root/"single.qros", fields("QROS_PROGRAM_V1", single_program()))
        self.command("compile", single, "0"*64, 0, self.root/"wrong-program", error="CONTRACT_HASH_MISMATCH")
        self.mine(single, spec, vault, self.root/"budget", rows=10, error="RESOURCE_ROW_BUDGET_EXCEEDED")
        self.check(kv(self.root/"budget/control/HEAD")["end"] == "0", "resource limit cannot advance head")
        bad_data, bad_vault = dataset(self.root/"wrong-hash", ticks, sessions)
        (bad_data.parent/"ticks.csv").write_text((bad_data.parent/"ticks.csv").read_text().replace("\n", "\r\n", 1))
        self.mine(single, bad_data, bad_vault, self.root/"hash-store", error="DATA_AUTHORITY_HASH_MISMATCH")
        self.check(kv(self.root/"hash-store/control/HEAD")["end"] == "0", "late hash failure discards all candidate work")
        short, _ = dataset(self.root/"truncated", ticks, sessions, "PACKED17")
        raw = (short.parent/"ticks.p17").read_bytes()
        (short.parent/"ticks.p17").write_bytes(raw[:-1])
        self.command("data-check", short, digest(short), self.root/"must-not-short", error="TRUNCATED_PACKED17")
        crossed_ticks = [dict(t) for t in ticks]; crossed_ticks[-1]["ask_u"] = crossed_ticks[-1]["bid_u"]-1
        crossed, crossed_vault = dataset(self.root/"crossed", crossed_ticks, sessions)
        self.mine(single, crossed, crossed_vault, self.root/"crossed-store", error="CROSSED_QUOTE_RESEARCH_POLICY")
        self.check(kv(self.root/"crossed-store/control/HEAD")["end"] == "0", "final crossed quote blocks commit")
        for name, override, error in [
            ("traversal", dict(ticks_path="../csv/ticks.csv"), "INPUT_PATH_TRAVERSAL"),
            ("symlink", dict(ticks_path="linked.csv"), "SYMLINK_FORBIDDEN"),
            ("anchor", dict(session_fragment_sha256="0"*64), "SHARD_CONTRACT_BINDING")]:
            data, _ = dataset(self.root/name, ticks, sessions, overrides=override)
            if name == "symlink":
                (data.parent/"linked.csv").symlink_to(spec.parent/"ticks.csv")
            self.command("data-check", data, digest(data), self.root/f"must-not-{name}", error=error)
        real_data, real_vault = dataset(self.root/"real-denied", ticks, sessions, overrides=dict(
            purpose="RESEARCH", exposure="DEVELOPMENT_EXPOSED", source_clock="DARWINEX_SERVER_WALL", broker_origin="DARWINEX_USER_CONFIRMED"))
        research_program = single_program(); research_program["purpose"] = "RESEARCH"
        research = put(self.root/"research-denied.qros", fields("QROS_PROGRAM_V1", research_program))
        self.mine(research, real_data, real_vault, self.root/"must-not-research", error="RESEARCH_BLOCKED_EXTERNAL_TIME_QDATA_AND_FROZEN_ONTOLOGY_REQUIRED")
        sealed, sealed_vault = dataset(self.root/"sealed", ticks, sessions, overrides=dict(purpose="RESEARCH", exposure="HOLDOUT_SEALED"))
        self.command("vault-check", sealed, digest(sealed), sealed_vault, digest(sealed_vault), digest(single), error="HOLDOUT_ACCESS_DENIED")
        self.check(not (self.root/"must-not-research").exists(), "no research dispatch created")
        grant = put(self.root/"grant.fixture", fields("QROS_HOLDOUT_GRANT_V1", dict(policy_sha256=digest(sealed_vault),
            data_sha256=kv(sealed)["ticks_sha256"], candidate_sha256=digest(single), authorization_id="SOFTWARE_TEST_ONLY",
            action="FIXED_CANDIDATE_HOLDOUT", expires_unix_seconds=4102444800)))
        grant_store = self.root/"grant-store"
        text = self.command("vault-consume", sealed_vault, digest(sealed_vault), grant, digest(grant), grant_store)
        self.check("economic_data_opened=0" in text, "grant consumption opens no economic data")
        self.command("vault-consume", sealed_vault, digest(sealed_vault), grant, digest(grant), grant_store, error="HOLDOUT_CAPABILITY_ALREADY_CONSUMED")

        # The statistical policy is configured, not claimed preregistered.
        policy_values = dict(program_path=program.name, program_sha256=digest(program), completion_path="resumed/final/COMPLETED.receipt",
            completion_sha256=digest(resumed/"final/COMPLETED.receipt"), min_trades=1, min_pf_ppm=0, max_dd_u=100000,
            max_negative_years=10, min_positive_years=0, alpha_ppm=900000, n_tests=96, correction="BY",
            repetitions=999, rng_seed=70493, method="YEAR_BLOCK_SIGN_FLIP_V1")
        gate = put(self.root/"gate.policy", fields("QROS_GATE_POLICY_V1", policy_values))
        text = self.command("gates", ledger, digest(ledger), gate, digest(gate), self.root/"gate.receipt")
        self.check("decision_scope=CONFIGURED_SCREEN_ONLY" in text and "research_approved=0" in text, "screen cannot approve scientific research")
        table = text[text.index("candidate_id,trades,"):]
        screens = list(csv.DictReader(io.StringIO(table)))
        for screen in screens:
            values = [int(r["net_u"]) for r in rows if r["candidate_id"] == screen["candidate_id"]]
            equity = peak = dd = 0
            for value in values:
                equity += value; peak = max(peak, equity); dd = max(dd, peak-equity)
            self.check(int(screen["net_u"]) == sum(values) and int(screen["dd_u"]) == dd, "independent net and settled drawdown "+screen["candidate_id"][:8])
        policy_values["n_tests"] = 48
        undercount = put(self.root/"gate-undercount.policy", fields("QROS_GATE_POLICY_V1", policy_values))
        self.command("gates", ledger, digest(ledger), undercount, digest(undercount), self.root/"must-not-gate", error="GATE_DECLARED_FAMILY_OR_RNG")
        candidate_id = rows[0]["candidate_id"]
        sg = dict(candidate_id=candidate_id, frozen_spec_sha256=digest(program))
        for role in ("gate", "oos", "robustness", "holdout", "forward", "mt5"):
            sg[role+"_path"], sg[role+"_sha256"] = "UNAVAILABLE", "0"*64
        supergate = put(self.root/"supergate.plan", fields("QROS_SUPERGATE_PLAN_V1", sg))
        text = self.command("supergate", supergate, digest(supergate), self.root/"supergate.receipt")
        self.check("status=BLOCKED_MISSING_VALIDATIONS" in text and "missing=6" in text, "missing external validations block Supergate")
        fake = put(self.root/"supergate-fake-scope.fixture", "SYNTHETIC_SCOPE_ATTACK\nother_candidate_id="+candidate_id+"\nother_frozen_spec_sha256="+digest(program)+"\n")
        sg.update(gate_path=fake.name, gate_sha256=digest(fake))
        forged = put(self.root/"supergate-fake-scope.plan", fields("QROS_SUPERGATE_PLAN_V1", sg))
        self.command("supergate", forged, digest(forged), self.root/"must-not-supergate", error="SUPERGATE_EVIDENCE_SCOPE")
        self.positive_gate_and_spec_attack()

        # Diagnostic portfolio allocation, explicitly no joint causal strategy replay.
        unique = list(dict.fromkeys(r["candidate_id"] for r in rows))[:4]
        members = write_csv(self.root/"members.csv", [dict(candidate_id=cid, ledger_path="resumed/final/trades.csv", ledger_sha256=digest(ledger),
                       priority=i, usd_micro_per_unit=10000) for i,cid in enumerate(unique)])
        portfolio = put(self.root/"portfolio.plan", fields("QROS_PORTFOLIO_PLAN_V1", dict(members_path=members.name, members_sha256=digest(members),
            per_asset_daily_limit=3, global_daily_limit=5, purpose="TEST_ONLY", time_basis="SHARED_UTC", initial_capital_usd_micro=100000000000)))
        text = self.command("portfolio", portfolio, digest(portfolio), self.root/"allocated.csv", self.root/"portfolio.receipt")
        self.check("joint_strategy_replay_validated=0" in text and "mark_to_market_drawdown=NOT_COMPUTED" in text, "portfolio diagnostic scope explicit")
        allocated = list(csv.DictReader((self.root/"allocated.csv").open()))
        daily = {}
        for row in allocated:
            key = row["symbol"], row["entry_day"]
            daily[key] = daily.get(key, 0) + 1
        self.check(all(n<=3 for n in daily.values()) and len(allocated)>0, "portfolio per-asset daily cap enforced")

        self.mt5_checks(program, rows)
        self.kill_and_resume(single)
        self.check_authorities()
        # A different input identity cannot resume a previously completed store.
        self.mine(single, spec, vault, resumed, error="STORE_INPUT_OR_ENTRYPOINT_CHANGED")
        self.report("PASS")

    def execution_edges(self):
        base = 1609750800000000000
        cases = [
            ("buy-gap", "BUY", [1000,1000,960,965], [2,2,2,2], 1, "NQX"),
            ("sell-gap", "SELL", [1000,1000,1040,1035], [2,2,2,2], 1, "NQX"),
            ("session-last-executable", "BUY", [1000,1000,1001,1002], [2,2,2,0], 1, "NQX"),
            ("no-fabricated-close", "BUY", [1000,1000,1001,1002], [2,0,2,0], 0, "NQX"),
            ("no-entry-at-close", "BUY", [1000,1000,1001,1002], [2,0,0,2], 0, "NQX"),
            ("pending-expiry", "BUY", [1000,1000,1001,1002,1003,1004], [2,0,0,0,2,2], 1, "NQX"),
            ("xau-cent-scale", "SELL", [200000,200000,199980,199975], [3,3,3,3], 1, "XAUUSD"),
        ]
        for label, side, prices, spreads, count, symbol in cases:
            ticks = [dict(seq=i+1, ts_ns=base+i*1000000000, session_day=20210104, bid_u=p, ask_u=p+spreads[i]) for i,p in enumerate(prices)]
            sessions = [dict(session_day=20210104, open_seq=1, close_seq=len(ticks), open_ts_ns=ticks[0]["ts_ns"], close_ts_ns=ticks[-1]["ts_ns"], utc_offset_seconds=0)]
            folder = self.root/"execution-edges"/label
            data, vault = dataset(folder, ticks, sessions, "PACKED17", symbol)
            config = single_program(); config.update(name=label, side=side, symbol=symbol, expiry_records="2")
            program = put(folder/"case.qros", fields("QROS_PROGRAM_V1", config))
            output = folder/"result"
            self.command("backtest", program, digest(program), data, digest(data), vault, digest(vault), output)
            rows = list(csv.DictReader((output/"final/trades.csv").open()))
            expected, unresolved = oracle.backtest(next(oracle.variants(config)), ticks, sessions)
            self.check(len(rows)==len(expected)==count, "edge trade count "+label)
            for a,b in zip(expected,rows):
                self.check(all(str(value)==b[key] for key,value in a.items()), "edge exact independent parity "+label)
            self.check(kv(output/"final/COMPLETED.receipt")["unresolved"]==str(unresolved), "edge unresolved classification "+label)
            if label=="no-fabricated-close":
                self.check(unresolved==1, "single entry quote cannot fabricate an exit")
            elif label=="session-last-executable":
                self.check(rows[0]["exit_reason"]=="SESSION_CLOSE" and rows[0]["exit_seq"]=="3", "EOD uses actual last executable post-entry quote")
            elif label.endswith("gap"):
                self.check(int(rows[0]["gross_u"])<-10, "gaps execute observed price beyond stop distance "+label)

    def positive_gate_and_spec_attack(self):
        ticks, sessions = fixture(count=20)
        for i,tick in enumerate(ticks):
            tick.update(bid_u=10000+(i%20)*10, ask_u=10002+(i%20)*10)
        folder = self.root/"positive-gate"
        data, vault = dataset(folder, ticks, sessions)
        program = put(folder/"candidate.qros", fields("QROS_PROGRAM_V1", single_program()))
        output = folder/"result"
        self.command("backtest", program, digest(program), data, digest(data), vault, digest(vault), output)
        ledger = output/"final/trades.csv"; completion = output/"final/COMPLETED.receipt"
        policy_values = dict(program_path=program.name, program_sha256=digest(program), completion_path="result/final/COMPLETED.receipt",
            completion_sha256=digest(completion), min_trades=12, min_pf_ppm=1000000, max_dd_u=0,
            max_negative_years=0, min_positive_years=4, alpha_ppm=900000, n_tests=1, correction="BH",
            repetitions=999, rng_seed=70493, method="YEAR_BLOCK_SIGN_FLIP_V1")
        policy = put(folder/"gate.policy", fields("QROS_GATE_POLICY_V1", policy_values))
        text = self.command("gates", ledger, digest(ledger), policy, digest(policy), folder/"gate.receipt")
        table = list(csv.DictReader(io.StringIO(text[text.index("candidate_id,trades,"):])))
        self.check(len(table)==1 and table[0]["screen"]=="PASS" and "research_approved=0" in text, "a positive synthetic screen still cannot promote research")
        rows = list(csv.DictReader(ledger.open()))
        for row in rows:
            row["risk_u"] = "11"
        fake_ledger = write_csv(folder/"forged-risk.fixture.csv", rows)
        fake_completion_values = kv(completion); fake_completion_values["ledger_sha256"] = digest(fake_ledger)
        fake_completion = put(folder/"forged-completion.fixture", fields("QROS_MINING_COMPLETION_V1", fake_completion_values))
        policy_values.update(completion_path=fake_completion.name, completion_sha256=digest(fake_completion))
        fake_policy = put(folder/"forged-risk.policy", fields("QROS_GATE_POLICY_V1", policy_values))
        self.command("gates", fake_ledger, digest(fake_ledger), fake_policy, digest(fake_policy), folder/"must-not-approve", error="GATE_LEDGER_EXECUTION_SPEC_MISMATCH")

    def mt5_checks(self, program, rows):
        output = self.root/"mt5"
        output.mkdir()
        # Export is tested as code generation only; no invented EX5 or tester execution.
        cfg = single_program()
        p = put(output/"export.qros", fields("QROS_PROGRAM_V1", cfg))
        ea = output/"SYNTHETIC_QROS.mq5"
        self.command("export-mt5", p, digest(p), 0, ea)
        self.check("MQL_TESTER" in ea.read_text() and "ResultRetcode" in ea.read_text(), "export has tester guard and trade result checks")
        self.check(kv(Path(str(ea)+".receipt"))["mt5_compiled"] == "0", "export never claims MT5 compilation")
        cid = rows[0]["candidate_id"]
        selected = [r for r in rows if r["candidate_id"] == cid]
        expected = write_csv(output/"expected.csv", selected)
        observed = write_csv(output/"observed.csv", selected)
        provenance = dict(purpose="TEST_ONLY", candidate_id=cid, frozen_spec_sha256=digest(program), terminal_build="SYNTHETIC",
                          tester_agent_build="SYNTHETIC", broker_server="SYNTHETIC_NO_BROKER", mode="SYNTHETIC_FIXTURE")
        for role in ("mq5", "ex5", "set", "symbol_spec", "observed_ticks", "raw_deals"):
            artifact = put(output/(role+".fixture"), f"SYNTHETIC SOFTWARE FIXTURE ONLY: {role}; not a broker artifact\n")
            provenance[role+"_path"], provenance[role+"_sha256"] = artifact.name, digest(artifact)
        provenance["expected_ticks_sha256"] = provenance["observed_ticks_sha256"]
        pp = put(output/"provenance.contract", fields("QROS_MT5_PROVENANCE_V1", provenance))
        plan_values = dict(candidate_id=cid, frozen_spec_sha256=digest(program), expected_path=expected.name, expected_sha256=digest(expected),
                           observed_path=observed.name, observed_sha256=digest(observed), provenance_path=pp.name, provenance_sha256=digest(pp))
        plan = put(output/"parity.plan", fields("QROS_MT5_PARITY_PLAN_V1", plan_values))
        text = self.command("mt5-parity", plan, digest(plan), output/"parity.receipt")
        self.check("status=FIXTURE_PARITY_PASS" in text and "mt5_runtime_independently_executed_here=0" in text, "MT5 synthetic match cannot imply real tester parity")
        empty = write_csv(output/"empty-observation.csv", [], list(selected[0]))
        empty_values = dict(plan_values, observed_path=empty.name, observed_sha256=digest(empty))
        empty_plan = put(output/"empty.plan", fields("QROS_MT5_PARITY_PLAN_V1", empty_values))
        self.command("mt5-parity", empty_plan, digest(empty_plan), output/"must-not-empty", error="MT5_PARITY_REQUIRES_OBSERVED_TRADES")
        for kind in ("DATA", "SIGNAL", "FILL", "COST", "SESSION"):
            first = dict(selected[0]); other = dict(first)
            if kind == "DATA":
                other["entry_ts_ns"] = str(int(other["entry_ts_ns"])+1)
            elif kind == "SIGNAL":
                other["mae_u"] = str(int(other["mae_u"])-1)
            elif kind == "FILL":
                other["entry_price_u"] = str(int(other["entry_price_u"])+1)
                other["exit_price_u"] = str(int(other["exit_price_u"])+1)
            elif kind == "COST":
                other["commission_u"] = str(int(other["commission_u"])+1)
                other["net_u"] = str(int(other["net_u"])-1)
            else:
                other["exit_reason"] = "SL" if other["exit_reason"] != "SL" else "TP"
            a = write_csv(output/(kind+"-expected.csv"), [first]); b = write_csv(output/(kind+"-observed.csv"), [other])
            values = dict(plan_values, expected_path=a.name, expected_sha256=digest(a), observed_path=b.name, observed_sha256=digest(b))
            plan = put(output/(kind+".plan"), fields("QROS_MT5_PARITY_PLAN_V1", values))
            text = self.command("mt5-parity", plan, digest(plan), output/(kind+".receipt"), status=2)
            self.check(f"{kind}=1\n" in text and "status=PARITY_FAIL" in text, "classify MT5 difference "+kind)

    def kill_and_resume(self, program):
        ticks, sessions = fixture(days=(20210104,), count=200000)
        spec, vault = dataset(self.root/"interrupt-data", ticks, sessions, "PACKED17")
        interrupted = self.root/"interrupted"
        args = [str(self.binary), "mine", str(program), digest(program), str(spec), digest(spec), str(vault), digest(vault),
                str(interrupted), "1", "1", "200000"]
        process = subprocess.Popen(args, cwd=self.root, env=self.env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            # Native START_CHUNK is flushed before walking ticks. SIGSTOP freezes only
            # this owned test process so lock and abrupt-loss behavior are observable.
            line = process.stdout.readline().decode()
            if not line.startswith("START_CHUNK"):
                raise AssertionError("interrupt fixture did not reach declared work: "+line)
            os.killpg(process.pid, signal.SIGSTOP)
            self.mine(program, spec, vault, interrupted, chunk=1, max_chunks=1, rows=200000, error="SCOPE_ALREADY_OWNED")
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=10)
        self.check(process.returncode == -signal.SIGKILL and kv(interrupted/"control/HEAD")["end"] == "0", "real SIGKILL cannot fabricate a committed chunk")
        self.mine(program, spec, vault, interrupted, chunk=1, max_chunks=1, rows=200000)
        fresh = self.root/"interrupt-fresh"
        self.mine(program, spec, vault, fresh, chunk=1, max_chunks=1, rows=200000)
        self.check((fresh/"final/trades.csv").read_bytes() == (interrupted/"final/trades.csv").read_bytes(), "SIGKILL recovery equals uninterrupted execution")
        print("INTERRUPTION_AND_FENCING_PASS", flush=True)

    def check_authorities(self):
        checker = ROOT/"tests/check_active_authorities.py"
        result = subprocess.run([sys.executable, str(checker)], cwd=ROOT, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10)
        self.check(result.returncode == 0, "active physical authority hashes match their profiles")
        folder = self.root/"authority-negative"
        shutil.copytree(ROOT/"profiles", folder/"profiles")
        p = folder/"profiles/XAU_FULL_HISTORY_ZIP_v2.authority"
        p.write_text(p.read_text()+"\n# altered fixture\n")
        result = subprocess.run([sys.executable, str(checker), str(folder)], cwd=ROOT, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10)
        self.check(result.returncode != 0, "altered XAU authority profile rejected")

    def report(self, status, error=None):
        result = dict(schema="QROS_SOFTWARE_INTEGRATION_REPORT_V1", status=status, purpose="TEST_ONLY", checks=self.checks,
                      entrypoint_sha256=digest(self.binary), test_sha256=digest(Path(__file__)), oracle_sha256=digest(ROOT/"reference/pipeline_reference.py"),
                      independent_trade_comparisons=getattr(self, "trade_parity_count", 0), independent_feature_cells=getattr(self, "feature_parity_cells", 0),
                      elapsed_seconds=round(time.monotonic()-self.started, 3), labels=self.labels, commands=self.commands,
                      real_broker_ticks_used=False, mt5_executed=False, research_approved=False, error=error)
        result["leak_check_requested"] = self.leak_check
        put(self.root/"INTEGRATION_REPORT.json", json.dumps(result, indent=2)+"\n")
        print(json.dumps({k:result[k] for k in ("status", "checks", "independent_trade_comparisons", "independent_feature_cells", "elapsed_seconds")}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fresh-run", action="store_true", help="create a new child directory for repeated CTest runs")
    parser.add_argument("--leak-check", choices=["enabled", "disabled"], default="enabled")
    args = parser.parse_args()
    if args.fresh_run:
        args.out.mkdir(parents=True, exist_ok=True)
        args.out = Path(tempfile.mkdtemp(prefix="run-", dir=args.out))
    suite = Suite(args.binary, args.out, args.leak_check)
    try:
        suite.run()
    except Exception as exc:
        suite.report("FAIL", str(exc))
        raise
