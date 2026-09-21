from __future__ import annotations
import hashlib,json,struct
from pathlib import Path
from typing import Any,Callable
from qros_typed_action import canonical_bytes, action_key
from qros_factor_ir_store import immutable_publish_bytes

MANIFEST_SCHEMA='QROS_TYPED_DAG_MANIFEST_1.0'
NODE_MAGIC=b'QROS_TYPED_DAG_NODE_V1\n'
NODE_LEN=struct.Struct('>Q')
EXECUTION_CONTRACT='TECHNICAL_ONLY_UNBOUND_MANIFESTS_NOT_SCIENTIFICALLY_ADMISSIBLE'

def _sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def _hex64(v,label):
    if not isinstance(v,str) or len(v)!=64:raise ValueError(label+'_INVALID')
    try:int(v,16)
    except Exception as e:raise ValueError(label+'_INVALID') from e

def normalize_manifest(manifest:dict[str,Any])->dict[str,Any]:
    if not isinstance(manifest,dict) or manifest.get('schema')!=MANIFEST_SCHEMA:raise ValueError('MANIFEST_SCHEMA_INVALID')
    nodes=manifest.get('nodes')
    if not isinstance(nodes,list) or not nodes:raise ValueError('MANIFEST_NODES_REQUIRED')
    out=[];seen=set()
    required=('id','operation','operation_version','code_hashes','domain','parameters','static_inputs','environment','deps')
    for raw in nodes:
        if not isinstance(raw,dict):raise ValueError('NODE_INVALID')
        if set(raw)!=set(required):raise ValueError('NODE_FIELDS_INVALID')
        nid=raw['id']
        if not isinstance(nid,str) or not nid:raise ValueError('NODE_ID_INVALID')
        if nid in seen:raise ValueError('DUPLICATE_NODE_ID')
        seen.add(nid)
        deps=raw['deps']
        if not isinstance(deps,list) or any(not isinstance(x,str) or not x for x in deps):raise ValueError('DEPS_INVALID')
        if len(set(deps))!=len(deps):raise ValueError('DUPLICATE_DEP')
        static=raw['static_inputs']
        if not isinstance(static,dict) or not static:raise ValueError('STATIC_INPUTS_REQUIRED')
        for k,v in static.items():
            if not isinstance(k,str) or not k or not isinstance(v,str):raise ValueError('STATIC_INPUT_INVALID')
            _hex64(v,'STATIC_INPUT_HASH')
        code=raw['code_hashes']
        if not isinstance(code,dict) or not code:raise ValueError('CODE_HASHES_REQUIRED')
        for k,v in code.items():
            if not isinstance(k,str) or not k:raise ValueError('CODE_HASH_LABEL_INVALID')
            _hex64(v,'CODE_HASH')
        if not isinstance(raw['operation'],str) or not raw['operation'] or not isinstance(raw['operation_version'],str) or not raw['operation_version']:raise ValueError('OPERATION_INVALID')
        canonical_bytes(raw['domain']);canonical_bytes(raw['parameters']);canonical_bytes(raw['environment'])
        out.append({'id':nid,'operation':raw['operation'],'operation_version':raw['operation_version'],'code_hashes':dict(sorted(code.items())),'domain':raw['domain'],'parameters':raw['parameters'],'static_inputs':dict(sorted(static.items())),'environment':raw['environment'],'deps':sorted(deps)})
    out.sort(key=lambda x:x['id'])
    ids={n['id'] for n in out}
    for n in out:
        unknown=set(n['deps'])-ids
        if unknown:raise ValueError('MISSING_DEPENDENCY:'+','.join(sorted(unknown)))
        if n['id'] in n['deps']:raise ValueError('SELF_CYCLE:'+n['id'])
    normalized={'schema':MANIFEST_SCHEMA,'nodes':out}
    topological_order(normalized)
    return normalized

def manifest_root(manifest:dict[str,Any])->str:
    return _sha(canonical_bytes(normalize_manifest(manifest)))

def topological_order(normalized_manifest:dict[str,Any])->list[str]:
    nodes={n['id']:n for n in normalized_manifest['nodes']}
    indeg={k:len(v['deps']) for k,v in nodes.items()};children={k:[] for k in nodes}
    for nid,n in nodes.items():
        for d in n['deps']:children[d].append(nid)
    ready=sorted(k for k,v in indeg.items() if v==0);order=[]
    while ready:
        x=ready.pop(0);order.append(x)
        for c in sorted(children[x]):
            indeg[c]-=1
            if indeg[c]==0:
                ready.append(c);ready.sort()
    if len(order)!=len(nodes):raise ValueError('DAG_CYCLE')
    return order

def _node_bytes(action_key_hex:str,action_payload:dict[str,Any],output:bytes)->bytes:
    apsha=_sha(canonical_bytes(action_payload));header={'schema':'QROS_TYPED_DAG_NODE_OBJECT_1.0','action_key':action_key_hex,'action_payload':action_payload,'action_payload_sha256':apsha,'output_sha256':_sha(output),'output_bytes':len(output)}
    hb=canonical_bytes(header);return NODE_MAGIC+NODE_LEN.pack(len(hb))+hb+output

def _read_node(data:bytes,*,expected_action_key:str,expected_payload:dict[str,Any])->tuple[bytes,dict[str,Any]]:
    if not data.startswith(NODE_MAGIC):raise ValueError('NODE_MAGIC_MISMATCH')
    pos=len(NODE_MAGIC)
    if len(data)<pos+NODE_LEN.size:raise ValueError('NODE_TRUNCATED_LENGTH')
    (hlen,)=NODE_LEN.unpack_from(data,pos);pos+=NODE_LEN.size
    if hlen<=0 or hlen>64*1024*1024 or len(data)<pos+hlen:raise ValueError('NODE_HEADER_INVALID')
    hb=data[pos:pos+hlen];pos+=hlen
    try:h=json.loads(hb.decode())
    except Exception as e:raise ValueError('NODE_HEADER_JSON_INVALID') from e
    if canonical_bytes(h)!=hb:raise ValueError('NODE_HEADER_NOT_CANONICAL')
    if h.get('schema')!='QROS_TYPED_DAG_NODE_OBJECT_1.0':raise ValueError('NODE_SCHEMA_MISMATCH')
    if h.get('action_key')!=expected_action_key:raise ValueError('NODE_ACTION_KEY_MISMATCH')
    if h.get('action_payload')!=expected_payload:raise ValueError('NODE_ACTION_PAYLOAD_MISMATCH')
    if _sha(canonical_bytes(expected_payload))!=h.get('action_payload_sha256'):raise ValueError('NODE_ACTION_PAYLOAD_SHA_MISMATCH')
    output=data[pos:]
    if len(output)!=h.get('output_bytes') or _sha(output)!=h.get('output_sha256'):raise ValueError('NODE_OUTPUT_MISMATCH')
    if _sha(canonical_bytes(expected_payload))!=expected_action_key:raise ValueError('EXPECTED_ACTION_KEY_INTERNAL_MISMATCH')
    return output,h

def _build_payload(node:dict[str,Any],results:dict[str,dict[str,Any]])->tuple[str,dict[str,Any]]:
    inputs=dict(node['static_inputs'])
    for d in node['deps']:inputs['dep:'+d]=results[d]['output_sha256']
    return action_key(operation=node['operation'],operation_version=node['operation_version'],code_hashes=node['code_hashes'],domain=node['domain'],parameters=node['parameters'],input_artifacts=inputs,environment=node['environment'])

def execute_manifest(manifest:dict[str,Any],cas_dir:str|Path,operations:dict[str,Callable[[dict[str,Any],dict[str,bytes]],bytes]],*,crash_after_nodes:int|None=None)->dict[str,Any]:
    norm=normalize_manifest(manifest);root=manifest_root(norm);nodes={n['id']:n for n in norm['nodes']};order=topological_order(norm);cas=Path(cas_dir);cas.mkdir(parents=True,exist_ok=True);results={};executed=0;reused=0
    outputs={}
    for nid in order:
        node=nodes[nid];akey,payload=_build_payload(node,results);path=cas/(akey+'.node')
        if path.exists():
            out,h=_read_node(path.read_bytes(),expected_action_key=akey,expected_payload=payload);reused+=1
        else:
            op=operations.get(node['operation'])
            if op is None:raise ValueError('OPERATION_NOT_REGISTERED:'+node['operation'])
            deps={d:outputs[d] for d in node['deps']}
            out=op(payload,deps)
            if not isinstance(out,(bytes,bytearray,memoryview)):raise ValueError('OPERATION_OUTPUT_NOT_BYTES')
            out=bytes(out);obj=_node_bytes(akey,payload,out)
            immutable_publish_bytes(path,obj)
            out,h=_read_node(path.read_bytes(),expected_action_key=akey,expected_payload=payload);executed+=1
        outputs[nid]=out;results[nid]={'action_key':akey,'output_sha256':h['output_sha256'],'output_bytes':h['output_bytes'],'object_sha256':_sha(path.read_bytes())}
        if crash_after_nodes is not None and len(results)>=crash_after_nodes:raise RuntimeError('INJECTED_DAG_CRASH')
    receipt={'schema':'QROS_TYPED_DAG_RUN_RECEIPT_1.0','manifest_root_sha256':root,'nodes':{k:results[k] for k in sorted(results)},'node_count':len(results)}
    rb=canonical_bytes(receipt);rpath=cas/(root+'.run.json');immutable_publish_bytes(rpath,rb)
    return {'status':'PASS','manifest_root_sha256':root,'node_count':len(results),'executed_nodes':executed,'reused_nodes':reused,'receipt_sha256':_sha(rb),'nodes':results}

def validate_run_receipt(manifest:dict[str,Any],cas_dir:str|Path)->dict[str,Any]:
    norm=normalize_manifest(manifest);root=manifest_root(norm);path=Path(cas_dir)/(root+'.run.json')
    if not path.exists():raise ValueError('RUN_RECEIPT_MISSING')
    raw=path.read_bytes()
    try:r=json.loads(raw.decode())
    except Exception as e:raise ValueError('RUN_RECEIPT_JSON_INVALID') from e
    if canonical_bytes(r)!=raw:raise ValueError('RUN_RECEIPT_NOT_CANONICAL')
    if r.get('manifest_root_sha256')!=root or r.get('node_count')!=len(norm['nodes']):raise ValueError('RUN_RECEIPT_MANIFEST_MISMATCH')
    nodes={n['id']:n for n in norm['nodes']};results={};outputs={}
    for nid in topological_order(norm):
        akey,payload=_build_payload(nodes[nid],results);p=Path(cas_dir)/(akey+'.node')
        if not p.exists():raise ValueError('NODE_OBJECT_MISSING:'+nid)
        out,h=_read_node(p.read_bytes(),expected_action_key=akey,expected_payload=payload);outputs[nid]=out;results[nid]={'action_key':akey,'output_sha256':h['output_sha256'],'output_bytes':h['output_bytes'],'object_sha256':_sha(p.read_bytes())}
    if r.get('nodes')!={k:results[k] for k in sorted(results)}:raise ValueError('RUN_RECEIPT_NODE_MAP_MISMATCH')
    return r
