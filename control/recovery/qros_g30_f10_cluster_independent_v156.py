#!/usr/bin/env python3
import json, math, hashlib
from collections import defaultdict
SIG_MIN=0.50; TRD_MIN=0.50; GEO_MIN=0.70

def inter_two_pointer(a,b):
    i=j=n=0
    while i<len(a) and j<len(b):
        x=a[i]; y=b[j]
        if x==y: n+=1; i+=1; j+=1
        elif x<y: i+=1
        else: j+=1
    return n

def jac(a,b):
    n=inter_two_pointer(a,b); d=len(a)+len(b)-n
    return n/d if d else 1.0

def geo(a,b): return math.sqrt(a*b)

def accepted_edges(nodes):
    out=[]
    for i,a in enumerate(nodes):
        for j in range(i+1,len(nodes)):
            b=nodes[j]; sj=jac(a['signal_ts'],b['signal_ts'])
            if sj < SIG_MIN: continue
            tj=jac(a['entry_ts'],b['entry_ts'])
            if tj < TRD_MIN: continue
            g=geo(sj,tj)
            if g>=GEO_MIN: out.append((i,j,sj,tj,g))
    return out

def bfs_components(nodes,edges):
    adj=[[] for _ in nodes]
    for i,j,*_ in edges: adj[i].append(j); adj[j].append(i)
    seen=[False]*len(nodes); comps=[]
    for s in range(len(nodes)):
        if seen[s]: continue
        q=[s]; seen[s]=True; c=[]
        for u in q:
            c.append(u)
            for v in adj[u]:
                if not seen[v]: seen[v]=True; q.append(v)
        comps.append(sorted(c,key=lambda x:nodes[x]['stable_id']))
    return comps

def medoid(comp,nodes):
    best_i=None; best_mean=-1.0; best_id=None
    for i in comp:
        total=0.0
        for j in comp:
            if i!=j: total += geo(jac(nodes[i]['signal_ts'],nodes[j]['signal_ts']),jac(nodes[i]['entry_ts'],nodes[j]['entry_ts']))
        mean=total/(len(comp)-1) if len(comp)>1 else 1.0
        sid=nodes[i]['stable_id']
        if mean>best_mean+1e-15 or (abs(mean-best_mean)<=1e-15 and (best_id is None or sid<best_id)):
            best_mean=mean; best_id=sid; best_i=i
    return best_i

def canonical_sha(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()
