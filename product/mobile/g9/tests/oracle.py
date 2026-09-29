"""Independent Python/G5 verification of actual JS/Worker bytes, not copied expected outputs."""
import base64,hashlib,json,pathlib,sys,copy
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT.parent/'g4'),str(ROOT.parent/'g5')]
from proof_gateway import VerifiedSnapshot
from witness import Head
from data_audit import canonical
f=json.loads((ROOT/'evidence/parity_fixture.json').read_text());p=f['payload']
raw=(ROOT/'evidence/worker_snapshot.json').read_bytes()
assert raw==canonical(p)
assert hashlib.sha256(raw).hexdigest()==f['canonical_payload_sha256']
def verify(p):
 return VerifiedSnapshot.construct(tenant='tenant_A',project='project_A',campaign='campaign_A',audit_receipt=p['audit_receipt'],signed_witness_event=p['witness_event'],witness_public_key=base64.b64decode(f['public_key_b64']),witness_id='g9_backend_test_only',known_prior_head=Head(0,'0'*64))
s=verify(p);assert s.witness_head.sha256==p['head']['sha256']
for kind in ['signature','audit','tenant']:
 q=copy.deepcopy(p)
 if kind=='signature':q['witness_event']['signature_b64']=base64.b64encode(bytes(64)).decode()
 if kind=='audit':q['audit_receipt']['rows']=999
 if kind=='tenant':q['witness_event']['body']['tenant']='tenant_B'
 try:verify(q)
 except ValueError:pass
 else:raise AssertionError(kind)
r={'schema':'QROS_G9_PYTHON_ORACLE_V1','classification':'TEST_ONLY','canonical_payload_sha256':f['canonical_payload_sha256'],'positive':1,'negative':3,'status':'PASS','external_custody':'NOT_DEPLOYED'}
(ROOT/'evidence/python_oracle.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
