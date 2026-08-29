#!/usr/bin/env python3
import random, subprocess, tempfile, hashlib, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CPP=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'build-release/qros'
PY=ROOT/'reference/replay_reference.py'
rng=random.Random(20260827)
CASES=20
for case in range(CASES):
    n=rng.randint(5,60); day=20260827
    ts=1000; price=rng.randint(100_000,300_000)
    ticks=[]
    for i in range(n):
        ts += rng.choice([0,1,1,2])
        price += rng.randint(-80,80)
        spread=rng.choice([0,5,10,15,20])
        ticks.append((i+1,ts,day,price,price+spread))
    signal_i=rng.randint(0,n-3)
    close_i=rng.randint(signal_i+2,n-1)
    side=rng.choice(['BUY','SELL'])
    stop=rng.randint(20,250); target=rng.randint(20,250)
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); tf=td/'ticks.csv'; it=td/'intent.qros'; out=td/'cpp.csv'
        tf.write_text('seq,ts_ns,session_day,bid_u,ask_u\n'+''.join(f'{a},{b},{c},{d},{e}\n' for a,b,c,d,e in ticks))
        sig=ticks[signal_i]
        data_sha=hashlib.sha256(tf.read_bytes()).hexdigest()
        it.write_text('QROS_INTENT_V1\n'+f'strategy_id=RND_{case}\ndata_sha256={data_sha}\nside={side}\nsignal_seq={sig[0]}\nsignal_ts_ns={sig[1]}\nsignal_session_day={day}\nsession_close_seq={ticks[close_i][0]}\nstop_distance_u={stop}\ntarget_distance_u={target}\n')
        subprocess.run([str(CPP),'replay',str(tf),str(it),str(out)],check=True,stdout=subprocess.DEVNULL)
        py=subprocess.check_output(['python3',str(PY),str(tf),str(it)],text=True)
        cpp=out.read_text()
        if cpp!=py:
            raise SystemExit(f'PARITY FAIL case={case}\nCPP={cpp}\nPY={py}')
print(f'RANDOMIZED_PARITY_PASS cases={CASES} seed=20260827')
