#!/usr/bin/env python3
import hashlib, shutil, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from time_fixture_lib import build_time_fixture, rehash_time_fixture, _replace_line

BIN=Path(sys.argv[1]); ROOT=Path(sys.argv[2]); CUST=ROOT/'examples/custody_v1/custody_test.receipt'

def invoke(d:Path,cust=CUST):
    out=d/'receipt'; cp=subprocess.run([str(BIN),'time-authority',str(d/'profile.time'),str(d/'schedule.csv'),str(d/'anchors.csv'),str(d/'provenance.txt'),str(cust),str(out)],text=True,capture_output=True)
    return cp

def case(name, fn):
    try: fn(); print('PASS',name)
    except Exception as e: print('FAIL',name,e); raise

def receipt_map(text:str):
    out={}
    for line in text.splitlines():
        if '=' in line:
            k,v=line.split('=',1); out[k]=v
    return out

def assert_counter_positive(text:str,key:str):
    m=receipt_map(text)
    assert key in m,(key,text)
    assert int(m[key])>0,(key,m[key],text)

def fresh(**kw):
    td=tempfile.TemporaryDirectory(); d=Path(td.name); build_time_fixture(d,CUST,**kw); return td,d

def positive():
    td,d=fresh();
    try:
        cp=invoke(d); assert cp.returncode==0,(cp.stdout,cp.stderr); assert 'status=TEST_TIME_READY' in cp.stdout
    finally: td.cleanup()
case('positive',positive)

def tamper_file(file, old, new, needle):
    td,d=fresh();
    try:
        p=d/file; p.write_text(p.read_text().replace(old,new),encoding='ascii'); cp=invoke(d); assert cp.returncode!=0; assert needle in cp.stdout+cp.stderr,(cp.stdout,cp.stderr)
    finally: td.cleanup()
case('schedule_hash_tamper',lambda: tamper_file('schedule.csv','SEG_A','SEG_X','schedule_hash_match=0'))
case('anchors_hash_tamper',lambda: tamper_file('anchors.csv','A_START','A_STORT','anchors_hash_match=0'))
case('provenance_hash_tamper',lambda: tamper_file('provenance.txt','method=SYNTHETIC_GENERATED','method=SYNTHETIC_GENERATED_X','provenance_hash_match=0'))

def semantic_build(name, mutate, counter=None, needle=None, **kw):
    td,d=fresh(**kw)
    try:
        watched=[d/'schedule.csv',d/'anchors.csv',d/'provenance.txt']
        before={x:hashlib.sha256(x.read_bytes()).hexdigest() for x in watched}
        mutate(d)
        after={x:hashlib.sha256(x.read_bytes()).hexdigest() for x in watched}
        assert before != after,(name,'mutation did not change fixture')
        rehash_time_fixture(d,CUST); cp=invoke(d); assert cp.returncode!=0,(cp.returncode,cp.stdout,cp.stderr)
        text=cp.stdout+cp.stderr
        if counter is not None: assert_counter_positive(text,counter)
        if needle is not None: assert needle in text,(name,cp.stdout,cp.stderr)
        assert 'status=FAIL_TIME_AUTHORITY' in cp.stdout,(name,cp.stdout,cp.stderr)
    finally: td.cleanup()

case('schedule_gap',lambda: semantic_build('gap',lambda d:(d/'schedule.csv').write_text((d/'schedule.csv').read_text().replace('SEG_A,1000000000000,10000000000000,7200','SEG_A,1000000000000,9900000000000,7200')),counter='schedule_errors'))
case('schedule_same_adjacent_offset',lambda: semantic_build('same',lambda d:(d/'schedule.csv').write_text((d/'schedule.csv').read_text().replace('SEG_B,10000000000000,20000000000000,10800','SEG_B,10000000000000,20000000000000,7200')),counter='schedule_errors'))
case('schedule_jump_too_large',lambda: semantic_build('jump',lambda d:(d/'schedule.csv').write_text((d/'schedule.csv').read_text().replace(',10800\n',',20000\n')),counter='schedule_errors'))
def wrong_offset(d):
    lines=(d/'anchors.csv').read_text().splitlines()
    for i,line in enumerate(lines):
        if line.startswith('B_POST,'):
            f=line.split(','); f[1]=str(int(f[1])-1_000_000_000_000); lines[i]=','.join(f); break
    else: raise AssertionError('B_POST missing')
    (d/'anchors.csv').write_text('\n'.join(lines)+'\n')
case('anchor_wrong_offset',lambda: semantic_build('wrongoff',wrong_offset,counter='anchor_errors'))

def nonintegral(d):
    lines=(d/'anchors.csv').read_text().splitlines(); f=lines[1].split(','); f[1]=str(int(f[1])+1); lines[1]=','.join(f); (d/'anchors.csv').write_text('\n'.join(lines)+'\n')
case('anchor_nonintegral_offset',lambda: semantic_build('nonint',nonintegral,counter='anchor_errors'))

def nonmonotonic(d):
    lines=(d/'anchors.csv').read_text().splitlines(); lines[1],lines[2]=lines[2],lines[1]; (d/'anchors.csv').write_text('\n'.join(lines)+'\n')
case('anchor_nonmonotonic',lambda: semantic_build('nonmono',nonmonotonic,counter='anchor_errors'))

def missing_bracket(d):
    txt=(d/'anchors.csv').read_text().replace('17100000000000,9900000000000','13000000000000,5800000000000').replace('20900000000000,10100000000000','25800000000000,15000000000000')
    (d/'anchors.csv').write_text(txt)
case('transition_bracket_missing',lambda: semantic_build('bracket',missing_bracket,counter='transition_bracket_errors'))

def edge_far(d):
    txt=(d/'anchors.csv').read_text().replace('8300000000000,1100000000000','9200000000000,2000000000000'); (d/'anchors.csv').write_text(txt)
case('edge_coverage_far',lambda: semantic_build('edge',edge_far,counter='edge_coverage_errors'))

def evidence_mismatch(d):
    txt=(d/'anchors.csv').read_text().replace('A_START,8300000000000,1100000000000,SYNTH_TIME_EVIDENCE_V1','A_START,8300000000000,1100000000000,OTHER_EVIDENCE'); (d/'anchors.csv').write_text(txt)
case('anchor_evidence_id_mismatch',lambda: semantic_build('evid',evidence_mismatch,counter='provenance_errors'))

def prov_authority(d): _replace_line(d/'provenance.txt','authority_id','OTHER_AUTH')
case('provenance_semantic_mismatch',lambda: semantic_build('prov',prov_authority,needle='semantic_provenance_match=0'))

def bad_custody_receipt():
    td,d=fresh(); fake=d/'fake_custody.receipt'; shutil.copy2(CUST,fake); fake.write_text(fake.read_text().replace('source_provenance_ready=1','source_provenance_ready=0'))
    cp=invoke(d,fake); assert cp.returncode!=0; assert 'custody_receipt_semantic_valid=0' in cp.stdout,(cp.stdout,cp.stderr); td.cleanup()
case('forged_custody_flag',bad_custody_receipt)

def root_mismatch():
    td,d=fresh(); _replace_line(d/'profile.time','source_custody_evidence_root_sha256','0'*64); cp=invoke(d); assert cp.returncode!=0 and 'custody_evidence_root_match=0' in cp.stdout; td.cleanup()
case('custody_root_profile_mismatch',root_mismatch)

def research_synth():
    td,d=fresh(purpose='RESEARCH',status='VERIFIED'); cp=invoke(d); assert cp.returncode!=0 and 'status=RESEARCH_REJECTED_SYNTHETIC_PROVENANCE' in cp.stdout,(cp.stdout,cp.stderr); td.cleanup()
case('research_rejects_synthetic',research_synth)

def research_nonsynth():
    td,d=fresh(purpose='RESEARCH',method='BROKER_LOG_PARSED',status='VERIFIED'); cp=invoke(d); assert cp.returncode!=0 and 'status=SEMANTICS_PASS_PRODUCTION_SOURCE_CUSTODY_NOT_READY' in cp.stdout,(cp.stdout,cp.stderr); td.cleanup()
case('research_requires_production_custody',research_nonsynth)

def duplicate_anchor():
    td,d=fresh(); lines=(d/'anchors.csv').read_text().splitlines(); lines[2]=lines[2].replace('A_PRE','A_START'); (d/'anchors.csv').write_text('\n'.join(lines)+'\n'); rehash_time_fixture(d,CUST); cp=invoke(d); assert cp.returncode!=0 and 'duplicate anchor_id' in cp.stderr; td.cleanup()
case('duplicate_anchor_id',duplicate_anchor)

def invalid_clock_domain():
    td,d=fresh(); _replace_line(d/'profile.time','server_clock_domain','ASSUMED_UTC'); cp=invoke(d); assert cp.returncode!=0 and 'unsupported server_clock_domain' in cp.stderr; td.cleanup()
case('invalid_clock_domain',invalid_clock_domain)

def min_anchors_too_high():
    td,d=fresh(min_anchors=7); cp=invoke(d); assert cp.returncode!=0 and 'anchor_errors=1' in cp.stdout; td.cleanup()
case('min_anchor_gate',min_anchors_too_high)

def custody_receipt_exact_hash_binding():
    td,d=fresh(); fake=d/'fake_custody_attestation.receipt'; shutil.copy2(CUST,fake)
    text=fake.read_text(); version=receipt_map(text)['engine_version']
    fake.write_text(text.replace('engine_version='+version,'engine_version='+version+'.tampered'),encoding='ascii')
    cp=invoke(d,fake); text=cp.stdout+cp.stderr
    assert cp.returncode!=0,(cp.stdout,cp.stderr)
    assert 'custody_evidence_root_match=1' in cp.stdout
    assert 'custody_receipt_semantic_valid=1' in cp.stdout
    assert 'custody_receipt_hash_match=0' in cp.stdout
    assert 'status=FAIL_TIME_AUTHORITY' in cp.stdout
    td.cleanup()
case('custody_receipt_exact_hash_binding',custody_receipt_exact_hash_binding)

def schedule_symlink_rejected():
    td,d=fresh(); original=d/'schedule.real'; (d/'schedule.csv').rename(original); (d/'schedule.csv').symlink_to(original)
    cp=invoke(d); assert cp.returncode!=0 and 'symlink rejected' in cp.stderr,(cp.stdout,cp.stderr); td.cleanup()
case('schedule_symlink_rejected',schedule_symlink_rejected)

def profile_symlink_rejected():
    td,d=fresh(); original=d/'profile.real'; (d/'profile.time').rename(original); (d/'profile.time').symlink_to(original)
    cp=invoke(d); assert cp.returncode!=0 and 'symlink rejected' in cp.stderr,(cp.stdout,cp.stderr); td.cleanup()
case('profile_symlink_rejected',profile_symlink_rejected)

def provenance_size_bound():
    td,d=fresh(); (d/'provenance.txt').write_bytes(b'X'*70000)
    cp=invoke(d); assert cp.returncode!=0 and 'byte limit exceeded' in cp.stderr,(cp.stdout,cp.stderr); td.cleanup()
case('provenance_size_bound',provenance_size_bound)

print('TIME_AUTHORITY_CASES_PASS=24')
