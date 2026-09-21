import hashlib,json,multiprocessing as mp,tempfile,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from qros_typed_dag import execute_manifest,validate_run_receipt,manifest_root,normalize_manifest

H=lambda s:hashlib.sha256(s.encode()).hexdigest()
ENV={'python':'test','numpy':'test','numba':None,'byteorder':'little'}
CODE={'impl':H('impl-v1')}
def node(nid,op,deps=(),params=None,static=None):
    return {'id':nid,'operation':op,'operation_version':'1','code_hashes':CODE,'domain':{'asset':'SYN','side':'NONE','timeframe':'NA'},'parameters':params or {},'static_inputs':static or {'fixture':H('fixture')},'environment':ENV,'deps':list(deps)}
def op_emit(payload,deps):return payload['parameters']['value'].encode()
def op_concat(payload,deps):return b'|'.join(deps[k] for k in sorted(deps))+b'#'+payload['parameters'].get('suffix','').encode()
OPS={'EMIT':op_emit,'CONCAT':op_concat}
def manifest(v='A',parent_param='x'):
    return {'schema':'QROS_TYPED_DAG_MANIFEST_1.0','nodes':[node('a','EMIT',params={'value':parent_param}),node('b','EMIT',params={'value':'B'}),node('c','CONCAT',deps=['a','b'],params={'suffix':v}),node('d','CONCAT',deps=['c'],params={'suffix':'D'})]}
def worker(m,cas,q):
    try:q.put(('ok',execute_manifest(m,cas,OPS)))
    except Exception as e:q.put(('err',type(e).__name__,str(e)))
if __name__=='__main__':
    for bad,token in [
      ({'schema':'QROS_TYPED_DAG_MANIFEST_1.0','nodes':[node('a','EMIT',deps=['missing'],params={'value':'x'})]},'MISSING_DEPENDENCY'),
      ({'schema':'QROS_TYPED_DAG_MANIFEST_1.0','nodes':[node('a','CONCAT',deps=['b']),node('b','CONCAT',deps=['a'])]},'DAG_CYCLE'),
    ]:
      try:normalize_manifest(bad);raise AssertionError(token+'_ACCEPTED')
      except ValueError as e:assert token in str(e)
    with tempfile.TemporaryDirectory() as td:
      m=manifest();r1=execute_manifest(m,td,OPS);assert r1['executed_nodes']==4 and r1['reused_nodes']==0;validate_run_receipt(m,td)
      r2=execute_manifest(m,td,OPS);assert r2['executed_nodes']==0 and r2['reused_nodes']==4
      td2=Path(td)/'crash';m2=manifest(v='CRASH')
      try:execute_manifest(m2,td2,OPS,crash_after_nodes=2);raise AssertionError('CRASH_NOT_INJECTED')
      except RuntimeError as e:assert 'INJECTED_DAG_CRASH' in str(e)
      assert not (td2/(manifest_root(m2)+'.run.json')).exists()
      rr=execute_manifest(m2,td2,OPS);assert rr['reused_nodes']==2 and rr['executed_nodes']==2;validate_run_receipt(m2,td2)
      old=r1['nodes'];m3=manifest(parent_param='changed');r3=execute_manifest(m3,td,OPS)
      assert r3['nodes']['a']['action_key']!=old['a']['action_key']
      assert r3['nodes']['b']['action_key']==old['b']['action_key']
      assert r3['nodes']['c']['action_key']!=old['c']['action_key']
      assert r3['nodes']['d']['action_key']!=old['d']['action_key']
      cpath=Path(td)/(r3['nodes']['c']['action_key']+'.node');raw=cpath.read_bytes();cpath.write_bytes(raw[:-1])
      try:execute_manifest(m3,td,OPS);raise AssertionError('TRUNCATED_NODE_ACCEPTED')
      except ValueError as e:assert 'NODE_OUTPUT_MISMATCH' in str(e)
      cpath.write_bytes(raw)
      ctx=mp.get_context('fork');td3=Path(td)/'dup';q=ctx.Queue();ps=[ctx.Process(target=worker,args=(m,str(td3),q)) for _ in range(2)]
      [p.start() for p in ps];[p.join(10) for p in ps];rows=[q.get() for _ in ps]
      assert all(x[0]=='ok' for x in rows),rows
      validate_run_receipt(m,td3)
      print(json.dumps({'status':'PASS','missing_dependency_rejected':True,'cycle_rejected':True,'cold_execution_nodes':4,'warm_reuse_nodes':4,'crash_resume_reused_nodes':2,'crash_resume_executed_nodes':2,'stale_parent_invalidated_descendants':['a','c','d'],'unaffected_sibling_reused':'b','truncated_node_rejected':True,'duplicate_workers_pass':True},sort_keys=True))
