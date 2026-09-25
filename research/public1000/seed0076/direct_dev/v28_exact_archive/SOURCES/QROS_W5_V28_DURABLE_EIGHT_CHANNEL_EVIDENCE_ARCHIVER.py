#!/usr/bin/env python3
"""Scientific W5 V28 reproducible eight-channel sharded release, exact SHA member manifests.
No raw 2.57GB tick carrier in ZIP; its original SHA and eight Drive predecessor ZIPs pinned separately.
"""
from __future__ import annotations
import pathlib,zipfile,json,hashlib,os,time,sys
R=pathlib.Path(__file__).resolve().parent;OUT=pathlib.Path('/mnt/data');P=pathlib.Path('/mnt/data/qros_nonstall_v23/work/legacy/source_pins')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(8<<20),b''):h.update(chunk)
 return h.hexdigest()
def pack(target,items):
 meta=[];started=time.monotonic();t=target.with_suffix('.zip.partial')
 with zipfile.ZipFile(t,'w',allowZip64=True) as z:
  for arc,p in sorted(items,key=lambda a:a[0]):
   assert p.is_file() and p.stat().st_size>0 and arc!='SHA256_MEMBERS_MANIFEST.json'
   d=zipfile.ZIP_STORED if p.suffix in {'.npz','.npy','.gz','.bin'} else zipfile.ZIP_DEFLATED
   z.write(p,arcname=arc,compress_type=d,compresslevel=(6 if d==zipfile.ZIP_DEFLATED else None))
   meta.append({'path':arc,'bytes':p.stat().st_size,'sha256':sha(p)})
  manifest={'schema':'QROS_W5_V28_ZIP_VERIFIABLE_ALL_MEMBERS_V1','member_count':len(meta),'files':meta,'holdout_open':False,'GA2_open':False,'economic_scope':'DEV_2018_2019_EXPLORATORY_COSTS_UNCERTIFIED'}
  z.writestr('SHA256_MEMBERS_MANIFEST.json',json.dumps(manifest,sort_keys=True,indent=2)+'\n')
 os.replace(t,target)
 with zipfile.ZipFile(target) as z:
  assert z.testzip() is None
  m=json.loads(z.read('SHA256_MEMBERS_MANIFEST.json'));assert len(m['files'])==len(meta)
  for a in m['files']:
   h=hashlib.sha256();
   with z.open(a['path']) as f:
    for data in iter(lambda:f.read(8<<20),b''):h.update(data)
   assert h.hexdigest()==a['sha256']
 return {'name':target.name,'bytes':target.stat().st_size,'sha256':sha(target),'member_count':len(meta),'internal_crc_and_all_byte_hashes':'PASS','elapsed_seconds':round(time.monotonic()-started,2)}

full=json.load(open(R/'V28_INDEPENDENT_COMPLETE_EXPOSED_DEV_ECONOMIC_BYTE_ID_AUDIT.json'));assert full['total_semantic_configs']==22352 and full['total_distinct_physical_masks']==14459
can=json.load(open(R/'V28_ALL_56_ROUTE_REAL_INDEPENDENT_PARITY_MASTER_RECEIPT.json'));assert can['status'].startswith('PASS_')
archives=[]
for ch in range(8):
 items=[]
 for path in [R/f'W5_V27_EXECUTABLE_CANDIDATES_CH{ch}.npz',R/f'V27_EXECUTABLE_CANDIDATE_CH{ch}.json',R/f'V28_56_ROUTE_INDEPENDENT_CANARY_CH{ch}.json']:
  items.append((path.name,path))
 for d in [R/f'V27_FULL10_PRE_ECON_CH{ch}',R/f'V28_EXPOSED_DEV_SPREAD_ONLY_CH{ch}']:
  for path in d.rglob('*'):
   if path.is_file() and not path.name.endswith('.partial'):items.append((f'{d.name}/{path.relative_to(d)}',path))
 for d in sorted(R.glob(f'V28_ECON_TAPE_CH{ch}_r*')):
  for path in d.rglob('*'):
   if path.is_file() and not path.name.endswith('.partial'):items.append((f'{d.name}/{path.relative_to(d)}',path))
 target=OUT/f'QROS_SEED0076_W5_V28_CHANNEL_{ch}_FULL_CAUSAL_AND_ECONOMIC_EVIDENCE.zip';a=pack(target,items);a['channel']=ch;archives.append(a);print(json.dumps({'channel':ch,'zip_bytes':a['bytes'],'members':a['member_count'],'sha256':a['sha256'],'verified':'PASS'}),flush=True)
meta=[]
for p in sorted(R.glob('*.py')):meta.append((f'SOURCES/{p.name}',p))
for p in sorted(R.glob('*.json')):meta.append((f'RECEIPTS/{p.name}',p))
for p in sorted(R.glob('README*.md')):meta.append((f'README/{p.name}',p))
for name in ['QROS_SEED0076_MACHINE_UNIVERSE_SPEC_V209_v1.json','qros_seed0076_config_stream.py','qros_seed0076_gate_engine_v221.py','qros_seed0076_structural_v220.py']:
 meta.append(('FROZEN_ORIGINAL_SOURCE/'+name,P/name))
for name in ['qros_w5_mtf_causal_adapter_v1.py']:
 meta.append(('MTF_CAUSAL_ADAPTER/'+name,pathlib.Path('/mnt/data/qros_nonstall_v23/work')/name))
for name in ['V28_ALL_22352_EXPOSED_DEV_EXPLORATORY_COMPLETE_RESULTS.jsonl','V28_ALL_22352_EXPLORATORY_2018_2019_DEV_RESULTS.csv']:
 meta.append(('ALL_22352_COMPLETE_RESULTS/'+name,R/name))
# Preserve channel ZIP pin table inside master independently of ZIP self-hash.
listing=R/'V28_DURABLE_EIGHT_CHANNEL_ARCHIVE_PINS.json';tmp=listing.with_suffix('.partial');tmp.write_text(json.dumps({'schema':'QROS_W5_V28_DURABLE_ARCHIVE_COHORT_V1','channels':archives,'raw_carrier_sha256':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53','holdout_open':False,'GA2_open':False,'Gate_A_approved':False},sort_keys=True,indent=2)+'\n');os.replace(tmp,listing);meta.append(('RELEASE/V28_DURABLE_EIGHT_CHANNEL_ARCHIVE_PINS.json',listing))
master=OUT/'QROS_SEED0076_W5_V28_MASTER_COMPLETE_22352_RESULTS_AND_REPRODUCTION.zip';ma=pack(master,meta);out=R/'V28_DURABLE_RELEASE_ARCHIVE_ROOT_SHA256.json';tmp=out.with_suffix('.partial');tmp.write_text(json.dumps({'schema':'QROS_W5_V28_DURABLE_ALL_8_SHARDS_MASTER_SHA_ANCHOR','master':ma,'channels':archives,'prior_original_GitHub_pointer_still_to_be_promoted':True,'library_persistence_still_to_be_verified':True,'holdout_open':False,'GA2_open':False},sort_keys=True,indent=2)+'\n');os.replace(tmp,out)
print(json.dumps({'result':'PASS_MASTER_AND_EIGHT_INDEPENDENT_SHA_VERIFIABLE_CHANNEL_ARCHIVES','master':ma,'channels':[{'ch':x['channel'],'sha':x['sha256'],'bytes':x['bytes']} for x in archives],'root_receipt_sha256':sha(out)}),flush=True)
