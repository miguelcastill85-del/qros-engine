#!/usr/bin/env python3
from decimal import Decimal
D=Decimal

def quote_from_packed(value, price_unit): return D(str(value))*D(str(price_unit))
def distance(a,b): return abs(D(str(a))-D(str(b)))
def atr_stop(atr,mult): return D(str(atr))*D(str(mult))
def structural_stop(entry,stop): return distance(entry,stop)
def mixed_stop(structural,atr,mode):
    s,a=D(str(structural)),D(str(atr))
    if mode=='TIGHTER': return min(s,a)
    if mode=='WIDER': return max(s,a)
    raise ValueError(mode)
def target_distance(r,multiple): return D(str(r))*D(str(multiple))
def qros_points(distance_quote,point_price): return D(str(distance_quote))/D(str(point_price))
def usd_value_of_distance(distance_quote,contract_size,volume='1'): return D(str(distance_quote))*D(str(contract_size))*D(str(volume))
def ndx_commission_per_order(volume='1'): return D('2.75')*D(str(volume))
def xau_commission_per_order(fill_price,volume='1'): return D('0.000025')*abs(D(str(fill_price)))*D('100')*D(str(volume))
