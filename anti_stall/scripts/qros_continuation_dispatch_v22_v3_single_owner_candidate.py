#!/usr/bin/env python3
"""ENGINEERING_CANDIDATE: retain v2.2 dispatch but call single-owner guarded v2.1 clone.

Failover without relaxing causal dependencies or re-running closed QROS stages.

Queue is an externally pinned SHA256 document. Every job has its own frozen v2.1
plan and workdir; only independent jobs may run after a failed upstream route.
One invocation auto-switches up to two distinct preregistered equivalent routes,
then switches to the first dependency-safe unfinished job if available.
"""
from __future__ import annotations
import argparse,hashlib,json,pathlib,sys,time
from qros_anti_stall_v2_2_single_owner_candidate import (Incident,atomic_json,check_bytes,invoke,load_state,mutex,parse_plan,sha_file)

def queue_load(path,expected_sha):
    raw=pathlib.Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha:raise Incident('QUEUE_EXTERNAL_SHA_DRIFT')
    q=json.loads(raw)
    if q.get('schema')!='QROS_BOUNDED_CONTINUATION_QUEUE_V2_2':raise Incident('BAD_QUEUE_SCHEMA')
    if not q.get('authority',{}).get('base_commit') or not q.get('jobs'):raise Incident('EMPTY_OR_UNPINNED_QUEUE')
    jobs=q['jobs'];ids=[j['id'] for j in jobs]
    if len(set(ids))!=len(ids):raise Incident('DUPLICATE_JOB_ID')
    for i,j in enumerate(jobs):
        if set(j.get('depends_on',[]))-set(ids[:i]):raise Incident('FUTURE_OR_MISSING_DEPENDENCY')
        if not (20<=j.get('hard_route_seconds',0)<=600):raise Incident('UNSAFE_ROUTE_TIMEOUT_POLICY')
        if j.get('max_distinct_routes') not in (1,2):raise Incident('UNSAFE_RETRY_POLICY')
        if j.get('kind') not in ('local','external'):raise Incident('UNKNOWN_JOB_KIND')
    return q

def stage_status(work,plan,pin):
    root=pathlib.Path(work).resolve();p=parse_plan(root,plan,pin)
    if len(p['stages'])!=1:raise Incident('ONE_FROZEN_STAGE_PER_QUEUE_JOB_REQUIRED')
    return p

def snapshot(q):
    rows={}
    for j in q['jobs']:
        p=stage_status(j['work'],j['plan'],j['plan_sha256'])
        if p['authority']!=q['authority']:raise Incident('LANE_AUTHORITY_MIXING')
        if p['stages'][0]['kind']!=j['kind']:raise Incident('JOB_KIND_DRIFT')
        stage=p['stages'][0]
        if j['kind']=='local':
            if stage.get('timeout_seconds',120)>j['hard_route_seconds']:raise Incident('FROZEN_ROUTE_TIMEOUT_EXCEEDS_HARD_BUDGET')
            if len(stage['routes'])>j['max_distinct_routes']:raise Incident('TOO_MANY_ROUTES_NOT_PREREGISTERED')
        root=pathlib.Path(j['work'])
        if not (root/'QROS_ANTI_STALL_STATE_V2_1.json').exists():
            rows[j['id']]={'state':'UNINITIALIZED','stage_id':stage['id']};continue
        s=load_state(root);row=s['stages'][0]
        if s['plan_sha256']!=j['plan_sha256'] or s['authority']!=q['authority']:raise Incident('STATE_AUTHORITY_OR_PLAN_DRIFT')
        # invoke status enforces source/outputs + hash-chain before trusting PASS.
        stat=invoke(root,j['plan'],j['plan_sha256'],'status')
        rows[j['id']]={'state':row['status'],'stage_id':stage['id'],'cursor':stat['cursor'],'tried':list(row['attempted_routes'])}
    return rows

def dispatch(queue_file,expected_sha,overall_budget=180):
    q=queue_load(queue_file,expected_sha)
    if overall_budget<1 or overall_budget>1800:raise Incident('BAD_DISPATCH_BUDGET')
    deadline=time.monotonic()+overall_budget
    lock=pathlib.Path(q['control_root']).resolve()
    with mutex(lock):
        rows=snapshot(q);events=[]
        for j in q['jobs']:
            jid=j['id'];row=rows[jid]
            if row['state']=='PASS':continue
            if any(rows[p]['state']!='PASS' for p in j.get('depends_on',[])):
                events.append({'job':jid,'action':'DEPENDENCY_BLOCKED_SAFE_SKIP'});continue
            if j['kind']=='external':
                events.append({'job':jid,'action':'EXTERNAL_PROOF_REQUIRED_SAFE_SKIP'});continue
            root=j['work'];plan=j['plan'];pin=j['plan_sha256']
            if row['state']=='UNINITIALIZED':
                x=invoke(root,plan,pin,'init');events.append({'job':jid,'action':x['status']})
            elif row['state']=='RUNNING':
                # NO implicit retry after crash; explicit verified-output recovery only.
                events.append({'job':jid,'action':'INTERRUPTED_NEEDS_INDEPENDENT_RECOVERY'});continue
            elif row['state']=='HALTED':
                events.append({'job':jid,'action':'HALTED_NO_RELAUNCH'});continue
            attempts=0
            while time.monotonic()<deadline and attempts<j['max_distinct_routes']:
                stage=stage_status(root,plan,pin)['stages'][0]
                if deadline-time.monotonic()<stage.get('timeout_seconds',120)+2:
                    events.append({'job':jid,'action':'BUDGET_EXHAUSTED_SAFE_DEFER'});break
                res=invoke(root,plan,pin,'run');events.append({'job':jid,'action':res['status'],'details':res})
                attempts+=1
                if res['status']=='ONE_STAGE_PASS':
                    rows[jid]['state']='PASS'
                    result={'status':'ONE_VERIFIED_STAGE_PASS','job':jid,'events':events,'next':next((k['id'] for k in q['jobs'] if k['id']!=jid and rows.get(k['id'],{}).get('state')!='PASS'),None)}
                    atomic_json(lock/'QROS_CONTINUATION_LAST_RECEIPT_V22_V3_SINGLE_OWNER_CANDIDATE.json',result)
                    return result
                if res['status']!='FAILED_ROUTE_SWITCH_REQUIRED':break
            rows[jid]['state']='DEFERRED'  # never pretend prerequisite passed
        result={'status':'NO_STAGE_PROMOTED_SAFE_DEFER','events':events,'blocked_jobs':[k for k,v in rows.items() if v['state']!='PASS']}
        atomic_json(lock/'QROS_CONTINUATION_LAST_RECEIPT_V22_V3_SINGLE_OWNER_CANDIDATE.json',result)
        return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--queue',required=True);ap.add_argument('--expected-queue-sha256',required=True);ap.add_argument('--budget-seconds',type=float,default=180);a=ap.parse_args()
    try:print(json.dumps(dispatch(a.queue,a.expected_queue_sha256,a.budget_seconds),sort_keys=True))
    except Exception as e:print(json.dumps({'status':'FAIL_CLOSED','error':str(e)},sort_keys=True),file=sys.stderr);raise SystemExit(3)
if __name__=='__main__':main()
