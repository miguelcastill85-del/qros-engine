#!/usr/bin/env python3
"""Negative controls on a non-authoritative copy of the frozen session evaluator."""
from pathlib import Path
import ast,hashlib,json,datetime as dt,sys
import numpy as np
import qros_xau_v221_session_source_oracle_v1 as s
out=Path('/mnt/data/qros_seed0076_delta_20260922/XAU_V219_CLOCK_NEGATIVE_CONTROL_RECEIPT_20260922_v1.json')
src=Path(s.__file__).read_text();extract=src.split('def session_eval_ms(server_ms,variant):',1)[1].split('\n\n# === EXACT V221 SOURCE FRAGMENT END ===',1)[0]
fn='def session_eval_ms(server_ms,variant):'+extract+'\n'
if fn.count('server-np.int64(7*3600000)')!=1:raise ValueError('SOURCE_MUTATION_PRECONDITION_CHANGED')
mutated=fn.replace('server-np.int64(7*3600000)','server-np.int64(6*3600000)')
ns={'np':np,'_dt':dt,'NY':s.NY,'LONDON':s.LONDON};exec(compile(mutated,'<isolated-mutant-six-hours>','exec'),ns)
# Daytime and boundary grid includes US vs UK DST mismatch weeks and late Sunday (market opens).
vals=[]
for day in [dt.date(2018,1,15),dt.date(2018,3,15),dt.date(2018,3,26),dt.date(2018,10,30),dt.date(2018,11,5),dt.date(2019,3,14),dt.date(2019,3,26),dt.date(2019,10,30),dt.date(2019,11,5)]:
 for hour in range(24):
  for minute in (0,15,29,30,44,59):
   ny=dt.datetime(day.year,day.month,day.day,hour,minute)
   vals.append(s.numeric_civil_millis(ny+dt.timedelta(hours=7)))
values=np.array(vals,np.int64)
truth=np.array([s.independent_truth(x) for x in values],bool)
orig_errors=0;mutant_detections=0;by_rule={}
for i,r in enumerate(s.RULES):
 correct=s.session_eval_ms(values,{'rule':r}); wrong=ns['session_eval_ms'](values,{'rule':r})
 orig=int(np.count_nonzero(correct!=truth[:,i]));found=int(np.count_nonzero(wrong!=truth[:,i]));orig_errors+=orig;mutant_detections+=found
 by_rule[r]={'correct_errors':orig,'six_hour_mutation_detected_errors':found}
if orig_errors!=0 or mutant_detections<=0:raise ValueError('NEGATIVE_CONTROL_FAILED')
receipt={'schema':'QROS_XAU_V219_SEED0076_SESSION_CLOCK_NEGATIVE_CONTROL_1.0','status':'PASS_MISBOUND_CLOCK_MUTATION_DETECTED',
'original_source_fragment_crc32':'ee065503','source_git_blob_sha1':'74290f11e7a95a25f54c5c9989af110de7dde4e2',
'isolated_wrong_clock_minus_six_hours_only':True,'cases':len(values),'window_comparisons':len(values)*len(s.RULES),
'correct_engine_mismatches':orig_errors,'incorrect_engine_mismatches':mutant_detections,'per_rule':by_rule,
'no_historical_pnl':True,'holdout_open':False,'mutated_copy_persisted':False}
out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
print('PASS_NEGATIVE_CLOCK_CANARY CASES',len(values),'WINDOWS',len(values)*len(s.RULES),'MUTATED_MISMATCHES',mutant_detections,'ORIGINAL_MISMATCHES',orig_errors,'RECEIPT_SHA256',hashlib.sha256(out.read_bytes()).hexdigest())
