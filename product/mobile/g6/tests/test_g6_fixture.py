"""G6 cross-language frozen proof, independent G5 receipt oracle and tamper probes."""
from __future__ import annotations
import base64, copy, hashlib, json, pathlib, sys, unittest
HERE=pathlib.Path(__file__).resolve().parents[1]
MOBILE=HERE.parent
sys.path[:0]=[str(HERE),str(MOBILE/'g4'),str(MOBILE/'g5')]
from generate_signed_fixture import generate
from proof_gateway import StrictHttpsDemoClient,GatewayReject
from data_audit import strict_json, canonical,digest, AuditReject
from witness import GENESIS, WitnessVerifier, Head
FIXTURE=MOBILE/'flutter_app/assets/g6_signed_snapshot.json'
TRUST=MOBILE/'flutter_app/assets/g6_offline_trust.json'

class G6FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=FIXTURE.read_bytes();cls.trust_raw=TRUST.read_bytes()
        cls.payload=strict_json(cls.raw);cls.trust=strict_json(cls.trust_raw)
        cls.public=base64.b64decode(cls.trust['witness_public_b64'],validate=True)

    @classmethod
    def independent_client(cls):
        # Instantiate verification-only path, never bypass actual G5 _verify.
        inst=StrictHttpsDemoClient.__new__(StrictHttpsDemoClient)
        inst.tenant=cls.trust['tenant'];inst.project=cls.trust['project']
        inst.campaign=cls.trust['campaign'];inst.known_head=GENESIS
        inst.verifier=WitnessVerifier(cls.public,cls.trust['witness_id'])
        return inst

    def test_generator_exact_reproduction(self):
        expected,trust,_,_=generate()
        self.assertEqual(self.raw,expected+b'\n');self.assertEqual(self.trust_raw,trust+b'\n')
    def test_g5_existing_independent_client_verifies_g6(self):
        client=self.independent_client();got=client._verify(copy.deepcopy(self.payload))
        self.assertEqual(got['head']['sha256'],self.trust['expected_head_sha256'])
        self.assertEqual(client.known_head.sequence,1)
    def test_g5_idempotent_second_proof(self):
        c=self.independent_client();c._verify(copy.deepcopy(self.payload));c._verify(copy.deepcopy(self.payload))
        self.assertEqual(c.known_head.sequence,1)
    def test_frozen_fixture_wire_and_audit_sha(self):
        self.assertEqual(digest(canonical(self.payload)),self.trust['snapshot_wire_sha256'])
        self.assertEqual(digest(canonical(self.payload['audit_receipt'])),self.trust['expected_audit_sha256'])
    def test_test_only_and_sealed_authority(self):
        self.assertFalse(self.payload['scientific_approval']);self.assertEqual(self.payload['economic_backtests'],0)
        self.assertFalse(self.payload['holdout_open']);self.assertFalse(self.payload['ga2_open'])
        self.assertEqual(self.payload['external_independent_custody'],'NOT_DEPLOYED')
        self.assertFalse(self.trust['production_trust_root'])
    def test_duplicate_wire_key_rejected(self):
        altered=self.raw.replace(b'"ga2_open":false',b'"ga2_open":false,"ga2_open":true',1)
        with self.assertRaisesRegex(AuditReject,'DUPLICATE_JSON_KEY'):strict_json(altered)
    def test_forged_signature_rejected(self):
        v=copy.deepcopy(self.payload);sig=v['witness_event']['signature_b64']
        v['witness_event']['signature_b64']=('A' if sig[0]!='A' else 'B')+sig[1:]
        with self.assertRaises((AuditReject,GatewayReject)):self.independent_client()._verify(v)
    def test_cross_tenant_rejected(self):
        v=copy.deepcopy(self.payload);v['tenant']='another_tenant'
        with self.assertRaisesRegex(GatewayReject,'WRONG_CLIENT_IDENTITY'):self.independent_client()._verify(v)
    def test_audit_tamper_rejected(self):
        v=copy.deepcopy(self.payload);v['audit_receipt']['rows']+=1
        with self.assertRaisesRegex(GatewayReject,'AUDIT_PROOF_MISMATCH'):self.independent_client()._verify(v)
    def test_head_tamper_rejected(self):
        v=copy.deepcopy(self.payload);v['head']['sha256']='f'*64
        with self.assertRaisesRegex(GatewayReject,'DECLARED_WITNESS_HEAD_MISMATCH'):self.independent_client()._verify(v)
    def test_wrong_pinned_root_rejected(self):
        c=self.independent_client();c.verifier=WitnessVerifier(bytes([1])*32,self.trust['witness_id'])
        with self.assertRaises(AuditReject):c._verify(copy.deepcopy(self.payload))
    def test_same_sequence_fork_rejected(self):
        c=self.independent_client();c._verify(copy.deepcopy(self.payload));v=copy.deepcopy(self.payload)
        v['witness_event']['body']['subject_sha256']='f'*64
        with self.assertRaisesRegex(GatewayReject,'SAME_SEQUENCE_FORK'):c._verify(v)
    def test_previous_head_pin_not_server_supplied(self):
        body=self.payload['witness_event']['body'];self.assertEqual(body['previous_sha256'],GENESIS.sha256)
        self.assertEqual(self.trust['expected_head_sha256'],digest(canonical(body)))
    def test_no_private_test_seed_in_mobile_assets(self):
        for raw in (self.raw,self.trust_raw):
            self.assertNotIn(b'ISSUER_SEED',raw);self.assertNotIn(b'WITNESS_SEED',raw)
        self.assertNotIn('BEGIN PRIVATE KEY',self.raw.decode()+self.trust_raw.decode())
if __name__=='__main__':unittest.main()
