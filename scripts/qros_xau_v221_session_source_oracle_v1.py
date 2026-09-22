#!/usr/bin/env python3
"""Narrow byte-frozen V221 session-function extract vs independent IANA evaluation.
Full module's Git blob is separately pinned: 74290f11e7a95a25f54c5c9989af110de7dde4e2.
This is a source-fragment reimplementation test, not full independent generator parity.
"""
import numpy as np
import datetime as _dt
from zoneinfo import ZoneInfo
from pathlib import Path
import hashlib,json,zlib
NY=ZoneInfo('America/New_York');LONDON=ZoneInfo('Europe/London')
# === EXACT V221 SOURCE FRAGMENT START ===
def session_eval_ms(server_ms,variant):
    """Evaluate frozen civil-session windows on exact event signal time.
    server_ms are Darwinex source-server civil labels encoded as epoch-like ms.
    V219 byte-level binding: server civil = America/New_York civil + 7h.
    London conversion uses IANA offsets per NY civil date; DST transition Sundays are non-session.
    """
    server=np.asarray(server_ms,dtype=np.int64)
    nyms=server-np.int64(7*3600000)
    mins=((nyms//60000)%1440).astype(np.int16)
    rule=variant['rule']
    if rule=='NY_RTH': return (mins>=570)&(mins<960)
    if rule=='NY_OPEN_120': return (mins>=570)&(mins<690)
    if rule=='NY_MIDDAY': return (mins>=690)&(mins<840)
    if rule=='NY_CLOSE_120': return (mins>=840)&(mins<960)
    day=np.floor_divide(nyms,np.int64(86400000))
    uniq,inv=np.unique(day,return_inverse=True)
    diffs=np.empty(len(uniq),dtype=np.int16)
    epoch_date=_dt.date(1970,1,1)
    for i,d in enumerate(uniq):
        date=epoch_date+_dt.timedelta(days=int(d))
        ndt=_dt.datetime(date.year,date.month,date.day,12,0,tzinfo=NY)
        ldt=ndt.astimezone(LONDON)
        diffs[i]=(_dt.date(ldt.year,ldt.month,ldt.day)-date).days*1440 + ldt.hour*60+ldt.minute-720
    lmins=(mins.astype(np.int32)+diffs[inv].astype(np.int32))%1440
    london=(lmins>=480)&(lmins<990)
    if rule=='LONDON': return london
    if rule=='LONDON_NY_OVERLAP': return london&(mins>=570)&(mins<960)
    raise ValueError(rule)

# === EXACT V221 SOURCE FRAGMENT END ===

ROOT=Path('/mnt/data/qros_seed0076_delta_20260922')
DT=np.dtype([('ts','<i8'),('bid','<i4'),('ask','<i4'),('flags','u1')])
RULES=('NY_RTH','NY_OPEN_120','NY_MIDDAY','NY_CLOSE_120','LONDON','LONDON_NY_OVERLAP')

def numeric_civil_millis(d):
 # timezone.utc represents numeric epoch encoding of source civil labels, never actual UTC origin.
 return int(round(d.replace(tzinfo=_dt.timezone.utc).timestamp()*1000))

def independent_truth(server_ms):
 raw=_dt.datetime.fromtimestamp(int(server_ms)/1000,tz=_dt.timezone.utc).replace(tzinfo=None)
 ny=(raw-_dt.timedelta(hours=7)).replace(tzinfo=NY)
 ld=ny.astimezone(LONDON)
 a=ny.hour*60+ny.minute; b=ld.hour*60+ld.minute
 ny_rth=570<=a<960; london=480<=b<990
 return (ny_rth,570<=a<690,690<=a<840,840<=a<960,london,london and ny_rth)

def main():
 s=Path(__file__).read_text();fragment=s.split('def session_eval_ms(server_ms,variant):',1)[1].split('\n\n# === EXACT V221 SOURCE FRAGMENT END ===',1)[0]
 fragment='def session_eval_ms(server_ms,variant):'+fragment+'\n'
 crc=zlib.crc32(fragment.encode())
 if crc!=int('ee065503',16):raise ValueError(f'V221_SESSION_EXTRACT_BYTE_MISMATCH got={crc:08x}')
 t=np.memmap('/mnt/data/qros_data_dev/XAUUSD_DEV_PACKED17_151382388.bin',dtype=DT,mode='r')
 real_idx=np.unique(np.linspace(0,len(t)-1,10031,dtype=np.int64));real=np.asarray(t['ts'][real_idx],dtype=np.int64)
 # Synthetic source-server labels cover all UK/US DST mismatch weeks, session thresholds and NY day shifts.
 synthetic=[];d=_dt.date(2018,1,1);last=_dt.date(2019,12,31)
 hours_minutes=((0,0),(2,59),(3,0),(4,0),(7,29),(7,30),(8,0),(9,29),(9,30),(11,29),(11,30),(12,59),(13,59),(14,0),(15,59),(16,0),(16,29),(16,30),(17,0),(18,0),(20,0),(23,59))
 while d<=last:
  if d.weekday()<5 or d.weekday()==6:
   for hour,minute in hours_minutes:
    if d.weekday()==6 and hour<18:continue
    naive=_dt.datetime(d.year,d.month,d.day,hour,minute)
    synthetic.append(numeric_civil_millis(naive+_dt.timedelta(hours=7)))
  d+=_dt.timedelta(days=1)
 cases=np.r_[real, np.array(synthetic,dtype=np.int64)]
 independent=np.array([independent_truth(ms) for ms in cases],dtype=bool)
 failures={};checks={};uniques=np.unique(((cases-7*3600000)//86400000))
 for j,rule in enumerate(RULES):
  result=session_eval_ms(cases,{'rule':rule})
  fail=np.flatnonzero(result!=independent[:,j]);checks[rule]=len(cases)
  if len(fail):failures[rule]={'count':len(fail),'first_server_ms':int(cases[fail[0]]),'expected':bool(independent[fail[0],j]),'actual':bool(result[fail[0]])}
 # Session source should fail closed on missing inputs, not silently infer UTC.
 try:session_eval_ms(real[:1],{'rule':'INVALID_SESSION'})
 except ValueError:bad_rule_rejected=True
 else:bad_rule_rejected=False;failures['INVALID_SESSION']='ACCEPTED'
 receipt={'schema':'QROS_SEED0076_XAU_V221_SESSION_PREDICATE_INDEPENDENT_IANA_CANARY_1.0','status':'PASS' if not failures else 'FAIL',
 'frozen_full_engine_blob_sha1':'74290f11e7a95a25f54c5c9989af110de7dde4e2','exact_session_function_crc32':f'{crc:08x}',
 'verified_historical_source_timestamp_samples':len(real),'synthetic_frozen_DST_and_session_boundaries':len(synthetic),
 'source_server_civil_dates':len(uniques),'six_rules_checked':checks,'independent_reference':'Python zoneinfo NY and London from raw source civil minus seven hours',
 'invalid_rule_rejected':bad_rule_rejected,'failures':failures,'no_economic_pnl':True,'holdout_open':False,
 'scope_limitation':'Source-fragment comparison; independent reference calendar checks six session windows on sampled real timestamps and constructed transition boundaries. Not exact event-generator, full historical every-tick proof, nor per-symbol execution calendar.'}
 out=ROOT/'XAU_V221_SESSION_PREDICATE_INDEPENDENT_IANA_CANARY_20260922_v1.json';out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
 print('SESSION_SOURCE_CRC',f'{crc:08x}','STATUS',receipt['status'],'REAL_SAMPLES',len(real),'SYNTHETIC',len(synthetic),'WINDOW_COMPARISONS',sum(checks.values()),'FAILURES',failures,'RECEIPT_SHA256',hashlib.sha256(out.read_bytes()).hexdigest(),flush=True)
 if failures:raise SystemExit(2)
if __name__=='__main__':main()
