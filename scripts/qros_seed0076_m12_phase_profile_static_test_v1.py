#!/usr/bin/env python3
import ast,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=ROOT/"scripts/qros_seed0076_m12_phase_profile_v1.py"
ast.parse(p.read_text(encoding="utf-8"))
c=json.loads((ROOT/"control/QROS_SEED0076_M12_PHASE_PROFILE_CONTRACT_20260920_v1.json").read_text())
assert c["status"]=="PREREGISTERED_NO_PHASE_RESULTS"
assert c["representative_groups"]==[0,7,15,23]
assert "config_id" in c["instrumented_phases"]
assert "group_packages_exact" in c["instrumented_phases"]
assert "ClassDB.register" in c["instrumented_phases"]
assert c["scientific_firewall"]["economic_pnl_read"] is False
print("PASS_PHASE_PROFILE_STATIC")
