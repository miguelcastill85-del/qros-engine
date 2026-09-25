"""Differential G3 Python/C++ synthetic execution tests; no real market/PnL."""
from __future__ import annotations
import hashlib
import importlib.util
import os
from pathlib import Path
import random
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from oracle import InvalidTimeline,simulate
CPP=Path(os.environ.get('QROS_G3_NATIVE_BINARY',str(ROOT/'native/qros_g3_exec')))

def row(t,bid,ask,session=1,end=0,bl=None,bh=None,al=None,ah=None):
    bl=bid if bl is None else bl
    bh=bid if bh is None else bh
    al=ask if al is None else al
    ah=ask if ah is None else ah
    return (t,bid,ask,bl,bh,al,ah,session,end)

def source(ticks,plans):
    return 'QROS_G3_SYNTHETIC_TIMELINE_V1\nTICKS|'+str(len(ticks))+'\n'+'\n'.join('|'.join(map(str,t)) for t in ticks)+'\nPLANS|'+str(len(plans))+'\n'+'\n'.join('|'.join(map(str,p)) for p in plans)+'\nEND\n'

def native(raw):
    proc=subprocess.run([str(CPP)],input=raw,text=True,capture_output=True,timeout=5)
    return proc

class G3DifferentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CPP.exists():raise AssertionError('INDEPENDENT_NATIVE_EXECUTOR_MUST_BE_COMPILED')

    def same(self,raw,marker=None):
        py=simulate(raw)
        c=native(raw)
        self.assertEqual(c.returncode,0,c.stderr)
        self.assertEqual(c.stdout,py)
        if marker:self.assertIn(marker,py)
        return py

    def rejected(self,raw):
        with self.assertRaises(InvalidTimeline):simulate(raw)
        cp=native(raw)
        self.assertNotEqual(cp.returncode,0)
        self.assertIn('QROS_G3_REJECTED:',cp.stderr)

    def test_buy_ask_entry_sell_bid_entry_and_session_exit(self):
        ticks=[row(1000,100,102),row(1001,100,102),row(1002,101,103,end=1)]
        out=self.same(source(ticks,[('A','BUY',0,1,5,100)]),'FILL|A|BUY|1|102|97|202|2|101|SESSION_CLOSE')
        self.assertEqual(out.count('FILL|'),1)
        out=self.same(source(ticks,[('B','SELL',0,1,5,10)]),'FILL|B|SELL|1|100|105|90|2|103|SESSION_CLOSE')
        self.assertEqual(out.count('FILL|'),1)

    def test_buy_ambiguous_low_high_sl_first(self):
        ticks=[row(1000,100,102),row(1001,100,102),row(1002,101,103,bl=96,bh=110,end=1)]
        self.same(source(ticks,[('A','BUY',0,1,5,5)]),'FILL|A|BUY|1|102|97|107|2|97|SL_FIRST')

    def test_sell_ambiguous_ask_low_high_sl_first(self):
        ticks=[row(1000,200,202),row(1001,200,202),row(1002,200,202,al=190,ah=210,end=1)]
        self.same(source(ticks,[('S','SELL',0,1,5,5)]),'FILL|S|SELL|1|200|205|195|2|205|SL_FIRST')

    def test_bid_ask_gap_worst_first_executable_quote(self):
        buy=[row(1000,100,102),row(1001,100,102),row(1002,90,92,end=1)]
        sell=[row(1000,200,202),row(1001,200,202),row(1002,208,210,end=1)]
        self.same(source(buy,[('A','BUY',0,1,5,5)]),'FILL|A|BUY|1|102|97|107|2|90|SL_FIRST')
        self.same(source(sell,[('B','SELL',0,1,5,5)]),'FILL|B|SELL|1|200|205|195|2|210|SL_FIRST')

    def test_favorable_target_first_quote(self):
        buy=[row(1000,100,102),row(1001,100,102),row(1002,110,112,end=1)]
        sell=[row(1000,200,202),row(1001,200,202),row(1002,188,190,end=1)]
        self.same(source(buy,[('A','BUY',0,1,5,5)]),'FILL|A|BUY|1|102|97|107|2|110|TP')
        self.same(source(sell,[('B','SELL',0,1,5,5)]),'FILL|B|SELL|1|200|205|195|2|190|TP')

    def test_same_tick_reentry_and_busy(self):
        t=[row(1000,100,102),row(1001,100,102),row(1002,106,108),row(1003,106,108,end=1)]
        p=[('A','BUY',0,1,5,3),('B','SELL',0,1,5,3),('C','SELL',0,2,5,3)]
        out=self.same(source(t,p),'SKIP|B|SELL|POSITION_BUSY')
        self.assertIn('SKIP|C|SELL|SAME_TICK_REENTRY',out)

    def test_daily_limit_exactly_three_and_session_reset(self):
        ticks=[]
        for s in (1,2):
            for i in range(10):
                t=1000+(s-1)*100+i
                bid=100 if i%2==1 else 110
                ticks.append(row(t,bid,bid+2,session=s,end=int(i==9)))
        plans=[]
        for s,base in ((1,0),(2,10)):
            for j,e in enumerate((1,3,5,7)):
                plans.append((f'S{s}_{j}','BUY',base,base+e,5,4))
        out=self.same(source(ticks,plans))
        self.assertEqual(out.count('|DAILY_LIMIT'),2)
        self.assertEqual(out.count('FILL|'),6)

    def test_no_entry_at_session_end(self):
        t=[row(1000,100,102),row(1001,101,103,end=1)]
        self.rejected(source(t,[('A','BUY',0,1,5,5)]))

    def test_missing_end_and_overnight_signal_rejected(self):
        a=[row(1000,100,102),row(1001,100,102,session=2,end=1)]
        self.rejected(source(a,[('A','BUY',0,1,5,5)]))
        b=[row(1000,100,102,end=1),row(1001,100,102,session=2),row(1002,101,103,session=2,end=1)]
        self.rejected(source(b,[('A','BUY',0,1,5,5)]))

    def test_reject_quote_corruption_or_lookahead(self):
        cases=[
            [row(1000,100,100),row(1001,100,102,end=1)],
            [row(1000,103,101),row(1001,100,102,end=1)],
            [row(1000,100,102),row(1000,100,102,end=1)],
            [row(1000,100,102,bl=110),row(1001,100,102,end=1)],
        ]
        for ts in cases:
            with self.subTest(ticks=ts):self.rejected(source(ts,[('A','BUY',0,1,5,5)]))
        self.rejected(source([row(1000,100,102),row(1001,101,103,end=1)],[('A','BUY',1,0,5,5)]))

    def test_incorrect_order_duplicate_id_and_invalid_bounds_rejected(self):
        ts=[row(1000,100,102),row(1001,100,102),row(1002,101,103,end=1)]
        self.rejected(source(ts,[('A','BUY',0,1,5,5),('A','SELL',0,1,5,5)]))
        self.rejected(source(ts,[('A','BUY',0,1,0,5)]))
        self.rejected(source(ts,[('A','BUY',0,1,5,100001)]))
        self.rejected(source(ts,[('A','BUY',0,8,5,5)]))

    def test_reject_unauthorized_mutation_or_injection(self):
        ts=[row(1000,100,102),row(1001,100,102),row(1002,100,102,end=1)]
        base=source(ts,[('A','BUY',0,1,5,5)])
        for corrupt in (base+'APPROVED_FINAL\n',base.replace('PLANS|1','PLANS|01'),base.replace('A|BUY','A|BUY|ADMIN'),base.replace('1000|','-1000|'),base.replace('QROS_G3_SYNTHETIC_TIMELINE_V1','BROKER_LIVE_DATA_V1')):
            with self.subTest(prefix=corrupt[:25]):self.rejected(corrupt)

    def test_frozen_golden_fixture_byte_parity(self):
        fp=ROOT/'tests/fixtures/g3_synthetic_golden.txt'
        ep=ROOT/'tests/fixtures/g3_expected_trades.txt'
        self.assertEqual(self.same(fp.read_text()),ep.read_text())
        self.assertEqual(hashlib.sha256(ep.read_bytes()).hexdigest(),'d8ce45cfa9ab8b928b714c7f7fbe7b68030372b95c2d19591f9fbfa87c369253')

    def test_deterministic_randomized_independent_parity(self):
        rng=random.Random(501)
        for round_id in range(160):
            ticks=[]
            for ix in range(12):
                session=1 if ix<6 else 2
                bid=1000+rng.randrange(-20,21)
                ask=bid+rng.randrange(1,5)
                ticks.append(row(10000+ix,bid,ask,session=session,end=int(ix in (5,11)),
                                 bl=bid-rng.randrange(0,9),bh=bid+rng.randrange(0,9),
                                 al=ask-rng.randrange(0,9),ah=ask+rng.randrange(0,9)))
            plans=[]
            for j in range(6):
                session_start=rng.choice((0,6))
                entry=session_start+rng.randrange(1,5)
                signal=session_start+rng.randrange(entry-session_start)
                plans.append((f'R{round_id}_{j}',rng.choice(('BUY','SELL')),
                              signal,entry,rng.randrange(1,20),rng.randrange(1,20)))
            with self.subTest(round=round_id):self.same(source(ticks,plans))

if __name__=='__main__':unittest.main()
