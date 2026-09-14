#!/usr/bin/env python3
import json, subprocess, sys, tempfile
from pathlib import Path

def write(p,o): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o))
def build(root):
 stable={'current_version':'V1','target_path':'control/target.json'}
 target={'version':'V1','governance':{'promotion_ledger':'control/ledger.json'},'verified_counts':{'ga1_formally_completed_shards':1,'first_economic_gate_queue_count':1},'completed_shards':[{'asset':'NQX','side':'BUY','timeframe':'H1','distinct_mask_classes':10,'completion_receipt':'control/comp.json'}],'current_shard':{'asset':'NQX','side':'BUY','timeframe':'H4','shard_id':'s','expected_config_root_sha256':'r','groups_pass':24,'groups_total':24},'authority':{'h4_group_checkpoint':'control/cp.json'},'economic_pnl_read':False,'holdout_open':False,'ga2_open':False}
 ledger={'completed_and_promoted_shards':[{'asset':'NQX','side':'BUY','timeframe':'H1','distinct_mask_classes':10,'completion_receipt':'control/comp.json','semantic_class_root_sha256':'sem'}],'queued_shard_count':1,'economic_pnl_read':False,'holdout_open':False,'ga2_open':False}
 comp={'domain':{'asset':'NQX','side':'BUY','timeframe':'H1'},'signal_configs':804672,'distinct_mask_classes':10,'semantic_class_root_sha256':'sem','scientific_guards':{'economic_pnl_read':False,'holdout_open':False,'ga2_open':False}}
 cp={'asset':'NQX','side':'BUY','timeframe':'H4','shard_id':'s','expected_config_root_sha256':'r','groups_pass':24,'groups_total':24,'processed_signal_configs':804672}
 for n,o in [('QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json',stable),('target.json',target),('ledger.json',ledger),('comp.json',comp),('cp.json',cp)]:write(root/'control'/n,o)

def run(script,root,out): return subprocess.run([sys.executable,str(script),'--repo-root',str(root),'--out',str(out)],capture_output=True,text=True)
def main():
 script=Path(__file__).resolve().parents[1]/'scripts'/'qros_cross_chat_resume_preflight_v233.py'
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);build(root)
  a=run(script,root,root/'pass.json'); assert a.returncode==0,(a.stdout,a.stderr); assert json.load(open(root/'pass.json'))['status']=='PASS'
  p=root/'control'/'ledger.json';x=json.load(open(p));x['queued_shard_count']=2;write(p,x)
  b=run(script,root,root/'fail.json'); assert b.returncode==2,(b.stdout,b.stderr);r=json.load(open(root/'fail.json'));assert r['status']=='FAIL';assert 'LEDGER_QUEUE_COUNT' in r['errors'];assert 'QUEUE_EQUALS_COMPLETED' in r['errors']
 print('PASS cross-chat resume preflight positive+negative regression')
if __name__=='__main__':main()
