from pathlib import Path
import base64,hashlib,json
ROOT=Path(__file__).resolve().parent
m=json.loads((ROOT/'CARRIER_MANIFEST.json').read_text())
chunks=[]
for rec in m['ordered_parts']:
    p=ROOT/'package'/rec['name']; b=p.read_bytes()
    assert len(b)==rec['bytes'], ('PART_BYTES',rec['name'])
    assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==rec['git_blob_sha1'], ('PART_GIT_SHA1',rec['name'])
    assert hashlib.sha256(b).hexdigest()==rec['sha256'], ('PART_SHA256',rec['name'])
    chunks.append(b.decode('ascii'))
raw=base64.b64decode(''.join(chunks),validate=True)
assert len(raw)==m['archive_bytes'], 'ARCHIVE_BYTES'
assert hashlib.sha256(raw).hexdigest()==m['archive_sha256'], 'ARCHIVE_SHA256'
out=ROOT/m['archive_name']; out.write_bytes(raw)
print(json.dumps({'status':'PASS','archive':out.name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},sort_keys=True))
