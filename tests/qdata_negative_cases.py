#!/usr/bin/env python3
import hashlib, shutil, subprocess, tempfile, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
QROS=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'build-release/qros'
FIX=(Path(sys.argv[2]).resolve() if len(sys.argv)>2 else ROOT)/'examples/qdata_v1'

def h(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def replace_field(path,key,value):
    p=Path(path); lines=p.read_text().splitlines(); found=False; out=[]
    for line in lines:
        if line.startswith(key+'='):
            out.append(f'{key}={value}'); found=True
        else: out.append(line)
    if not found: raise RuntimeError(key)
    p.write_text('\n'.join(out)+'\n')
def refresh_manifest(td, data=True, sess=True):
    # Rebind the entire authority chain so negative tests isolate the intended invariant.
    m=td/'manifest.qdata'; tz=td/'timezone_evidence.txt'; src=td/'source_evidence.txt'
    if data:
        d=h(td/'ticks.csv')
        replace_field(m,'dataset_sha256',d)
        replace_field(src,'dataset_sha256',d)
    if sess:
        sh=h(td/'sessions.csv')
        replace_field(m,'sessions_sha256',sh)
        replace_field(src,'sessions_sha256',sh)
        replace_field(tz,'sessions_sha256',sh)
    replace_field(m,'timezone_evidence_sha256',h(tz))
    replace_field(m,'source_evidence_sha256',h(src))
def audit(td):
    r=subprocess.run([str(QROS),'qdata-audit',str(td/'ticks.csv'),str(td/'sessions.csv'),str(td/'manifest.qdata'),str(td/'timezone_evidence.txt'),str(td/'source_evidence.txt'),str(td/'audit.receipt')],capture_output=True,text=True)
    return r

def clone():
    tmp=tempfile.TemporaryDirectory(); td=Path(tmp.name)
    for p in FIX.iterdir():
        if p.is_file() and p.name in {'ticks.csv','sessions.csv','manifest.qdata','timezone_evidence.txt','source_evidence.txt','buy_tp_v2.qros'}:
            shutil.copy2(p,td/p.name)
    return tmp,td


# Positive fixture diagnostics are exact, not sampled.
tmp,td=clone(); r=audit(td); assert r.returncode==0;
for expected in ['min_spread_u=10','p50_spread_u=10','p95_spread_u=10','p99_spread_u=10','max_spread_u=10','max_intraday_gap_ns=1']:
    assert expected in r.stdout, expected
tmp.cleanup()

# Impossible calendar session must fail even when every hash is refreshed consistently.
tmp,td=clone();
(td/'ticks.csv').write_text((td/'ticks.csv').read_text().replace('20260827','20260230'))
(td/'sessions.csv').write_text((td/'sessions.csv').read_text().replace('20260827','20260230'))
refresh_manifest(td,data=True,sess=True); r=audit(td); assert r.returncode!=0 and 'invalid_session_dates=1' in r.stdout; tmp.cleanup()

# A non-positive manifest extent is rejected before dataset audit; this is fail-closed by contract.
tmp,td=clone();
(td/'ticks.csv').write_text((td/'ticks.csv').read_text().replace('1,1000000000,','1,0,',1))
(td/'sessions.csv').write_text((td/'sessions.csv').read_text().replace('1,6,1000000000,','1,6,0,',1))
replace_field(td/'manifest.qdata','first_ts_ns','0'); refresh_manifest(td,data=True,sess=True); r=audit(td);
assert r.returncode!=0 and 'invalid qdata extents' in r.stderr and r.stdout==''; tmp.cleanup()

# A non-positive timestamp inside otherwise parseable extents reaches the auditor and is counted exactly.
tmp,td=clone();
(td/'ticks.csv').write_text((td/'ticks.csv').read_text().replace('3,1000000001,','3,0,',1))
refresh_manifest(td,data=True,sess=False); r=audit(td);
assert r.returncode!=0 and 'nonpositive_timestamps=1' in r.stdout and 'research_ready=0' in r.stdout; tmp.cleanup()

# Exact ppm boundary: 1 zero-spread row of 6 = floor(1e6/6)=166666 ppm.
tmp,td=clone();
(td/'ticks.csv').write_text((td/'ticks.csv').read_text().replace('1005,1015','1005,1005',1)); refresh_manifest(td,data=True);
replace_field(td/'manifest.qdata','max_zero_spread_ppm','166666'); r=audit(td);
assert r.returncode==0 and 'zero_spread_ppm=166666' in r.stdout and 'test_ready=1' in r.stdout and 'research_ready=0' in r.stdout; tmp.cleanup()

# One ppm below that exact floor must reject the same bytes.
tmp,td=clone();
(td/'ticks.csv').write_text((td/'ticks.csv').read_text().replace('1005,1015','1005,1005',1)); refresh_manifest(td,data=True);
replace_field(td/'manifest.qdata','max_zero_spread_ppm','166665'); r=audit(td);
assert r.returncode!=0 and 'zero_spread_ppm=166666' in r.stdout; tmp.cleanup()

# A declared UTC-offset transition is measured exactly when session evidence and bytes are coherently rebound.
tmp,td=clone();
(td/'ticks.csv').write_text('seq,ts_ns,session_day,bid_u,ask_u\n1,1000000000,20260827,1000,1010\n2,1000000001,20260827,1005,1015\n3,1000000002,20260827,1010,1020\n4,2000000000,20260828,1020,1030\n5,2000000001,20260828,1025,1035\n6,2000000002,20260828,1030,1040\n')
(td/'sessions.csv').write_text('session_day,open_seq,close_seq,open_ts_ns,close_ts_ns,utc_offset_seconds\n20260827,1,3,1000000000,1000000002,-14400\n20260828,4,6,2000000000,2000000002,-10800\n')
(td/'timezone_evidence.txt').write_text('QROS_TIMEZONE_EVIDENCE_V1\nauthority_id=SYNTHETIC_QDATA_V1\ntimezone_name=TEST_FIXED_MINUS_04\nmethod=SYNTHETIC_DST_TRANSITION\ncoverage_first_day=20260827\ncoverage_last_day=20260828\nsessions_sha256='+h(td/'sessions.csv')+'\nobserved_offset_transitions=1\nmax_offset_jump_seconds=3600\nstatus=TEST_ONLY\n')
replace_field(td/'manifest.qdata','last_ts_ns','2000000002'); refresh_manifest(td,data=True,sess=True); r=audit(td);
assert r.returncode==0 and 'session_offset_transitions=1' in r.stdout and 'max_offset_jump_seconds=3600' in r.stdout and 'test_ready=1' in r.stdout and 'research_ready=0' in r.stdout; tmp.cleanup()

# Evidence bytes altered but still structurally valid: the sealed evidence hash must fail.
tmp,td=clone(); replace_field(td/'timezone_evidence.txt','method','SYNTHETIC_CHANGED'); r=audit(td); assert r.returncode!=0 and 'timezone_evidence_hash_match=0' in r.stdout and 'test_ready=0' in r.stdout; tmp.cleanup()
tmp,td=clone(); replace_field(td/'source_evidence.txt','method','SYNTHETIC_CHANGED'); r=audit(td); assert r.returncode!=0 and 'source_evidence_hash_match=0' in r.stdout and 'test_ready=0' in r.stdout; tmp.cleanup()

# A correctly rehashed evidence file with wrong semantics must still be rejected.
tmp,td=clone(); replace_field(td/'timezone_evidence.txt','coverage_last_day','20260828'); replace_field(td/'manifest.qdata','timezone_evidence_sha256',h(td/'timezone_evidence.txt')); r=audit(td); assert r.returncode!=0 and 'timezone_evidence_semantic_match=0' in r.stdout and 'test_ready=0' in r.stdout; tmp.cleanup()
tmp,td=clone(); replace_field(td/'source_evidence.txt','source_id','OTHER_SOURCE'); replace_field(td/'manifest.qdata','source_evidence_sha256',h(td/'source_evidence.txt')); r=audit(td); assert r.returncode!=0 and 'source_evidence_semantic_match=0' in r.stdout and 'test_ready=0' in r.stdout; tmp.cleanup()

# Relabeling synthetic evidence as production cannot open RESEARCH_READY in v0.3.
tmp,td=clone();
replace_field(td/'manifest.qdata','purpose','RESEARCH'); replace_field(td/'manifest.qdata','timezone_status','VERIFIED')
replace_field(td/'timezone_evidence.txt','status','VERIFIED'); replace_field(td/'source_evidence.txt','status','VERIFIED')
replace_field(td/'manifest.qdata','timezone_evidence_sha256',h(td/'timezone_evidence.txt')); replace_field(td/'manifest.qdata','source_evidence_sha256',h(td/'source_evidence.txt'))
r=audit(td); assert r.returncode!=0 and 'production_evidence_verifier_available=0' in r.stdout and 'research_ready=0' in r.stdout; tmp.cleanup()

# False close boundary, even with hashes refreshed, must fail structural authority.
tmp,td=clone(); td.joinpath('sessions.csv').write_text('session_day,open_seq,close_seq,open_ts_ns,close_ts_ns,utc_offset_seconds\n20260827,1,7,1000000000,1000000004,-14400\n'); refresh_manifest(td,sess=True); r=audit(td); assert r.returncode!=0 and 'session_boundary_errors=' in r.stdout and 'research_ready=0' in r.stdout; tmp.cleanup()

# Wrong close timestamp with internally consistent file hash must fail exact boundary record check.
tmp,td=clone(); txt=(td/'sessions.csv').read_text().replace('1000000004,-14400','1000009999,-14400'); (td/'sessions.csv').write_text(txt); refresh_manifest(td,sess=True); r=audit(td); assert r.returncode!=0 and 'session_boundary_errors=' in r.stdout; tmp.cleanup()

# Tick grid violation.
tmp,td=clone(); replace_field(td/'manifest.qdata','tick_size_u','5'); r=audit(td); assert r.returncode!=0 and 'tick_size_violations=' in r.stdout; tmp.cleanup()

# Blank row forbidden even if data SHA is updated.
tmp,td=clone(); txt=(td/'ticks.csv').read_text().replace('\n3,','\n\n3,'); (td/'ticks.csv').write_text(txt); refresh_manifest(td,data=True); r=audit(td); assert r.returncode!=0 and 'blank_tick_records=1' in r.stdout; tmp.cleanup()

# Zero spread forbidden by the fixture's max_zero_spread_ppm=0.
tmp,td=clone(); txt=(td/'ticks.csv').read_text().replace('1005,1015','1005,1005'); (td/'ticks.csv').write_text(txt); refresh_manifest(td,data=True); r=audit(td); assert r.returncode!=0 and 'zero_spread=1' in r.stdout; tmp.cleanup()

# Crossed market.
tmp,td=clone(); txt=(td/'ticks.csv').read_text().replace('1005,1015','1015,1005'); (td/'ticks.csv').write_text(txt); refresh_manifest(td,data=True); r=audit(td); assert r.returncode!=0 and 'crossed_market=1' in r.stdout; tmp.cleanup()

# Non-positive quote.
tmp,td=clone(); txt=(td/'ticks.csv').read_text().replace('1000,1010','0,10',1); (td/'ticks.csv').write_text(txt); refresh_manifest(td,data=True); r=audit(td); assert r.returncode!=0 and 'nonpositive_quotes=1' in r.stdout; tmp.cleanup()

# Time reversal.
tmp,td=clone(); txt=(td/'ticks.csv').read_text().replace('4,1000000002','4,999999999'); (td/'ticks.csv').write_text(txt); refresh_manifest(td,data=True); r=audit(td); assert r.returncode!=0 and 'time_reversals=' in r.stdout; tmp.cleanup()

# Duplicate/non-increasing seq.
tmp,td=clone(); txt=(td/'ticks.csv').read_text().replace('4,1000000002','3,1000000002'); (td/'ticks.csv').write_text(txt); refresh_manifest(td,data=True); r=audit(td); assert r.returncode!=0 and 'seq_errors=' in r.stdout; tmp.cleanup()

# CRLF representation is accepted, but the authority hash must bind those exact bytes.
tmp,td=clone()
for name in ['ticks.csv','sessions.csv']:
    p=td/name; b=p.read_bytes().replace(b'\n',b'\r\n'); p.write_bytes(b)
refresh_manifest(td,data=True,sess=True); r=audit(td); assert r.returncode==0 and 'test_ready=1' in r.stdout and 'research_ready=0' in r.stdout, r.stderr+r.stdout; tmp.cleanup()

# Intent authority close may not be shortened, even though the seq exists and same day.
tmp,td=clone(); it=td/'buy_tp_v2.qros'; replace_field(it,'session_close_seq','5'); replace_field(it,'qdata_manifest_sha256',h(td/'manifest.qdata'))
out=td/'ledger.csv'; r=subprocess.run([str(QROS),'replay-qdata',str(td/'ticks.csv'),str(td/'sessions.csv'),str(td/'manifest.qdata'),str(td/'timezone_evidence.txt'),str(td/'source_evidence.txt'),str(it),str(out)],capture_output=True,text=True); assert r.returncode!=0 and 'INTENT_SESSION_CLOSE_NOT_AUTHORITY_CLOSE' in r.stderr; tmp.cleanup()

# Semantic contract mismatch must be rejected before execution.
tmp,td=clone(); it=td/'buy_tp_v2.qros'; replace_field(it,'event_contract_sha256','0'*64); out=td/'ledger.csv'; r=subprocess.run([str(QROS),'replay-qdata',str(td/'ticks.csv'),str(td/'sessions.csv'),str(td/'manifest.qdata'),str(td/'timezone_evidence.txt'),str(td/'source_evidence.txt'),str(it),str(out)],capture_output=True,text=True); assert r.returncode!=0 and 'SEMANTIC_CONTRACT_MISMATCH' in r.stderr; tmp.cleanup()

# CSV/ledger injection through strategy_id is rejected by the closed intent parser.
tmp,td=clone(); it=td/'buy_tp_v2.qros'; replace_field(it,'strategy_id','BAD,CSV'); out=td/'ledger.csv'; r=subprocess.run([str(QROS),'replay-qdata',str(td/'ticks.csv'),str(td/'sessions.csv'),str(td/'manifest.qdata'),str(td/'timezone_evidence.txt'),str(td/'source_evidence.txt'),str(it),str(out)],capture_output=True,text=True); assert r.returncode!=0 and 'unsafe characters' in r.stderr; tmp.cleanup()

print('QDATA_ADVERSARIAL_CASES_PASS attacks=22 positive_contract_checks=4')
