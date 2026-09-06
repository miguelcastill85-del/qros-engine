from __future__ import annotations
import hashlib, json, os, sqlite3, tempfile
from pathlib import Path

SCHEMA='QROS_CHECKPOINT_RECOVERY_V2'

def sha256_bytes(b: bytes)->str: return hashlib.sha256(b).hexdigest()
def canonical_json(obj)->bytes: return json.dumps(obj,sort_keys=True,separators=(',',':')).encode()
def atomic_write(path: Path, data: bytes):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.tmp.',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def state_payload(input_hash:str, algorithm_hash:str, raw_done:int, uid_count:int, chunk_root:str, epoch:int=1):
    core={'schema':SCHEMA,'input_hash':input_hash,'algorithm_hash':algorithm_hash,'raw_done':int(raw_done),'uid_count':int(uid_count),'chunk_root':chunk_root,'epoch':int(epoch)}
    core['self_sha256']=sha256_bytes(canonical_json(core))
    return core

def write_state(path:Path, **kw): atomic_write(path, canonical_json(state_payload(**kw)))
def read_state(path:Path, expected_input_hash:str, expected_algorithm_hash:str):
    obj=json.loads(Path(path).read_text())
    got=obj.pop('self_sha256',None); exp=sha256_bytes(canonical_json(obj))
    if got!=exp: raise RuntimeError('STATE_SELF_HASH_FAIL')
    if obj.get('schema')!=SCHEMA: raise RuntimeError('STATE_SCHEMA_FAIL')
    if obj.get('input_hash')!=expected_input_hash: raise RuntimeError('INPUT_HASH_MISMATCH')
    if obj.get('algorithm_hash')!=expected_algorithm_hash: raise RuntimeError('ALGORITHM_HASH_MISMATCH')
    obj['self_sha256']=got; return obj

def init_db(path:Path):
    con=sqlite3.connect(path)
    con.execute('create table if not exists unique_masks(uid integer primary key, digest text unique not null, canonical_raw_idx integer not null)')
    con.execute('create table if not exists raw_map(raw_idx integer primary key, uid integer not null)')
    con.commit(); return con

def reconcile_to_state(con:sqlite3.Connection, state:dict):
    raw_done=int(state['raw_done']); uid_count=int(state['uid_count'])
    con.execute('delete from raw_map where raw_idx>=?',(raw_done,))
    con.execute('delete from unique_masks where uid>?',(uid_count,))
    con.commit()
    c,n,mi,ma=con.execute('select count(*),count(distinct uid),coalesce(min(uid),0),coalesce(max(uid),0) from unique_masks').fetchone()
    if c!=uid_count or n!=uid_count or (uid_count and (mi!=1 or ma!=uid_count)): raise RuntimeError('UID_CONTIGUITY_FAIL')
    rc=con.execute('select count(*) from raw_map').fetchone()[0]
    if rc!=raw_done: raise RuntimeError('RAW_MAP_PROGRESS_FAIL')

def commit_batch(con:sqlite3.Connection, raw_start:int, digests:list[str]):
    row=con.execute('select coalesce(max(uid),0) from unique_masks').fetchone(); next_uid=int(row[0])+1
    cache={}
    for j,d in enumerate(digests):
        raw_idx=raw_start+j
        uid=cache.get(d)
        if uid is None:
            r=con.execute('select uid from unique_masks where digest=?',(d,)).fetchone()
            if r: uid=int(r[0])
            else:
                uid=next_uid; next_uid+=1
                con.execute('insert into unique_masks(uid,digest,canonical_raw_idx) values(?,?,?)',(uid,d,raw_idx))
            cache[d]=uid
        con.execute('insert or replace into raw_map(raw_idx,uid) values(?,?)',(raw_idx,uid))
    con.commit()

def chunk_receipt(start:int,end:int,input_hash:str,algorithm_hash:str,payload_sha:str):
    if end<=start: raise ValueError('BAD_RANGE')
    return {'start':start,'end':end,'input_hash':input_hash,'algorithm_hash':algorithm_hash,'payload_sha256':payload_sha}

def validate_chunk_chain(receipts:list[dict], expected_start:int, expected_end:int, input_hash:str, algorithm_hash:str):
    p=expected_start
    for r in sorted(receipts,key=lambda x:x['start']):
        if r['start']!=p: raise RuntimeError('CHUNK_GAP_OR_OVERLAP')
        if r['end']<=r['start']: raise RuntimeError('CHUNK_BAD_RANGE')
        if r['input_hash']!=input_hash: raise RuntimeError('CHUNK_INPUT_HASH_MISMATCH')
        if r['algorithm_hash']!=algorithm_hash: raise RuntimeError('CHUNK_ALGORITHM_HASH_MISMATCH')
        p=r['end']
    if p!=expected_end: raise RuntimeError('CHUNK_COVERAGE_INCOMPLETE')
    return True
