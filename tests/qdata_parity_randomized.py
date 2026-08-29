#!/usr/bin/env python3
import hashlib, random, subprocess, tempfile, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
QROS=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'build-release/qros'
REF=ROOT/'reference/qdata_reference.py'
rng=random.Random(20260827)
CASES=20

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
contracts=subprocess.check_output([str(QROS),'contracts'],text=True)
event_sha=next(x.split('=',1)[1] for x in contracts.splitlines() if x.startswith('event_contract_sha256='))
exec_sha=next(x.split('=',1)[1] for x in contracts.splitlines() if x.startswith('execution_policy_sha256='))
for case in range(CASES):
    n=rng.randint(6,80); day=20260827
    ts=1_000_000_000; px=rng.randint(100_000,300_000); ticks=[]
    for i in range(n):
        ts += rng.choice([0,1,1,2,3]); px=max(100,px+rng.randint(-100,100)); spr=rng.choice([1,2,5,10,20])
        ticks.append((i+1,ts,day,px,px+spr))
    si=rng.randint(0,n-3); side=rng.choice(['BUY','SELL']); stop=rng.randint(20,300); target=rng.randint(20,300)
    with tempfile.TemporaryDirectory() as td0:
        td=Path(td0); tf=td/'ticks.csv'; sf=td/'sessions.csv'; tz=td/'timezone_evidence.txt'; src=td/'source_evidence.txt'; mf=td/'manifest.qdata'; it=td/'intent.qros'; out=td/'cpp.csv'
        tf.write_text('seq,ts_ns,session_day,bid_u,ask_u\n'+''.join(f'{a},{b},{c},{d},{e}\n' for a,b,c,d,e in ticks))
        sf.write_text('session_day,open_seq,close_seq,open_ts_ns,close_ts_ns,utc_offset_seconds\n'+f'{day},1,{n},{ticks[0][1]},{ticks[-1][1]},0\n')
        tz.write_text('QROS_TIMEZONE_EVIDENCE_V1\n'+f'authority_id=RND_{case}\ntimezone_name=TEST_UTC\nmethod=SYNTHETIC_FIXED_OFFSET\ncoverage_first_day={day}\ncoverage_last_day={day}\nsessions_sha256={sha(sf)}\nobserved_offset_transitions=0\nmax_offset_jump_seconds=0\nstatus=TEST_ONLY\n')
        src.write_text('QROS_SOURCE_EVIDENCE_V1\n'+f'authority_id=RND_{case}\nsource_kind=SYNTHETIC_TEST\nsource_id=RND_FIXTURE\nmethod=SYNTHETIC_GENERATOR\ndataset_sha256={sha(tf)}\nsessions_sha256={sha(sf)}\nstatus=TEST_ONLY\n')
        mf.write_text('QROS_QDATA_MANIFEST_V1\n'+
            f'authority_id=RND_{case}\nsymbol=XAUUSD_TEST\ndataset_sha256={sha(tf)}\nsessions_sha256={sha(sf)}\nschema=TICKS_CSV_V1\nexpected_rows={n}\nfirst_seq=1\nlast_seq={n}\nfirst_ts_ns={ticks[0][1]}\nlast_ts_ns={ticks[-1][1]}\nprice_decimals=2\npoint_size_u=1\ntick_size_u=1\ntimezone_name=TEST_UTC\ntimezone_status=TEST_ONLY\ntimezone_evidence_sha256={sha(tz)}\nsource_kind=SYNTHETIC_TEST\nsource_id=RND_FIXTURE\nsource_evidence_sha256={sha(src)}\npurpose=TEST_ONLY\nsession_policy_id=ONE_SESSION\nmax_zero_spread_ppm=0\nallow_nonpositive_prices=0\n')
        sig=ticks[si]
        it.write_text('QROS_INTENT_V2\n'+f'strategy_id=RND_{case}\ndata_sha256={sha(tf)}\nside={side}\nsignal_seq={sig[0]}\nsignal_ts_ns={sig[1]}\nsignal_session_day={day}\nsession_close_seq={n}\nstop_distance_u={stop}\ntarget_distance_u={target}\nqdata_manifest_sha256={sha(mf)}\nsessions_sha256={sha(sf)}\nevent_contract_sha256={event_sha}\nexecution_policy_sha256={exec_sha}\n')
        subprocess.run([str(QROS),'replay-qdata',str(tf),str(sf),str(mf),str(tz),str(src),str(it),str(out)],check=True,stdout=subprocess.DEVNULL)
        py=subprocess.check_output(['python3',str(REF),str(tf),str(sf),str(mf),str(tz),str(src),str(it),'replay'],text=True)
        cpp=out.read_text()
        if cpp!=py: raise SystemExit(f'QDATA PARITY FAIL case={case}\nCPP={cpp}\nPY={py}')
print(f'QDATA_RANDOMIZED_PARITY_PASS cases={CASES} seed=20260827')
