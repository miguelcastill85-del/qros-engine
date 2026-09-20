#!/usr/bin/env python3
import ast, pathlib, json
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=ROOT/"scripts/qros_seed0076_m12_profile_driver_v1.py"
ast.parse(p.read_text(encoding="utf-8"))
c=json.loads((ROOT/"control/QROS_SEED0076_M12_PERFORMANCE_BENCHMARK_CONTRACT_20260920_v1.json").read_text())
assert c["status"]=="PREREGISTERED_NO_BENCHMARK_RESULTS"
assert c["golden"]["signal_configs"]==804672
assert c["golden"]["distinct_mask_classes"]==248010
assert c["golden"]["duplicate_aliases"]==556662
assert c["benchmark_phases"][1]["representative_groups"]==[0,7,15,23]
assert c["scientific_firewall"]=={"economic_pnl_read":False,"ga2_open":False,"holdout_open":False,"universe_changed":False}
print("PASS_STATIC_PROFILER_CONTRACT")
