import itertools, json, hashlib
FRONTIERS=[
 ('F02_SHOCK_MEASURE',[{'shock_measure':'TRUE_RANGE_OVER_ATR'},{'shock_measure':'ABS_CLOSE_TO_CLOSE_RETURN_OVER_ATR'},{'shock_measure':'BODY_OVER_ATR'}]),
 ('F03_ATR_PERIOD',[{'atr_period':x} for x in (7,10,20,28,50)]),
 ('F04_ATR_SMOOTHING',[{'atr_smoothing':x} for x in ('WILDER_RMA_TR','EMA_TR')]),
 ('F05_CLOSE_LOCATION',[{'close_location_filter':x} for x in ('TOP_BOTTOM_50PCT','TOP_BOTTOM_33PCT','TOP_BOTTOM_25PCT')]),
 ('F06_WICK_FILTER',[{'wick_filter':x} for x in ('MAX_OPPOSING_WICK_50PCT_RANGE','MAX_OPPOSING_WICK_33PCT_RANGE','MAX_OPPOSING_WICK_20PCT_RANGE')]),
 ('F07_POST_SHOCK_CONFIRMATION',[{'post_shock_confirmation':'NEXT_BAR_DIRECTIONAL_CLOSE','confirmation_window_bars':w} for w in (1,2,3)]+[{'post_shock_confirmation':'NEXT_BAR_BREAK_SHOCK_EXTREME','confirmation_window_bars':w} for w in (1,2,3)]+[{'post_shock_confirmation':'TWO_BAR_CONTINUATION','confirmation_window_bars':w} for w in (2,3)]),
 ('F08_VOLATILITY_CONTEXT',[{'volatility_regime_context':c,'volatility_lookback':l} for c in ('ATR_ABOVE_MEDIAN','ATR_PERCENTILE_20_80','ATR_TOP_QUINTILE','PRE_SHOCK_COMPRESSION') for l in (20,50,100,200,500)]),
 ('F09_SPREAD_CONTEXT',[{'spread_context':c,'spread_lookback':l} for c in ('SPREAD_BELOW_ROLLING_P75','SPREAD_BELOW_ROLLING_P90') for l in (50,100,500,2000)]+[{'spread_context':'SPREAD_POINTS_BELOW_FROZEN_CAP','spread_lookback':'CANONICAL_NOT_APPLICABLE'}]),
 ('F10_TICK_INTENSITY',[{'tick_intensity_context':c,'tick_intensity_lookback':l} for c in ('TICK_COUNT_ABOVE_MEDIAN','TICK_COUNT_TOP_QUINTILE') for l in (20,50,100,500)]),
 ('F11_REFRACTORY',[{'event_refractory_bars':x} for x in (1,2,3,5,8,13)]),
 ('F12_DAY_OF_WEEK',[{'day_of_week':x} for x in ('MON','TUE','WED','THU','FRI')]),
]
CORE={'bar_price_transform':'CLOSE','atr_reference_timing':['CURRENT_BAR_INCLUDED','LAGGED_ONE_BAR_PRE_SHOCK'],'shock_threshold':[1.0,1.25,1.5,1.75,2.0,2.5,3.0,3.5,4.0],'canonical_persistence_identities':18,'session':'ALL','gap_policy':'CORE_CURRENT_BEHAVIOR_NO_F13_MUTATION'}
def specs():
 for i in range(len(FRONTIERS)):
  ai,av=FRONTIERS[i]
  for j in range(i+1,len(FRONTIERS)):
   bi,bv=FRONTIERS[j]
   for a in av:
    for b in bv:
     yield {'frontiers':[ai,bi],'a':a,'b':b}
def main():
 s=list(specs()); assert len(s)==2229
 h=hashlib.sha256(); by_pair={}
 for x in s:
  z=json.dumps(x,sort_keys=True,separators=(',',':')).encode(); h.update(z+b'\n'); k='__X__'.join(x['frontiers']); by_pair[k]=by_pair.get(k,0)+1
 assert len(by_pair)==55 and sum(by_pair.values())==2229
 out={'schema':'QROS_G30_F13_CANONICAL_PAIR_ENUMERATION_V170_v1','resolved_frontiers':len(FRONTIERS),'pair_count':55,'pair_value_combinations':2229,'core_slice_identities':2*9*18,'raw_signal_identities_per_tf_feature_shard':2229*2*9*18,'shards_total_two_assets':24,'raw_signal_identities_total_two_assets':2229*2*9*18*24,'economic_buy_sell_configurations_before_exact_mask_dedupe':2229*2*9*18*24*2,'pair_spec_root_sha256':h.hexdigest(),'frontier_variant_counts':{k:len(v) for k,v in FRONTIERS},'pair_counts':by_pair,'core':CORE}
 print(json.dumps(out,sort_keys=True,separators=(',',':')))
if __name__=='__main__': main()
