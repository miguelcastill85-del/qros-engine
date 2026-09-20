"""Finite, externally anchored requirement coverage. No natural-language oracle."""
from . import runtime as v

SCHEMA='QRCEL_EXPLICIT_GOAL_CONTRACT_V1'
RISK={'LOW':0,'NORMAL':1,'IMPORTANT':2,'SCIENTIFIC':3}

def bind(contract,expected_sha,plan,mapping):
    """Require one explicit witness task per requirement, with exact dependencies.

    The caller must independently freeze a complete requirement specification.
    This checks preservation of that specification, not its real-world adequacy.
    Kernel.validate_plan is also required before executing the resulting plan.
    """
    v.require_hash(expected_sha)
    raw=v.canonical(contract);v.require(len(raw)<=1024*1024,'GOAL_SIZE_LIMIT')
    v.require(v.sha256(raw)==expected_sha,'GOAL_ANCHOR_MISMATCH')
    v.require(isinstance(contract,dict) and set(contract)=={'schema','scope','goal_id','description','requirements'},'GOAL_SCHEMA')
    v.require(contract['schema']==SCHEMA and contract['scope']=='EXPLICIT_LOCAL_REQUIREMENTS_ONLY','GOAL_SCOPE')
    for name,limit in [('goal_id',128),('description',16000)]:
        v.nonempty(contract[name],name);v.require(len(contract[name])<=limit,'GOAL_TEXT_LIMIT')
    requirements=contract['requirements']
    v.require(isinstance(requirements,list) and 0<len(requirements)<=100,'GOAL_REQUIREMENT_LIMIT')
    required={}
    for req in requirements:
        v.require(isinstance(req,dict) and set(req)=={'id','operation','inputs_sha256','parent_ids','minimum_risk'},'GOAL_REQUIREMENT_SCHEMA')
        v.nonempty(req['id'],'requirement_id')
        v.require(len(req['id'])<=128 and req['id'] not in required,'GOAL_DUPLICATE_REQUIREMENT')
        v.require(req['operation'] in ('EXACT_SUM','CHECK_DAG'),'GOAL_OPERATION')
        v.require_hash(req['inputs_sha256'])
        v.require(isinstance(req['minimum_risk'],str) and req['minimum_risk'] in RISK,'GOAL_RISK')
        required[req['id']]=req
    v.check_dag([{'item_id':r['id'],'prerequisites':r['parent_ids']} for r in requirements])
    v.require(isinstance(mapping,dict) and set(mapping)==set(required),'GOAL_MAPPING_COVERAGE')
    v.require(all(isinstance(x,str) for x in mapping.values()),'GOAL_MAPPING_TYPE')
    v.require(len(set(mapping.values()))==len(mapping),'GOAL_WITNESS_REUSED')
    tasks={t['task_id']:t for t in plan['tasks']}
    v.require(len(tasks)==len(plan['tasks']) and set(mapping.values())==set(tasks),'GOAL_TASK_COVERAGE')
    for identity,req in required.items():
        task=tasks[mapping[identity]]
        v.require(task['operation']==req['operation'] and task['inputs_sha256']==req['inputs_sha256'],
                  'GOAL_PREDICATE_MISMATCH',identity)
        v.require(set(task['parent_ids'])=={mapping[p] for p in req['parent_ids']},'GOAL_DEPENDENCY_MISMATCH',identity)
        v.require(task['risk'] in RISK and RISK[task['risk']]>=RISK[req['minimum_risk']],'GOAL_DEPTH_DOWNGRADE',identity)
    return {'schema':'QRCEL_GOAL_BINDING_V1','goal_sha256':expected_sha,'mapping':dict(mapping),
            'requirement_count':len(required),'scope':'EXPLICIT_LOCAL_REQUIREMENTS_ONLY',
            'natural_language_adequacy_verified':False,'scientific_effect_authorized':False}

def completion(binding,completed):
    if binding is None:return {'status':'NO_EXPLICIT_GOAL_CONTRACT','natural_language_adequacy_verified':False}
    covered=[r for r,t in binding['mapping'].items() if t in completed]
    pending=sorted(set(binding['mapping'])-set(covered))
    return {'status':'EXPLICIT_REQUIREMENTS_SATISFIED' if not pending else 'EXPLICIT_REQUIREMENTS_PENDING',
            'goal_sha256':binding['goal_sha256'],'covered':sorted(covered),'pending':pending,
            'scope':'EXPLICIT_LOCAL_REQUIREMENTS_ONLY','natural_language_adequacy_verified':False,
            'scientific_effect_authorized':False}
