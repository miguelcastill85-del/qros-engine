#!/usr/bin/env python3
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from pathlib import Path

HEX=set('0123456789abcdef')
def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def sha_file(p:Path)->str:return sha_bytes(p.read_bytes())
def safe_id(s:str,n:int)->bool:
    return 0<len(s)<=n and all(c.isascii() and (c.isalnum() or c in '_.-:/') for c in s)
def hex64(s:str)->bool:return len(s)==64 and all(c in HEX for c in s)
def read_lines(p:Path):
    raw=p.read_bytes(); text=raw.decode('ascii')
    lines=text.splitlines()
    if not lines or any(not x for x in lines): raise ValueError('blank/empty')
    return lines

def kv(line,key):
    prefix=key+'='
    if not line.startswith(prefix): raise ValueError('expected '+key)
    return line[len(prefix):]

@dataclass
class Profile:
    authority_id:str; source_id:str; purpose:str; clock:str
    schedule_sha:str; anchors_sha:str; provenance_sha:str; custody_root:str; custody_receipt_sha:str
    min_anchors:int; max_bracket:int; max_edge:int; max_abs_offset:int; max_jump:int
    verifier_id:str; profile_sha:str

def read_profile(p:Path)->Profile:
    l=read_lines(p)
    if len(l)!=17 or l[0]!='QROS_TIME_AUTHORITY_PROFILE_V1': raise ValueError('profile')
    x=Profile(kv(l[1],'authority_id'),kv(l[2],'source_id'),kv(l[3],'purpose'),kv(l[4],'server_clock_domain'),
              kv(l[5],'schedule_sha256'),kv(l[6],'anchors_sha256'),kv(l[7],'provenance_sha256'),kv(l[8],'source_custody_evidence_root_sha256'),kv(l[9],'source_custody_receipt_sha256'),
              int(kv(l[10],'min_anchors')),int(kv(l[11],'max_transition_bracket_ns')),int(kv(l[12],'max_edge_anchor_distance_ns')),
              int(kv(l[13],'max_abs_offset_seconds')),int(kv(l[14],'max_offset_jump_seconds')),kv(l[15],'production_anchor_verifier_id'),sha_file(p))
    if kv(l[16],'reserved')!='0': raise ValueError('reserved')
    if x.purpose not in ('RESEARCH','TEST_ONLY') or x.clock!='NAIVE_WALL_EPOCH_NS': raise ValueError('purpose/clock')
    if not safe_id(x.authority_id,128) or not safe_id(x.source_id,160) or not safe_id(x.verifier_id,128): raise ValueError('id')
    if not all(hex64(h) for h in (x.schedule_sha,x.anchors_sha,x.provenance_sha,x.custody_root,x.custody_receipt_sha)): raise ValueError('hash')
    if x.min_anchors<2 or x.max_bracket<=0 or x.max_edge<=0 or x.max_abs_offset<0 or x.max_abs_offset>86400 or x.max_jump<0 or x.max_jump>86400: raise ValueError('bounds')
    return x

def read_schedule(p:Path):
    l=read_lines(p)
    if l[0]!='segment_id,start_utc_ns,end_utc_ns,offset_seconds': raise ValueError('schedule header')
    out=[]; seen=set()
    for row in l[1:]:
        f=row.split(',')
        if len(f)!=4: raise ValueError('schedule cols')
        sid=f[0]
        if not safe_id(sid,128) or sid in seen: raise ValueError('schedule id')
        seen.add(sid); out.append((sid,int(f[1]),int(f[2]),int(f[3])))
    if not out: raise ValueError('empty schedule')
    return out

def read_anchors(p:Path):
    l=read_lines(p)
    if l[0]!='anchor_id,server_wall_ns,utc_ns,evidence_id': raise ValueError('anchor header')
    out=[]; seen=set()
    for row in l[1:]:
        f=row.split(',')
        if len(f)!=4: raise ValueError('anchor cols')
        aid,eid=f[0],f[3]
        if not safe_id(aid,128) or not safe_id(eid,128) or aid in seen: raise ValueError('anchor id')
        seen.add(aid); out.append((aid,int(f[1]),int(f[2]),eid))
    return out

def read_prov(p:Path):
    l=read_lines(p)
    if len(l)!=9 or l[0]!='QROS_TIME_PROVENANCE_V1': raise ValueError('prov')
    d={'authority_id':kv(l[1],'authority_id'),'source_id':kv(l[2],'source_id'),'method':kv(l[3],'method'),'status':kv(l[4],'status'),
       'anchors_sha':kv(l[5],'anchors_sha256'),'schedule_sha':kv(l[6],'schedule_sha256'),'custody_root':kv(l[7],'source_custody_evidence_root_sha256'),'evidence_id':kv(l[8],'evidence_id')}
    if not all(safe_id(d[k],128 if k!='source_id' else 160) for k in ('authority_id','source_id','method','status','evidence_id')): raise ValueError('prov id')
    if not all(hex64(d[k]) for k in ('anchors_sha','schedule_sha','custody_root')): raise ValueError('prov hash')
    return d

def parse_receipt(p:Path):
    l=read_lines(p)
    if l[0]!='QROS_SOURCE_CUSTODY_RECEIPT_V1': raise ValueError('custody receipt')
    d={}
    for row in l[1:]:
        if '=' in row:
            k,v=row.split('=',1)
            if k in d: raise ValueError('duplicate custody field '+k)
            d[k]=v
    required=('profile_sha256','source_class','measured_chain_root_sha256','decoded_measured_sha256','custody_evidence_root_sha256',
              'archive_custody_verified','decoded_bytes_verified','decode_lineage_verified','source_provenance_ready','production_source_provenance_ready')
    if any(k not in d for k in required): raise ValueError('custody missing')
    for k in ('profile_sha256','measured_chain_root_sha256','decoded_measured_sha256','custody_evidence_root_sha256'):
        if not hex64(d[k]): raise ValueError('custody hash')
    if not safe_id(d['source_class'],128): raise ValueError('source class')
    for k in required[5:]:
        if d[k] not in ('0','1'): raise ValueError('custody bool')
    material=('QROS_CUSTODY_EVIDENCE_ROOT_V1\n'+
              f"profile_sha256={d['profile_sha256']}\nsource_class={d['source_class']}\n"+
              f"measured_chain_root_sha256={d['measured_chain_root_sha256']}\n"+
              f"decoded_measured_sha256={d['decoded_measured_sha256']}\n"+
              f"archive_custody_verified={d['archive_custody_verified']}\n"+
              f"decoded_bytes_verified={d['decoded_bytes_verified']}\n"+
              f"decode_lineage_verified={d['decode_lineage_verified']}\n"+
              f"production_source_provenance_ready={d['production_source_provenance_ready']}\n").encode('ascii')
    root=sha_bytes(material)
    archive=d['archive_custody_verified']=='1'; decoded=d['decoded_bytes_verified']=='1'; lineage=d['decode_lineage_verified']=='1'
    source=d['source_provenance_ready']=='1'; production=d['production_source_provenance_ready']=='1'
    semantic=(root==d['custody_evidence_root_sha256'] and source==(archive and decoded and lineage) and not production)
    return {'root':d['custody_evidence_root_sha256'],'semantic':semantic,'source':source,'production':production}

def audit(profile_path:Path,schedule_path:Path,anchors_path:Path,prov_path:Path,custody_path:Path):
    p=read_profile(profile_path); schedule=read_schedule(schedule_path); anchors=read_anchors(anchors_path); prov=read_prov(prov_path); cust=parse_receipt(custody_path)
    sh,ah,ph=sha_file(schedule_path),sha_file(anchors_path),sha_file(prov_path)
    a={'segments':len(schedule),'anchors':len(anchors),'offset_transitions':0,'schedule_errors':0,'anchor_errors':0,'transition_bracket_errors':0,'edge_coverage_errors':0,'provenance_errors':0,
       'schedule_hash_match':int(sh==p.schedule_sha),'anchors_hash_match':int(ah==p.anchors_sha),'provenance_hash_match':int(ph==p.provenance_sha),
       'custody_evidence_root_match':int(cust['root']==p.custody_root),'custody_receipt_hash_match':int(sha_file(custody_path)==p.custody_receipt_sha),'custody_receipt_semantic_valid':int(cust['semantic']),'custody_source_ready':int(cust['source']),'custody_production_ready':int(cust['production'])}
    for i,seg in enumerate(schedule):
        _,start,end,off=seg; valid=-p.max_abs_offset<=off<=p.max_abs_offset
        if start<=0 or end<=start or not valid:a['schedule_errors']+=1
        if i:
            prev=schedule[i-1]; po=prev[3]
            if start!=prev[2]:a['schedule_errors']+=1
            prevvalid=-p.max_abs_offset<=po<=p.max_abs_offset
            if valid and prevvalid and abs(off-po)>p.max_jump:a['schedule_errors']+=1
            if off==po:a['schedule_errors']+=1
            else:a['offset_transitions']+=1
    if len(anchors)<p.min_anchors:a['anchor_errors']+=1
    previous=0; offsets=[]
    for aid,wall,utc,eid in anchors:
        basic=utc>0 and wall>0 and utc>previous
        if not basic:
            a['anchor_errors']+=1
            if utc>previous:previous=utc
            continue
        previous=utc
        if eid!=prov['evidence_id']:a['provenance_errors']+=1
        delta=wall-utc
        if delta%1_000_000_000:
            a['anchor_errors']+=1; continue
        off=delta//1_000_000_000; offsets.append(off)
        if not -p.max_abs_offset<=off<=p.max_abs_offset:a['anchor_errors']+=1
        match=next((s for s in schedule if utc>=s[1] and utc<s[2]),None)
        if match is None or match[3]!=off:a['anchor_errors']+=1
    a['min_observed_offset_seconds']=min(offsets) if offsets else 0
    a['max_observed_offset_seconds']=max(offsets) if offsets else 0
    a['anchor_offsets_match_schedule']=int(a['anchor_errors']==0)
    safe=a['schedule_errors']==0
    if anchors and safe:
        fd=anchors[0][2]-schedule[0][1]; ld=schedule[-1][2]-anchors[-1][2]
        if fd<0 or fd>p.max_edge:a['edge_coverage_errors']+=1
        if ld<=0 or ld>p.max_edge:a['edge_coverage_errors']+=1
    elif not anchors:a['edge_coverage_errors']+=2
    else:a['edge_coverage_errors']+=1
    if safe:
        for i in range(1,len(schedule)):
            boundary=schedule[i][1]; preoff=schedule[i-1][3]; postoff=schedule[i][3]; pre=post=False
            for _,wall,utc,_ in anchors:
                if utc<=0 or wall<=0:continue
                delta=wall-utc
                if delta%1_000_000_000:continue
                off=delta//1_000_000_000
                if utc<boundary:
                    if boundary-utc<=p.max_bracket and off==preoff:pre=True
                else:
                    if utc-boundary<=p.max_bracket and off==postoff:post=True
            if not pre or not post:a['transition_bracket_errors']+=1
    elif len(schedule)>1:a['transition_bracket_errors']+=len(schedule)-1
    semantic=(prov['authority_id']==p.authority_id and prov['source_id']==p.source_id and prov['anchors_sha']==ah and prov['schedule_sha']==sh and prov['custody_root']==cust['root'])
    a['semantic_provenance_match']=int(semantic)
    if not semantic:a['provenance_errors']+=1
    base=(all(a[k] for k in ('schedule_hash_match','anchors_hash_match','provenance_hash_match','custody_evidence_root_match','custody_receipt_hash_match','custody_receipt_semantic_valid','custody_source_ready')) and
          all(a[k]==0 for k in ('schedule_errors','anchor_errors','transition_bracket_errors','edge_coverage_errors','provenance_errors')))
    synthetic=prov['method'].startswith('SYNTHETIC'); test_status=prov['status']=='TEST_ONLY'; verified=prov['status']=='VERIFIED'
    a['production_anchor_verifier_available']=0
    a['test_time_ready']=int(base and p.purpose=='TEST_ONLY' and synthetic and test_status)
    a['research_time_ready']=int(base and p.purpose=='RESEARCH' and not synthetic and verified and cust['production'] and False)
    if a['research_time_ready']: status='TIME_VERIFIED'
    elif a['test_time_ready']: status='TEST_TIME_READY'
    elif base and p.purpose=='RESEARCH' and synthetic: status='RESEARCH_REJECTED_SYNTHETIC_PROVENANCE'
    elif base and p.purpose=='RESEARCH' and not cust['production']: status='SEMANTICS_PASS_PRODUCTION_SOURCE_CUSTODY_NOT_READY'
    elif base and p.purpose=='RESEARCH': status='SEMANTICS_PASS_PRODUCTION_ANCHOR_VERIFIER_NOT_IMPLEMENTED'
    else: status='FAIL_TIME_AUTHORITY'
    a['status']=status
    return a
