#!/usr/bin/env python3
"""Reproduce historical checker defects using inert strings; never run PS."""
import hashlib
import importlib.util
import json
from pathlib import Path

root=Path(__file__).resolve().parent
source=root.parent/'runner_qualification_system_v1/qros_runner_static_release_gate_v1_1.py'
manifest=json.loads((root/'SOURCE_INTEGRITY.json').read_text())
expected=next(row['sha256'] for row in manifest if row['path'].endswith('/qros_runner_static_release_gate_v1_1.py'))
if hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
    raise SystemExit('HISTORICAL_SOURCE_HASH_MISMATCH')
spec=importlib.util.spec_from_file_location('historical_gate',source)
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
cases={
    'top_level_unguarded_stop':'Set-StrictMode -Version 3.0\ntry{}catch{}\nStop-Process -Id 123 -Force',
    'comment_only_envelope':'Set-StrictMode -Version 3.0\n# try{\n# catch{',
}
rows=[]
for name,ps in cases.items():
    rules=gate.static_rules(ps,'')
    accepted=all(r['pass'] for r in rules)
    if not accepted: raise SystemExit('HISTORICAL_REPRODUCTION_CHANGED:'+name)
    rows.append({'case':name,'all_10_rules_pass':accepted,'rule_count':len(rules),
                 'scope':'synthetic strings; PowerShell NOT executed'})
(root/'LEGACY_GATE_REPRODUCTION.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps({'reproduced':len(rows),'historical_validator_defective':True,
                  'latest_R1_source_available':False,'r2_native_qualified':False}))
