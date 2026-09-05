#!/usr/bin/env python3
import json, math, hashlib
from collections import defaultdict, deque

SIG_MIN=0.50
TRD_MIN=0.50
GEO_MIN=0.70


def jaccard_sorted(a,b):
    i=j=inter=0
    while i<len(a) and j<len(b):
        if a[i]==b[j]: inter+=1; i+=1; j+=1
        elif a[i]<b[j]: i+=1
        else: j+=1
    u=len(a)+len(b)-inter
    return inter/u if u else 1.0


def geometric(sj,tj): return math.sqrt(sj*tj)


def edge_ok(a,b):
    sj=jaccard_sorted(a['signal_ts'],b['signal_ts'])
    if sj < SIG_MIN: return None
    tj=jaccard_sorted(a['entry_ts'],b['entry_ts'])
    if tj < TRD_MIN: return None
    g=geometric(sj,tj)
    if g < GEO_MIN: return None
    return (sj,tj,g)


def _adjacent(v1,v2,order):
    try: i=order.index(v1); j=order.index(v2)
    except ValueError: return False
    return abs(i-j)==1


def local_neighbor(a,b,th_order,n_order):
    for k in ('asset','side','signal_timeframe','persistence_family','tick_intensity_context','tick_intensity_lookback'):
        if a[k]!=b[k]: return False
    diffs=[]
    for k in ('feature_side','shock_timing','shock_threshold','persistence_n'):
        if a[k]!=b[k]: diffs.append(k)
    if len(diffs)!=1: return False
    k=diffs[0]
    if k=='feature_side': return {a[k],b[k]}=={'BID','MID'}
    if k=='shock_timing': return {a[k],b[k]}=={'CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK'}
    if k=='shock_threshold': return _adjacent(a[k],b[k],th_order)
    if k=='persistence_n': return _adjacent(a[k],b[k],n_order)
    return False


def components(nodes,edges):
    adj=defaultdict(list)
    for i,j,*_ in edges: adj[i].append(j); adj[j].append(i)
    seen=set(); out=[]
    for i in range(len(nodes)):
        if i in seen: continue
        q=[i]; seen.add(i); c=[]
        while q:
            u=q.pop(); c.append(u)
            for v in adj[u]:
                if v not in seen: seen.add(v); q.append(v)
        out.append(sorted(c,key=lambda x:nodes[x]['stable_id']))
    return out


def medoid(comp,nodes):
    if len(comp)==1: return comp[0]
    best=None
    for i in comp:
        s=0.0
        for j in comp:
            if i==j: continue
            sj=jaccard_sorted(nodes[i]['signal_ts'],nodes[j]['signal_ts'])
            tj=jaccard_sorted(nodes[i]['entry_ts'],nodes[j]['entry_ts'])
            s += geometric(sj,tj)
        mean=s/(len(comp)-1)
        cand=(mean, nodes[i]['stable_id'], i)
        if best is None or mean>best[0]+1e-15 or (abs(mean-best[0])<=1e-15 and nodes[i]['stable_id']<best[1]): best=cand
    return best[2]


def run_partition(nodes,th_order,n_order):
    edges=[]
    for i in range(len(nodes)):
        for j in range(i+1,len(nodes)):
            e=edge_ok(nodes[i],nodes[j])
            if e is not None: edges.append((i,j,*e))
    comps=components(nodes,edges)
    rec=[]
    for c in comps:
        local=False
        if len(c)>=2:
            for x in range(len(c)):
                for y in range(x+1,len(c)):
                    if local_neighbor(nodes[c[x]],nodes[c[y]],th_order,n_order): local=True; break
                if local: break
        typ='PLATEAU' if len(c)>=2 and local else ('SINGLETON' if len(c)==1 else 'MULTI_MEMBER_NONLOCAL')
        m=medoid(c,nodes)
        rec.append({'members':[nodes[i]['stable_id'] for i in c],'medoid':nodes[m]['stable_id'],'type':typ})
    return edges,rec


def canonical_sha(obj):
    b=json.dumps(obj,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(b).hexdigest()
