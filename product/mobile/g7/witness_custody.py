"""G7 independently pinned external-witness *interface* / synthetic canary.

A simulated second operator can test fail-closed parsing and cryptography, but
cannot certify real administrative or geographical separation. Production PASS
requires real operator pin, independent HTTPS endpoint and audit documentation.
"""
from __future__ import annotations
import base64
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from oidc_canary import strict_json, identifier

HEX = re.compile('[0-9a-f]{64}\\Z')
class CustodyDeny(ValueError): pass

def deny(why: str) -> None:
    raise CustodyDeny('QROS_G7_CUSTODY_DENY:'+why)

def canonical(obj: Any) -> bytes:
    return json.dumps(obj,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':')).encode('utf-8')

@dataclass(frozen=True)
class CustodyHead:
    sequence: int
    hash: str

GENESIS = CustodyHead(0,'0'*64)
BODY={'schema','operator_id','witness_id','sequence','previous_sha256',
      'subject_sha256','tenant','campaign','created_utc','mode'}

class PinnedExternalWitnessVerifier:
    def __init__(self, admin_public_key: bytes, *, operator_id: str,
                 witness_id: str, synthetic_canary: bool):
        if type(admin_public_key) is not bytes or len(admin_public_key)!=32:
            deny('SEPARATELY_PINNED_OPERATOR_KEY_REQUIRED')
        self.key=Ed25519PublicKey.from_public_bytes(admin_public_key)
        self.operator=identifier(operator_id,'OPERATOR')
        self.witness=identifier(witness_id,'WITNESS')
        self.synthetic=synthetic_canary

    def verify(self, event: Any, *, prior: CustodyHead, subject_sha256: str,
               tenant: str, campaign: str) -> CustodyHead:
        if type(event) is not dict or set(event)!={'body','signature_b64'}:
            deny('ENVELOPE_SCHEMA')
        body=event['body']
        if type(body) is not dict or set(body)!=BODY:
            deny('BODY_SCHEMA')
        if body['schema']!='QROS_G7_OPERATOR_ATTESTATION_V1' or \
           body['operator_id']!=self.operator or body['witness_id']!=self.witness:
            deny('UNPINNED_OPERATOR_OR_SCHEMA')
        if body['mode']!='SYNTHETIC_SECOND_PROCESS_TEST' or not self.synthetic:
            deny('REAL_EXTERNAL_CUSTODY_NOT_ATTESTED')
        if type(body['sequence']) is not int or body['sequence']!=prior.sequence+1 or \
           body['previous_sha256']!=prior.hash or \
           body['subject_sha256']!=subject_sha256 or \
           body['tenant']!=identifier(tenant,'TENANT') or \
           body['campaign']!=identifier(campaign,'CAMPAIGN'):
            deny('REPLAY_FORK_TENANT_OR_SOURCE')
        if any(type(body[k]) is not str or HEX.fullmatch(body[k]) is None for k in ('subject_sha256','previous_sha256')):
            deny('MALFORMED_DIGEST')
        if type(body['created_utc']) is not str or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',body['created_utc']):
            deny('TIMESTAMP_FORMAT')
        sig=event['signature_b64']
        if type(sig) is not str or len(sig)>100:
            deny('SIGNATURE_FORMAT')
        try:
            decoded=base64.b64decode(sig,validate=True)
            if len(decoded)!=64: deny('SIGNATURE_LENGTH')
            self.key.verify(decoded,canonical(body))
        except (ValueError,InvalidSignature):
            deny('SIGNATURE_INVALID')
        return CustodyHead(body['sequence'],hashlib.sha256(canonical(body)).hexdigest())


def production_status(*, verified_off_host_administration: bool,
                      verified_off_host_tls: bool, independently_pinned_key: bool,
                      nonrollbackable_monotonic_receipt: bool) -> dict:
    # No assertion by the same local test process is adequate evidence of custody.
    # This function only reports missing infrastructure; it cannot promote PASS.
    required={'independent_operator':verified_off_host_administration,
              'independent_https':verified_off_host_tls,
              'independently_distributed_pin':independently_pinned_key,
              'external_antirollback_receipt':nonrollbackable_monotonic_receipt}
    return {'status':'BLOCKED_BY_INFRASTRUCTURE_EXTERNAL_CUSTODY',
            'missing':[k for k,v in required.items() if v is not True],
            'promotable_from_local_test':False,'scientific_authority':False}
