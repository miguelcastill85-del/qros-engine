"""Adversarial synthetic G7 only. No real OIDC, market data or external custody."""
from __future__ import annotations
import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
import pathlib
import sys
import unittest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from oidc_canary import SyntheticOidcVerifier, OidcDeny, strict_json
from witness_custody import PinnedExternalWitnessVerifier,CustodyDeny,GENESIS,canonical,production_status

NOW=1790358000

def b64(b:bytes)->str:return base64.urlsafe_b64encode(b).decode().rstrip('=')

def rawpub(k):return k.public_key().public_bytes(encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)

class OidcCases(unittest.TestCase):
    def setUp(self):
        self.private=Ed25519PrivateKey.generate()
        self.other=Ed25519PrivateKey.generate()
        self.verifier=SyntheticOidcVerifier('https://oidc.test.invalid/issuer','qros-mobile','kid-test',rawpub(self.private))
        self.header={'alg':'EdDSA','typ':'JWT','kid':'kid-test'}
        self.claim={'iss':'https://oidc.test.invalid/issuer','aud':'qros-mobile','sub':'unit_user',
                    'tenant':'tenant_A','project':'project_A','scope':['demo:read'],
                    'iat':NOW-10,'nbf':NOW-10,'exp':NOW+60,'jti':'random_A'}

    def jwt(self,header=None,claim=None,key=None)->str:
        header=header if header is not None else self.header
        claim=claim if claim is not None else self.claim
        signed='.'.join((b64(json.dumps(x,separators=(',',':')).encode()) for x in (header,claim)))
        sig=(key or self.private).sign(signed.encode())
        return signed+'.'+b64(sig)

    def accept(self,t=None,**kw):
        return self.verifier.verify(t or self.jwt(),tenant=kw.get('tenant','tenant_A'),
              project=kw.get('project','project_A'),scope=kw.get('scope','demo:read'),
              now_utc_seconds=kw.get('now',NOW))

    def test_valid_scoped_synthetic_token(self):
        r=self.accept()
        self.assertFalse(r['scientific_authority'])
        self.assertEqual(r['production_oidc'],'NOT_DEPLOYED')
    def test_replay_denied(self):
        t=self.jwt();self.accept(t)
        with self.assertRaisesRegex(OidcDeny,'REPLAY'):self.accept(t)
    def test_signature_wrong_key_denied(self):
        with self.assertRaisesRegex(OidcDeny,'SIGNATURE'):self.accept(self.jwt(key=self.other))
    def test_tampered_claim_denied(self):
        t=self.jwt().split('.');claim=copy.deepcopy(self.claim);claim['tenant']='tenant_B';t[1]=b64(json.dumps(claim).encode())
        with self.assertRaises(OidcDeny):self.accept('.'.join(t))
    def test_wrong_tenant_denied(self):
        with self.assertRaisesRegex(OidcDeny,'TENANT'):self.accept(tenant='tenant_B')
    def test_wrong_project_denied(self):
        with self.assertRaisesRegex(OidcDeny,'TENANT'):self.accept(project='project_B')
    def test_issuer_denied(self):
        self.claim['iss']='https://other.invalid/issuer'
        with self.assertRaises(OidcDeny):self.accept()
    def test_audience_denied(self):
        self.claim['aud']='another-product'
        with self.assertRaises(OidcDeny):self.accept()
    def test_scope_denied(self):
        with self.assertRaisesRegex(OidcDeny,'SCOPE'):self.accept(scope='status:read')
    def test_scope_escalation_denied(self):
        self.claim['scope']=['demo:read','admin:write']
        with self.assertRaisesRegex(OidcDeny,'SCOPE'):self.accept()
    def test_duplicate_scope_denied(self):
        self.claim['scope']=['demo:read','demo:read']
        with self.assertRaises(OidcDeny):self.accept()
    def test_expired_denied(self):
        with self.assertRaisesRegex(OidcDeny,'TIME'):self.accept(now=NOW+70)
    def test_future_token_denied(self):
        self.claim['nbf']=NOW+20
        with self.assertRaisesRegex(OidcDeny,'TIME'):self.accept()
    def test_long_lived_token_denied(self):
        self.claim['exp']=NOW+500
        with self.assertRaises(OidcDeny):self.accept()
    def test_boolean_timestamp_denied(self):
        self.claim['iat']=True
        with self.assertRaisesRegex(OidcDeny,'TIMESTAMP'):self.accept()
    def test_alg_none_denied(self):
        self.header['alg']='none'
        with self.assertRaisesRegex(OidcDeny,'ALG'):self.accept()
    def test_hs256_denied(self):
        self.header['alg']='HS256'
        with self.assertRaises(OidcDeny):self.accept()
    def test_jku_injection_denied(self):
        self.header['jku']='https://evil.invalid/jwks.json'
        with self.assertRaisesRegex(OidcDeny,'HEADER'):self.accept()
    def test_key_confusion_denied(self):
        self.header['kid']='untrusted-key'
        with self.assertRaisesRegex(OidcDeny,'PINNED'):self.accept()
    def test_malformed_compact_denied(self):
        with self.assertRaisesRegex(OidcDeny,'COMPACT'):self.accept('one.two')
    def test_duplicate_json_keys_denied(self):
        with self.assertRaisesRegex(OidcDeny,'DUPLICATE'):strict_json(b'{"x":1,"x":2}')
    def test_token_not_integer_clock(self):
        with self.assertRaisesRegex(OidcDeny,'CLOCK'):self.accept(now=True)
    def test_extra_privilege_field_denied(self):
        self.claim['is_admin']=True
        with self.assertRaisesRegex(OidcDeny,'CLAIMS'):self.accept()
    def test_missing_out_of_band_pin_denied(self):
        with self.assertRaisesRegex(OidcDeny,'PIN'):SyntheticOidcVerifier('https://oidc.test.invalid/issuer','qros-mobile','kid-test',b'')
    def test_noncanonical_b64_denied(self):
        s=self.jwt().split('.');s[0]+='='
        with self.assertRaisesRegex(OidcDeny,'BASE64'):self.accept('.'.join(s))

class WitnessCases(unittest.TestCase):
    def setUp(self):
        self.key=Ed25519PrivateKey.generate();self.other=Ed25519PrivateKey.generate()
        self.verifier=PinnedExternalWitnessVerifier(rawpub(self.key),operator_id='operator_B',witness_id='witness_B',synthetic_canary=True)
        self.body={'schema':'QROS_G7_OPERATOR_ATTESTATION_V1','operator_id':'operator_B','witness_id':'witness_B','sequence':1,'previous_sha256':'0'*64,'subject_sha256':'a'*64,'tenant':'tenant_A','campaign':'campaign_A','created_utc':'2026-09-25T20:00:00Z','mode':'SYNTHETIC_SECOND_PROCESS_TEST'}
    def event(self,body=None,key=None):
        b=body if body is not None else self.body
        return {'body':b,'signature_b64':base64.b64encode((key or self.key).sign(canonical(b))).decode()}
    def validate(self,event=None,prior=GENESIS,tenant='tenant_A',campaign='campaign_A'):
        return self.verifier.verify(event if event is not None else self.event(),prior=prior,subject_sha256='a'*64,tenant=tenant,campaign=campaign)
    def test_pinned_synthetic_event(self):
        h=self.validate();self.assertEqual(h.sequence,1)
    def test_replay_same_event(self):
        h=self.validate()
        with self.assertRaisesRegex(CustodyDeny,'REPLAY'):self.validate(prior=h)
    def test_cross_tenant(self):
        with self.assertRaises(CustodyDeny):self.validate(tenant='tenant_B')
    def test_cross_campaign(self):
        with self.assertRaises(CustodyDeny):self.validate(campaign='campaign_B')
    def test_bad_signature(self):
        with self.assertRaisesRegex(CustodyDeny,'SIGNATURE'):self.validate(self.event(key=self.other))
    def test_unknown_operator(self):
        self.body['operator_id']='operator_C'
        with self.assertRaisesRegex(CustodyDeny,'OPERATOR'):self.validate(self.event())
    def test_subject_mismatch(self):
        self.body['subject_sha256']='b'*64
        with self.assertRaisesRegex(CustodyDeny,'SOURCE'):self.validate(self.event())
    def test_fork_previous_sha(self):
        self.body['previous_sha256']='f'*64
        with self.assertRaisesRegex(CustodyDeny,'FORK'):self.validate(self.event())
    def test_wrong_schema(self):
        self.body['schema']='TRADING_APPROVED'
        with self.assertRaises(CustodyDeny):self.validate(self.event())
    def test_real_custody_not_promoted_from_simulator(self):
        self.body['mode']='PRODUCTION_EXTERNAL'
        with self.assertRaisesRegex(CustodyDeny,'REAL_EXTERNAL'):self.validate(self.event())
    def test_unpinned_operator_cannot_promote(self):
        with self.assertRaisesRegex(CustodyDeny,'KEY_REQUIRED'):PinnedExternalWitnessVerifier(b'',operator_id='operator_B',witness_id='witness_B',synthetic_canary=True)
    def test_status_reports_missing_external_controls(self):
        result=production_status(verified_off_host_administration=False,verified_off_host_tls=False,independently_pinned_key=False,nonrollbackable_monotonic_receipt=False)
        self.assertEqual(len(result['missing']),4);self.assertFalse(result['promotable_from_local_test'])
    def test_faked_all_true_cannot_self_promote(self):
        self.assertEqual(production_status(verified_off_host_administration=True,verified_off_host_tls=True,independently_pinned_key=True,nonrollbackable_monotonic_receipt=True)['status'],'BLOCKED_BY_INFRASTRUCTURE_EXTERNAL_CUSTODY')

if __name__=='__main__':unittest.main()
