#!/usr/bin/env python3
"""Evidence-bound, non-mutating correction of one-character W5 bar SHA typo.
Requires: two independent sources: real rebuilt bytes + older signed W5 manifest.
Does not change historical preregistration or authorize economic execution.
"""
from __future__ import annotations
import pathlib,sys,json,zipfile,hashlib,os,datetime
BASE=pathlib.Path('/mnt/data');root=BASE/'QROS_W5_REALDATA_20260924'
sys.path.insert(0,str(BASE/'qros_nonstall_v23'/'work'))
import qros_w5_realdata_preflight_v1 as pre
oldzip=BASE/'QROS_SEED0076_DIRECT_M1_W5_17258_EVIDENCE_20260923.zip'
with zipfile.ZipFile(oldzip) as z:old=json.loads(z.read('direct_w5_7family_dev_v1/MANIFEST.json'))
assert old['raw_xau_sha256']==pre.PINS['ticks']['sha256']
assert old['ind_sha256']==pre.PINS['indicators']['sha256']
orig_in_prereg=pre.PINS['bars']['sha256'];corrected=old['bar_sha256']
assert corrected=='35a8644644daab5fc04a218d5527c3839b5248471801f8a56ebb8a71a7457f59'
assert orig_in_prereg=='35a8644644daab5fc04a218d5527c3839b5248471801f8a56bbb8a71a7457f59'
assert sum(x!=y for x,y in zip(corrected,orig_in_prereg))==1
pre.PINS['bars']['sha256']=corrected
result=pre.audit(root/'XAUUSD_DEV_PACKED17_151382388.bin',root/'XAUUSD_M1_BID_BARS.npy',root/'XAUUSD_M1_INDICATORS.npz')
assert result['status']=='REAL_DEV_CARRIER_SHA_AND_BASIC_QUOTE_AUDIT_PASS'
assert result['data_SHA256']['bars']==corrected
receipt={'schema':'QROS_W5_V24_PIN_ERRATUM_AND_REAL_DEV_PREFLIGHT','status':'REAL_DEV_EXACT_CARRIER_BARS_INDICATORS_AND_BASIC_QUOTE_AUDIT_PASS','original_prereg_bar_pin_preserved':orig_in_prereg,'verified_correct_bar_pin_from_prior_7family_manifest':corrected,'original_prereg_bar_pin_one_char_typo':True,'old_manifest_archive_sha256':None,'parent_manifest_member':'direct_w5_7family_dev_v1/MANIFEST.json','parent_manifest_sha256':oldzip.name,'source_timestamps':'DARWINEX_BROKER_SERVER_CLOCK_UNVERIFIED','real_data_preflight':result,'economic_run_authorized':False,'holdout_open':False,'GA2_open':False,'still_required':['BROKER_TIMEZONE_DST_OR_NON_SESSION_FILTER_PROFILE','GUARDED_ACTUAL_TICK_RAW_CROSS_REARM_0_FULL_PARITY','ALL_10_FAMILY_TICK_RETEST_MTF_NONLOOKAHEAD','COST_PROFILE_CERTIFICATION'],'original_scientific_specs_mutated':False}
h=hashlib.sha256();
with oldzip.open('rb') as f:
 for b in iter(lambda:f.read(8_388_608),b''):h.update(b)
receipt['old_manifest_archive_sha256']=h.hexdigest()
out=root/'V24_EXACT_REAL_DEV_PREFLIGHT_AND_BAR_PIN_ERRATUM.json';tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');os.replace(tmp,out)
print(json.dumps({'status':receipt['status'],'quotes':result['quote_issues'],'bars':result['M1_bar_count'],'bar_typo':True,'economic_run_authorized':False}),flush=True)
