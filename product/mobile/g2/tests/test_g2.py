"""G2 adversarial parity, census, failure injection, no-op and contamination tests."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

G2 = Path(__file__).resolve().parents[1]
REPO = G2.parents[2]
BACKEND = G2.parent/'backend'
sys.path.insert(0,str(G2))
from shard_engine import (IntegrityError,blueprint_from_raw,canonical_bytes,digest,
                          native_matches,product_oracle,random_access_row,run_shards,
                          spec_bytes,report_filename)

FIXTURE = REPO/'product/mobile/flutter_app/test/fixtures/universe_oracle.json'
NATIVE = os.environ.get('QROS_G2_NATIVE_BINARY')
BASE = json.loads(FIXTURE.read_text())


class Base(unittest.TestCase):
    def setUp(self):
        self.raw=json.loads(json.dumps(BASE['raw_input']))
        self.obj=blueprint_from_raw(self.raw)
        self.tmp=tempfile.TemporaryDirectory(prefix='qros-g2-')
        self.addCleanup(self.tmp.cleanup)
        self.work=Path(self.tmp.name)/'run'

    def cli(self, boundary=None, crash_start=0, max_new=None):
        cmd=[sys.executable,str(G2/'run_once.py'),'--fixture',str(FIXTURE),
             '--work',str(self.work),'--chunk','37']
        if max_new is not None:cmd.extend(['--max-new',str(max_new)])
        env=os.environ.copy()
        if boundary:
            env['QROS_G2_CRASH_BOUNDARY']=boundary
            env['QROS_G2_CRASH_START']=str(crash_start)
        else:
            env.pop('QROS_G2_CRASH_BOUNDARY',None)
            env.pop('QROS_G2_CRASH_START',None)
        return subprocess.run(cmd,capture_output=True,text=True,env=env,timeout=15)


class FiniteCensusTests(Base):
    def test_g1_exact_frozen_144_sha256(self):
        self.assertEqual(self.obj['raw_births'],144)
        self.assertEqual(digest(b''.join(product_oracle(self.obj))),BASE['oracle']['toy_enumeration_sha256'])
        self.assertEqual(digest(canonical_bytes(self.obj)[:-1]),BASE['oracle']['canonical_sha256'])

    def test_random_access_matches_independent_itertools_every_birth(self):
        for index,oracle in enumerate(product_oracle(self.obj)):
            self.assertEqual(random_access_row(self.obj,index),oracle)

    def test_seventeen_slice_boundaries(self):
        sizes=(1,2,3,7,8,11,12,17,19,23,24,37,38,47,71,72,143)
        full=list(product_oracle(self.obj))
        for count in sizes:
            for start in (0,1,37,72,144-count):
                if start+count>144:continue
                self.assertEqual(list(product_oracle(self.obj,start,count)),full[start:start+count])

    def test_zero_and_out_of_range(self):
        self.assertEqual(list(product_oracle(self.obj,144,0)),[])
        with self.assertRaisesRegex(IntegrityError,'RANK_OUT_OF_RANGE'):random_access_row(self.obj,144)
        with self.assertRaisesRegex(IntegrityError,'INVALID_ORACLE_SLICE'):list(product_oracle(self.obj,143,2))

    def test_no_live_or_lookahead_input(self):
        for field,bad in [('symbol','XAUUSD'),('observability','CURRENT_BAR'),('overnight_allowed',True),('max_entries_per_day',4)]:
            raw=json.loads(json.dumps(self.raw));raw[field]=bad
            with self.subTest(field=field),self.assertRaises(ValueError):blueprint_from_raw(raw)

    def test_each_axis_single_value_still_exact(self):
        for field in ('sides','timeframes','lookback_bars','confirmation_bars','stop_ratios','maximum_holding_bars'):
            raw=json.loads(json.dumps(self.raw));raw[field]=raw[field][:1]
            obj=blueprint_from_raw(raw)
            vals=list(product_oracle(obj))
            self.assertEqual(len(vals),obj['raw_births'])
            self.assertEqual(vals,[random_access_row(obj,i) for i in range(obj['raw_births'])])


@unittest.skipUnless(NATIVE,'Native path supplied via QROS_G2_NATIVE_BINARY')
class IndependentNativeTests(Base):
    def setUp(self):
        super().setUp()
        self.spec=Path(self.tmp.name)/'spec.txt'
        self.spec.write_bytes(spec_bytes(self.obj))

    def test_frozen_144_trade_by_trade_style_full_census(self):
        count,h=native_matches(Path(NATIVE),self.spec,self.obj)
        self.assertEqual(count,144)
        self.assertEqual(h,BASE['oracle']['toy_enumeration_sha256'])

    def test_selected_partial_ranges(self):
        for start,count in ((0,1),(1,37),(37,37),(72,71),(143,1),(144,0)):
            with self.subTest(start=start,count=count):
                n,h=native_matches(Path(NATIVE),self.spec,self.obj,start,count)
                self.assertEqual(n,count)
                self.assertEqual(h,digest(b''.join(product_oracle(self.obj,start,count))))

    def test_deterministic_random_census_subsets(self):
        rng=random.Random(0xA143)
        for _ in range(25):
            raw=json.loads(json.dumps(self.raw))
            for field in ('sides','timeframes','lookback_bars','confirmation_bars','stop_ratios','maximum_holding_bars'):
                raw[field]=rng.sample(raw[field],rng.randrange(1,len(raw[field])+1))
            obj=blueprint_from_raw(raw)
            self.spec.write_bytes(spec_bytes(obj))
            n,h=native_matches(Path(NATIVE),self.spec,obj)
            self.assertEqual(n,obj['raw_births'])
            self.assertEqual(h,digest(b''.join(product_oracle(obj))))

    def test_cpp_rejects_tampered_spec_and_unrecognized_keys(self):
        src=spec_bytes(self.obj)
        cases=[src.replace(b'SIM_XAUUSD',b'XAUUSD'),src.replace(b'BUY,SELL',b'BUY,BUY'),
               src.replace(b'raw_births=144',b'raw_births=145'),src+b'actor=QROS_CORE\n',
               src.replace(b'lookback_bars=5,10,15',b'lookback_bars=15,10,5'),
               src.replace(b'confirmation_bars=1,2',b'confirmation_bars=1,2,0'),b'{}\n',
               src.replace(b'1/1,2/1,3/2',b'0,2/1,3/2')]
        for i,bad in enumerate(cases):
            with self.subTest(case=i):
                self.spec.write_bytes(bad)
                r=subprocess.run([NATIVE,'--spec',str(self.spec),'--count-only'],capture_output=True)
                self.assertEqual(r.returncode,2)
                self.assertIn(b'G2_FAIL_CLOSED',r.stderr)

    def test_cpp_rejects_start_and_count_overflows(self):
        for args in (['--start','145'],['--start','143','--count','2'],['--start','-1'],['--count','18446744073709551616']):
            with self.subTest(args=args):
                r=subprocess.run([NATIVE,'--spec',str(self.spec),*args],capture_output=True)
                self.assertEqual(r.returncode,2)


class DurableShardTests(Base):
    def test_complete_four_shards_and_idempotent_replay(self):
        first=run_shards(self.work,self.raw,37)
        self.assertEqual(first['status'],'COMPLETE')
        self.assertEqual(first['verified_births'],144)
        self.assertEqual(first['verified_shards'],4)
        orig={p.name:digest(p.read_bytes()) for p in self.work.glob('shard-*.ids')}
        self.assertEqual(len(orig),4)
        self.assertEqual(run_shards(self.work,self.raw,37)['new_shards_this_run'],0)
        self.assertEqual(orig,{p.name:digest(p.read_bytes()) for p in self.work.glob('shard-*.ids')})

    def test_single_shard_budget_resumes_only_delta(self):
        half=run_shards(self.work,self.raw,37,max_new_shards=1)
        self.assertEqual(half['status'],'PAUSED')
        self.assertEqual(half['verified_births'],37)
        final=run_shards(self.work,self.raw,37)
        self.assertEqual(final['new_shards_this_run'],3)
        self.assertEqual(final['status'],'COMPLETE')

    def test_frozen_plan_cannot_change_chunk_or_inputs(self):
        run_shards(self.work,self.raw,37,max_new_shards=1)
        with self.assertRaisesRegex(IntegrityError,'FROZEN_IDENTITY_CHANGED'):
            run_shards(self.work,self.raw,10)
        edited=json.loads(json.dumps(self.raw));edited['sides']=['BUY']
        with self.assertRaisesRegex(IntegrityError,'FROZEN_IDENTITY_CHANGED'):
            run_shards(self.work,edited,37)

    def test_tampered_shard_fail_closed_without_recomputing(self):
        run_shards(self.work,self.raw,37)
        p=sorted(self.work.glob('shard-*'))[1]
        p.write_bytes(p.read_bytes().replace(b'BUY',b'SELL',1))
        with self.assertRaisesRegex(IntegrityError,'SHARD_TAMPER'):
            run_shards(self.work,self.raw,37)

    def test_forged_receipt_cannot_change_authority(self):
        run_shards(self.work,self.raw,37)
        p=sorted(self.work.glob('receipt-*'))[0]
        rec=json.loads(p.read_text());rec['holdout_open']=True
        p.write_bytes(canonical_bytes(rec))
        with self.assertRaisesRegex(IntegrityError,'RECEIPT_PROVENANCE_DRIFT'):
            run_shards(self.work,self.raw,37)

    def test_checkpoint_forged_ahead_aborts(self):
        run_shards(self.work,self.raw,37,max_new_shards=1)
        cp=self.work/'checkpoint.json'
        doc=json.loads(cp.read_text());doc['next_index']=144
        cp.write_bytes(canonical_bytes(doc))
        with self.assertRaisesRegex(IntegrityError,'CHECKPOINT_ROLLBACK_OR_FUTURE'):
            run_shards(self.work,self.raw,37)

    def test_truncated_receipt_rejected(self):
        run_shards(self.work,self.raw,37,max_new_shards=1)
        p=next(self.work.glob('receipt-*'))
        p.write_bytes(p.read_bytes()[:10])
        with self.assertRaisesRegex(IntegrityError,'INVALID_RECEIPT_JSON'):
            run_shards(self.work,self.raw,37)

    def test_missing_shard_halts_not_rebuild(self):
        run_shards(self.work,self.raw,37,max_new_shards=1)
        next(self.work.glob('shard-*')).unlink()
        with self.assertRaisesRegex(IntegrityError,'MISSING_FILE'):
            run_shards(self.work,self.raw,37)

    def test_duplicate_or_gap_receipt_rejected(self):
        run_shards(self.work,self.raw,37,max_new_shards=1)
        (self.work/'receipt-00000100-00000110.json').write_text('{}')
        with self.assertRaisesRegex(IntegrityError,'RECEIPT_GAP_OR_REPLAY'):
            run_shards(self.work,self.raw,37)

    def test_symlinked_shard_rejected(self):
        run_shards(self.work,self.raw,37,max_new_shards=1)
        p=next(self.work.glob('shard-*'))
        other=self.work/'outside.ids';other.write_bytes(p.read_bytes());p.unlink();p.symlink_to(other)
        with self.assertRaisesRegex(IntegrityError,'UNTRUSTED_FILE'):
            run_shards(self.work,self.raw,37)

    def test_zero_new_budget_records_no_false_completed(self):
        p=run_shards(self.work,self.raw,37,max_new_shards=0)
        self.assertEqual(p['status'],'PAUSED')
        self.assertEqual(p['verified_births'],0)
        self.assertEqual(p['new_shards_this_run'],0)

    def test_recovery_from_all_three_actual_process_exit_boundaries(self):
        baseline=run_shards(Path(self.tmp.name)/'baseline',self.raw,37)
        for boundary in ('AFTER_SHARD','AFTER_RECEIPT','AFTER_CHECKPOINT'):
            with self.subTest(boundary=boundary):
                self.work=Path(self.tmp.name)/boundary
                child=self.cli(boundary=boundary,crash_start=0)
                self.assertEqual(child.returncode,75,(child.stdout,child.stderr))
                final=run_shards(self.work,self.raw,37)
                self.assertEqual(final['status'],'COMPLETE')
                self.assertEqual(final['verified_shards'],4)
                self.assertEqual(final['last_receipt_sha256'],baseline['last_receipt_sha256'])
                self.assertEqual(run_shards(self.work,self.raw,37)['new_shards_this_run'],0)
                if boundary=='AFTER_SHARD':
                    self.assertEqual(len(list((self.work/'orphan').glob('shard-*.ids.*'))),1)

    def test_root_run_cli_no_authority(self):
        p=self.cli(max_new=2)
        self.assertEqual(p.returncode,0,p.stderr)
        obj=json.loads(p.stdout)
        self.assertEqual(obj['status'],'PAUSED')
        self.assertFalse(obj['scientific_authority'])
        self.assertFalse(obj['holdout_open'])
        self.assertEqual(obj['pnl_tests'],0)

if __name__=='__main__':unittest.main()
