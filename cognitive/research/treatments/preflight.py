"""Matched-treatment checks. A software PASS is not a model benchmark result."""
from cognitive import runtime as v
ARMS={'SOL_BASELINE','SOL_QROS_PROTOCOL_V191','SOL_QRCEL','ASTRA_BASELINE','ASTRA_QROS_PROTOCOL_V191','ASTRA_QRCEL'}
MATCHED=('task_set_sha256','scorer_sha256','toolset_sha256','resource_envelope','data_access_sha256')
def check(protocol,expected_sha,confirmatory=False):
    v.require(v.sha256(v.canonical(protocol))==expected_sha,'PROTOCOL_ANCHOR_MISMATCH')
    v.require(protocol.get('schema')=='QRCEL_MATCHED_TREATMENT_PROTOCOL_V1','PROTOCOL_SCHEMA')
    rows=protocol.get('arms');v.require(isinstance(rows,list) and len(rows)==6,'ARM_COUNT')
    v.require(all(isinstance(r,dict) for r in rows),'ARM_SCHEMA')
    v.require({r.get('id') for r in rows}==ARMS,'ARM_IDENTITIES')
    for row in rows:
        for key in ('task_set_sha256','scorer_sha256','toolset_sha256','data_access_sha256','prompt_sha256'):v.require_hash(row.get(key))
        budget=row.get('resource_envelope');v.require(isinstance(budget,dict) and set(budget)=={'max_tool_calls','max_output_tokens','max_wall_seconds'},'RESOURCE_SCHEMA')
        v.require(all(type(n) is int and n>0 for n in budget.values()),'RESOURCE_VALUES')
        v.require(row.get('requested_route')==('gpt-5.6-sol' if row['id'].startswith('SOL_') else 'gpt-6-astra'),'ROUTE_ASSIGNMENT')
        for key in MATCHED:v.require(row[key]==rows[0][key],'UNMATCHED_'+key.upper())
    for suffix in ('BASELINE','QROS_PROTOCOL_V191','QRCEL'):
        pair=[r for r in rows if r['id'] in {'SOL_'+suffix,'ASTRA_'+suffix}]
        v.require(pair[0]['prompt_sha256']==pair[1]['prompt_sha256'],'UNMATCHED_MODEL_CONTEXT')
    v.require(protocol.get('sealed') is False,'SEALED_REQUIRES_SEPARATE_CUSTODIAN_PROTOCOL')
    limitations=['Protocol instruction effects only; not full CURRENT_QROS implementation','Requested aliases do not attest immutable model revisions','Declared tool/resource limits require host observations']
    if confirmatory:raise v.ContractError('CONFIRMATORY_EVIDENCE_NOT_ESTABLISHED')
    return {'status':'READY_PROTOCOL_DEVELOPMENT_ONLY','arms':6,'new_model_calls':0,'full_current_qros_comparison':False,'parity_claim_allowed':False,'limitations':limitations}
