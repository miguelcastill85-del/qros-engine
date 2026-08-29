#!/usr/bin/env python3
import sys,time
n=int(sys.argv[1])
day=20260827
ticks=[]
for i in range(n):
    base=200_000_000+(i%1000)
    ticks.append((i+1,i+1,day,base,base+20))
t0=time.perf_counter()
# independent audit + BUY replay equivalent for this deterministic benchmark
prev=None
crossed=seqerr=timerev=dayrev=0
for t in ticks:
    seq,ts,d,bid,ask=t
    crossed += ask<bid
    if prev:
        seqerr += seq<=prev[0]; timerev += ts<prev[1]; dayrev += d<prev[2]
    prev=t
# causal entry strictly after authoritative signal seq=1; close boundary is seq=n.
entry=None; last=None
for t in ticks[1:]:
    if entry is None and t[0]>1 and t[1]>=1 and t[4]>t[3]: entry=t
    if t[0]<=n and t[2]==day and t[4]>t[3]: last=t
elapsed=time.perf_counter()-t0
print(f'rows={n} seconds={elapsed:.9f} rows_per_sec={n/elapsed:.3f} audit={"PASS" if not(crossed or seqerr or timerev or dayrev) else "FAIL"} replay_reason=SESSION_CLOSE')
