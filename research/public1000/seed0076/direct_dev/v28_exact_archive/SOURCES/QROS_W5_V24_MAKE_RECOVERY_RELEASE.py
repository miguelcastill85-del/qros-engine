#!/usr/bin/env python3
"""Make SHA256/CRC self-audited W5 v24 preeconomic real-data recovery release.
The 2.57GB raw source is NOT duplicated; eight original Drive ZIPs are external exact pins.
"""
import pathlib,zipfile,json,hashlib,os,datetime,sys
base=pathlib.Path('/mnt/data/QROS_W5_REALDATA_20260924');mount=pathlib.Path('/mnt/data');repo='miguelcastill85-del/qros-engine';out=mount/'QROS_W5_V24_REAL_DEV_SOURCE_AND_TICK_PARITY_20260924.zip'
parts=[('14wIm9bBPq7eRikgLp03swoVNmztgkfmN','102025545'),('1w_JxSuVpInp44EcUC9fgxlCILQuAbqY5','100422805'),('1QL-oatGoYum_tSlNmlF3djbVYB6EkKwD','99870071'),('193S2vMhoS63si1A6ZJnVxQ_9i6rSqa12','101825467'),('15ivpOfYuvtL1buanKyGu9LYBLY4NINgM','101538275'),('1XHZBUU-YvyeHDWZjxWdDevenG5G3AT3c','102849303'),('1Ho7uAW5eqoUktE1rVQsU4rYHsrUKpJ1r','104515054'),('1cido_oBhY_TjDWc30lfyFna0Oeo_1C_9','104291866')]
def hashfile(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for x in iter(lambda:f.read(8_388_608),b''):h.update(x)
 return h.hexdigest()
recovery=json.loads((base/'DEV_RECOVERY_RECEIPT.json').read_bytes());assert recovery['status']=='PASS'
ids=[]
for i,(drive,size) in enumerate(parts,1):
 path=mount/f'QROS_XAU_FULL_HISTORY_v2_part{i:03d}-of-035.zip';assert path.stat().st_size==int(size)
 ids.append({'part':i,'drive_id':drive,'zip_name':path.name,'zip_bytes':path.stat().st_size,'zip_sha256':hashfile(path),'payload_sha256':recovery['parts'][i-1]['payload_sha256'],'payload_used_bytes':recovery['parts'][i-1]['bytes_used']})
assert hashfile(base/'XAUUSD_DEV_PACKED17_151382388.bin')=='3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53'
extra={
 'source_raw_sha256':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53',
 'source_raw_bytes':2573500596,'source_raw_records':151382388,
 'original_bid_M1_bars_sha256':'35a8644644daab5fc04a218d5527c3839b5248471801f8a56ebb8a71a7457f59',
 'original_M1_indicators_sha256':'f30da86f6c11b5a6573b3571ffd3c3621bbe4d51134258c89d956d6f9ab115b5',
 'preregistered_bar_pin_typo':'35a8644644daab5fc04a218d5527c3839b5248471801f8a56bbb8a71a7457f59',
 'clean_bid_M1_bars_sha256':'8fed642eb3f948a9e0612d7b9b0ece453a71b32e41609a8fcc84ee41bd713b13',
 'clean_bid_M1_indicators_sha256':'8a522e381d86684523a3707ec618f6825af25c103059fc368014291de742bdf6',
 'full_valid_quote_raw_and_rearm_tape_sha256':'8e4cb5b630c44ae3a526bee81fde2493f7385619ba096c804275a9b79004bdd0',
 'carrier_restored_from_original_parts':ids,
 'scientific_locks':{'original_13cell_results_untouched':True,'W3_deferred':True,'economic_DEV_W5_executed':False,'holdout_open':False,'GA2_open':False},
 'tests_current_turn':{'v21_regressions_PASS':37,'v22_regressions_PASS':8,'v23_W5_source_PASS':21,'v23_realdata_negative_PASS':5,'v23_pipeline_12':'TIMED_OUT_NO_CURRENT_PASS'},
 'previous_v23_package_83_tests':'REPORTED_AND_PACKAGED_NOT_A_CURRENT_VERIFIED_RESULT',
 'next_only':'PROSPECTIVE_SANITIZED_INPUT_ADDENDUM_SHA_FREEZE; FULL_10_FAMILY_SOURCE_AND_RETEST_ENTRY_REAL_CANDIDATE_MASK_PARITY; THEN ONLY SINGLE_W5_CHUNKED_DEV_ECONOMIC_EXPLORATORY_WITH_APPROVED_COST_CONTRACT',
 'broker_clock_certified':False,'broker_commission_certified':False,'PnL_read':False
}
checkpoint={'schema':'QROS_SEED0076_W5_REAL_DEV_PRE_ECON_CHECKPOINT_V24','OBJECTIVE':'Rescue exact W5 2018-2019 DEV tick bytes, correct one-character W5 bar SHA typo, sanitize invalid quotes before fractals, prove full raw tick/rearm0 and MTF parity; never imply economic success.',
'AUTHORITY':{'scientific_branch':'research/seed0076-direct-dev-backtest-20260922','original_pointer_sha1':'8370decb2c8e033c4b60662e72f03b22516ae899','last_known_branch_commit':'73f53d83f2bc214a5e8bff062f3aec417415a4f0','governance_v2_2_main_pointer_sha1':'3996a65e3377da6976a5457177d6a169cee93ff3','frozen_V209_source_sha1':'c6f7ac8b1daea6096f1e36b10bacbc5e6f2a8ebf','original_V220_sha1':'805044c9918a87456a95e150a1c9a1292112cf4c','prereg_W5_SHA1':'40275ce4fc0454759a181d9e3d7e8757630134da'},
'DATA':extra,'WORK_EXECUTED':['Fetched eight exact original XAU history ZIPs from Google Drive by ID','ZIP CRC and each complete 20m tick payload SHA-256 verified','Restored first 151382388 raw Packed17 ticks; full SHA matched exact pinned original','Rebuilt original M1 BID bars and original 36-indicator cache, old manifest SHA matches','Recomputed quote-valid M1 bars/indicators excluding invalid-only minutes without imputation','Processed full valid quotes for BUY/SELL raw tick break + four ATR buffers + rearm 0','Independent full-tape offline rearm oracle + 240 Python reference sample comparisons','Rebuilt M5/M15 from sanitized M1 and independently checked 185092 MTF completion indices'],
'RESULTS_VERIFIED':{'DEV_exact_SHA_match':True,'old_M1_and_IND_SHA_match':True,'invalid_zero_spread':942184,'invalid_crossed':74,'invalid_only_M1_removed':27,'sanitized_M1_bars':681745,'real_quote_full_raw_and_rearm_oracle_8_of_8':True,'independent_raw_python_window_checks':240,'independent_M5_M15_MTF_checks':185092},
'GATES':{'exact_data':'PASS','quote_data_audit':'PASS','sanitized_M1_1051_independent_bar_oracle':'PASS','full_guarded_tick_raw_rearm_0':'PASS','MTF_real_closed_bar_boundary':'PASS','all_10_family_11176_filters_real_tick':'PENDING','RETEST_ENTRY_full_real_tick':'PENDING','session_DST_calendar_broker_certified':'PENDING','broker_commission_certified':'PENDING','W5_economic_backtest':'NOT_RUN','Gate_A':'NOT_OPEN','holdout':'SEALED','GA2':'SEALED'},
'PROBLEMS':['New prereg bar SHA typo: expected hash differs from restored historic SHA by one character','27 M1 bars lack any executable tick; original extrema contain quote contamination in some bars','W5 v23 pipeline 12-suite timed out current turn; previous packaged PASS is not reverified'],
'ROOT_CAUSES':['New prereg copied one-character incorrect bar pin despite older economic manifests pointing to exact correct bytes','Original V220 formed BID OHLC without valid Ask guard','v23 realdata external route previously had no mounted original raw carrier'],
'CORRECTIONS':['Bound correct old M1 bar SHA to exact reconstructed bytes; preserve original prereg unchanged','Created separate versioned valid-quote M1 and MTF caches with published SHA and unmodified original carrier','Invalid quotes excluded before raw break or rearm; dropped 27 invalid-only bars without synthetic prices','Bound raw tape and full offline oracle outputs by SHA256'],
'SCIENTIFIC_STATE':'DEVELOPMENT_RUNNING_W5_PREREGISTERED_NO_ECONOMIC_RESULTS','PORTFOLIO_IMPACT':'NONE_VERIFIED_NO_LIVE_AND_NO_APPROVAL','NEXT_AUTOMATIC_ACTION':extra['next_only'], 'TIME_BUDGET_POLICY':'120s per route and 45s without verified bytes; 2 distinct preregistered equivalent routes. No unattended task authorized by this release.'}
cp=base/'V24_W5_SCIENTIFIC_CHECKPOINT.json';cp.write_text(json.dumps(checkpoint,sort_keys=True,indent=2)+'\n')
readme=f'''# QROS W5 v2.4 — real DEV pre-economic receipt\n\nRecovered 151382388 exact original XAU Packed17 ticks from eight signed Drive fragments. 2.57GB raw is intentionally not duplicated in release. Rehydrate from `CARRIER_EXTERNAL_ZIP_PINS.json` with `QROS_W5_RECOVER_DEV_20260924.py`, compare exact SHA before use. The v23 release remains immutable; no W3 changes or holdout.\n\nOriginal historical BAR hash is `35a864...a56ebb8...`; W5 prereg contains typo `...a56bbb8...`. Restore exact original historical bytes and preserve original prereg as evidence. New sanitized caches are **derived inputs**, not replacements for frozen historical artifacts. New semantics must be SHA-frozen in addendum BEFORE W5 economics.\n\nReal full tick pre-economic raw break/rearm0 parity 8/8 channels, Python real stratified 240 checks, M5+M15 185092 independent no-lookahead checks. NEW full 10-family masks, RETEST_ENTRY and broker session/cost profiles unverified; W5 economics not executed. 71/83 previous regression tests re-executed and PASS; 12 pipeline integration tests timed out on current replay and must be investigated separately within bounded attempts (historic v23 archived 12 PASS is REPORTADO here).\n\nRun current artifacts under the same one-stage time budgets; do not mistake real raw signal candidates for economic strategy trades. No GA2, no holdout, no original economic archive rewrite.\n'''
(base/'README_V24_W5.md').write_text(readme)
(base/'CARRIER_EXTERNAL_ZIP_PINS.json').write_text(json.dumps({'schema':'QROS_W5_V24_EXACT_CARRIER_EIGHT_DRIVE_PART_PINS','parts':ids,'full_raw_SHA256':extra['source_raw_sha256'],'full_raw_bytes':extra['source_raw_bytes']},indent=2,sort_keys=True)+'\n')
entries=[
 ('README_V24_W5.md',base/'README_V24_W5.md'),('V24_W5_SCIENTIFIC_CHECKPOINT.json',cp),('CARRIER_EXTERNAL_ZIP_PINS.json',base/'CARRIER_EXTERNAL_ZIP_PINS.json'),
 ('source/QROS_W5_RECOVER_DEV_20260924.py',mount/'QROS_W5_RECOVER_DEV_20260924.py'),('source/QROS_W5_BUILD_M1_20260924.py',mount/'QROS_W5_BUILD_M1_20260924.py'),
 ('source/qros_seed0076_indicators_v220.py',base/'qros_seed0076_indicators_v220.py'),('source/QROS_W5_BUILD_INDICATORS.py',base/'QROS_W5_BUILD_INDICATORS.py'),
 ('source/QROS_W5_V24_PIN_ERRATUM_PREFLIGHT.py',base/'QROS_W5_V24_PIN_ERRATUM_PREFLIGHT.py'),('source/QROS_W5_VALID_QUOTE_BAR_AND_FRACTAL_AUDIT.py',base/'QROS_W5_VALID_QUOTE_BAR_AND_FRACTAL_AUDIT.py'),
 ('source/QROS_W5_SANITIZED_M1_CACHE_V24.py',base/'QROS_W5_SANITIZED_M1_CACHE_V24.py'),('source/QROS_W5_REAL_GUARDED_RAW_REARM_V24.py',base/'QROS_W5_REAL_GUARDED_RAW_REARM_V24.py'),('source/QROS_W5_MTF_VALID_CAUSAL_V24.py',base/'QROS_W5_MTF_VALID_CAUSAL_V24.py'),
 ('legacy/frozen_original_V220.py',base/'frozen_structural.py'),
 ('receipts/DEV_RECOVERY_RECEIPT.json',base/'DEV_RECOVERY_RECEIPT.json'),('receipts/BAR_REBUILD_RECEIPT.json',base/'BAR_REBUILD_RECEIPT.json'),('receipts/IND_REBUILD_RECEIPT.json',base/'IND_REBUILD_RECEIPT.json'),('receipts/V24_EXACT_REAL_DEV_PREFLIGHT_AND_BAR_PIN_ERRATUM.json',base/'V24_EXACT_REAL_DEV_PREFLIGHT_AND_BAR_PIN_ERRATUM.json'),('receipts/V24_REAL_QUOTE_BAR_W5_CAUSALITY_AUDIT.json',base/'V24_REAL_QUOTE_BAR_W5_CAUSALITY_AUDIT.json'),('receipts/V24_SANITIZED_M1_CACHE_RECEIPT.json',base/'V24_SANITIZED_M1_CACHE_RECEIPT.json'),('receipts/V24_REAL_GUARDED_COUNTS_CHECKPOINT.json',base/'V24_REAL_GUARDED_COUNTS_CHECKPOINT.json'),('receipts/V24_REAL_GUARDED_TICK_RAW_AND_REARM0_ORACLE_RECEIPT.json',base/'V24_REAL_GUARDED_TICK_RAW_AND_REARM0_ORACLE_RECEIPT.json'),('receipts/V24_MTF_VALID_CACHE_AND_INDEPENDENT_CAUSAL_PARITY.json',base/'V24_MTF_VALID_CACHE_AND_INDEPENDENT_CAUSAL_PARITY.json'),
 ('artifacts/XAUUSD_M1_VALID_BID_BARS_V24.npy',base/'XAUUSD_M1_VALID_BID_BARS_V24.npy'),('artifacts/XAUUSD_M5_VALID_BID_BARS_V24.npy',base/'XAUUSD_M5_VALID_BID_BARS_V24.npy'),('artifacts/XAUUSD_M15_VALID_BID_BARS_V24.npy',base/'XAUUSD_M15_VALID_BID_BARS_V24.npy'),('artifacts/W5_VALID_QUOTE_RAW_AND_REARM_TAPES_V24.npz',base/'W5_VALID_QUOTE_RAW_AND_REARM_TAPES_V24.npz'),
 ('evidence/V24_TESTS_V21_37.log',base/'V24_TESTS_V21_37.log'),('evidence/V24_TESTS_V22_8.log',base/'V24_TESTS_V22_8.log'),('evidence/V24_TESTS_W5_SOURCE_21.log',base/'V24_TESTS_W5_SOURCE_21.log'),('evidence/V24_TESTS_REALDATA_NEG_5.log',base/'V24_TESTS_REALDATA_NEG_5.log'),('evidence/V24_TESTS_PIPELINE_12_TIMEOUT.log',base/'V24_TESTS_PIPELINE_12.log'),
]
assert all(p.is_file() for _,p in entries),[(n,str(p)) for n,p in entries if not p.is_file()]
manifest={'schema':'QROS_W5_V24_RELEASE_SHA256_CONTENT_MANIFEST','entries':[{'path':n,'bytes':p.stat().st_size,'sha256':hashfile(p)} for n,p in entries],'scientific_state':'DEVELOPMENT_RUNNING_W5_PREREGISTERED_NO_ECONOMIC_RESULTS','source_duplicated_gb':0,'holdout_open':False,'GA2_open':False}
man=base/'V24_FILE_MANIFEST.json';man.write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=3,allowZip64=True) as z:
 for n,p in entries:z.write(p,arcname=n)
 z.write(man,arcname='V24_FILE_MANIFEST.json')
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None
 for item in manifest['entries']:
  payload=z.read(item['path']);assert len(payload)==item['bytes'] and hashlib.sha256(payload).hexdigest()==item['sha256'],item['path']
assert len(manifest['entries'])+1==len(zipfile.ZipFile(out).namelist())
print(json.dumps({'status':'V24_PACKAGE_CRC_AND_MEMBER_SHA256_PASS','path':str(out),'bytes':out.stat().st_size,'sha256':hashfile(out),'members':len(entries)+1,'eight_verified_historical_zip_pins':len(ids),'raw_carrier_sha256':extra['source_raw_sha256'],'holding_locks':checkpoint['GATES']},sort_keys=True))
