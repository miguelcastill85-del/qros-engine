#!/usr/bin/env python3
from fractions import Fraction

def F(x): return Fraction(str(x))
def quote_from_packed(value, price_unit): return F(value)*F(price_unit)
def distance(a,b): return F(a)-F(b) if F(a)>=F(b) else F(b)-F(a)
def atr_stop(atr,mult): return F(atr)*F(mult)
def structural_stop(entry,stop): return distance(entry,stop)
def mixed_stop(structural,atr,mode):
    s,a=F(structural),F(atr)
    if mode=='TIGHTER': return s if s<=a else a
    if mode=='WIDER': return s if s>=a else a
    raise ValueError(mode)
def target_distance(r,multiple): return F(r)*F(multiple)
def qros_points(distance_quote,point_price): return F(distance_quote)/F(point_price)
def usd_value_of_distance(distance_quote,contract_size,volume='1'): return F(distance_quote)*F(contract_size)*F(volume)
def ndx_commission_per_order(volume='1'): return F('2.75')*F(volume)
def xau_commission_per_order(fill_price,volume='1'): return F('0.000025')*abs(F(fill_price))*F('100')*F(volume)
