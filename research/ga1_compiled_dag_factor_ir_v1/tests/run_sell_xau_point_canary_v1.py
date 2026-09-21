from __future__ import annotations
import hashlib, json
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qros_independent_event_canary import tick_crosses_scalar, tick_crosses_alt
from qros_factor_ir import FactorIR

H=lambda s: hashlib.sha256(s.encode()).hexdigest()
rng=np.random.default_rng(7600761)

nb=60
per=9
nt=nb*per
first=np.arange(0,nt,per,dtype=np.int64)
last=first+per-1

# Exact physical-price equivalence under two point encodings.
steps=rng.integers(-4,5,nt,dtype=np.int64)*10
bid_001=np.cumsum(steps)+200000
point_001=0.01
bid_0001=bid_001*10
point_0001=0.001

def bars(bid,point):
    high=np.array([bid[s:e+1].max()*point for s,e in zip(first,last)],dtype=np.float64)
    low=np.array([bid[s:e+1].min()*point for s,e in zip(first,last)],dtype=np.float64)
    return high,low

high_001,low_001=bars(bid_001,point_001)
high_0001,low_0001=bars(bid_0001,point_0001)
if not np.array_equal(high_001,high_0001) or not np.array_equal(low_001,low_0001):
    raise SystemExit("XAU_PHYSICAL_PRICE_SCALING_MISMATCH")

level=(high_001+low_001)/2.0
atr=np.full(nb,2.5,dtype=np.float64)
atr[7]=np.nan
level_id=np.arange(nb,dtype=np.int64)

point_scaling_counts={}
for side in (1,-1):
    a=tick_crosses_scalar(bid_001,first,last,high_001,low_001,level,level_id,atr,side,point_001)
    b=tick_crosses_alt(bid_001,first,last,high_001,low_001,level,level_id,atr,side,point_001)
    c=tick_crosses_scalar(bid_0001,first,last,high_0001,low_0001,level,level_id,atr,side,point_0001)
    d=tick_crosses_alt(bid_0001,first,last,high_0001,low_0001,level,level_id,atr,side,point_0001)
    if a!=b or c!=d:
        raise SystemExit("XAU_POINT_SCALING_GENERATOR_PARITY_MISMATCH")
    if a!=c:
        raise SystemExit("XAU_POINT_SCALING_EVENT_MISMATCH")
    point_scaling_counts["BUY" if side==1 else "SELL"]=sum(len(x) for x in a)

# Mirror BUY path into SELL path around a fixed physical-price center.
center=2500.0
mirror_bid=np.rint((2.0*center-(bid_001*point_001))/point_001).astype(np.int64)
mirror_high=2.0*center-low_001
mirror_low=2.0*center-high_001
mirror_level=2.0*center-level

buy=tick_crosses_scalar(bid_001,first,last,high_001,low_001,level,level_id,atr,1,point_001)
sell=tick_crosses_scalar(mirror_bid,first,last,mirror_high,mirror_low,mirror_level,level_id,atr,-1,point_001)
sell_alt=tick_crosses_alt(mirror_bid,first,last,mirror_high,mirror_low,mirror_level,level_id,atr,-1,point_001)
if sell!=sell_alt:
    raise SystemExit("SELL_MIRROR_INDEPENDENT_GENERATOR_MISMATCH")
if buy!=sell:
    raise SystemExit("SELL_MIRROR_EVENT_MISMATCH")

# Same physical mask must remain semantically distinct across BUY/SELL domains.
source=np.arange(32,dtype=np.uint64)
mask=np.zeros(32,dtype=bool)
mask[[1,3,7,10,18,31]]=True
ir=FactorIR.build(source,{"p":mask},{"r":["p"]})
buy_hash=ir.class_hash("r",{"asset":"NQX","side":"BUY","timeframe":"M2"})
sell_hash=ir.class_hash("r",{"asset":"NQX","side":"SELL","timeframe":"M2"})
if buy_hash==sell_hash:
    raise SystemExit("SIDE_DOMAIN_CLASS_HASH_COLLISION")

out={
  "status":"PASS",
  "classification":"SYNTHETIC_NON_ECONOMIC",
  "tests":{
    "sell_mirror_event_exact":True,
    "sell_independent_generator_exact":True,
    "side_domain_class_hash_separated":True,
    "xau_point_scaling_physical_prices_exact":True,
    "xau_point_scaling_buy_events_exact":True,
    "xau_point_scaling_sell_events_exact":True,
    "xau_point_scaling_independent_generator_exact":True
  },
  "event_counts":{
    "sell_mirror_total":sum(len(x) for x in sell),
    "xau_point_scaling":point_scaling_counts
  },
  "points_tested":[0.01,0.001]
}
print(json.dumps(out,sort_keys=True,separators=(",",":")))
