from __future__ import annotations
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import progress_gate as gate

class AntiStallCases(unittest.TestCase):
    def test_local_exact_source_gate(self):
        self.assertEqual(gate.check()['status'],'PASS_G7_SOURCE_INTEGRITY_TEST_ONLY')
    def test_no_fake_release_promotion(self):
        original=gate.Path.read_text
        def fake(p,*args,**kw):
            result=original(p,*args,**kw)
            if p.name=='G7_PROGRESS_HEAD.json':
                j=json.loads(result);j['release_signed']=True;return json.dumps(j)
            return result
        with patch.object(gate.Path,'read_text',fake):
            with self.assertRaisesRegex(gate.GateDeny,'FAKED'):gate.check()
    def test_missing_code_rejected(self):
        old=gate.ROOT
        with patch.object(gate,'ROOT',Path('/nonexistent/qros-g7')):
            with self.assertRaisesRegex(gate.GateDeny,'SOURCE_CHANGED'):gate.check()
    def test_no_report_only_delta(self):
        actual=gate.git
        def wrong(*args):
            if args[:2]==('diff','--name-only'):
                return 'product/mobile/g7/G7_SECURITY_AND_DEVICE_RUNBOOK.md'
            return gate.G6_PRODUCT_BLOB if 'MOBILE_PRODUCT_HEAD' in args[-1] else gate.G6_VERIFIED_BLOB
        with patch.object(gate,'git',wrong):
            with self.assertRaisesRegex(gate.GateDeny,'NOOP'):gate.check(remote_git=True)

if __name__=='__main__':unittest.main()
