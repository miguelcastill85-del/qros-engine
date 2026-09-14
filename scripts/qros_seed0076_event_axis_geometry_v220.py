from __future__ import annotations
import hashlib, json

def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()

def canonical_event_axis_id(asset, side, timeframe, availability_source_record_index):
    obj={'asset':asset,'side':side,'timeframe':timeframe,'availability_source_record_index':int(availability_source_record_index)}
    return hashlib.sha256(canonical(obj)).digest()

def candidate_instance_id(seed, asset, side, timeframe, signal_config_id, confirmed_level_identity, availability_source_record_index, transform_signature):
    obj={'seed':seed,'asset':asset,'side':side,'timeframe':timeframe,'signal_config_id':signal_config_id,
         'confirmed_level_identity':confirmed_level_identity,'availability_source_record_index':int(availability_source_record_index),
         'event_transform_signature':transform_signature}
    return hashlib.sha256(canonical(obj)).digest()

def geometry_pass(box_widths_distinct, fract_high, fract_low, atr14, fast_ema, contraction_n='OFF', max_box_atr='OFF', max_midpoint_to_fast_ema_atr='OFF'):
    if atr14 is None or atr14 <= 0:
        if max_box_atr!='OFF' or max_midpoint_to_fast_ema_atr!='OFF': return False
    width=abs(float(fract_high)-float(fract_low))
    if contraction_n!='OFF':
        n=int(contraction_n)
        if len(box_widths_distinct)<n: return False
        xs=box_widths_distinct[-n:]
        if not all(xs[i] > xs[i+1] for i in range(len(xs)-1)): return False
    if max_box_atr!='OFF' and not (width/float(atr14) <= float(max_box_atr)): return False
    midpoint=(float(fract_high)+float(fract_low))/2.0
    if max_midpoint_to_fast_ema_atr!='OFF' and not (abs(midpoint-float(fast_ema))/float(atr14) <= float(max_midpoint_to_fast_ema_atr)): return False
    return True
