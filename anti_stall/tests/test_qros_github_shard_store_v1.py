"""Adversarial software tests. Synthetic fixtures are NOT market/MT5 evidence."""
import base64, hashlib, io, json, pathlib, sys, tempfile, unittest, warnings, zipfile
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'chat'))
import qros_github_shard_store_v1 as S

def enc(o):return (json.dumps(o,sort_keys=True,separators=(',',':'))+'\n').encode()
def task(ch,ord):return {'ch':ch,'route':'r0_w1_batch000','ordinals':[ord]}
def file(r):return f"CH{r['channel']}_{r['route']}_I{r['ordinals'][0]:03d}_{r['ordinals'][-1]:03d}.json"
def rec(ch,ord,ph,raw):
    return {'schema':'QROS_W5_V33_INDEPENDENT_FROZEN_REMAINING_LARGE_CHANNEL_MASK_PARITY_SHARD_V1','channel':ch,'route':'r0_w1_batch000','ordinals':[ord], 'status':'PASS','new_economic_PNL':False,'Gate_A_approved':False,'holdout_open':False,'ga2_open':False,'plan_SHA256':ph,'original_raw_sha256':raw,'tested_mask_occurrences':1,'independent_exact_trades':1,'exact_fields':11,'sampled_signals':1,'tests':[{'ordinal':ord,'11_fields_compared':11,'PNL_blind_sampled_source_signals':1,'all_rejections_equal':True,'independent_exact_trades':1,'zero_signal_mask':False}]}
def fixture(n=2,gate=False):
    tasks=[task(0,i) for i in range(1,356)]+[task(4,i) for i in range(1,356)]
    plan=enc({'frozen_tasks':tasks});runner=b'# synthetic code fixture\n';raw='a'*64
    selected=tasks[:n]
    receipts={file(rec(t['ch'],t['ordinals'][0],S.sha(plan),raw)):enc(rec(t['ch'],t['ordinals'][0],S.sha(plan),raw)) for t in selected}
    from collections import Counter
    chcounts={str(k):v for k,v in Counter(t['ch'] for t in selected).items()}
    ledger=[{'filename':k,'sha256':S.sha(v)} for k,v in receipts.items()]
    master={'completed_shards':n,'pending_shards':710-n,'planned_shards':710,'frozen_plan_sha256':S.sha(plan),'source_runner_sha256':S.sha(runner),'original_raw_sha256':raw,'receipt_byte_manifest':ledger,'by_channel_complete':chcounts,'identical_independent_trades_new':n,'matching_independent_fields_new':n*11,'sampled_source_signals_new':n,'mask_occurrences_covered_new':n,'zero_signal_original_masks_new':[],'no_new_PnL':True,'Gate_A_approved':gate,'holdout_open':False,'ga2_open':False,'historical_account_commission_certified':False,'historical_symbol_special_hours_certified':False}
    files={'FROZEN_PLAN/V33_FROZEN_REMAINING_ALL_MASK_PLAN.json':plan,'MASTER/V33_PARTIAL_MASTER_RECEIPT.json':enc(master),'SOURCE/v33_run_frozen_remaining_large_mask_parity.py':runner,**{'RECEIPTS/'+k:v for k,v in receipts.items()}}
    manifest={'files':[{'name':k,'bytes':len(v),'sha256':S.sha(v)} for k,v in files.items()]}
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        for k,v in files.items():z.writestr(k,v)
        z.writestr('MANIFEST/V33_PARTIAL_INTERNAL_MANIFEST.json',enc(manifest))
    return buf.getvalue(),plan,runner,raw,receipts
class GitOnlyTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=pathlib.Path(self.temp.name);self.z,self.plan,self.runner,self.raw,self.receipts=fixture();self.sha=S.sha(self.z);self.path=self.root/'baseline.zip';self.path.write_bytes(self.z)
    def test_complete_synthetic_baseline(self):self.assertEqual(S.verify_baseline(self.path,self.sha)['completed'],2)
    def test_bad_external_archive_sha(self):
        with self.assertRaises(S.Stop):S.verify_baseline(self.path,'f'*64)
    def test_manifest_tamper_with_updated_outer_sha(self):
        # Mutate a real decompressed member, repackage with valid CRC, retain
        # original independent internal manifest. A mere changed outer hash
        # must not conceal the altered scientific source.
        buf=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.z)) as original,zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as out:
            for name in original.namelist():
                raw=original.read(name)
                if name=='SOURCE/v33_run_frozen_remaining_large_mask_parity.py':raw=b'SYNTHETIC source alteration\n'
                out.writestr(name,raw)
        bad=buf.getvalue();self.path.write_bytes(bad)
        with self.assertRaises(S.Stop):S.verify_baseline(self.path,S.sha(bad))
    def test_scientific_gate_must_stay_closed(self):
        bad,*_=fixture(gate=True);self.path.write_bytes(bad)
        with self.assertRaises(S.Stop):S.verify_baseline(self.path,S.sha(bad))
    def test_duplicate_zip_entry(self):
        buf=io.BytesIO(self.z)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',UserWarning)
            with zipfile.ZipFile(buf,'a') as z:z.writestr('MASTER/V33_PARTIAL_MASTER_RECEIPT.json',b'fake')
        self.path.write_bytes(buf.getvalue())
        with self.assertRaises(S.Stop):S.verify_baseline(self.path,S.sha(buf.getvalue()))
    def transport(self):
        b64=base64.b64encode(self.z).decode();parts=[b64[i:i+130] for i in range(0,len(b64),130)];rows=[];root=self.root/'segments';root.mkdir(exist_ok=True)
        for i,s in enumerate(parts):
            name=f'part_{i:03d}.b64';b=s.encode();(root/name).write_bytes(b);rows.append({'ordinal':i,'path':name,'sha256':S.sha(b),'git_blob_sha1':S.gb(b),'b64_characters':len(s)})
        idx={'schema':'QROS_W5_GITHUB_ASCII_TRANSPORT_V1','source_git_blob_sha1':S.gb(self.z),'parts':rows};ip=self.root/'index.json';ip.write_bytes(enc(idx));return root,ip
    def test_restore_from_git_text_parts(self):
        root,idx=self.transport();self.assertEqual(S.restore_ascii_parts(root,idx,self.sha),self.z)
    def test_detect_tampered_git_text_part(self):
        root,idx=self.transport();p=root/'part_000.b64';b=p.read_bytes();p.write_bytes((b'Z' if b[0:1]!=b'Z' else b'Y')+b[1:])
        with self.assertRaises(S.Stop):S.restore_ascii_parts(root,idx,self.sha)
    def test_detect_missing_git_text_part(self):
        root,idx=self.transport();(root/'part_001.b64').unlink()
        with self.assertRaises(FileNotFoundError):S.restore_ascii_parts(root,idx,self.sha)
    def test_baseline_chain_idempotent(self):
        x=S.load_chain(self.z,self.sha,[]);self.assertEqual(x['completed'],2);self.assertEqual(x['next']['0']['ordinals'],[3])
    def test_valid_synthetic_delta_then_duplicate_rejected(self):
        d=self.root/'new';d.mkdir();r=rec(0,3,S.sha(self.plan),self.raw);(d/file(r)).write_bytes(enc(r));out=self.root/'delta.json';s=S.build_delta(self.path,self.sha,[],d,out)
        self.assertEqual((s['completed'],s['new']),(3,1));self.assertEqual(S.load_chain(self.z,self.sha,[out])['pending'],707)
        with self.assertRaises(S.Stop):S.build_delta(self.path,self.sha,[out],d,self.root/'again.json')
    def test_delta_parent_drift(self):
        d=self.root/'new';d.mkdir();r=rec(0,3,S.sha(self.plan),self.raw);(d/file(r)).write_bytes(enc(r));out=self.root/'delta.json';S.build_delta(self.path,self.sha,[],d,out);j=json.loads(out.read_bytes());j['parent_sha256']='f'*64;out.write_bytes(enc(j))
        with self.assertRaises(S.Stop):S.load_chain(self.z,self.sha,[out])
    def test_forged_pass_with_bad_fields_is_rejected(self):
        d=self.root/'new';d.mkdir();r=rec(0,3,S.sha(self.plan),self.raw);r['exact_fields']=999;(d/file(r)).write_bytes(enc(r))
        with self.assertRaises(S.Stop):S.build_delta(self.path,self.sha,[],d,self.root/'delta.json')
    def test_seventh_shard_requires_checkpoint(self):
        d=self.root/'new';d.mkdir()
        for i in range(3,10):
            r=rec(0,i,S.sha(self.plan),self.raw);(d/file(r)).write_bytes(enc(r))
        with self.assertRaises(S.Stop):S.build_delta(self.path,self.sha,[],d,self.root/'delta.json')
    def test_non_frozen_ordinals_rejected(self):
        d=self.root/'new';d.mkdir();r=rec(0,999,S.sha(self.plan),self.raw);(d/file(r)).write_bytes(enc(r))
        with self.assertRaises(S.Stop):S.build_delta(self.path,self.sha,[],d,self.root/'delta.json')
if __name__=='__main__':unittest.main()
