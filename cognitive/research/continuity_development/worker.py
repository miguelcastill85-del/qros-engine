"""Synthetic worker only. No QROS dispatcher, trading data, network or model calls."""
import argparse
import hashlib
import json
import os
import sqlite3
from pathlib import Path


def encode(x):
    return (json.dumps(x,sort_keys=True,separators=(',',':'))+'\n').encode()


def digest(b):
    return hashlib.sha256(b).hexdigest()


def atom(path, value):
    temp=path.with_name(path.name+'.partial')
    with temp.open('wb') as f:
        f.write(encode(value)); f.flush(); os.fsync(f.fileno())
    os.replace(temp,path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def run(root, variant, spec, fault):
    identity=digest(encode(spec))
    def metric(event):
        with (root/'events.jsonl').open('ab') as f:
            f.write(encode({'event':event}));f.flush();os.fsync(f.fileno())
    values=[]; db=None
    if variant=='SQLITE_TRANSACTION_PREFIX':
        db=sqlite3.connect(root/'state.sqlite')
        db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
        db.execute('CREATE TABLE IF NOT EXISTS meta(identity TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS results(idx INTEGER PRIMARY KEY, value INTEGER NOT NULL, digest TEXT NOT NULL)')
        rows=db.execute('SELECT identity FROM meta').fetchall()
        if not rows:
            db.execute('INSERT INTO meta VALUES (?)',(identity,));db.commit()
        elif rows!=[(identity,)]:raise ValueError('INPUT_IDENTITY_MISMATCH')
        records=[{'index':i,'value':v,'sha256':h} for i,v,h in db.execute('SELECT idx,value,digest FROM results ORDER BY idx')]
    else:
        path=root/'state.json'
        if path.exists():
            state=json.loads(path.read_bytes())
            if state.get('identity')!=identity:raise ValueError('INPUT_IDENTITY_MISMATCH')
            records=state['records']
        else:records=[]
    if len(records)>spec['nodes']:raise ValueError('EXCESS_RECORDS')
    for i,row in enumerate(records):
        payload={'index':i,'value':row['value']}
        if row['index']!=i or type(row['value']) is not int or row['sha256']!=digest(encode(payload)):
            raise ValueError('DURABLE_OUTPUT_INVALID')
        values.append(row['value'])
    for i in range(len(values),spec['nodes']):
        value=(values[-1] if values else 0)+spec['base']+spec['step']*i
        metric('SOLVE')
        row={'index':i,'value':value};row['sha256']=digest(encode(row))
        values.append(value);records.append(row)
        if db is not None:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO results VALUES (?,?,?)',(i,value,row['sha256']))
        if fault=='BEFORE' and i==15:os._exit(75)
        if db is not None:
            db.commit();metric('COMMIT')
        elif variant=='ATOMIC_JSON_PREFIX':
            atom(root/'state.json',{'identity':identity,'records':records});metric('COMMIT')
        if fault=='AFTER' and i==15:os._exit(75)
    if variant=='REPLAY_ALL':
        atom(root/'state.json',{'identity':identity,'records':records});metric('COMMIT')
    if db is not None:db.close()
    atom(root/'output.json',{'identity':identity,'values':values,'sha256':digest(encode(values))})
    return {'status':'PASS','nodes':len(values),'scientific_dispatch':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--variant',choices=['REPLAY_ALL','ATOMIC_JSON_PREFIX','SQLITE_TRANSACTION_PREFIX'],required=True)
    p.add_argument('--spec',type=Path,required=True);p.add_argument('--expected-spec-sha256',required=True)
    p.add_argument('--fault',choices=['NONE','BEFORE','AFTER'],default='NONE');a=p.parse_args()
    try:
        raw=a.spec.read_bytes()
        if digest(raw)!=a.expected_spec_sha256:raise ValueError('SPEC_ANCHOR_MISMATCH')
        spec=json.loads(raw)
        if set(spec)!={'nodes','base','step','worker_sha256'}:raise ValueError('SPEC_SCHEMA')
        if not all(type(spec[k]) is int for k in ('nodes','base','step')) or not 1<=spec['nodes']<=96:
            raise ValueError('SPEC_RANGE')
        if digest(Path(__file__).read_bytes())!=spec['worker_sha256']:raise ValueError('WORKER_IDENTITY_MISMATCH')
        result=run(a.root,a.variant,spec,a.fault)
    except (ValueError,KeyError,sqlite3.DatabaseError) as e:
        result={'status':'FAIL_CLOSED','error':str(e),'scientific_dispatch':False}
    print(json.dumps(result,sort_keys=True))
    raise SystemExit(0 if result['status']=='PASS' else 2)
