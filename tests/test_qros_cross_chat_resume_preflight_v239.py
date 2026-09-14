from __future__ import annotations
import json,shutil,subprocess,sys,tempfile
from pathlib import Path
SRC=Path(__file__).resolve().parents[1]; SCRIPT_REL=Path('scripts/qros_cross_chat_resume_preflight_v239.py')
def run(root):
 out=root/'preflight_out.json';p=subprocess.run([sys.executable,str(root/SCRIPT_REL),'--repo-root',str(root),'--out',str(out)],capture_output=True,text=True);return p,json.loads(out.read_text())
def mutate_json(p,key,val):
 o=json.loads(p.read_text());o[key]=val;p.write_text(json.dumps(o,sort_keys=True,indent=2)+'\n')
def clone():
 td=tempfile.TemporaryDirectory();dst=Path(td.name)/'repo';shutil.copytree(SRC,dst,ignore=shutil.ignore_patterns('__pycache__','preflight_out.json'));return td,dst
cases=[]
for name,mut in [
 ('actual_coherent_graph',None),
 ('mutate_m10_alias_root',lambda r:mutate_json(r/'control/QROS_PUBLIC_1000_SEED_0076_GA1_SHARD_NQX_BUY_M10_COMPLETION_V239_v1.json','full_alias_mapping_root_sha256','00'*32)),
 ('mutate_m12_config_root',lambda r:mutate_json(r/'control/QROS_PUBLIC_1000_SEED_0076_GA1_NQX_BUY_M12_CONFIG_STREAM_PARITY_V239_v1.json','ordered_config_id_stream_root_sha256','11'*32)),
 ('mutate_ledger_count',lambda r:mutate_json(r/'control/QROS_PUBLIC_1000_FIRST_ECONOMIC_GATE_PROMOTION_LEDGER_v5.json','queued_shard_count',6)),
 ('mutate_runner_blob',lambda r:(r/'scripts/qros_seed0076_ga1_cached_wrapper_v236.py').write_text((r/'scripts/qros_seed0076_ga1_cached_wrapper_v236.py').read_text()+'\n#mutation\n'))]:
 td,r=clone()
 if mut: mut(r)
 p,o=run(r)
 if mut is None:
  assert p.returncode==0 and o['status']=='PASS';cases.append([name,'PASS',len(o['checks'])])
 else:
  assert p.returncode==2 and o['status']=='FAIL';cases.append([name,'FAIL_CLOSED',o['errors'][:3]])
 td.cleanup()
print(json.dumps(cases,sort_keys=True))
