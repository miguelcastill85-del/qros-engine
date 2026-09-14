#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path
PAIR=64

def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha256_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--groups-root',required=True);ap.add_argument('--merge-receipt',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
 root=Path(a.groups_root); mr=json.load(open(a.merge_receipt)); failures=[]
 classes={}; aliases={}; group_receipts=[]; local_class_sum=0
 for gi in range(24):
  gd=root/f'group{gi:02d}'; rp=gd/'worker_receipt.json'
  if not rp.is_file(): failures.append(f'MISSING_RECEIPT:{gi}'); continue
  r=json.load(open(rp)); group_receipts.append(r.get('receipt_sha256'))
  if r.get('status')!='PASS' or r.get('processed_signal_configs')!=33528 or r.get('economic_pnl_read') or r.get('holdout_open'): failures.append(f'BAD_RECEIPT:{gi}')
  for art in r.get('artifacts',[]):
   p=gd/art['path']
   if not p.is_file() or p.stat().st_size!=art['bytes'] or sha256_file(p)!=art['sha256']: failures.append(f'BAD_ARTIFACT:{gi}:{art["path"]}')
  rep_to_class={}; alias_sum=0; lc=0
  with (gd/'mask_class_index.jsonl').open('rb') as f:
   for line in f:
    row=json.loads(line); ch=row['class_hash']; rep=row['representative_config_id']; ac=int(row['alias_count']); ec=int(row['event_count']); mh=row['mask_content_sha256']; lc+=1;alias_sum+=ac;rep_to_class[rep]=ch
    old=classes.get(ch)
    if old is None: classes[ch]={'rep':rep,'alias_count':ac,'event_count':ec,'mask_content_sha256':mh}
    else:
     if old['event_count']!=ec or old['mask_content_sha256']!=mh: failures.append(f'CLASS_METADATA_COLLISION:{ch}')
     old['rep']=min(old['rep'],rep);old['alias_count']+=ac
    if rep in aliases: failures.append(f'DUP_CONFIG_REP:{rep}')
    aliases[rep]=ch
  if alias_sum!=33528 or lc!=r.get('distinct_mask_class_count'): failures.append(f'LOCAL_ACCOUNTING:{gi}')
  local_class_sum+=lc
  with (gd/'duplicate_alias_pairs.bin').open('rb') as f:
   while True:
    b=f.read(PAIR)
    if not b: break
    if len(b)!=PAIR: failures.append(f'TRUNCATED_DUP:{gi}');break
    cfg=b[:32].hex(); rep=b[32:].hex(); ch=rep_to_class.get(rep)
    if ch is None: failures.append(f'DUP_REP_MISSING:{gi}:{rep}');continue
    if cfg in aliases: failures.append(f'DUP_CONFIG:{cfg}')
    aliases[cfg]=ch
 if len(aliases)!=804672: failures.append(f'GLOBAL_CONFIG_COUNT:{len(aliases)}')
 if sum(v['alias_count'] for v in classes.values())!=804672: failures.append('GLOBAL_ALIAS_SUM')
 if len(classes)+int(mr.get('duplicate_config_count',-1))!=804672: failures.append('MERGE_DUP_COUNT_IDENTITY')
 hsem=hashlib.sha256()
 zero_alias=0;zero_rep=None
 for ch in sorted(classes):
  v=classes[ch]; row={'class_hash':ch,'representative_config_id':v['rep'],'alias_count':v['alias_count'],'event_count':v['event_count'],'mask_content_sha256':v['mask_content_sha256']}
  hsem.update(hashlib.sha256(canonical(row)).digest())
  if v['event_count']==0: zero_alias=v['alias_count'];zero_rep=v['rep']
 halias=hashlib.sha256()
 for cfg in sorted(aliases): halias.update(bytes.fromhex(cfg));halias.update(bytes.fromhex(aliases[cfg]))
 checks={
  'processed_signal_configs':len(aliases)==mr.get('processed_signal_configs')==804672,
  'distinct_mask_class_count':len(classes)==mr.get('distinct_mask_class_count'),
  'local_distinct_class_sum':local_class_sum==mr.get('local_distinct_class_sum_before_cross_group_merge'),
  'semantic_class_root_sha256':hsem.hexdigest()==mr.get('semantic_class_root_sha256'),
  'full_alias_mapping_root_sha256':halias.hexdigest()==mr.get('full_alias_mapping_root_sha256'),
  'zero_event_class_alias_count':zero_alias==mr.get('zero_event_class_alias_count'),
  'zero_event_representative_config_id':zero_rep==mr.get('zero_event_representative_config_id'),
  'group_receipt_sequence':group_receipts==[x['receipt_sha256'] for x in mr.get('group_receipts',[])]
 }
 if not all(checks.values()): failures.extend('CHECK_FAIL:'+k for k,v in checks.items() if not v)
 out={'schema':'QROS_SEED0076_GA1_DISTRIBUTED_MERGE_ORACLE_1.0','status':'PASS' if not failures else 'FAIL','seed':'WEB_SEED_0076','domain':{'asset':'XAUUSD','side':'BUY','timeframe':'M1'},'checks':checks,'reconstructed':{'processed_signal_configs':len(aliases),'distinct_mask_class_count':len(classes),'local_distinct_class_sum':local_class_sum,'semantic_class_root_sha256':hsem.hexdigest(),'full_alias_mapping_root_sha256':halias.hexdigest(),'zero_event_class_alias_count':zero_alias,'zero_event_representative_config_id':zero_rep},'failures':failures,'economic_pnl_read':False,'holdout_open':False}
 out['receipt_sha256']=hashlib.sha256(canonical(out)).hexdigest();Path(a.out).write_text(json.dumps(out,sort_keys=True,indent=2)+'\n');print(json.dumps({'status':out['status'],**out['reconstructed']}));raise SystemExit(0 if out['status']=='PASS' else 2)
if __name__=='__main__':main()
