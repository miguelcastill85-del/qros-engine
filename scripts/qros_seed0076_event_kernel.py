#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass

def _neighbors(values,t,window):
    if window<3 or window%2==0: raise ValueError("window must be odd >=3")
    k=window//2
    if t<window-1: return None
    pivot_i=t-k; lo=t-window+1; hi=t+1
    left=values[lo:pivot_i]; right=values[pivot_i+1:hi]
    return pivot_i,values[pivot_i],left,right

def confirmed_fractal_high(highs,t,window,tie_policy):
    x=_neighbors(highs,t,window)
    if x is None: return None
    i,p,left,right=x
    if tie_policy=="SOURCE_ASYMMETRIC":
        ok=all(p>=v for v in left) and all(p>v for v in right)
    elif tie_policy=="STRICT_ALL_NEIGHBORS":
        ok=all(p>v for v in left+right)
    else: raise ValueError(tie_policy)
    return (i,p) if ok else None

def confirmed_fractal_low(lows,t,window,tie_policy):
    x=_neighbors(lows,t,window)
    if x is None: return None
    i,p,left,right=x
    if tie_policy=="SOURCE_ASYMMETRIC":
        ok=all(p<=v for v in left) and all(p<v for v in right)
    elif tie_policy=="STRICT_ALL_NEIGHBORS":
        ok=all(p<v for v in left+right)
    else: raise ValueError(tie_policy)
    return (i,p) if ok else None

def threshold(level,side,atr=None,buffer_atr=None):
    if buffer_atr is None: return level
    if atr is None: raise ValueError("ATR required when buffer active")
    b=float(buffer_atr)*float(atr)
    return level+b if side=="BUY" else level-b

def crossed(prev_price,price,thr,side):
    if side=="BUY": return prev_price<=thr and price>thr
    if side=="SELL": return prev_price>=thr and price<thr
    raise ValueError(side)

@dataclass
class LevelState:
    side: str
    rearm_mode: str
    level: float|None=None
    level_id: str|None=None
    consumed: bool=False
    pending_retest: bool=False
    pending_threshold: float|None=None

    def replace_level(self,level,level_id):
        changed=(self.level_id!=level_id)
        self.level=float(level); self.level_id=str(level_id)
        if changed:
            self.consumed=False; self.pending_retest=False; self.pending_threshold=None

    def observe_rearm_price(self,price):
        if self.level is None or not self.consumed: return False
        if self.rearm_mode=="RETURN_INSIDE_OR_LEVEL_REPLACED":
            if (self.side=="BUY" and price<=self.level) or (self.side=="SELL" and price>=self.level):
                self.consumed=False; return True
        return False

    def breakout(self,prev_price,price,thr,retest_active=False):
        if self.level is None or self.consumed or self.pending_retest: return "NONE"
        if not crossed(prev_price,price,thr,self.side): return "NONE"
        if retest_active:
            self.pending_retest=True; self.pending_threshold=float(thr); return "RETEST_ARMED"
        return "FINAL_CANDIDATE"

    def retest_tick(self,prev_price,price):
        if not self.pending_retest: return "NONE"
        thr=self.pending_threshold
        if self.side=="BUY":
            touched=prev_price>thr and price<=thr
            reclaimed=prev_price<=thr and price>thr
        else:
            touched=prev_price<thr and price>=thr
            reclaimed=prev_price>=thr and price<thr
        if touched: return "RETEST_TOUCHED"
        if reclaimed: return "FINAL_CANDIDATE"
        return "NONE"

    def finalize_candidate(self,gates_pass):
        self.pending_retest=False; self.pending_threshold=None
        self.consumed=True
        return "SIGNAL" if gates_pass else "FILTERED_CONSUMED"

def close_cross(prev_close,close,thr,side):
    return crossed(prev_close,close,thr,side)
