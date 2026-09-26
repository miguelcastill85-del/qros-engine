#!/usr/bin/env python3
"""Tiny Git-native preflight: O(1) chat turns; no full 446-receipt replay.
Inputs must be separately fetched from live authenticated GitHub refs.
The trust anchor is the previously independently audited 446-Git baseline.
This script does not execute a backtest, promote any economic gate, or run offline.
"""
import argparse,base64,hashlib,json,pathlib,re,sys

BASE='d424206c8001422f4d9930b23d8eced5e7115009e40d5fe5b2f0e57ee259ec05'
BLOB='688ec3fa2123ec9df900c41487e4f6298b4ceea5'
PLAN='2be3c09dbcf80576125187f45ae9e7c8ce265a67bab6170a3809adb6a464dc0c'
RUNNER='d545f846a09dc2059193c5a9a6703235bf9f27554ac802eafdf4c032b5a501bf'
RAW='3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53'
TOTAL=710
class Stop(Exception):pass
def need(condition,reason):
 if not condition:raise Stop(reason)
def sha(x):return hashlib.sha256(x).hexdigest()
def gb(x):return hashlib.sha1(b'blob '+str(len(x)).encode()+b'\0'+x).hexdigest()
def read_exact(path,expected):
 b=pathlib.Path(path).read_bytes();need(re.fullmatch('[0-9a-f]{40}',expected) and gb(b)==expected,'GIT_BLOB_SHA_DRIFT:'+str(path));return json.loads(b),b
def verify(pointer,frontier,target,anchor,p_sha,f_sha,t_sha,a_sha,delta=None):
 p,pb=read_exact(pointer,p_sha);f,fb=read_exact(frontier,f_sha);_,_=read_exact(target,t_sha);_,_=read_exact(anchor,a_sha)
 need(p.get('schema')=='QROS_SEED0076_DIRECT_CURRENT_CHAT_HANDOFF_POINTER_V1','POINTER_SCHEMA')
 ff=p.get('fast_frontier_v2') or {}
 need(ff.get('git_blob_sha1')==f_sha and ff.get('sequence')==f['sequence'] and ff.get('ledger_root_sha256')==f['ledger_root_sha256'],'POINTER_FRONTIER_BINDING')
 need(p.get('target_git_blob_sha1')==t_sha and p.get('last_closed_remote_anchor_blob_sha1')==a_sha,'POINTER_AUTHORITY_DRIFT')
 need(f.get('schema')=='QROS_W5_FAST_FRONTIER_V2' and f.get('baseline_sha256')==BASE and f.get('baseline_git_blob_sha1')==BLOB,'BASELINE_AUTHORITY_DRIFT')
 need(f.get('original_plan_sha256')==PLAN and f.get('original_runner_sha256')==RUNNER and f.get('original_raw_sha256')==RAW,'ORIGINAL_PLAN_RUNNER_OR_DATA_DRIFT')
 for obj in (p,f):
  need(all(obj.get(k) is False for k in ('Gate_A_approved','holdout_open','ga2_open')),'SCIENTIFIC_GATE_DRIFT')
 need(f.get('new_economic_PNL') is False and f.get('historical_account_commission_certified') is False and f.get('historical_symbol_special_hours_certified') is False,'ECONOMIC_AUTHORITY_DRIFT')
 try:bits=base64.b64decode(f['bitmap_b64'],validate=True)
 except Exception as e:raise Stop('BAD_BITSET') from e
 need(len(bits)==89 and bits[-1]>>6==0,'BITSET_LENGTH_OR_UNUSED_BITS')
 count=sum(x.bit_count() for x in bits)
 need(count==f['completed']==p.get('v33_shards_completed') and count+f['remaining']==TOTAL and count>=446,'BITSET_COUNT_DRIFT')
 need(sum(f['channels'].values())==count and set(f['channels'])=={'0','4'},'CHANNEL_COUNT_DRIFT')
 for ch in ('0','4'):
  next_rows=f.get('next_by_channel',{}).get(ch,[])
  need(len(next_rows)<=6 and all(0<=x['task_index']<TOTAL and not(bits[x['task_index']//8]&(1<<x['task_index']%8)) and x['ch']==int(ch) for x in next_rows),'NEXT_CURSOR_DRIFT')
 seq=f['sequence'];need(type(seq) is int and seq>=0,'BAD_SEQUENCE')
 if seq==0:need(count==446 and not f.get('latest_delta_git_blob_sha1') and delta is None,'UNEXPECTED_BASELINE_DELTA')
 else:
  need(delta is not None,'LAST_DELTA_REQUIRED');raw=pathlib.Path(delta).read_bytes()
  need(gb(raw)==f['latest_delta_git_blob_sha1'] and sha(raw)==f['latest_delta_sha256'],'DELTA_BYTES_DRIFT')
  d=json.loads(raw)
  need(d.get('schema')=='QROS_W5_FAST_DELTA_V2' and d.get('sequence')==seq and d.get('new_count')==count and d.get('previous_ledger_root_sha256')==f['previous_ledger_root_sha256'] and d.get('previous_frontier_git_blob_sha1')==f['previous_frontier_git_blob_sha1'],'DELTA_CHAIN_DRIFT')
  need(1<=len(d['receipts'])<=6 and d['previous_count']+len(d['receipts'])==count,'DELTA_COUNT_DRIFT')
  prev=bytearray(bits);root=bytes.fromhex(d['previous_ledger_root_sha256']);seen=set()
  for x in d['receipts']:
   raw=base64.b64decode(x['b64'],validate=True);i=x['task_index'];need(i not in seen and 0<=i<TOTAL and len(raw)==x['bytes'] and sha(raw)==x['sha256'],'DELTA_RECEIPT_DRIFT');seen.add(i)
   obj=json.loads(raw);need(obj['Gate_A_approved'] is False and obj['holdout_open'] is False and obj['ga2_open'] is False and obj['new_economic_PNL'] is False,'DELTA_GATE_DRIFT')
   need(bits[i//8]&(1<<i%8),'DELTA_TASK_NOT_COMPLETE');prev[i//8]&=~(1<<i%8)&255
   root=hashlib.sha256(root+i.to_bytes(2,'big')+x['name'].encode()+bytes.fromhex(x['sha256'])).digest()
  need(root.hex()==f['ledger_root_sha256'] and sha(bytes(prev))==d['previous_bitmap_sha256'] and sha(bits)==d['post_bitmap_sha256'],'DELTA_LEDGER_OR_BITMAP_DRIFT')
 return {'status':'FAST_GITHUB_CHAT_RESUME_VERIFIED','completed':count,'remaining':TOTAL-count,'new_receipts_rehashed':0 if seq==0 else len(d['receipts']),'old_receipts_replayed':0,'baseline_zip_download_required':False,'next':f['next_by_channel'],'full_audit_due':seq>=f['periodic_full_reaudit_due_at_sequence']}
def main():
 ap=argparse.ArgumentParser()
 for k in ('pointer','frontier','target','anchor','pointer-sha','frontier-sha','target-sha','anchor-sha'):ap.add_argument('--'+k,required=True)
 ap.add_argument('--delta');a=ap.parse_args()
 try:
  print(json.dumps(verify(a.pointer,a.frontier,a.target,a.anchor,a.pointer_sha,a.frontier_sha,a.target_sha,a.anchor_sha,a.delta),sort_keys=True));return 0
 except (Stop,KeyError,TypeError,ValueError,OSError) as e:print(json.dumps({'status':'FAIL_CLOSED','reason':str(e)}),file=sys.stderr);return 3
if __name__=='__main__':raise SystemExit(main())
