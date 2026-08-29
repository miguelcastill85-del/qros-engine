#!/usr/bin/env python3
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Part:
    index:int; name:str; size:int; sha256:str
@dataclass(frozen=True)
class Profile:
    profile_id:str; source_id:str; source_class:str; namespace_prefix:str; parts:tuple[Part,...]
    total_bytes:int; decoded_required:bool; decoded_name:str; decoded_bytes:int; decoded_sha256:str
    decoder_id:str; historical_lineage_status:str; profile_sha256:str

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def chain_root(parts):
    prev='0'*64
    for p in parts:
        material=("QROS_CUSTODY_CHAIN_V1\n"+f"previous_sha256={prev}\n"+f"index={p.index}\n"+
                  f"name={p.name}\n"+f"bytes={p.size}\n"+f"sha256={p.sha256}\n").encode()
        prev=sha(material)
    return prev

def read_profile(path:Path)->Profile:
    raw=path.read_bytes(); text=raw.decode('ascii'); lines=text.splitlines()
    assert lines[0]=='QROS_SOURCE_CUSTODY_PROFILE_V1'
    def val(i,k): assert lines[i].startswith(k); return lines[i][len(k):]
    profile_id=val(1,'profile_id='); source_id=val(2,'source_id='); source_class=val(3,'source_class='); prefix=val(4,'namespace_prefix=')
    n=int(val(5,'parts_count=')); total=int(val(6,'total_bytes=')); parts=[]; pos=7
    for expected in range(1,n+1):
        assert lines[pos].startswith('part='); f=lines[pos][5:].split(','); assert len(f)==4 and int(f[0])==expected
        parts.append(Part(expected,f[1],int(f[2]),f[3])); pos+=1
    dr=val(pos,'decoded_required=')=='1'; pos+=1
    dn=val(pos,'decoded_name='); pos+=1
    db=int(val(pos,'decoded_bytes=')); pos+=1
    dh=val(pos,'decoded_sha256='); pos+=1
    decoder=val(pos,'decoder_id='); pos+=1
    hist=val(pos,'historical_lineage_status='); pos+=1
    assert pos==len(lines)
    return Profile(profile_id,source_id,source_class,prefix,tuple(parts),total,dr,dn,db,dh,decoder,hist,sha(raw))

def profile_receipt(p:Profile)->str:
    return ("QROS_SOURCE_CUSTODY_PROFILE_RECEIPT_V1\n"+
      f"profile_id={p.profile_id}\nsource_id={p.source_id}\nsource_class={p.source_class}\nprofile_sha256={p.profile_sha256}\n"+
      f"parts_count={len(p.parts)}\ntotal_bytes={p.total_bytes}\nexpected_chain_root_sha256={chain_root(p.parts)}\n"+
      f"decoded_required={1 if p.decoded_required else 0}\ndecoded_name={p.decoded_name}\ndecoded_bytes={p.decoded_bytes}\n"+
      f"decoded_sha256={p.decoded_sha256}\ndecoder_id={p.decoder_id}\nhistorical_lineage_status={p.historical_lineage_status}\n"+
      "status=PROFILE_VALID_BYTES_NOT_MEASURED\n")

def semantic_audit(p:Profile, directory:Path):
    wrong_size=wrong_hash=missing=0; measured=[]; total=0
    for part in p.parts:
        q=directory/part.name
        if not q.exists(): missing+=1; continue
        b=q.read_bytes(); h=sha(b); total+=len(b); measured.append(Part(part.index,part.name,len(b),h))
        wrong_size += len(b)!=part.size; wrong_hash += h!=part.sha256
    archive=(missing==0 and wrong_size==0 and wrong_hash==0 and total==p.total_bytes and chain_root(measured)==chain_root(p.parts))
    decoded=False
    if p.decoded_required and (directory/p.decoded_name).exists():
        b=(directory/p.decoded_name).read_bytes(); decoded=len(b)==p.decoded_bytes and sha(b)==p.decoded_sha256
    elif not p.decoded_required: decoded=True
    lineage=False
    if archive and decoded and p.decoder_id=='QROS_CONCAT_V1':
        b=b''.join((directory/x.name).read_bytes() for x in p.parts)
        lineage=len(b)==p.decoded_bytes and sha(b)==p.decoded_sha256
    source_ready=archive and decoded and lineage
    measured_chain=chain_root(measured) if len(measured)==len(p.parts) else '0'*64
    decoded_measured='0'*64
    if p.decoded_required and (directory/p.decoded_name).exists():
        decoded_measured=sha((directory/p.decoded_name).read_bytes())
    material=("QROS_CUSTODY_EVIDENCE_ROOT_V1\n"+
              f"profile_sha256={p.profile_sha256}\n"+
              f"source_class={p.source_class}\n"+
              f"measured_chain_root_sha256={measured_chain}\n"+
              f"decoded_measured_sha256={decoded_measured}\n"+
              f"archive_custody_verified={int(archive)}\n"+
              f"decoded_bytes_verified={int(decoded)}\n"+
              f"decode_lineage_verified={int(lineage)}\n"+
              "production_source_provenance_ready=0\n").encode('ascii')
    return {'archive_custody_verified':int(archive),'decoded_bytes_verified':int(decoded),'decode_lineage_verified':int(lineage),
            'source_provenance_ready':int(source_ready),'production_source_provenance_ready':0,
            'custody_evidence_root_sha256':sha(material)}
