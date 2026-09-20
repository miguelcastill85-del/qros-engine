"""Experimental deterministic task kernel, not a model or scientific dispatcher."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import time
import uuid
from fractions import Fraction
from pathlib import Path

from . import runtime as v
from . import goal_contract as goals
from .verify_release import verify as verify_release

SCHEMA='QRCEL_LOCAL_TASK_PLAN_V1'
CLAIMS={'VERIFIED','SUPPORTED','INFERENCE','HYPOTHESIS','UNKNOWN','BLOCKED'}


def source_identity():
    return {p.name:v.sha256(p.read_bytes()) for p in (Path(__file__),Path(v.__file__),Path(goals.__file__))}


def number(x):
    v.require(type(x) in (int,str),'NUMBER_TYPE')
    text=str(x)
    v.require(len(text)<=130 and re.fullmatch(r'-?[0-9]{1,64}(?:/[1-9][0-9]{0,63})?',text) is not None,'NUMBER_FORMAT')
    try:return Fraction(text)
    except (ValueError,ZeroDivisionError) as e:raise v.ContractError('NUMBER_VALUE') from e


def route(task):
    risk=task['risk']
    levels={'LOW':'L0','NORMAL':'L1','IMPORTANT':'L2','SCIENTIFIC':'L3'}
    v.require(isinstance(risk,str) and risk in levels,'RISK_UNKNOWN')
    return levels[risk], 'FROZEN_HOST_RISK_'+risk


def validate_plan(plan):
    v.require(len(v.canonical(plan))<=1024*1024,'PLAN_SIZE_LIMIT')
    v.require(isinstance(plan,dict) and set(plan)=={'schema','scope','tasks'},'PLAN_SCHEMA')
    v.require(plan['schema']==SCHEMA and plan['scope']=='NON_SCIENTIFIC_LOCAL','PLAN_SCOPE')
    tasks=plan['tasks'];v.require(isinstance(tasks,list) and 0<len(tasks)<=100,'TASK_LIMIT')
    fields={'task_id','parent_ids','objective','operation','inputs','inputs_sha256','risk'}
    nodes=[]
    for t in tasks:
        v.require(isinstance(t,dict) and set(t)==fields,'TASK_SCHEMA')
        for k in ('task_id','objective'):v.nonempty(t[k],k)
        v.require(len(t['task_id'])<=128 and len(t['objective'])<=4096,'TASK_TEXT_LIMIT')
        v.require(t['operation'] in ('EXACT_SUM','CHECK_DAG'),'OPERATION_NOT_ALLOWED')
        v.require(isinstance(t['inputs'],dict),'INPUT_SCHEMA')
        v.require_hash(t['inputs_sha256'])
        v.require(v.sha256(v.canonical(t['inputs']))==t['inputs_sha256'],'INPUT_HASH_MISMATCH')
        route(t)
        if t['operation']=='EXACT_SUM':
            v.require(set(t['inputs'])=={'numbers','include_parent_sums'},'SUM_SCHEMA')
            nums=t['inputs']['numbers'];v.require(isinstance(nums,list) and len(nums)<=128,'NUMBER_LIMIT')
            for x in nums:number(x)
            v.require(type(t['inputs']['include_parent_sums']) is bool,'SUM_PARENT_FLAG')
        else:
            v.require(set(t['inputs'])=={'nodes'},'DAG_INPUT_SCHEMA')
            v.require(isinstance(t['inputs']['nodes'],list) and len(t['inputs']['nodes'])<=100,'DAG_LIMIT')
        nodes.append({'item_id':t['task_id'],'prerequisites':t['parent_ids']})
    return v.check_dag(nodes)


def fraction_oracle(values):
    # Independent representation: common denominator integer arithmetic.
    denominator=math.lcm(*(n.denominator for n in values)) if values else 1
    numerator=sum(n.numerator*(denominator//n.denominator) for n in values)
    return Fraction(numerator,denominator)


def bounded_fraction(value):
    v.require(value.numerator.bit_length()<=2048 and value.denominator.bit_length()<=2048,'FRACTION_RESOURCE_LIMIT')
    return value


def dag_oracle(nodes):
    # DFS cycle criterion, independent of runtime.check_dag's Kahn procedure.
    graph={n['item_id']:n['prerequisites'] for n in nodes}
    color={}
    def visit(node):
        if color.get(node)==1:raise v.ContractError('ORACLE_CYCLE')
        if color.get(node)==2:return
        color[node]=1
        for dep in graph[node]:visit(dep)
        color[node]=2
    for node in graph:visit(node)
    return True


def _evaluate(task,parents):
    level,reason=route(task)
    v.require(level!='L3','SCIENTIFIC_GATES_NOT_SATISFIED')
    evidence={'level':level,'routing_reason':reason,'independent_verification':False,'bounded_falsification':False}
    if task['operation']=='EXACT_SUM':
        values=[number(x) for x in task['inputs']['numbers']]
        if task['inputs']['include_parent_sums']:
            for p in parents:
                v.require(set(p)=={'fraction'},'PARENT_OUTPUT_TYPE')
                values.append(Fraction(p['fraction']))
        answer=Fraction(0)
        for value in values:answer=bounded_fraction(answer+value)
        if level in ('L1','L2'):
            oracle=fraction_oracle(values)
            v.require(answer==oracle,'INDEPENDENT_VERIFIER_FAILED')
            evidence['independent_verification']=True
        if level=='L2':
            v.require(bool(values),'EMPTY_FALSIFIER_DOMAIN')
            for i,x in enumerate(values):
                v.require(fraction_oracle(values[:i]+values[i+1:])==answer-x,'FALSIFICATION_FAILED')
            evidence.update(bounded_falsification=True,fault_model='every_single_operand_deletion',falsifier_probes=len(values))
        output={'fraction':str(answer)}
    else:
        nodes=task['inputs']['nodes']
        output={'order':v.check_dag(nodes)}
        if level in ('L1','L2'):
            dag_oracle(nodes);evidence['independent_verification']=True
        if level=='L2':
            v.require(bool(nodes),'EMPTY_FALSIFIER_DOMAIN')
            for node in nodes:
                bad=[{'item_id':n['item_id'],'prerequisites':list(n['prerequisites'])} for n in nodes]
                next(n for n in bad if n['item_id']==node['item_id'])['prerequisites'].append(node['item_id'])
                try:dag_oracle(bad)
                except v.ContractError:pass
                else:raise v.ContractError('FALSIFIER_ACCEPTED_SELF_CYCLE')
            evidence.update(bounded_falsification=True,fault_model='self_cycle_at_every_node',falsifier_probes=len(nodes))
    evidence['claim_status']='VERIFIED' if level!='L0' else 'SUPPORTED'
    evidence['predicate_scope']='EXACT_LOCAL_OPERATION_ONLY'
    evidence['scientific_effect_authorized']=False
    return output,evidence


def execute(task,parents):
    """Dispatch one new local task. Validation of stored results is separate."""
    return _evaluate(task,parents)


def open_store(path: Path, startup_timeout: float = 2.0):
    """SQLite journal-mode changes can return BUSY without waiting for busy_timeout."""
    v.require(type(startup_timeout) in (int,float) and 0 < startup_timeout <= 2, 'STARTUP_TIMEOUT')
    db=sqlite3.connect(path,timeout=min(startup_timeout,0.05),isolation_level=None)
    try:
        db.execute('PRAGMA trusted_schema=OFF')
        deadline=time.monotonic()+startup_timeout
        while True:
            try:
                row=db.execute('PRAGMA journal_mode=WAL').fetchone()
                v.require(row==('wal',),'STORE_WAL_UNAVAILABLE')
                break
            except sqlite3.OperationalError as exc:
                code=getattr(exc,'sqlite_errorcode',None)
                if code is None or (code & 255) != sqlite3.SQLITE_BUSY:raise
                remaining=deadline-time.monotonic()
                if remaining <= 0:raise v.ContractError('STORE_STARTUP_BUSY') from exc
                time.sleep(min(0.01,remaining))
        db.execute('PRAGMA busy_timeout=2000')
        db.execute('PRAGMA synchronous=FULL')
        return db
    except Exception:
        db.close()
        raise


class Kernel:
    def __init__(self,repo:Path,plan:dict,plan_sha:str,authority_blob:str,run_id:str,expected_resume_anchor=None,
                 *,goal_contract=None,goal_sha256=None,goal_mapping=None):
        self.repo=repo.resolve();self.plan=v.parse_json(v.canonical(plan));self.order=validate_plan(self.plan)
        v.require_hash(plan_sha);v.require(v.sha256(v.canonical(plan))==plan_sha,'PLAN_ANCHOR_MISMATCH')
        v.require(isinstance(run_id,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}',run_id),'RUN_ID')
        self.authority=authority_blob;self.observe()
        self.binding={'plan_sha256':plan_sha,'authority_manifest_blob_sha1':authority_blob,'source_sha256':source_identity()}
        supplied=(goal_contract is not None,goal_sha256 is not None,goal_mapping is not None)
        v.require(all(supplied) or not any(supplied),'GOAL_ARGUMENTS_INCOMPLETE')
        self.goal_contract=v.parse_json(v.canonical(goal_contract)) if all(supplied) else None
        self.goal_mapping=v.parse_json(v.canonical(goal_mapping)) if all(supplied) else None
        self.goal_sha256=goal_sha256
        self.goal_binding=goals.bind(self.goal_contract,goal_sha256,self.plan,self.goal_mapping) if all(supplied) else None
        if self.goal_binding is not None:self.binding['goal_binding']=self.goal_binding
        self.tasks={t['task_id']:t for t in self.plan['tasks']}
        self.expected_resume_anchor=v.parse_json(v.canonical(expected_resume_anchor)) if expected_resume_anchor is not None else None
        self._verified_results={}
        self.semantic_revalidations=0
        base=self.repo/'cognitive'
        v.require(base.is_dir() and not base.is_symlink(),'KERNEL_NAMESPACE_UNSAFE')
        for part in ('runs',run_id):
            base=base/part
            v.require(not base.is_symlink(),'KERNEL_NAMESPACE_UNSAFE')
            base.mkdir(exist_ok=True)
        self.directory=base
        for name in ('state.sqlite','state.sqlite-wal','state.sqlite-shm','checkpoint.json','checkpoint.json.partial'):
            v.require(not (base/name).is_symlink(),'KERNEL_NAMESPACE_UNSAFE')
        self.db=open_store(base/'state.sqlite')
        try:
            self.db.execute('BEGIN IMMEDIATE')
            self.db.execute('CREATE TABLE IF NOT EXISTS meta(binding BLOB NOT NULL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS completed(id TEXT PRIMARY KEY, output BLOB NOT NULL, digest TEXT NOT NULL, evidence BLOB NOT NULL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, payload BLOB NOT NULL, digest TEXT NOT NULL)')
            rows=self.db.execute('SELECT binding FROM meta').fetchall()
            if not rows:
                v.require(not self.db.execute('SELECT 1 FROM completed LIMIT 1').fetchall() and not self.db.execute('SELECT 1 FROM events LIMIT 1').fetchall(),'STORE_METADATA_MISSING')
                self.db.execute('INSERT INTO meta VALUES (?)',(v.canonical(self.binding),))
            else:v.require(rows==[(v.canonical(self.binding),)],'RUN_BINDING_MISMATCH')
            self.db.commit()
        except Exception:self.db.rollback();self.db.close();raise
        # Actual local SQLite transaction and directory access have just occurred.
        self.capability={'session_id':str(uuid.uuid4()),'observed_at_ns':time.time_ns(),'pid':os.getpid(),
                         'sqlite_version':sqlite3.sqlite_version,'local_transaction_observed':True,
                         'operations':['EXACT_SUM','CHECK_DAG'],'model_calls_available':False,
                         'inheritable':False,'scientific_dispatch':False}

    def observe(self):
        snapshot=v.Snapshot(self.repo)
        observation=v.observe_authority(snapshot,self.authority)
        v.require(observation.manifest['authority_epoch'] in (189,191), 'UNSUPPORTED_KERNEL_AUTHORITY_EPOCH')
        if observation.manifest['authority_epoch']==191:
            v.inspect_control_bootstrap(snapshot,self.authority)
        return observation

    def close(self):self.db.close()

    def rows(self,verify_semantics=True):
        result={}
        for identity,raw,h,evidence in self.db.execute('SELECT id,output,digest,evidence FROM completed ORDER BY id'):
            v.require(identity in self.tasks,'UNKNOWN_COMPLETED_TASK')
            v.require(v.sha256(raw)==h,'OUTPUT_INTEGRITY_FAILED')
            e=v.parse_json(evidence);level,reason=route(self.tasks[identity])
            v.require(level!='L3' and e.get('claim_status')==('SUPPORTED' if level=='L0' else 'VERIFIED'),'CLAIM_STATUS')
            v.require(e.get('level')==level and e.get('routing_reason')==reason and e.get('scientific_effect_authorized') is False,'EVIDENCE_SCOPE')
            v.require(e.get('independent_verification') is (level in ('L1','L2')) and e.get('bounded_falsification') is (level=='L2'),'EVIDENCE_DEPTH_MISMATCH')
            result[identity]={'output':v.parse_json(raw),'sha256':h,'evidence':e}
        for identity in result:
            v.require(set(self.tasks[identity]['parent_ids'])<=set(result),'IMPOSSIBLE_COMPLETION')
        if verify_semantics:self._revalidate_results(result)
        return result

    def _revalidate_results(self,result):
        # Self-consistent hashes cannot authenticate rewritten local state. Recheck
        # the actual pure predicate before returning any stored claim to callers.
        for identity in self.order:
            if identity not in result:continue
            task=self.tasks[identity];row=result[identity]
            key=v.sha256(v.canonical({'task':task,'row':row,'parents':[result[p]['sha256'] for p in task['parent_ids']]}))
            if self._verified_results.get(identity)!=key:
                expected,evidence=_evaluate(task,[result[p]['output'] for p in task['parent_ids']])
                v.require(row['output']==expected and row['evidence']==evidence,'PERSISTED_RESULT_SEMANTIC_MISMATCH')
                self._verified_results[identity]=key
                self.semantic_revalidations+=1

    def event(self,payload):
        previous=self.db.execute('SELECT seq,digest FROM events ORDER BY seq DESC LIMIT 1').fetchone()
        seq=previous[0]+1 if previous else 0;v.require(seq<10000,'LEDGER_LIMIT')
        envelope={'seq':seq,'previous':previous[1] if previous else None,'event':payload}
        raw=v.canonical(envelope);self.db.execute('INSERT INTO events VALUES (?,?,?)',(seq,raw,v.sha256(raw)))

    def ledger(self):
        rows=[];previous=None
        for seq,raw,h in self.db.execute('SELECT seq,payload,digest FROM events ORDER BY seq'):
            item=v.parse_json(raw)
            v.require(seq==len(rows) and item.get('seq')==seq and item.get('previous')==previous and v.sha256(raw)==h,'LEDGER_INTEGRITY_FAILED')
            rows.append({'payload':item,'sha256':h});previous=h
        return rows

    def integrity(self):
        v.require(self.db.execute('SELECT binding FROM meta').fetchall()==[(v.canonical(self.binding),)],'RUN_BINDING_MISMATCH')
        v.require(v.sha256(v.canonical(self.plan))==self.binding['plan_sha256'] and source_identity()==self.binding['source_sha256'],'RUN_INPUT_OR_CODE_CHANGED')
        if self.goal_contract is not None:
            v.require(goals.bind(self.goal_contract,self.goal_sha256,self.plan,self.goal_mapping)==self.binding.get('goal_binding'),'GOAL_BINDING_CHANGED')
        rows=self.rows(verify_semantics=False);events=self.ledger();started=set();finished={}
        if self.expected_resume_anchor is not None:
            anchor=self.expected_resume_anchor
            v.require(set(anchor)=={'schema','binding_sha256','event_count','head_sha256'} and anchor['schema']=='QRCEL_RESUME_ANCHOR_V1','RESUME_ANCHOR_SCHEMA')
            v.require(anchor['binding_sha256']==v.sha256(v.canonical(self.binding)),'RESUME_ANCHOR_BINDING')
            n=anchor['event_count'];v.require(type(n) is int and 0<=n<=10000,'RESUME_ANCHOR_COUNT')
            v.require(len(events)>=n,'STATE_ROLLBACK_DETECTED')
            v.require((events[n-1]['sha256'] if n else None)==anchor['head_sha256'],'STATE_HISTORY_REWRITTEN')
        for row in events:
            event=row['payload'].get('event');v.require(isinstance(event,dict),'EVENT_SCHEMA')
            identity=event.get('task_id');v.require(isinstance(identity,str) and identity in self.tasks,'EVENT_TASK_UNKNOWN')
            if event.get('type')=='START':
                capability=event.get('capability')
                v.require(isinstance(capability,dict) and type(capability.get('observed_at_ns')) is int and capability.get('inheritable') is False,'CAPABILITY_RECEIPT_INVALID')
                v.require(identity not in started,'DUPLICATE_START');started.add(identity)
            elif event.get('type')=='COMPLETE':
                v.require(identity in started and identity not in finished,'INVALID_COMPLETION_EVENT')
                finished[identity]=event
            else:v.require(event.get('type') in ('BLOCKED','ERROR'),'EVENT_TYPE')
        v.require(set(rows)==set(finished)==started,'OUTPUT_LEDGER_MISMATCH')
        for identity,row in rows.items():
            event=finished[identity]
            v.require(event.get('output_sha256')==row['sha256'] and event.get('evidence_sha256')==v.sha256(v.canonical(row['evidence'])),'OUTPUT_LEDGER_MISMATCH')
        self._revalidate_results(rows)
        return rows,events

    def resume_anchor(self):
        _,events=self.integrity()
        return {'schema':'QRCEL_RESUME_ANCHOR_V1','binding_sha256':v.sha256(v.canonical(self.binding)),
                'event_count':len(events),'head_sha256':events[-1]['sha256'] if events else None}

    def event_once(self,payload):
        if not any(r['payload']['event']==payload for r in self.ledger()):self.event(payload)

    def graphs(self,completed,ledger):
        tasks=[];claims=[]
        starts={r['payload']['event']['task_id']:r['payload']['event'] for r in ledger if r['payload']['event']['type']=='START'}
        failed={r['payload']['event']['task_id'] for r in ledger if r['payload']['event']['type']=='ERROR'}
        for identity in self.order:
            t=self.tasks[identity];level,reason=route(t)
            status='COMPLETED' if identity in completed else 'INVALID' if identity in failed else 'BLOCKED' if level=='L3' else 'READY' if set(t['parent_ids'])<=set(completed) else 'WAITING_PREREQUISITE'
            tasks.append({'TASK_ID':identity,'PARENT_IDS':t['parent_ids'],'OBJECTIVE':t['objective'],
                'INPUTS':t['inputs'],'INPUT_HASHES':{'own':t['inputs_sha256'],'parents':{p:completed[p]['sha256'] for p in t['parent_ids'] if p in completed}},
                'PRECONDITIONS':['AUTHORITY_IDENTITY_MATCH','ALL_PARENTS_COMPLETE','LOCAL_ONLY_SCOPE','L3_GATES_REQUIRED_IF_SCIENTIFIC'],
                'EXPECTED_OUTPUT':'exact rational sum' if t['operation']=='EXACT_SUM' else 'valid topological order',
                'EVIDENCE_REQUIRED':['output_digest']+(['independent_oracle'] if level in ('L1','L2') else [])+(['bounded_falsifier'] if level=='L2' else []),
                'EXECUTOR':'cognitive.kernel.execute','VERIFIER':'common_denominator_oracle' if t['operation']=='EXACT_SUM' else 'DFS_cycle_oracle',
                'STATUS':status,'DEPTH':level,'ROUTING_REASON':reason})
            if identity in completed:
                row=completed[identity];escaped=identity.replace('~','~0').replace('/','~1')
                claims.append({'CLAIM_ID':'CLAIM_'+v.sha256(identity.encode())[:24],'CLAIM':'Output satisfies '+t['operation']+' on the bound inputs','USER_OBJECTIVE':t['objective'],
                    'STATUS':row['evidence']['claim_status'],'EVIDENCE_POINTER':'#/completed/'+escaped+'/evidence',
                    'SOURCE_IDENTITY':identity,'SOURCE_HASH':row['sha256'],
                    'OBSERVED_AT':starts[identity]['capability']['observed_at_ns'],'VERIFIER':tasks[-1]['VERIFIER'] if level!='L0' else 'MINIMAL_OUTPUT_CHECK',
                    'SCOPE':'EXACT_LOCAL_OPERATION_ONLY_NOT_THE_FREE_TEXT_OBJECTIVE'})
        return tasks,claims

    def checkpoint(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            completed,ledger=self.integrity()
            tasks,claims=self.graphs(completed,ledger)
            value={'schema':'QRCEL_KERNEL_CHECKPOINT_V1','binding':self.binding,'plan':self.plan,
                   'goal_contract':self.goal_contract,'goal_mapping':self.goal_mapping,
                   'completed':completed,'ledger':ledger,'task_graph':tasks,'evidence_graph':claims,'scientific_effect_authorized':False}
            raw=v.canonical(value);temp=self.directory/'checkpoint.json.partial'
            v.require(len(raw)<=4*1024*1024,'CHECKPOINT_SIZE_LIMIT')
            v.require(not temp.is_symlink(),'KERNEL_NAMESPACE_UNSAFE')
            with temp.open('wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
            os.replace(temp,self.directory/'checkpoint.json')
            fd=os.open(self.directory,os.O_DIRECTORY|os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
            self.db.commit()
        except Exception:self.db.rollback();raise
        return v.sha256(raw)

    def restore(self,raw,expected_sha):
        v.require_hash(expected_sha);v.require(v.sha256(raw)==expected_sha,'CHECKPOINT_ANCHOR_MISMATCH')
        cp=v.parse_json(raw)
        v.require(cp.get('schema')=='QRCEL_KERNEL_CHECKPOINT_V1' and cp.get('binding')==self.binding and cp.get('plan')==self.plan,'CHECKPOINT_BINDING_MISMATCH')
        v.require(cp.get('goal_contract')==self.goal_contract and cp.get('goal_mapping')==self.goal_mapping,'CHECKPOINT_GOAL_MISMATCH')
        v.require(cp.get('scientific_effect_authorized') is False,'CHECKPOINT_SCOPE')
        v.require(isinstance(cp.get('completed'),dict) and isinstance(cp.get('ledger'),list),'CHECKPOINT_SCHEMA')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            v.require(not self.rows() and not self.ledger(),'RESTORE_REQUIRES_EMPTY_TARGET')
            for identity,row in cp['completed'].items():
                v.require(isinstance(row,dict) and set(row)=={'output','sha256','evidence'},'CHECKPOINT_ROW_SCHEMA')
                self.db.execute('INSERT INTO completed VALUES (?,?,?,?)',(identity,v.canonical(row['output']),row['sha256'],v.canonical(row['evidence'])))
            for row in cp['ledger']:
                v.require(isinstance(row,dict) and set(row)=={'payload','sha256'} and isinstance(row['payload'],dict) and type(row['payload'].get('seq')) is int,'CHECKPOINT_EVENT_SCHEMA')
                self.db.execute('INSERT INTO events VALUES (?,?,?)',(row['payload']['seq'],v.canonical(row['payload']),row['sha256']))
            completed,ledger=self.integrity();tasks,claims=self.graphs(completed,ledger)
            v.require(cp.get('task_graph')==tasks and cp.get('evidence_graph')==claims,'CHECKPOINT_DERIVED_GRAPH_MISMATCH')
            self.observe();self.db.commit()
        except Exception:self.db.rollback();raise
        self.checkpoint()

    def run(self,fault=None):
        newly_completed=0;blocked=[];errors=[]
        for identity in self.order:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                self.observe();completed,ledger=self.integrity()
                if identity in completed:self.db.rollback();continue
                prior_error=next((r['payload']['event'] for r in ledger if r['payload']['event']['type']=='ERROR' and r['payload']['event']['task_id']==identity),None)
                if prior_error:
                    self.db.rollback();errors.append({'task_id':identity,'error':prior_error['error']});continue
                task=self.tasks[identity];level,reason=route(task)
                if level=='L3' or not set(task['parent_ids'])<=set(completed):
                    self.event_once({'type':'BLOCKED','task_id':identity,'reason':'SCIENTIFIC_GATES_NOT_SATISFIED' if level=='L3' else 'PARENT_BLOCKED','level':level})
                    self.db.commit();blocked.append(identity);continue
                self.event({'type':'START','task_id':identity,'level':level,'routing_reason':reason,'capability':self.capability})
                try:output,evidence=execute(task,[completed[p]['output'] for p in task['parent_ids']])
                except v.ContractError as error:
                    self.db.rollback();self.db.execute('BEGIN IMMEDIATE');self.integrity()
                    self.event_once({'type':'ERROR','task_id':identity,'error':error.code,'fix_status':'UNFIXED'})
                    self.db.commit();errors.append({'task_id':identity,'error':error.code});continue
                raw=v.canonical(output)
                self.db.execute('INSERT INTO completed VALUES (?,?,?,?)',(identity,raw,v.sha256(raw),v.canonical(evidence)))
                self.event({'type':'COMPLETE','task_id':identity,'output_sha256':v.sha256(raw),'evidence_sha256':v.sha256(v.canonical(evidence)),'claim_status':evidence['claim_status']})
                if fault==('BEFORE',identity):os._exit(75)
                self.observe();self.db.commit();newly_completed+=1
                if fault==('AFTER',identity):os._exit(75)
            except Exception:
                self.db.rollback();raise
        checkpoint_sha=self.checkpoint()
        return {'schema':'QRCEL_KERNEL_RUN_RECEIPT_V1','status':'BLOCKED' if blocked or errors else 'COMPLETED_LOCAL_TASKS',
                'completed_tasks':len(self.rows()),'newly_completed':newly_completed,'blocked':blocked,
                'errors':errors,
                'checkpoint_sha256':checkpoint_sha,'capability':self.capability,
                'resume_anchor':self.resume_anchor(),
                'history_authentication':'EXTERNAL_PREFIX_VERIFIED' if self.expected_resume_anchor is not None else 'UNATTESTED_LOCAL_HISTORY',
                'persisted_results_semantically_revalidated':True,
                'semantic_revalidations_this_instance':self.semantic_revalidations,
                'goal_completion':goals.completion(self.goal_binding,self.rows()),
                'scientific_effect_authorized':False,'background_running':False,'model_calls':0}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo-root',type=Path,required=True)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--plan-sha256',required=True)
    p.add_argument('--authority-blob',required=True);p.add_argument('--release-blob',required=True);p.add_argument('--run-id',required=True)
    p.add_argument('--restore',type=Path);p.add_argument('--checkpoint-sha256')
    p.add_argument('--resume-anchor',type=Path);p.add_argument('--resume-anchor-sha256')
    p.add_argument('--goal-contract',type=Path);p.add_argument('--goal-sha256');p.add_argument('--goal-mapping',type=Path)
    a=p.parse_args();kernel=None
    try:
        verify_release(a.repo_root,a.release_blob)
        plan=v.parse_json(v.Snapshot(a.plan.parent).read(a.plan.name))
        anchor=None
        v.require((a.resume_anchor is None)==(a.resume_anchor_sha256 is None),'RESUME_ANCHOR_ARGUMENTS')
        if a.resume_anchor:
            raw=v.Snapshot(a.resume_anchor.parent).read(a.resume_anchor.name)
            v.require_hash(a.resume_anchor_sha256)
            v.require(v.sha256(raw)==a.resume_anchor_sha256,'RESUME_ANCHOR_HASH_MISMATCH')
            anchor=v.parse_json(raw)
        goal=v.parse_json(v.Snapshot(a.goal_contract.parent).read(a.goal_contract.name)) if a.goal_contract else None
        mapping=v.parse_json(v.Snapshot(a.goal_mapping.parent).read(a.goal_mapping.name)) if a.goal_mapping else None
        kernel=Kernel(a.repo_root,plan,a.plan_sha256,a.authority_blob,a.run_id,expected_resume_anchor=anchor,
                      goal_contract=goal,goal_sha256=a.goal_sha256,goal_mapping=mapping)
        if a.restore:
            v.require(a.checkpoint_sha256 is not None,'RESTORE_ANCHOR_REQUIRED')
            kernel.restore(v.Snapshot(a.restore.parent).read(a.restore.name),a.checkpoint_sha256)
        result=kernel.run()
    except (v.ContractError,sqlite3.DatabaseError,OSError) as error:
        result={'status':'FAIL_CLOSED','error':str(error),'scientific_effect_authorized':False,'model_calls':0}
    finally:
        if kernel is not None:kernel.close()
    print(json.dumps(result,sort_keys=True));return 0 if result['status']=='COMPLETED_LOCAL_TASKS' else 2


if __name__=='__main__':raise SystemExit(main())
