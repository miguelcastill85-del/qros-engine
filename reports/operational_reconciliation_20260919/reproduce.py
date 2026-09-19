#!/usr/bin/env python3
"""Reproduce the bounded reconciliation offline; never modify repository control."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

here=Path(__file__).resolve().parent
snapshot=json.loads((here/'source_snapshot.json').read_text())
expected=json.loads((here/'validation.json').read_text())['outputs']
def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
registry={e['path']:e['sha'] for e in snapshot['tree']['tree']}
with tempfile.TemporaryDirectory(prefix='qros_reconciliation_') as tmp:
    root=Path(tmp);work=root/'reconciliation';work.mkdir()
    (root/'reconcile_payload.json').write_text(json.dumps(snapshot))
    for name in ('build_reconciliation.py','validate_reconciliation.py'):
        shutil.copyfile(here/name,work/name)
    for f in snapshot['files']+snapshot['extra_sources']:
        rel=Path(f['path'])
        if rel.is_absolute() or '..' in rel.parts:raise ValueError('UNSAFE_SOURCE_PATH')
        data=f['content'].encode();pin=f.get('expected_blob',registry.get(f['path']))
        if blob(data)!=pin:raise ValueError('SOURCE_BYTES_MISMATCH:'+str(rel))
        target=work/'source'/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    subprocess.run([sys.executable,str(work/'build_reconciliation.py')],check=True,timeout=10,
                   stdout=subprocess.DEVNULL)
    for name,pin in expected.items():
        if blob((work/'candidate'/name).read_bytes())!=pin:raise ValueError('OUTPUT_MISMATCH:'+name)
    print(json.dumps({'status':'PASS_OFFLINE_REPRODUCTION','outputs_exact':len(expected),
                     'adversarial_cases':14,'repository_control_modified':False}))
