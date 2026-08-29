from __future__ import annotations
import hashlib
from pathlib import Path

def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()

def receipt_root(path:Path)->str:
    for line in path.read_text().splitlines():
        if line.startswith('custody_evidence_root_sha256='): return line.split('=',1)[1]
    raise ValueError('custody root missing')

def build_time_fixture(root:Path,custody_receipt:Path,*,segments=None,anchors=None,method='SYNTHETIC_GENERATED',status='TEST_ONLY',purpose='TEST_ONLY',evidence_id='SYNTH_TIME_EVIDENCE_V1',authority_id='SYNTH_TIME_AUTH_V1',source_id='SYNTH_SOURCE_001',min_anchors=6,max_transition_bracket_ns=200_000_000_000,max_edge_anchor_distance_ns=200_000_000_000,max_abs_offset_seconds=50400,max_offset_jump_seconds=7200,production_anchor_verifier_id='NONE'):
    root.mkdir(parents=True,exist_ok=True)
    if segments is None:
        segments=[('SEG_A',1_000_000_000_000,10_000_000_000_000,7200),('SEG_B',10_000_000_000_000,20_000_000_000_000,10800),('SEG_C',20_000_000_000_000,30_000_000_000_000,7200)]
    if anchors is None:
        anchors=[('A_START',1_100_000_000_000,7200),('A_PRE',9_900_000_000_000,7200),('B_POST',10_100_000_000_000,10800),('B_PRE',19_900_000_000_000,10800),('C_POST',20_100_000_000_000,7200),('C_END',29_900_000_000_000,7200)]
    schedule=root/'schedule.csv'; schedule.write_text('segment_id,start_utc_ns,end_utc_ns,offset_seconds\n'+''.join(f'{i},{s},{e},{o}\n' for i,s,e,o in segments),encoding='ascii')
    af=root/'anchors.csv'; lines=['anchor_id,server_wall_ns,utc_ns,evidence_id']
    for aid,utc,off,*rest in anchors:
        eid=rest[0] if rest else evidence_id; wall=utc+off*1_000_000_000
        lines.append(f'{aid},{wall},{utc},{eid}')
    af.write_text('\n'.join(lines)+'\n',encoding='ascii')
    croot=receipt_root(custody_receipt)
    prov=root/'provenance.txt'; prov.write_text('\n'.join(['QROS_TIME_PROVENANCE_V1',f'authority_id={authority_id}',f'source_id={source_id}',f'method={method}',f'status={status}',f'anchors_sha256={sha(af)}',f'schedule_sha256={sha(schedule)}',f'source_custody_evidence_root_sha256={croot}',f'evidence_id={evidence_id}'])+'\n',encoding='ascii')
    profile=root/'profile.time'; profile.write_text('\n'.join(['QROS_TIME_AUTHORITY_PROFILE_V1',f'authority_id={authority_id}',f'source_id={source_id}',f'purpose={purpose}','server_clock_domain=NAIVE_WALL_EPOCH_NS',f'schedule_sha256={sha(schedule)}',f'anchors_sha256={sha(af)}',f'provenance_sha256={sha(prov)}',f'source_custody_evidence_root_sha256={croot}',f'source_custody_receipt_sha256={sha(custody_receipt)}',f'min_anchors={min_anchors}',f'max_transition_bracket_ns={max_transition_bracket_ns}',f'max_edge_anchor_distance_ns={max_edge_anchor_distance_ns}',f'max_abs_offset_seconds={max_abs_offset_seconds}',f'max_offset_jump_seconds={max_offset_jump_seconds}',f'production_anchor_verifier_id={production_anchor_verifier_id}','reserved=0'])+'\n',encoding='ascii')
    return profile,schedule,af,prov

def _replace_line(path:Path,key:str,value:str):
    lines=path.read_text().splitlines(); prefix=key+'='; found=False
    for i,l in enumerate(lines):
        if l.startswith(prefix): lines[i]=prefix+value; found=True
    if not found: raise KeyError(key)
    path.write_text('\n'.join(lines)+'\n',encoding='ascii')

def rehash_time_fixture(root:Path,custody_receipt:Path):
    schedule=root/'schedule.csv'; anchors=root/'anchors.csv'; prov=root/'provenance.txt'; profile=root/'profile.time'; croot=receipt_root(custody_receipt)
    _replace_line(prov,'anchors_sha256',sha(anchors)); _replace_line(prov,'schedule_sha256',sha(schedule)); _replace_line(prov,'source_custody_evidence_root_sha256',croot)
    _replace_line(profile,'schedule_sha256',sha(schedule)); _replace_line(profile,'anchors_sha256',sha(anchors)); _replace_line(profile,'provenance_sha256',sha(prov)); _replace_line(profile,'source_custody_evidence_root_sha256',croot); _replace_line(profile,'source_custody_receipt_sha256',sha(custody_receipt))
