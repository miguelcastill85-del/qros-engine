#!/usr/bin/env python3
import random, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference'))
from time_fixture_lib import build_time_fixture
from time_authority_reference import audit

BIN=Path(sys.argv[1]); ROOT=Path(sys.argv[2]); CUST=ROOT/'examples/custody_v1/custody_test.receipt'
rng=random.Random(20260827)

def parse(text):
    d={}
    for line in text.splitlines()[1:]:
        if '=' in line:
            k,v=line.split('=',1); d[k]=v
    return d

keys=['segments','anchors','offset_transitions','min_observed_offset_seconds','max_observed_offset_seconds','schedule_errors','anchor_errors',
      'transition_bracket_errors','edge_coverage_errors','provenance_errors','schedule_hash_match','anchors_hash_match','provenance_hash_match',
      'custody_evidence_root_match','custody_receipt_hash_match','custody_receipt_semantic_valid','custody_source_ready','custody_production_ready','semantic_provenance_match',
      'anchor_offsets_match_schedule','production_anchor_verifier_available','test_time_ready','research_time_ready','status']

for case in range(25):
    with tempfile.TemporaryDirectory() as td:
        d=Path(td); n=rng.randint(2,6); start=1_000_000_000_000_000+rng.randint(0,100)*1_000_000_000
        lengths=[rng.randint(700,1500)*1_000_000_000 for _ in range(n)]
        off=rng.choice([-18000,-14400,-10800,-7200,-3600,0,3600,7200,10800,14400,18000])
        segments=[]; cur=start
        for i,L in enumerate(lengths):
            if i:
                candidates=[x for x in (-7200,-3600,3600,7200) if -36000<=off+x<=36000]
                off += rng.choice(candidates)
            segments.append((f'S{case}_{i}',cur,cur+L,off)); cur+=L
        bracket=120_000_000_000; edge=120_000_000_000
        anchors=[]
        # one near start, two around every transition, one near end
        first=segments[0]; u=first[1]+30_000_000_000; anchors.append((f'A{case}_START',u,first[3]))
        for i in range(1,n):
            b=segments[i][1]
            anchors.append((f'A{case}_{i}_PRE',b-30_000_000_000,segments[i-1][3]))
            anchors.append((f'A{case}_{i}_POST',b+30_000_000_000,segments[i][3]))
        last=segments[-1]; u=last[2]-30_000_000_000; anchors.append((f'A{case}_END',u,last[3]))
        build_time_fixture(d,CUST,segments=segments,anchors=anchors,min_anchors=len(anchors),max_transition_bracket_ns=bracket,
                           max_edge_anchor_distance_ns=edge,max_abs_offset_seconds=50400,max_offset_jump_seconds=7200,
                           authority_id=f'RAND_TIME_AUTH_{case}',evidence_id=f'RAND_TIME_EVID_{case}')
        out=d/'receipt'
        cp=subprocess.run([str(BIN),'time-authority',str(d/'profile.time'),str(d/'schedule.csv'),str(d/'anchors.csv'),str(d/'provenance.txt'),str(CUST),str(out)],text=True,capture_output=True)
        assert cp.returncode==0,(case,cp.stdout,cp.stderr)
        cpp=parse(cp.stdout); py=audit(d/'profile.time',d/'schedule.csv',d/'anchors.csv',d/'provenance.txt',CUST)
        for k in keys:
            assert k in cpp,(case,k)
            assert cpp[k]==str(py[k]),(case,k,cpp[k],py[k],cp.stdout)
print('TIME_AUTHORITY_RANDOMIZED_PARITY_PASS=25 seed=20260827')
