#!/usr/bin/env python3
"""No-PnL rematerialization preflight for XAU BUY M1 frozen GA1 group00 only.
Consumes exact, already verified DEV and V220 caches. Never runs GA1, scorer or holdout.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

ROOT='/mnt/data'
GIT_SOURCES={
'qros_seed0076_ga1_shard_worker_v223.py':'c77e0a5156c5bb1a874d3c33fde49f162a2a3041',
'qros_seed0076_config_stream.py':'a01268bd8bab639977b22c419926d94306754bba',
'qros_seed0076_structural_v220.py':'805044c9918a87456a95e150a1c9a1292112cf4c',
'qros_seed0076_gate_engine_v221.py':'74290f11e7a95a25f54c5c9989af110de7dde4e2',
'qros_seed0076_carrier_masks_v221.py':'0396e5ed2f6e1579d3159b7f4e64d0cc8bf22b25'}
FROZEN={
'campaign':'PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA',
'shard_id':'aa2e1ab0ecd6cd08d18e98288e70847d6ff863c6790f0928b9109138abe24070',
'full_ordered_config_stream_sha256':'96d664f4c4efb431dbd475355249b51aa49c8ac656ad5fd1caaf46d7086fc1c3',
'group_index':0,'group_configs':33528,'group_local_distinct':10521,'group_local_duplicates':23007,
'group_original_delta_u32_bytes':96786988,
'group_original_delta_u32_sha256':'ff55eb32bddddff384736644888aff775c760b2e9f79c72d7ce328cf6b9c03cd',
'group_original_compressed_sha256':'3753e18781e4a62dbeec4cb66d3d098c303731ab81a9fe0ee7960261557c59bd',
'original_group_receipt_sha256':'25ffb7adc55b6dbf1fe75d6488ccb8ea854e4d9d584dae8aa71de00ae978ce6e',
'all24_distinct_masks_expected':303572,
'all24_semantic_root_sha256':'cf28be12f7dd94a9551fe018a4679d129d4373e6e186e17ef628f418d9b91ce4',
'all24_alias_root_sha256':'4151cccd363d4d71b29d123952dc5c4dd355fb2ea27806c09cb16a5cf3c1d458',
'dev_sha256':'3ddb3c95acb9284196c5b6db84385271702800209ee33b1b1a2e1bd59cc9ff53',
'V209_git_blob_sha1':'c6f7ac8b1daea6096f1e36b10bacbc5e6f2a8ebf',
'V219_clock_git_blob_sha1':'c16d561b66a51d3735960470ba893e53e6913d40',
'V212_symbol_session_git_blob_sha1':'e841166c558c93a15fef16f174e55449b1f8164d',
'preopen_diagnostic_sha256':'cd986a994480bb12dfbbb2aaa6520d22c58e0a9d4c408062773a668b1f06ffc8'}

class PreflightError(RuntimeError):pass

def require(ok,msg):
    if not ok:raise PreflightError(msg)

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for x in iter(lambda:f.read(8*1024*1024),b''):h.update(x)
    return h.hexdigest()

def gitblob(path):
    b=Path(path).read_bytes()
    return hashlib.sha1(('blob '+str(len(b))+'\0').encode()+b).hexdigest()

def build_descriptor():
    x={'asset':'XAUUSD','side':'BUY','timeframe':'M1','base_tuples':72,'filter_packages':11176,'signal_configs':804672}
    raw=json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    d=hashlib.sha256(raw).hexdigest()
    require(d==FROZEN['shard_id'],'FROZEN_SHARD_ID_MISMATCH')
    return {'descriptor':x,'shard_id':d,'descriptor_sha256':d}

def verify(*,base,source,check_heavy=True):
    base,source=Path(base),Path(source)
    dev=base/'qros_data_dev/XAUUSD_DEV_PACKED17_151382388.bin'
    require(dev.is_file() and dev.stat().st_size==2573500596,'XAU_DEV_MISSING_OR_SIZE_DRIFT')
    if check_heavy:require(digest(dev)==FROZEN['dev_sha256'],'XAU_DEV_SHA256_DRIFT')
    manifest=base/'qros_seed0076_delta_20260922/portable_groups/QROS_XAU_V220_CARRIER_GROUP_MANIFEST_20260922_v1.json'
    require(manifest.is_file(),'V220_CARRIER_MANIFEST_MISSING')
    m=json.loads(manifest.read_text());items={v['tf']:v for grp in m['groups'].values() for v in grp['members']}
    require(len(items)==17,'V220_17TF_MEMBERSHIP_DRIFT')
    verified=[]
    for tf,v in sorted(items.items()):
        for label,fname,expected in (('bars',v['bar_path'].split('/')[-1],v['bar_sha256']),('indicators',v['indicator_path'].split('/')[-1],v['indicator_sha256'])):
            p=base/('qros_bar_cache' if label=='bars' else 'qros_indicator_cache')/fname
            require(p.is_file(),'CACHE_MISSING_'+tf+'_'+label)
            if check_heavy:require(digest(p)==expected,'CACHE_SHA256_DRIFT_'+tf+'_'+label)
            verified.append({'tf':tf,'type':label,'sha256':expected,'bytes':p.stat().st_size})
    states=[]
    for file,sha in GIT_SOURCES.items():
        path=source/file
        if path.exists():
            require(gitblob(path)==sha,'GIT_SOURCE_BLOB_DRIFT_'+file)
            states.append({'file':file,'status':'VERIFIED','git_blob_sha1':sha})
        else: states.append({'file':file,'status':'NEEDS_EXACT_GITHUB_SOURCE','git_blob_sha1':sha})
    spec=source/'QROS_SEED0076_MACHINE_UNIVERSE_SPEC_V209_v1.json'
    if spec.exists():require(gitblob(spec)==FROZEN['V209_git_blob_sha1'],'V209_SPEC_BLOB_DRIFT')
    required=states+[{'file':spec.name,'status':'VERIFIED' if spec.exists() else 'NEEDS_EXACT_GITHUB_SOURCE','git_blob_sha1':FROZEN['V209_git_blob_sha1']}]
    shard=build_descriptor()
    return {'schema':'QROS_SEED0076_XAU_BUY_M1_GROUP00_MINIMAL_REPLAY_CAPSULE_1.0',
       'scope':'EXACT_MISSING_GROUP00_ONLY_NO_GA1_REENUMERATION_OR_ECONOMIC_PNL',
       'scientific_state':'PREREGISTERED_NO_RESULTS','economic_pnl_read':False,'holdout_open':False,'shard11_open':False,
       'frozen':FROZEN,'shard_descriptor':shard,'verified_caches':verified,'verified_cache_files':len(verified),
       'missing_source_closure':[x for x in required if x['status']!='VERIFIED'],
       'local_admission':'READY_ONLY_WHEN_EXACT_SOURCE_CLOSURE_PRESENT' if all(x['status']=='VERIFIED' for x in required) else 'INPUT_CARRIERS_PASS_SOURCE_CODE_CLOSURE_MISSING',
       'command_when_admitted':'python qros_seed0076_ga1_shard_worker_v223.py --shard-json <frozen_generated_shard_json> --spec <exact_V209_json> --out-dir <isolated_group00_dir> --receipt <non_economic_receipt> --ticks <verified_XAU_DEV> --bar-root <verified_V220_bar_cache> --ind-root <verified_V220_indicator_cache> --point 0.01 --expected-config-root 96d664f4c4efb431dbd475355249b51aa49c8ac656ad5fd1caaf46d7086fc1c3 --only-group-index 0',
       'admission_after_group_replay':'Require exact original uncompressed group00 SHA256 and counts; compressed zstd container digest is not a scientific requirement because compression settings/runtime may differ. Preserve 24-group semantic+alias-root full parity before any DEV PnL.',
       'clock_warning':'Use exact frozen V219+V212 and quarantine 28 early 2018 M1 01:00 bars at economic admission; never alter original feature/mask bytes to hide history.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',default=ROOT);ap.add_argument('--source',default='/mnt/data/qros_group00_frozen_source');ap.add_argument('--output',required=True);ap.add_argument('--skip-heavy-hashes',action='store_true');a=ap.parse_args()
    r=verify(base=a.base,source=a.source,check_heavy=not a.skip_heavy_hashes)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_suffix(out.suffix+'.tmp')
    tmp.write_text(json.dumps(r,sort_keys=True,indent=2)+'\n');tmp.replace(out)
    print(json.dumps({'status':r['local_admission'],'verified_cache_files':len(r['verified_caches']),'missing_source_closure':len(r['missing_source_closure']),'shard_id':r['shard_descriptor']['shard_id']}))

if __name__=='__main__':main()
