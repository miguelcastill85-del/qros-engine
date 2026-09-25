from __future__ import annotations
import json, pathlib, sys, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
G5=ROOT.parent/'g5'
G4=ROOT.parent/'g4'
sys.path[:0]=[str(G5),str(G4)]
from proof_gateway import VerifiedSnapshot
from witness import Head
from data_audit import canonical,digest

FIX=json.loads((ROOT/'tests/fixtures/g5_signed_snapshot_fixture.json').read_text())

class G6ParityFixtureTests(unittest.TestCase):
    def test_python_verifies_same_frozen_fixture_as_dart(self):
        f=FIX
        p=f['payload']
        snap=VerifiedSnapshot.construct(
            tenant=p['tenant'],project=p['project'],campaign=p['campaign'],
            audit_receipt=p['audit_receipt'],signed_witness_event=p['witness_event'],
            witness_public_key=__import__('base64').b64decode(f['public_key_b64']),
            witness_id=f['witness_id'],known_prior_head=Head(**f['known_prior_head']))
        self.assertEqual(snap.witness_head.sequence,1)
        self.assertEqual(snap.witness_head.sha256,p['head']['sha256'])
        self.assertEqual(digest(canonical(p)),f['canonical_payload_sha256'])
        self.assertEqual(p['economic_backtests'],0)
        self.assertFalse(p['holdout_open'])
        self.assertFalse(p['ga2_open'])

    def test_regeneration_is_byte_identical(self):
        sys.path.insert(0,str(ROOT))
        from generate_fixture import build
        expected=json.dumps(build(),indent=2,sort_keys=True)+'\n'
        self.assertEqual(expected,(ROOT/'tests/fixtures/g5_signed_snapshot_fixture.json').read_text())

    def test_private_seed_not_in_flutter_tree(self):
        seed='1f'*32
        flutter=ROOT.parent/'flutter_app'
        for p in flutter.rglob('*'):
            if p.is_file():
                self.assertNotIn(seed,p.read_text(errors='ignore'),str(p))

if __name__=='__main__': unittest.main()
