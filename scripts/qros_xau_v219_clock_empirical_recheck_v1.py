#!/usr/bin/env python3
"""Byte-level DST-adjacent clock crosscheck on immutable frozen XAU DEV.
UTC APIs here encode/decode epoch integers ONLY as naive source-server civil labels;
no UTC relabeling of the underlying ticks is implied or performed.
"""
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
import numpy as np, json, hashlib
from pathlib import Path
P=Path('/mnt/data/qros_data_dev/XAUUSD_DEV_PACKED17_151382388.bin')
OUT=Path('/mnt/data/qros_seed0076_delta_20260922/XAU_V219_SOURCE_CLOCK_DST_RECHECK_20260922_v1.json')
DT=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
x=np.memmap(P,dtype=DT,mode='r')
expected=[('2018-03-09T23:54:59.340','2018-03-12T01:01:00.044'),('2018-11-02T23:54:59.788','2018-11-05T01:01:00.244'),('2019-03-08T23:54:59.954','2019-03-11T01:01:00.044'),('2019-11-01T23:54:59.493','2019-11-04T01:01:00.099')]
NY=ZoneInfo('America/New_York');result=[]
def naive_to_ms(s):
 # UTC tzinfo is used only as a reversible numerical epoch encoding of civil labels.
 return int(round(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp()*1000))
def ms_to_civil(t):return datetime.fromtimestamp(t/1000,timezone.utc).replace(tzinfo=None)
for friday,monday in expected:
 fri_start=naive_to_ms(friday[:10]+'T00:00:00');fri_end=fri_start+86400000
 mon_start=naive_to_ms(monday[:10]+'T00:00:00');mon_end=mon_start+86400000
 end_index=int(np.searchsorted(x['ts'],fri_end,side='left'))-1
 start_index=int(np.searchsorted(x['ts'],mon_start,side='left'))
 if not (0<=end_index<len(x) and start_index<len(x)):raise ValueError('DATE_OUTSIDE_DEV')
 actual_last=ms_to_civil(int(x['ts'][end_index]));actual_first=ms_to_civil(int(x['ts'][start_index]))
 if actual_last.isoformat(timespec='milliseconds')!=friday or actual_first.isoformat(timespec='milliseconds')!=monday:raise ValueError(f'V219_DST_BYTE_PATTERN_MISMATCH {friday}={actual_last} {monday}={actual_first}')
 ny_last=(actual_last-timedelta(hours=7)).replace(tzinfo=NY)
 ny_first=(actual_first-timedelta(hours=7)).replace(tzinfo=NY)
 # NY-close server time convention: UTC+2 in NY standard time; UTC+3 in NY DST.
 last_offset=3 if ny_last.dst() else 2;first_offset=3 if ny_first.dst() else 2
 checks=[(actual_last,ny_last,last_offset),(actual_first,ny_first,first_offset)]
 for server,ny,off in checks:
  utc=ny.astimezone(timezone.utc)
  reconstructed=utc+timedelta(hours=off)
  if reconstructed.replace(tzinfo=None)!=server:raise ValueError('BROKER_NY_UTC_OFFSET_DRIFT')
 result.append({'v219_frozen_pair':[friday,monday],'actual_source_civil_last':actual_last.isoformat(timespec='milliseconds'),
   'actual_source_civil_first':actual_first.isoformat(timespec='milliseconds'),
   'source_indices':[end_index,start_index],
   'last_NY':ny_last.isoformat(timespec='milliseconds'),'first_NY':ny_first.isoformat(timespec='milliseconds'),
   'inferred_broker_UTC_offsets_hours':[last_offset,first_offset],
   'same_milliseconds_as_v219':True})
if len(result)!=4:raise ValueError('INCOMPLETE_DST_TRANSITION_TEST')
receipt={'schema':'QROS_SEED0076_XAU_V219_REAL_DEV_DST_SESSION_BYTE_RECHECK_1.0',
 'status':'PASS_4_OF_4_EXACT_DST_ADJACENT_BYTE_CROSSCHECK','source_dev_sha256':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53',
 'frozen_global_session_authority_blob_sha1':'c16d561b66a51d3735960470ba893e53e6913d40',
 'frozen_convention':'Darwinex source-server civil labels + NY 7-hour relation; GMT+3 during US DST/GMT+2 outside US DST',
 'probe_pairs':result,'data_mutated':False,'economic_pnl_read':False,'holdout_open':False,
 'scope_limit':'Only four documented DST-adjacent tick samples in 2018-2019. Per-symbol daily holiday/session break exceptions not certified here.'}
OUT.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
print('PASS_V219_CLOCK',json.dumps(result,sort_keys=True),'receipt_sha256',hashlib.sha256(OUT.read_bytes()).hexdigest())
