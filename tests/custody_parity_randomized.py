#!/usr/bin/env python3
import hashlib, os, random, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reference'))
from custody_reference import read_profile, profile_receipt, semantic_audit

BIN=Path(sys.argv[1]); random.seed(20260827)

def parse_receipt(text):
    out={}
    for line in text.splitlines()[1:]:
        if '=' in line:
            k,v=line.split('=',1); out[k]=v
    return out

for case in range(25):
    with tempfile.TemporaryDirectory() as t:
        d=Path(t); src=d/'source'; src.mkdir(); n=1+random.randrange(6); parts=[]; concat=b''
        for i in range(1,n+1):
            b=random.randbytes(1+random.randrange(4096)); concat+=b
            name=f'R{case:02d}.part{i:02d}.bin'; (src/name).write_bytes(b)
            parts.append((i,name,len(b),hashlib.sha256(b).hexdigest()))
        decoded=f'R{case:02d}.decoded.bin'; (src/decoded).write_bytes(concat)
        lines=['QROS_SOURCE_CUSTODY_PROFILE_V1',f'profile_id=RAND_{case:02d}',f'source_id=R{case:02d}','source_class=SYNTHETIC_MULTIPART',f'namespace_prefix=R{case:02d}.',f'parts_count={n}',f'total_bytes={sum(x[2] for x in parts)}']
        lines += [f'part={i},{name},{z},{h}' for i,name,z,h in parts]
        lines += ['decoded_required=1',f'decoded_name={decoded}',f'decoded_bytes={len(concat)}',f'decoded_sha256={hashlib.sha256(concat).hexdigest()}','decoder_id=QROS_CONCAT_V1','historical_lineage_status=TEST_ONLY']
        prof=d/'p.custody'; prof.write_text('\n'.join(lines)+'\n',encoding='ascii')
        py=read_profile(prof)
        cp=subprocess.run([str(BIN),'custody-profile-check',str(prof)],text=True,capture_output=True,check=True)
        assert cp.stdout==profile_receipt(py),(case,cp.stdout,profile_receipt(py))
        out=d/'receipt'
        cp=subprocess.run([str(BIN),'source-custody',str(prof),str(src),str(out)],text=True,capture_output=True)
        assert cp.returncode==0,(case,cp.stdout,cp.stderr)
        c=parse_receipt(cp.stdout); r=semantic_audit(py,src)
        for k,v in r.items(): assert c[k]==str(v),(case,k,c[k],v)
print('CUSTODY_RANDOMIZED_PARITY_PASS=25 seed=20260827')
