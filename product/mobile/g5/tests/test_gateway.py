"""G5 TLS/mobile-client, per-tenant read-only synthetic proof acceptance and attacks."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from http.client import HTTPSConnection
import ipaddress
import json
from pathlib import Path
import socket
import ssl
import sys
import tempfile
from threading import Thread
import unittest
from urllib.error import URLError

G5=Path(__file__).resolve().parents[1]
G4=G5.parent/'g4'
sys.path.insert(0,str(G4))
sys.path.insert(0,str(G5))
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa,ed25519
from cryptography.x509.oid import NameOID
from data_audit import AuditReject,audit,canonical,digest
from witness import GENESIS, Head, LocalTestWitnessStore
from proof_gateway import (DemoHttpsGateway, VerifiedSnapshot, TokenRegistry,
                            StrictHttpsDemoClient, GatewayReject)


def generate_tls_cert(path:Path):
    ca_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    cert_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    now=datetime.now(timezone.utc)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'QROS G5 ephemeral test CA')])
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-timedelta(hours=1)).not_valid_after(now+timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),critical=False)
        .add_extension(x509.KeyUsage(True,False,True,False,False,True,True,False,False),critical=True)
        .sign(ca_key,hashes.SHA256()))
    server=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')])
    leaf=(x509.CertificateBuilder().subject_name(server).issuer_name(name)
        .public_key(cert_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-timedelta(hours=1)).not_valid_after(now+timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),
                  x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False)
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(cert_key.public_key()),critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),critical=False)
        .sign(ca_key,hashes.SHA256()))
    (path/'ca.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (path/'leaf.pem').write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    (path/'tls-test-key.pem').write_bytes(cert_key.private_bytes(serialization.Encoding.PEM,
                                     serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption()))
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(str(path/'leaf.pem'),str(path/'tls-test-key.pem'))
    return ctx


def make_signed_synthetic_snapshot(root:Path,tenant:str,project:str,campaign:str):
    """Test-only: independent signed entitlement before audit, separate signed witness after audit."""
    issuer=ed25519.Ed25519PrivateKey.generate()
    lines=[{'local_time':'2026-09-25T09:30:00.000', 'utc_offset_minutes':-240,
            'fold':0,'bid_u':100,'ask_u':102,'session':1,'session_end':True}]
    raw=canonical(lines[0])+b'\n'
    spec={'schema':'QROS_G4_DATA_SPEC_TEST_V1','symbol':'SIM_XAUUSD',
          'source_sha256':digest(raw),'broker_timezone':'America/New_York',
          'max_gap_ms':60000,'max_rows':10,'source_class':'SYNTHETIC_ONLY'}
    body={'schema':'QROS_G4_SIGNED_ENTITLEMENT_TEST_V1','issuer':'G5_SYNTHETIC_ISSUER',
          'tenant':tenant,'source_sha256':digest(raw),'source_id':'SYNTHETIC_'+tenant,
          'license_id':'TEST_'+tenant,'purpose':'SYNTHETIC_SECURITY_TEST',
          'expires_utc':'2027-09-25T00:00:00Z','redistribution':False,
          'source_class':'SYNTHETIC_ONLY'}
    import base64
    entitlement={'body':body,'signature_b64':base64.b64encode(issuer.sign(canonical(body))).decode()}
    pub=issuer.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    report=audit(raw,spec,entitlement,trusted_issuer_public_key=pub,authenticated_tenant=tenant,
                 purpose='SYNTHETIC_SECURITY_TEST',current_utc='2026-09-25T14:00:00Z')
    signer=ed25519.Ed25519PrivateKey.generate()
    wid='G5_TEST_WITNESS_'+tenant
    store=LocalTestWitnessStore(root/('witness_'+tenant),signer,wid)
    head,event=store.append(prior=GENESIS,tenant=tenant,campaign=campaign,
                    subject_sha256=digest(canonical(report)),created_utc='2026-09-25T14:00:00Z',
                    audit_receipt=report)
    snapshot=VerifiedSnapshot.construct(tenant=tenant,project=project,campaign=campaign,
                    audit_receipt=report,signed_witness_event=event,
                    witness_public_key=store.public_key,witness_id=wid,
                    known_prior_head=GENESIS)
    return snapshot,store.public_key,wid

class HttpsTenantGatewayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='qros_g5_tls_test_')
        cls.root=Path(cls.tmp.name)
        cls.ctx=generate_tls_cert(cls.root)
        cls.snapshotA,cls.pubA,cls.widA=make_signed_synthetic_snapshot(cls.root,'tenant_A','project_A','campaign_A')
        cls.snapshotB,cls.pubB,cls.widB=make_signed_synthetic_snapshot(cls.root,'tenant_B','project_B','campaign_B')
        cls.tokens=TokenRegistry()
        now=datetime.now(timezone.utc)
        cls.keyA=cls.tokens.mint(tenant='tenant_A',project='project_A',scopes={'demo:read','status:read'},
                                not_before=now-timedelta(minutes=1),expires=now+timedelta(hours=1))
        cls.keyB=cls.tokens.mint(tenant='tenant_B',project='project_B',scopes={'demo:read'},
                                not_before=now-timedelta(minutes=1),expires=now+timedelta(hours=1))
        cls.keyExpired=cls.tokens.mint(tenant='tenant_A',project='project_A',scopes={'demo:read'},
                                not_before=now-timedelta(days=3),expires=now-timedelta(days=1))
        cls.keyFuture=cls.tokens.mint(tenant='tenant_A',project='project_A',scopes={'demo:read'},
                                not_before=now+timedelta(days=1),expires=now+timedelta(days=2))
        cls.server=DemoHttpsGateway(bind_host='127.0.0.1',ssl_context=cls.ctx,tokens=cls.tokens,
             snapshots={('tenant_A','project_A'):cls.snapshotA,('tenant_B','project_B'):cls.snapshotB})
        cls.thread=Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.port=cls.server.server_address[1]
        cls.origin=f'https://127.0.0.1:{cls.port}'
        cls.clientCtx=ssl.create_default_context(cafile=str(cls.root/'ca.pem'))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=3)
        cls.tmp.cleanup()

    @classmethod
    def client(cls,tenant='tenant_A',project='project_A',campaign='campaign_A',public=None,wid=None,ca=None):
        return StrictHttpsDemoClient(trusted_ca_file=ca or str(cls.root/'ca.pem'),
                                    pinned_witness_public_key=public or cls.pubA,
                                    witness_id=wid or cls.widA,
                                    tenant=tenant,project=project,campaign=campaign)

    @classmethod
    def request(cls,route='/v1/demo-snapshot',token=None,project='project_A',method='GET',headers=None):
        h={'X-QROS-Project':project}
        if token is not None:h['Authorization']='Bearer '+token
        if headers:h.update(headers)
        c=HTTPSConnection('127.0.0.1',cls.port,context=cls.clientCtx,timeout=4)
        try:
            c.request(method,route,headers=h)
            r=c.getresponse();return r.status,dict(r.getheaders()),r.read()
        finally:c.close()

    def test_full_tls_readonly_signed_synthetic_tenant_A(self):
        payload=self.client().fetch(self.origin,self.keyA)
        self.assertEqual(payload['head']['sequence'],1)
        self.assertFalse(payload['scientific_approval'])
        self.assertEqual(payload['audit_receipt']['source_class'],'SYNTHETIC_ONLY')
        self.assertEqual(payload['external_independent_custody'],'NOT_DEPLOYED')
        self.assertEqual(payload['economic_backtests'],0)

    def test_same_anchored_snapshot_idempotent_read(self):
        c=self.client();first=c.fetch(self.origin,self.keyA);second=c.fetch(self.origin,self.keyA)
        self.assertEqual(first['head'],second['head'])

    def test_tenant_B_only_sees_tenant_B(self):
        c=self.client('tenant_B','project_B','campaign_B',self.pubB,self.widB)
        x=c.fetch(self.origin,self.keyB)
        self.assertEqual(x['tenant'],'tenant_B')
        self.assertNotEqual(x['audit_receipt']['source_sha256'],'')
        self.assertNotIn('tenant_A',json.dumps(x))

    def test_cross_project_header_denied(self):
        status,headers,body=self.request(token=self.keyA,project='project_B')
        self.assertEqual(status,403)
        self.assertNotIn(b'tenant_A',body)

    def test_cross_tenant_token_cannot_request_other_project(self):
        status,_,body=self.request(token=self.keyB,project='project_A')
        self.assertEqual(status,403)
        self.assertNotIn(b'tenant_B',body)

    def test_missing_wrong_expired_future_and_short_tokens_denied(self):
        for token in (None,'WRONG'+'A'*40,self.keyExpired,self.keyFuture,'tiny'):
            with self.subTest(token='redacted'):
                status,headers,body=self.request(token=token)
                self.assertEqual(status,401)
                self.assertEqual(headers['Cache-Control'],'no-store, max-age=0')

    def test_status_requires_distinct_scope(self):
        status,_,_=self.request('/v1/status',token=self.keyB,project='project_B')
        self.assertEqual(status,403)
        status,_,body=self.request('/v1/status',token=self.keyA)
        self.assertEqual(status,200)
        obj=json.loads(body)
        self.assertFalse(obj['production_research_ready'])
        self.assertNotIn('tenant_A',str(obj))

    def test_all_writes_and_cors_preflight_denied(self):
        for method in ('POST','PUT','PATCH','DELETE','OPTIONS'):
            with self.subTest(method=method):
                status,headers,body=self.request(method=method,token=self.keyA)
                self.assertEqual(status,405)
                self.assertNotIn('Access-Control-Allow-Origin',headers)

    def test_head_denied_without_describing_as_readonly_get(self):
        status,_,body=self.request(method='HEAD',token=self.keyA)
        self.assertEqual(status,405)

    def test_no_query_actors_paths_or_token_in_url(self):
        for p in ('/v1/demo-snapshot?actor=QROS_CORE','/v1/campaign/approve','/v1/holdout/open',
                  '/v1/demo-snapshot/../holdout'):
            with self.subTest(path=p):
                self.assertEqual(self.request(route=p,token=self.keyA)[0],404)

    def test_duplicate_bearer_header_rejected(self):
        c=HTTPSConnection('127.0.0.1',self.port,context=self.clientCtx,timeout=4)
        try:
            c.putrequest('GET','/v1/demo-snapshot');c.putheader('Authorization','Bearer '+self.keyA)
            c.putheader('Authorization','Bearer '+self.keyB);c.putheader('X-QROS-Project','project_A');c.endheaders()
            r=c.getresponse();self.assertEqual(r.status,401);r.read()
        finally:c.close()

    def test_https_cert_wrong_ca_fail_closed(self):
        other=tempfile.TemporaryDirectory(prefix='qros_g5_wrong_ca_')
        try:
            p=Path(other.name);generate_tls_cert(p)
            client=self.client(ca=str(p/'ca.pem'))
            with self.assertRaises((ssl.SSLError, ConnectionError)):
                client.fetch(self.origin,self.keyA)
        finally:other.cleanup()

    def test_http_downgrade_and_credential_in_url_rejected(self):
        c=self.client()
        for url in ('http://127.0.0.1:'+str(self.port),'https://user:password@localhost:'+str(self.port),
                    self.origin+'/v1/demo-snapshot',self.origin+'?token=SECRET',
                    'https://attacker.example'):
            with self.subTest(url=url),self.assertRaises(GatewayReject):
                c.fetch(url,self.keyA)

    def test_unsigned_tampered_audit_rejected_after_tls(self):
        c=self.client();j=deepcopy(self.snapshotA.public_payload())
        j['audit_receipt']['rows']=100000
        with self.assertRaisesRegex(GatewayReject,'AUDIT_PROOF_MISMATCH'):
            c._verify(j)

    def test_unpinned_witness_public_key_rejected_even_valid_tls(self):
        wrong=ed25519.Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        with self.assertRaises(AuditReject):
            self.client(public=wrong).fetch(self.origin,self.keyA)

    def test_stale_replay_rejected_against_independently_pinned_head(self):
        c=self.client();c.known_head=Head(2,'f'*64)
        with self.assertRaisesRegex(GatewayReject,'REPLAY_OR_MISSING_PROOF'):
            c.fetch(self.origin,self.keyA)

    def test_same_sequence_fork_rejected(self):
        c=self.client();c.known_head=Head(1,'f'*64)
        with self.assertRaisesRegex(GatewayReject,'SAME_SEQUENCE_FORK'):
            c.fetch(self.origin,self.keyA)

    def test_forged_scientific_approval_forbidden_even_signed_audit(self):
        j=deepcopy(self.snapshotA.public_payload());j['scientific_approval']=True
        with self.assertRaisesRegex(GatewayReject,'UNAUTHORIZED_SCIENTIFIC_CLAIM'):
            self.client()._verify(j)

    def test_wrong_project_and_tenant_inside_signed_snapshot_rejected(self):
        j=deepcopy(self.snapshotA.public_payload());j['project']='project_B'
        with self.assertRaisesRegex(GatewayReject,'WRONG_CLIENT_IDENTITY'):
            self.client()._verify(j)

    def test_not_publicly_bindable_no_tls_downgrade(self):
        with self.assertRaisesRegex(GatewayReject,'PUBLIC_BIND_FORBIDDEN'):
            DemoHttpsGateway(bind_host='0.0.0.0',ssl_context=self.ctx,tokens=self.tokens,
                 snapshots={('tenant_A','project_A'):self.snapshotA})

    def test_trust_root_and_signing_keys_not_in_network_payload(self):
        _,_,b=self.request(token=self.keyA)
        self.assertNotIn(self.keyA.encode(),b)
        self.assertNotIn(b'private_key',b)
        self.assertNotIn(b'issuer_public_key',b)

    def test_response_security_headers_no_cors(self):
        status,headers,body=self.request(token=self.keyA)
        self.assertEqual(status,200)
        self.assertEqual(headers['Content-Type'],'application/json')
        self.assertEqual(headers['X-Content-Type-Options'],'nosniff')
        self.assertNotIn('Access-Control-Allow-Origin',headers)

if __name__=='__main__':unittest.main()
