#!/usr/bin/env python3
"""Independent Meta-Audit of v2.1 state (never imports the runner).

A self-checksum is not an authority. --state-pin must come from a distinct,
immutable trusted store to claim remote-pinned checkpoint integrity.
"""
from __future__ import annotations
import argparse,hashlib,json,pathlib,re,sys

H64=re.compile('^[0-9a-f]{64}$');H40=re.compile('^[0-9a-f]{40}$')

class AuditError(ValueError):pass

def encode(o):return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def hexsha(b):return hashlib.sha256(b).hexdigest()
def gitblob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def diskhash(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()
def check(ok,why):
    if not ok:raise AuditError(why)
def resolve(root,name):
    check(isinstance(name,str) and name and not name.startswith('/') and '\\' not in name,'AUDIT_UNSAFE_PATH')
    check(all(x not in ('..','.','') for x in name.split('/')),'AUDIT_UNSAFE_PATH')
    p=(root/name).resolve();check(p.is_relative_to(root.resolve()) and p!=root,'AUDIT_PATH_ESCAPE')
    return p

def audit(root,plan_path,plan_sha256,state_path=None,remote_state_sha256=None,git_anchors=None,drive_snapshots=None):
    root=pathlib.Path(root).resolve();raw=pathlib.Path(plan_path).read_bytes()
    check(isinstance(plan_sha256,str) and H64.fullmatch(plan_sha256),'EXTERNAL_PLAN_PIN_REQUIRED')
    check(hexsha(raw)==plan_sha256,'EXTERNAL_PLAN_PIN_FAIL')
    p=json.loads(raw);check(p.get('schema')=='QROS_ANTI_STALL_PLAN_V2_1','PLAN_SCHEMA_FAIL')
    sp=pathlib.Path(state_path) if state_path else root/'QROS_ANTI_STALL_STATE_V2_1.json'
    s_raw=sp.read_bytes()
    if remote_state_sha256 is not None:
        check(isinstance(remote_state_sha256,str) and H64.fullmatch(remote_state_sha256),'BAD_STATE_EXTERNAL_PIN')
        check(hexsha(s_raw)==remote_state_sha256,'CHECKPOINT_REMOTE_PIN_FAIL')
    state=json.loads(s_raw)
    check(state.get('schema')=='QROS_ANTI_STALL_STATE_V2_1','STATE_SCHEMA_FAIL')
    self_h=state.get('self_sha256')
    check(isinstance(self_h,str) and H64.fullmatch(self_h) and self_h==hexsha(encode({k:v for k,v in state.items() if k!='self_sha256'})),'STATE_SELF_HASH_FAIL')
    check(state.get('plan_sha256')==plan_sha256,'STATE_PLAN_DRIFT')
    check(state.get('authority')==p.get('authority') and state.get('lane_id')==p.get('lane_id'),'CROSS_LANE_AUTHORITY_MIXING')
    locks={'holdout_open':False,'ga2_open':False,'new_old_shard_ga1_authorized':False}
    check(all(state.get('scientific_firewalls',{}).get(k) is v and p.get('scientific_firewalls',{}).get(k) is v for k,v in locks.items()),'SCIENTIFIC_FIREWALL_OPEN')
    check(isinstance(p.get('stages'),list) and len(p['stages'])==len(state.get('stages',[])),'STAGE_CARDINALITY_FAIL')
    seen=set();passed=[];unclosed=[];pending=False
    for stage,st in zip(p['stages'],state['stages']):
        sid=stage.get('id');check(sid not in seen and sid==st.get('id'),'DUPLICATED_OR_REORDERED_STAGE');seen.add(sid)
        check(st.get('status') in ('PENDING','RUNNING','PASS','FAILED','HALTED'),'BAD_STAGE_STATE')
        check(len(st.get('attempted_routes',[]))<=2 and len(set(st.get('attempted_routes',[])))==len(st.get('attempted_routes',[])),'RETRY_LIMIT_BREACH')
        check(all(x in [q['name'] for q in stage.get('routes',[])] for x in st.get('attempted_routes',[])),'UNFROZEN_ROUTE_USED')
        if st['status']!='PASS':pending=True;unclosed.append(sid);continue
        check(not pending,'NON_PREFIX_PASS')
        contract=stage['outputs'];out=st.get('outputs',[])
        check(len(contract)==len(out) and [x['path'] for x in contract]==[x['path'] for x in out],'OUTPUT_CONTRACT_DRIFT')
        for item,obs in zip(contract,out):
            f=resolve(root,item['path']);check(f.is_file(),'OUTPUT_ABSENT:'+sid)
            check(f.stat().st_size==obs.get('bytes') and diskhash(f)==obs.get('sha256'),'OUTPUT_BYTES_CHANGED:'+sid)
            if item.get('sha256') is not None:check(obs['sha256']==item['sha256'],'OUTPUT_NOT_MATCHING_FROZEN_PLAN')
            if item.get('bytes') is not None:check(obs['bytes']==item['bytes'],'OUTPUT_SIZE_NOT_MATCHING_PLAN')
        if stage['kind']=='local':
            check(bool(st.get('attempted_routes')),'LOCAL_PASS_NO_ATTEMPT')
            for item in stage['inputs']:
                f=resolve(root,item['path']);check(f.is_file() and f.stat().st_size==item['bytes'] and diskhash(f)==item['sha256'],'INPUT_OR_RUNNER_DRIFT:'+sid)
        elif stage['kind']=='external':
            ev=st.get('remote_evidence') or {}
            pin=stage['anchor_git_blob_sha1']
            check(ev.get('anchor_git_blob_sha1')==pin and ev.get('remote_id')==stage['remote_id'] and ev.get('verified_remote_readback') is True,'EXTERNAL_PASS_LACKS_PIN')
            check(git_anchors is not None and sid in git_anchors,'EXTERNAL_GIT_BLOB_NOT_SUPPLIED:'+sid)
            anchor_raw=pathlib.Path(git_anchors[sid]).read_bytes()
            check(gitblob(anchor_raw)==pin,'EXTERNAL_GIT_BLOB_DRIFT:'+sid)
            anc=json.loads(anchor_raw)
            check(anc.get('schema')=='QROS_EXTERNAL_OUTPUT_ANCHOR_V1' and anc.get('lane_id')==p['lane_id'] and anc.get('stage_id')==sid and anc.get('remote_id')==stage['remote_id'],'EXTERNAL_ANCHOR_BINDINGS_DRIFT:'+sid)
            check(anc.get('outputs')==out,'EXTERNAL_HASH_BINDING_DRIFT:'+sid)
            check(drive_snapshots is not None and sid in drive_snapshots,'CONNECTED_DRIVE_SNAPSHOT_NOT_SUPPLIED:'+sid)
            snap=drive_snapshots[sid]
            check(snap.get('id')==stage['remote_id'] and snap.get('size')==str(out[0]['bytes']) and snap.get('title')==pathlib.PurePosixPath(out[0]['path']).name,'CONNECTED_DRIVE_READBACK_MISMATCH:'+sid)
        else:raise AuditError('BAD_STAGE_KIND')
        passed.append(sid)
    check(state['cursor']==len(passed),'CURSOR_NOT_MONOTONIC')
    events=state.get('events',[]);prev='0'*64;starts={};completions={};n_fail=0
    for i,e in enumerate(events,1):
        check(e.get('sequence')==i and e.get('previous_sha256')==prev,'EVENT_CHAIN_BROKEN')
        check(e.get('event_sha256')==hexsha(encode({k:v for k,v in e.items() if k!='event_sha256'})),'EVENT_HASH_BROKEN')
        k=e['kind'];sid=e.get('stage')
        if k=='START':starts[sid]=starts.get(sid,0)+1
        if k in ('PASS','RECOVER_VERIFIED_OUTPUT','EXTERNAL_PASS'):completions[sid]=completions.get(sid,0)+1
        if k=='FAIL':n_fail+=1
        prev=e['event_sha256']
    check(len(events)>0 and events[0]['kind']=='INIT','INIT_EVENT_MISSING')
    check(all(v==1 for v in completions.values()),'DUPLICATE_STAGE_COMPLETION')
    check(set(passed)==set(completions),'STAGE_PASS_EVENT_MISMATCH')
    check(all(starts.get(sid,0)<=2 for sid in starts),'START_RETRY_VIOLATION')
    check(all(not (e['kind']=='EXTERNAL_PASS' and p['stages'][[z['id'] for z in p['stages']].index(e['stage'])]['kind']!='external') for e in events if e['kind']=='EXTERNAL_PASS'),'EXTERNAL_EVENT_WRONG_KIND')
    return {'schema':'QROS_META_AUDIT_V2_1','status':'PASS' if not unclosed and remote_state_sha256 else 'TECHNICAL_PASS_NOT_FINAL',
            'lane_id':p['lane_id'],'authority':p['authority'],'passed_stages':passed,'unclosed_stages':unclosed,
            'cursor':len(passed),'event_count':len(events),'failed_route_count':n_fail,
            'remote_state_pin_verified':bool(remote_state_sha256),'external_stages_checked':[x['id'] for x in p['stages'][:len(passed)] if x['kind']=='external'],
            'gate_a_approved':False,'holdout_open':False,'production_release':False,
            'limitations':'Cannot prove prior subprocess side effects or provenance of a supplied Drive snapshot without its connected readback. Local self-hash is not an external authority.'}

def main():
    x=argparse.ArgumentParser();x.add_argument('--work',required=True);x.add_argument('--plan',required=True);x.add_argument('--plan-pin',required=True);x.add_argument('--state-pin');x.add_argument('--state');x.add_argument('--git-anchors-json');x.add_argument('--drive-snapshots-json');v=x.parse_args()
    try:
        anchors=json.loads(pathlib.Path(v.git_anchors_json).read_text()) if v.git_anchors_json else None
        snaps=json.loads(pathlib.Path(v.drive_snapshots_json).read_text()) if v.drive_snapshots_json else None
        print(json.dumps(audit(v.work,v.plan,v.plan_pin,v.state,v.state_pin,anchors,snaps),sort_keys=True))
    except Exception as e:
        print(json.dumps({'status':'FAIL_CLOSED','reason':str(e)},sort_keys=True),file=sys.stderr);raise SystemExit(4)
if __name__=='__main__':main()
