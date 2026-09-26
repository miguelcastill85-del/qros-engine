from __future__ import annotations
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import progress_gate as g


class AntiStallTests(unittest.TestCase):
    def test_local_manifest_integrity(self):
        self.assertEqual(g.verify(remote=False)['status'], 'PASS_EXACT_G8_SOURCE_DELTA_ONLY')

    def test_exact_parent_required(self):
        old = g.PARENT
        try:
            g.PARENT = '0' * 40
            with self.assertRaisesRegex(g.GateDeny, 'WRONG_PARENT_HEAD'):
                g.verify(remote=False)
        finally:
            g.PARENT = old

    def test_no_op_rejected_with_remote_git(self):
        original_git = g.git
        try:
            g.git = lambda *args: (
                g.G7_PRODUCT_BLOB if any('MOBILE_PRODUCT_HEAD' in a for a in args) else
                g.G7_VERIFIED_BLOB if any('G7_CURRENT_HEAD' in a for a in args) else
                g.PARENT if 'rev-parse' in args else '')
            with self.assertRaisesRegex(g.GateDeny, 'NO_OP_MISSING_OR_UNEXPECTED_FILES'):
                g.verify(remote=True)
        finally:
            g.git = original_git

    def test_faked_scientific_approval_rejected(self):
        old = g.G8
        try:
            original_loads = json.loads
            with patch('progress_gate.json.loads', wraps=original_loads) as loads:
                def fake(data):
                    obj = original_loads(data)
                    if obj.get('schema') == 'QROS_MOBILE_G8_PROGRESS_HEAD_V1':
                        obj['scientific_gate_pass'] = True
                    return obj
                loads.side_effect = fake
                with self.assertRaisesRegex(g.GateDeny, 'SCIENTIFIC_AUTHORITY_DRIFT'):
                    g.verify(remote=False)
        finally:
            g.G8 = old


if __name__ == '__main__': unittest.main()
