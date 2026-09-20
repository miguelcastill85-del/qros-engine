#!/usr/bin/env python3
import ast,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
driver=ROOT/"scripts/qros_seed0076_m12_profile_driver_v1.py"
ast.parse(driver.read_text(encoding="utf-8"))
contract=json.loads((ROOT/"control/QROS_SEED0076_M12_PERFORMANCE_BENCHMARK_CONTRACT_20260920_v1.json").read_text())
risk=json.loads((ROOT/"control/QROS_SEED0076_M12_PERFORMANCE_RISK_REGISTER_20260920_v1.json").read_text())
assert contract["status"]=="PREREGISTERED_NO_BENCHMARK_RESULTS"
assert contract["golden"]["signal_configs"]==804672
assert contract["golden"]["distinct_mask_classes"]==248010
assert contract["golden"]["duplicate_aliases"]==556662
assert contract["benchmark_phases"][1]["representative_groups"]==[0,7,15,23]
assert contract["benchmark_phases"][1]["repetitions"]=={"cold":1,"warm":3}
assert contract["benchmark_phases"][2]["id"]=="B1P_GROUP_PANEL_PROFILED"
assert risk["verified_code_level_findings"][0]["theoretical_counts"]["root_config_hash_calls_across_24_groups"]==19312128
assert abs(risk["verified_code_level_findings"][0]["theoretical_counts"]["theoretical_hash_call_reduction_fraction_if_root_reused"]-0.92)<1e-12
assert risk["scientific_integrity_risks"][0]["decision"]=="DO_NOT_CHANGE_CURRENT_FROZEN_UNIT_INSIDE_PERFORMANCE_WORK."
assert contract["scientific_firewall"]=={"economic_pnl_read":False,"ga2_open":False,"holdout_open":False,"universe_changed":False}
print("PASS_STATIC_PROFILER_CONTRACT_V11")
