from __future__ import annotations
import hashlib,tempfile,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from qros_typed_action import atomic_publish_bytes,action_key,canonical_bytes

with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    p=td/'same.bin'
    h1=atomic_publish_bytes(p,b'abc')
    h2=atomic_publish_bytes(p,b'abc')
    assert h1==h2==hashlib.sha256(b'abc').hexdigest()
    try:
        atomic_publish_bytes(p,b'different')
        raise AssertionError('CONFLICT_ACCEPTED')
    except FileExistsError as e:
        assert 'IMMUTABLE_ARTIFACT_CONFLICT' in str(e)
    q=td/'crash.bin'
    try:
        atomic_publish_bytes(q,b'abc',crash_before_rename=True)
        raise AssertionError('CRASH_NOT_INJECTED')
    except RuntimeError:
        pass
    assert not q.exists()
kwargs=dict(operation='X',operation_version='1',code_hashes={'c':'a'*64},domain={'d':1},
            parameters={'p':2},input_artifacts={'i':'b'*64},environment={'e':3})
k,payload=action_key(**kwargs)
assert k==hashlib.sha256(canonical_bytes(payload)).hexdigest()
print(json.dumps({'status':'PASS','initial_publish_sha256':h1,'idempotent_same_bytes':True,
                  'conflicting_bytes_rejected':True,'crash_before_publish_no_final':True,
                  'action_key_canonical_self_consistent':True},sort_keys=True))
