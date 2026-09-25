"""G5 opt-in loopback HTTPS read-only DEMO transport and independent signed-proof client.

Exactly SYNTHETIC_ONLY. Neither browser client nor network peer can sign, allocate
scientific authority, mutate campaigns, open holdout, or access broker data.
No public ingress or production tenant authorization is claimed.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
from http.client import HTTPSConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import secrets
import ssl
from threading import Thread
from typing import Any
from urllib.parse import urlsplit
from data_audit import AuditReject, exact, canonical, digest, strict_json, ident, hex64
from witness import GENESIS, Head, WitnessVerifier

class GatewayReject(ValueError):
    pass

def reject(name: str) -> None:
    raise GatewayReject('QROS_G5_FAIL_CLOSED:'+name)

TOKEN_RE=re.compile(r'[A-Za-z0-9_-]{43,128}\Z')

@dataclass(frozen=True)
class DemoPrincipal:
    tenant: str
    project: str
    scopes: frozenset[str]
    not_before: datetime
    expires: datetime

class TokenRegistry:
    """Ephemeral in-memory TEST_ONLY credentials. Production requires OIDC/JWT authority."""
    def __init__(self) -> None:
        self._tokens:dict[str, DemoPrincipal]={}

    def mint(self, *, tenant:str, project:str, scopes:set[str],
             not_before:datetime, expires:datetime) -> str:
        ident(tenant,'TENANT');ident(project,'PROJECT')
        if scopes-{ 'demo:read','status:read' } or not scopes:
            reject('INVALID_SCOPES')
        if not_before.tzinfo is None or expires.tzinfo is None or expires<=not_before:
            reject('INVALID_TOKEN_TIMES')
        key=secrets.token_urlsafe(32)
        if not TOKEN_RE.fullmatch(key):
            reject('EPHEMERAL_TOKEN_FORMAT')
        self._tokens[hashlib.sha256(key.encode()).hexdigest()]=DemoPrincipal(
            tenant,project,frozenset(scopes),not_before,expires)
        return key

    def lookup(self, bearer:Any, *, now:datetime|None=None) -> DemoPrincipal|None:
        if type(bearer) is not str or TOKEN_RE.fullmatch(bearer) is None:
            return None
        principal=self._tokens.get(hashlib.sha256(bearer.encode()).hexdigest())
        if principal is None:
            return None
        check=now or datetime.now(timezone.utc)
        if check.tzinfo is None or not principal.not_before<=check<principal.expires:
            return None
        return principal

@dataclass(frozen=True)
class VerifiedSnapshot:
    tenant: str
    project: str
    campaign: str
    audit_receipt: dict[str, Any]
    signed_witness_event: dict[str, Any]
    witness_head: Head

    @classmethod
    def construct(cls, *, tenant:str,project:str,campaign:str,
                  audit_receipt:dict[str,Any], signed_witness_event:dict[str,Any],
                  witness_public_key:bytes, witness_id:str, known_prior_head:Head) -> 'VerifiedSnapshot':
        for label,item in [('TENANT',tenant),('PROJECT',project),('CAMPAIGN',campaign)]:
            ident(item,label)
        if type(audit_receipt) is not dict or audit_receipt.get('schema')!='QROS_G4_DATA_AUDIT_TEST_RECEIPT_V1':
            reject('INVALID_AUDIT_SCHEMA')
        if audit_receipt.get('classification')!='TEST_ONLY_NO_SCIENTIFIC_AUTHORITY' or \
           audit_receipt.get('tenant')!=tenant or audit_receipt.get('source_class')!='SYNTHETIC_ONLY' or \
           audit_receipt.get('execution_eligible') is not True or \
           audit_receipt.get('economic_tests')!=0 or audit_receipt.get('holdout_open') is not False or \
           audit_receipt.get('ga2_open') is not False:
            reject('INELIGIBLE_SYNTHETIC_AUDIT')
        verifier=WitnessVerifier(witness_public_key,witness_id)
        head=verifier.verify_step(signed_witness_event,prior=known_prior_head,tenant=tenant,campaign=campaign)
        if signed_witness_event['body']['subject_sha256']!=digest(canonical(audit_receipt)):
            reject('WITNESS_AUDIT_DIGEST_MISMATCH')
        return cls(tenant,project,campaign,audit_receipt,signed_witness_event,head)

    def public_payload(self) -> dict[str,Any]:
        return {'schema':'QROS_G5_SIGNED_SYNTHETIC_SNAPSHOT_V1',
                'source_class':'SYNTHETIC_ONLY','scientific_approval':False,
                'tenant':self.tenant,'project':self.project,'campaign':self.campaign,
                'audit_receipt':self.audit_receipt,'witness_event':self.signed_witness_event,
                'head':{'sequence':self.witness_head.sequence,'sha256':self.witness_head.sha256},
                'external_independent_custody':'NOT_DEPLOYED','economic_backtests':0,
                'holdout_open':False,'ga2_open':False}

class DemoHttpsGateway(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=False
    def __init__(self, *, bind_host:str, ssl_context:ssl.SSLContext,
                 tokens:TokenRegistry, snapshots:dict[tuple[str,str],VerifiedSnapshot]):
        if bind_host!='127.0.0.1':
            reject('PUBLIC_BIND_FORBIDDEN_TEST_ONLY')
        if ssl_context.protocol!=ssl.PROTOCOL_TLS_SERVER or ssl_context.minimum_version<ssl.TLSVersion.TLSv1_2:
            reject('STRICT_TLS_SERVER_REQUIRED')
        self.tokens=tokens
        self.snapshots=snapshots.copy()
        for (t,p),s in self.snapshots.items():
            if (t,p)!=(s.tenant,s.project):
                reject('CROSS_TENANT_SNAPSHOT_REGISTRY')
        super().__init__((bind_host,0),DemoHandler)
        self.socket=ssl_context.wrap_socket(self.socket,server_side=True)

class DemoHandler(BaseHTTPRequestHandler):
    server:DemoHttpsGateway
    protocol_version='HTTP/1.1'

    def log_message(self, format:str, *args:Any) -> None:
        # Never print tokens or arbitrary user-supplied paths/headers in the demo.
        return

    def _respond(self, code:int, data:dict[str,Any]) -> None:
        body=canonical(data)
        self.send_response(code)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store, max-age=0')
        self.send_header('Pragma','no-cache')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'none'")
        self.send_header('Connection','close')
        self.end_headers()
        self.wfile.write(body)
        self.close_connection=True

    def do_GET(self) -> None:
        if self.path not in ('/v1/demo-snapshot','/v1/status'):
            return self._respond(404,{'error':'unknown_path'})
        auth=self.headers.get_all('Authorization')
        if not auth or len(auth)!=1 or not auth[0].startswith('Bearer '):
            return self._respond(401,{'error':'unauthorized'})
        principal=self.server.tokens.lookup(auth[0][7:])
        if principal is None:
            return self._respond(401,{'error':'unauthorized'})
        projects=self.headers.get_all('X-QROS-Project')
        if not projects or len(projects)!=1 or projects[0]!=principal.project:
            return self._respond(403,{'error':'forbidden_project'})
        scope='demo:read' if self.path=='/v1/demo-snapshot' else 'status:read'
        if scope not in principal.scopes:
            return self._respond(403,{'error':'forbidden_scope'})
        if self.path=='/v1/status':
            return self._respond(200,{'schema':'QROS_G5_DEMO_STATUS_V1',
                                      'classification':'TEST_ONLY_SYNTHETIC',
                                      'production_research_ready':False,
                                      'external_custody':'NOT_DEPLOYED',
                                      'scientific_gate_pass':False})
        item=self.server.snapshots.get((principal.tenant,principal.project))
        if item is None:
            return self._respond(404,{'error':'no_snapshot'})
        return self._respond(200,item.public_payload())

    def do_POST(self)->None:self._respond(405,{'error':'read_only'})
    def do_PUT(self)->None:self._respond(405,{'error':'read_only'})
    def do_PATCH(self)->None:self._respond(405,{'error':'read_only'})
    def do_DELETE(self)->None:self._respond(405,{'error':'read_only'})
    def do_OPTIONS(self)->None:self._respond(405,{'error':'read_only_no_cors'})
    def do_HEAD(self)->None:self._respond(405,{'error':'read_only'})

class StrictHttpsDemoClient:
    """System/explicit-CA HTTPS verification, no redirects, no token in URL."""
    def __init__(self, *, trusted_ca_file:str, pinned_witness_public_key:bytes,
                 witness_id:str, tenant:str, project:str,campaign:str):
        self.context=ssl.create_default_context(ssl.Purpose.SERVER_AUTH,cafile=trusted_ca_file)
        self.context.minimum_version=ssl.TLSVersion.TLSv1_2
        self.verifier=WitnessVerifier(pinned_witness_public_key,witness_id)
        self.tenant=ident(tenant,'TENANT');self.project=ident(project,'PROJECT')
        self.campaign=ident(campaign,'CAMPAIGN')
        self.known_head=GENESIS

    def fetch(self, origin:str, token:str) -> dict[str,Any]:
        if type(origin) is not str or not origin:
            reject('HTTPS_ORIGIN_REQUIRED')
        u=urlsplit(origin)
        if u.scheme!='https' or not u.hostname or u.username is not None or u.password is not None or u.path not in ('','/') or u.query or u.fragment:
            reject('HTTPS_ORIGIN_ONLY_NO_USERINFO_OR_QUERY')
        if u.hostname not in ('localhost','127.0.0.1'):
            reject('TEST_GATEWAY_LOOPBACK_ONLY')
        if not TOKEN_RE.fullmatch(token):
            reject('TOKEN_FORMAT_INVALID')
        conn=HTTPSConnection(u.hostname,u.port or 443,context=self.context,timeout=6)
        try:
            conn.request('GET','/v1/demo-snapshot',headers={'Authorization':'Bearer '+token,
                         'X-QROS-Project':self.project,'Accept':'application/json'})
            resp=conn.getresponse()
            if resp.status in (301,302,303,307,308):
                reject('REDIRECT_DENIED')
            if resp.status!=200:
                reject('GATEWAY_HTTP_'+str(resp.status))
            if resp.getheader('Content-Type')!='application/json':
                reject('CONTENT_TYPE_NOT_JSON')
            body=resp.read(65537)
            if len(body)>65536:
                reject('OVERSIZE_SIGNED_SNAPSHOT')
            payload=strict_json(body,max_size=65536)
            return self._verify(payload)
        finally:
            conn.close()

    def _verify(self,payload:Any)->dict[str,Any]:
        keys={'schema','source_class','scientific_approval','tenant','project','campaign',
              'audit_receipt','witness_event','head','external_independent_custody',
              'economic_backtests','holdout_open','ga2_open'}
        exact(payload,keys,'G5_SNAPSHOT')
        if payload['schema']!='QROS_G5_SIGNED_SYNTHETIC_SNAPSHOT_V1' or \
           payload['source_class']!='SYNTHETIC_ONLY' or \
           payload['external_independent_custody']!='NOT_DEPLOYED' or \
           payload['scientific_approval'] is not False or payload['economic_backtests']!=0 or \
           payload['holdout_open'] is not False or payload['ga2_open'] is not False:
            reject('UNAUTHORIZED_SCIENTIFIC_CLAIM')
        if (payload['tenant'],payload['project'],payload['campaign'])!=(self.tenant,self.project,self.campaign):
            reject('WRONG_CLIENT_IDENTITY')
        body=payload['witness_event']['body']
        if type(body['sequence']) is not int:
            reject('SEQUENCE_FORMAT')
        seq=body['sequence']
        if seq==self.known_head.sequence:
            if digest(canonical(body))!=self.known_head.sha256:
                reject('SAME_SEQUENCE_FORK')
            prev=Head(seq-1,body['previous_sha256'])
        elif seq==self.known_head.sequence+1:
            prev=self.known_head
        else:
            reject('REPLAY_OR_MISSING_PROOF')
        new_head=self.verifier.verify_step(payload['witness_event'],prior=prev,
                tenant=self.tenant,campaign=self.campaign)
        declared=exact(payload['head'],{'sequence','sha256'},'DECLARED_HEAD')
        if declared['sequence']!=new_head.sequence or declared['sha256']!=new_head.sha256:
            reject('DECLARED_WITNESS_HEAD_MISMATCH')
        audit=payload['audit_receipt']
        if type(audit) is not dict or audit.get('tenant')!=self.tenant or \
           audit.get('classification')!='TEST_ONLY_NO_SCIENTIFIC_AUTHORITY' or \
           audit.get('execution_eligible') is not True:
            reject('MISSING_OR_QUARANTINED_AUDIT')
        if body['subject_sha256']!=digest(canonical(audit)):
            reject('AUDIT_PROOF_MISMATCH')
        self.known_head=new_head
        return payload
