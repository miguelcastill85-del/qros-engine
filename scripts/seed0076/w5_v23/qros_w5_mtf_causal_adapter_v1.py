#!/usr/bin/env python3
"""W5 pre-econ corrected MTF completion adapter.
Original V221 retained unchanged. Uses exactly the latest bar whose *next bar's*
first source index is <= the signal index. No future incomplete HTF bar access.
"""
from __future__ import annotations
import numpy as np

def causal_context_index(context_bars,source_indices):
    first=np.asarray(context_bars['first_source_index'],dtype=np.int64)
    source=np.asarray(source_indices,dtype=np.int64)
    if len(first)<2:return np.full(source.shape,-1,dtype=np.int64)
    if np.any(first[1:]<=first[:-1]):raise ValueError('CONTEXT_BAR_NON_MONOTONIC_FIRST_SOURCE')
    # previous bar i becomes complete on first source tick of following bar i+1.
    # Side RIGHT includes completion at that same first tick (available then).
    return np.searchsorted(first[1:],source,side='right').astype(np.int64)-1

def causal_mtf_eval(v221,loader,signal_tf,source_idx,side,variant,active_trend=None):
    rule=variant['rule'];steps=2 if rule.startswith('TWO_STEPS') else 1
    tf=v221.higher_tf(signal_tf,steps)
    if tf is None:return np.zeros(len(source_idx),bool)
    bars,ind=loader(tf);ci=causal_context_index(bars,source_idx)
    if rule.endswith('TREND_ALIGN'):
        tv=active_trend if active_trend else {'mode':'PRICE_EMA_ORDER','ema_triple':[35,70,105]}
        return v221.trend_eval(ind,ci,side,tv)
    if 'RSI_DIRECTIONAL_50' in rule:
        x=v221._safe(ind['RSI14'],ci);return x>=50 if side=='BUY' else x<=50
    if 'CCI_SIGN_ALIGNED' in rule:
        x=v221._safe(ind['CCI20'],ci);return x>0 if side=='BUY' else x<0
    raise ValueError('UNKNOWN_FROZEN_MTF_RULE:'+rule)

def causal_gate_context_class(v221):
    """Returns a narrow adapter; never monkey-patches or mutates frozen V221."""
    class CausalGateContext(v221.GateContext):
        def eval_family(self,family,variant,source_idx,bar_idx,sh,sl,boxhist,active_trend=None,session_server_ms=None):
            if family=='MULTI_TF':
                return causal_mtf_eval(v221,self.load,self.tf,source_idx,self.side,variant,active_trend)
            return super().eval_family(family,variant,source_idx,bar_idx,sh,sl,boxhist,active_trend,session_server_ms)
    return CausalGateContext
