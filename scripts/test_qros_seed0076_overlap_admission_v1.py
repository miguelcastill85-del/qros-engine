#!/usr/bin/env python3
"""Adversarial synthetic-only seam tests; never run PnL or use actual DEV ticks.
Independent reference policy loop deliberately never calls production admit function.
"""
import copy
import hashlib
import json
import os
import random
import tempfile
import unittest
from pathlib import Path
import qros_seed0076_overlap_admission_v1 as p


def event(eid, cid='A', trigger=10, entry=None, exit_=None, side='BUY', reason='SAME_DAY', **updates):
    if entry is None: entry = trigger
    if exit_ is None: exit_ = entry + 10
    entry_px = '100'; stop = '90' if side == 'BUY' else '110'
    price = '105' if side == 'BUY' else '95'
    if reason == 'STOP': price = '85' if side == 'BUY' else '115'
    row = {'scenario_id':cid+'_'+eid,'canonical_signal_config_id':cid,
           'event_mask_sha256':hashlib.sha256(cid.encode()).hexdigest(),'event_id':eid,'side':side,
           'signal_observable_timestamp':trigger,'entry_trigger_timestamp':trigger,
           'entry_timestamp':entry,'entry_price':entry_px,'stop_price':stop,
           'exit_timestamp':exit_,'exit_price':price,'R':'-1.5' if reason=='STOP' else '0.5',
           'exit_reason':reason}
    row.update(updates)
    return row


def independent_reference(events):
    by = {}
    for x in events:
        by.setdefault(x['canonical_signal_config_id'], []).append(x)
    accepted = []; denied = []
    for cid in sorted(by):
        stream = sorted(by[cid],key=lambda x:(x['entry_trigger_timestamp'], x['entry_timestamp'], x['event_id'], x['scenario_id']))
        exit_at = None
        for x in stream:
            if exit_at is not None and x['entry_trigger_timestamp'] <= exit_at:
                denied.append((cid,x['event_id']))
            else:
                accepted.append((cid,x['event_id']))
                exit_at = x['exit_timestamp']
    return accepted,denied


def install_input(root, events):
    inp = root/'input'; inp.mkdir(exist_ok=True)
    trades = inp/'normalized_trades.jsonl'
    trades.write_bytes(''.join(p.canonical(x)+'\n' for x in events).encode())
    h = p.sha256(trades)
    receipt = {'status':'PASS','implementation':'PRIMARY','synthetic_only':True,
               'economic_pnl_read':False,'normalized_trades_sha256':h}
    (inp/'receipt.json').write_text(p.canonical(receipt)+'\n')
    manifest = {'schema':p.SCHEMA,'campaign':p.CAMPAIGN,'mode':p.MODE,'synthetic_fixture':True,
                'economic_pnl_read':False,'economic_decision_authorized':False,
                'overlap_policy_git_blob_sha1':p.OVERLAP_POLICY_SHA1,
                'normalizer_contract_git_blob_sha1':p.NORMALIZER_CONTRACT_SHA1,
                'normalizer_core_git_blob_sha1':p.NORMALIZER_CORE_SHA1,
                'normalized_trades_sha256':h,
                'normalizer_receipt':{'path':'receipt.json','sha256':p.sha256(inp/'receipt.json')}}
    (inp/'manifest.json').write_text(p.canonical(manifest)+'\n')
    return inp


def patch_manifest(path, edit):
    f=path/'manifest.json'; m=json.loads(f.read_text()); edit(m); f.write_text(p.canonical(m)+'\n')


class OverlapTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.root=Path(self.t.name)
    def tearDown(self):
        self.t.cleanup()
    def assertFailEvent(self, row, code):
        with self.assertRaisesRegex(p.AdmissionError,'^'+code+'$'):
            p.validate_event(row)
    def assertFailRows(self, rows, code):
        with self.assertRaisesRegex(p.AdmissionError,'^'+code+'$'):
            p.admit_normalized_events(rows)
    def test_base_fifo_equal_exit_rejected_and_next_admitted(self):
        rows=[event('a',trigger=10,exit_=15),event('b',trigger=12,exit_=13),
              event('c',trigger=15,exit_=17),event('d',trigger=16,exit_=19),event('other',cid='B',trigger=11)]
        a,b=p.admit_normalized_events(rows)
        self.assertEqual([(x['canonical_signal_config_id'],x['event_id']) for x in a],[('A','a'),('A','d'),('B','other')])
        self.assertEqual([(x['canonical_signal_config_id'],x['event_id']) for x in b],[('A','b'),('A','c')])
        self.assertTrue(all(x['active_event_id']=='a' for x in b))
    def test_tie_lexical_event_then_scenario(self):
        rows=[event('z',exit_=12),event('a',exit_=11)]
        a,b=p.admit_normalized_events(rows)
        self.assertEqual([x['event_id'] for x in a],['a'])
        self.assertEqual([x['event_id'] for x in b],['z'])
    def test_input_shuffle_does_not_change_admitted_bytes(self):
        rows=[event('a'),event('b',trigger=21),event('c',cid='C'),event('d',cid='B')]
        a,b=p.admit_normalized_events(rows)
        random.Random(33).shuffle(rows)
        c,d=p.admit_normalized_events(rows)
        self.assertEqual([p.canonical(x) for x in a],[p.canonical(x) for x in c])
        self.assertEqual([p.canonical(x) for x in b],[p.canonical(x) for x in d])
    def test_future_extension_does_not_change_past(self):
        rows=[event('a',exit_=15),event('b',trigger=16,exit_=20)]
        old=p.admit_normalized_events(rows)
        new=p.admit_normalized_events(rows+[event('future',trigger=200,exit_=220)])
        self.assertEqual([x['event_id'] for x in old[0]],[x['event_id'] for x in new[0] if x['entry_trigger_timestamp']<=20])
    def test_random_independent_policy_parity(self):
        r=random.Random(4702)
        for trial in range(240):
            rows=[]
            for ci in range(3):
                cid='ABC'[ci]; trigger=0; entry=0
                for j in range(r.randint(1,12)):
                    trigger+=r.randint(1,4)  # no ambiguous same-trigger carrier windows
                    entry=max(entry,trigger)+r.randint(0,2)
                    rows.append(event(str(j),cid=cid,trigger=trigger,entry=entry,exit_=entry+r.randint(0,7)))
            r.shuffle(rows)
            a,b=p.admit_normalized_events(rows)
            self.assertEqual(([(x['canonical_signal_config_id'],x['event_id']) for x in a],
                              [(x['canonical_signal_config_id'],x['event_id']) for x in b]),
                             independent_reference(rows),str(trial))
    def test_buy_and_sell_direction_and_r(self):
        self.assertEqual(p.validate_event(event('buy'))['R'],'0.5')
        self.assertEqual(p.validate_event(event('sell',cid='S',side='SELL'))['R'],'0.5')
        self.assertEqual(p.validate_event(event('stop',reason='STOP'))['R'],'-1.5')
        self.assertEqual(p.validate_event(event('sstop',cid='S',side='SELL',reason='STOP'))['R'],'-1.5')
    def test_old_synthetic_false_pass_bad_exit_reason(self):
        self.assertFailEvent(event('a',exit_reason='STOP'), 'EXIT_REASON_PRICE_CONFLICT')
    def test_old_synthetic_false_pass_wrong_r(self):
        self.assertFailEvent(event('a',R='-99'), 'R_PRICE_CONFLICT')
    def test_invalid_stop_direction(self):
        self.assertFailEvent(event('a',stop_price='101'),'INVALID_STOP_DIRECTION')
    def test_nonfinite_decimal(self):
        self.assertFailEvent(event('a',entry_price='NaN'),'NONFINITE_ENTRY_PRICE')
    def test_noncausal_signal(self):
        self.assertFailEvent(event('a',signal_observable_timestamp=11),'NONCAUSAL_EVENT_TIMESTAMPS')
    def test_noncausal_entry_and_exit(self):
        self.assertFailEvent(event('a',entry_timestamp=9),'NONCAUSAL_EVENT_TIMESTAMPS')
        self.assertFailEvent(event('a',exit_timestamp=8),'NONCAUSAL_EVENT_TIMESTAMPS')
    def test_bool_timestamp_rejected(self):
        self.assertFailEvent(event('a',entry_trigger_timestamp=True),'TIMESTAMP_INVALID')
    def test_duplicate_scenario(self):
        x=event('a'); self.assertFailRows([x,x],'DUPLICATE_SCENARIO_ID')
    def test_duplicate_candidate_event(self):
        self.assertFailRows([event('a'),event('a',scenario_id='other',trigger=21)],'DUPLICATE_CANDIDATE_EVENT_ID')
    def test_candidate_mask_drift(self):
        self.assertFailRows([event('a'),event('b',trigger=21,event_mask_sha256='e'*64)],'CANDIDATE_IDENTITY_DRIFT')
    def test_canonical_mask_duplicate_across_candidates(self):
        self.assertFailRows([event('a'),event('b',cid='B',event_mask_sha256=hashlib.sha256(b'A').hexdigest())],
                            'DUPLICATE_MASK_ACROSS_CANDIDATES')
    def test_same_trigger_conflicting_entry_windows(self):
        self.assertFailRows([event('a',trigger=10,entry=11),event('b',trigger=10,entry=12)],'SAME_TRIGGER_ENTRY_INCONSISTENT')
    def test_entry_chronology_inversion(self):
        self.assertFailRows([event('a',trigger=10,entry=30,exit_=40),event('b',trigger=20,entry=21,exit_=25)],'ENTRY_CHRONOLOGY_INVERSION')
    def test_manifest_production_rejected(self):
        i=install_input(self.root,[event('a')])
        patch_manifest(i,lambda m:m.update(mode='PRODUCTION',synthetic_fixture=False))
        with self.assertRaisesRegex(p.AdmissionError,'PRODUCTION_OR_UNTRUSTED_INPUT_FORBIDDEN'):
            p.run(i,self.root/'output')
    def test_manifest_policy_drift_rejected(self):
        i=install_input(self.root,[event('a')])
        patch_manifest(i,lambda m:m.update(overlap_policy_git_blob_sha1='0'*40))
        with self.assertRaisesRegex(p.AdmissionError,'OVERLAP_POLICY_DRIFT'):
            p.run(i,self.root/'output')
    def test_input_trades_hash_tamper_rejected(self):
        i=install_input(self.root,[event('a')])
        (i/'normalized_trades.jsonl').write_text('tamper\n')
        with self.assertRaisesRegex(p.AdmissionError,'NORMALIZED_TRADES_BYTES_DRIFT'):
            p.run(i,self.root/'output')
    def test_normalizer_receipt_tamper_rejected(self):
        i=install_input(self.root,[event('a')])
        (i/'receipt.json').write_text('{}')
        with self.assertRaisesRegex(p.AdmissionError,'NORMALIZER_RECEIPT_BYTES_DRIFT'):
            p.run(i,self.root/'output')
    def test_symlink_escape_rejected(self):
        i=install_input(self.root,[event('a')])
        (self.root/'outside.json').write_text('{}')
        (i/'outside.json').symlink_to(self.root/'outside.json')
        patch_manifest(i,lambda m:m.update(normalizer_receipt={'path':'outside.json','sha256':p.sha256(self.root/'outside.json')}))
        with self.assertRaisesRegex(p.AdmissionError,'INPUT_ESCAPES_ROOT'):
            p.run(i,self.root/'output')
    def test_receipt_path_traversal_rejected(self):
        i=install_input(self.root,[event('a')]);patch_manifest(i,lambda m:m.update(normalizer_receipt={'path':'../outside.json','sha256':'0'*64}))
        with self.assertRaisesRegex(p.AdmissionError,'PATH_TRAVERSAL'):
            p.run(i,self.root/'output')
    def test_output_atomic_commit_and_byte_identical_restart(self):
        i=install_input(self.root,[event('a'),event('b',trigger=11,entry=11)])
        out=self.root/'out';result=p.run(i,out)
        self.assertEqual((result['admitted_count'],result['rejected_count']),(1,1))
        self.assertFalse(result['economic_decision_authorized']);self.assertFalse(result['production_grant'])
        first={x.name:x.read_bytes() for x in out.iterdir()}
        again=p.run(i,out)
        self.assertTrue(again['idempotent_replay'])
        self.assertEqual(first,{x.name:x.read_bytes() for x in out.iterdir()})
        self.assertEqual(json.loads((out/'receipt.json').read_text())['status'],'PASS_SYNTHETIC_ONLY')
    def test_existing_partial_output_rejected(self):
        i=install_input(self.root,[event('a')]);out=self.root/'out';out.mkdir();(out/'admitted_normalized_trades.jsonl').write_text('partial')
        with self.assertRaisesRegex(p.AdmissionError,'OUTPUT_UNCOMMITTED'):
            p.run(i,out)
    def test_replayed_stale_input_fails_closed(self):
        i=install_input(self.root,[event('a')]);out=self.root/'out';p.run(i,out)
        install_input(self.root,[event('a'),event('b',trigger=21)])
        with self.assertRaisesRegex(p.AdmissionError,'NON_IDEMPOTENT_REPLAY'):
            p.run(i,out)
    def test_extra_staging_dir_does_not_block_clean_restart(self):
        i=install_input(self.root,[event('a')]);(self.root/'.out.staging.interrupted').mkdir()
        self.assertEqual(p.run(i,self.root/'out')['admitted_count'],1)
        self.assertTrue((self.root/'.out.staging.interrupted').exists())
    def test_cli_readback_smoke(self):
        i=install_input(self.root,[event('a')]);r=p.run(i,self.root/'out')
        for filename,h in r['artifacts_sha256'].items():
            self.assertEqual(p.sha256(self.root/'out'/filename),h)

if __name__=='__main__':
    unittest.main(verbosity=2)
