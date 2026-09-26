"""G7: fail-closed EdDSA JWT authorization canary. TEST_ONLY; no deployed OIDC.

Public keys, issuer, audience and tenant binding MUST be pinned outside the token.
The in-memory replay guard is NOT a production multi-instance revocation store.
"""
from __future__ import annotations
import base64
from dataclasses import dataclass, field
import json
import re
from typing import Any
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_ID = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,95}\Z')
_B64 = re.compile(r'[A-Za-z0-9_-]+\Z')
HEADER = {'alg', 'typ', 'kid'}
CLAIMS = {'iss', 'aud', 'sub', 'tenant', 'project', 'scope', 'iat', 'nbf', 'exp', 'jti'}

class OidcDeny(ValueError):
    pass

def deny(why: str) -> None:
    raise OidcDeny('QROS_G7_OIDC_DENY:' + why)

def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k,v in items:
        if k in result:
            deny('DUPLICATE_KEY')
        result[k] = v
    return result

def strict_json(data: bytes) -> Any:
    if not data or len(data)>8192:
        deny('JSON_BUDGET')
    try:
        return json.loads(data.decode('utf-8','strict'), object_pairs_hook=pairs,
                          parse_constant=lambda _: deny('NONFINITE'))
    except (ValueError, TypeError, UnicodeError) as exc:
        if isinstance(exc,OidcDeny):
            raise
        deny('INVALID_JSON')

def b64url(segment: str) -> bytes:
    if type(segment) is not str or len(segment)>10923 or not _B64.fullmatch(segment):
        deny('NONCANONICAL_BASE64URL')
    try:
        value=base64.urlsafe_b64decode(segment+'='*(-len(segment)%4))
    except (ValueError, UnicodeError):
        deny('INVALID_BASE64URL')
    if base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')!=segment:
        deny('NONCANONICAL_BASE64URL')
    return value

def exact(item: Any, keys: set[str], name: str) -> dict[str, Any]:
    if type(item) is not dict or set(item)!=keys:
        deny('INVALID_'+name+'_SCHEMA')
    return item

def identifier(value: Any, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        deny('INVALID_'+label)
    return value

@dataclass
class SyntheticOidcVerifier:
    issuer: str
    audience: str
    key_id: str
    public_key: bytes
    max_ttl_seconds: int = 300
    seen_jti: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if type(self.public_key) is not bytes or len(self.public_key)!=32:
            deny('OUT_OF_BAND_ED25519_PIN_REQUIRED')
        if not self.issuer.startswith('https://') or '/' not in self.issuer[8:]:
            deny('HTTPS_ISSUER_REQUIRED')
        identifier(self.key_id,'PINNED_KID')
        if type(self.max_ttl_seconds) is not int or not 1<=self.max_ttl_seconds<=300:
            deny('TTL_POLICY')

    def verify(self, compact: Any, *, tenant: str, project: str, scope: str,
               now_utc_seconds: int) -> dict[str, Any]:
        if type(compact) is not str or len(compact)>16384:
            deny('TOKEN_BUDGET')
        segments=compact.split('.')
        if len(segments)!=3:
            deny('COMPACT_JWT_REQUIRED')
        header=exact(strict_json(b64url(segments[0])),HEADER,'HEADER')
        if header!={'alg':'EdDSA','typ':'JWT','kid':self.key_id}:
            deny('ALG_OR_PINNED_KEY_MISMATCH')
        claims=exact(strict_json(b64url(segments[1])),CLAIMS,'CLAIMS')
        signature=b64url(segments[2])
        if len(signature)!=64:
            deny('SIGNATURE_LENGTH')
        try:
            Ed25519PublicKey.from_public_bytes(self.public_key).verify(
                signature,(segments[0]+'.'+segments[1]).encode('ascii'))
        except (InvalidSignature, ValueError, TypeError):
            deny('INVALID_SIGNATURE')
        if type(now_utc_seconds) is not int:
            deny('TRUSTED_CLOCK_REQUIRED')
        for k in ('iat','nbf','exp'):
            if type(claims[k]) is not int:
                deny('TIMESTAMP_TYPE')
        if claims['iss']!=self.issuer or claims['aud']!=self.audience or \
           claims['tenant']!=identifier(tenant,'TENANT') or \
           claims['project']!=identifier(project,'PROJECT'):
            deny('ISSUER_AUDIENCE_OR_TENANT')
        identifier(claims['sub'],'SUBJECT')
        identifier(claims['jti'],'JTI')
        if type(claims['scope']) is not list or not claims['scope'] or \
           any(type(s) is not str or s not in ('demo:read','status:read') for s in claims['scope']) or \
           len(set(claims['scope']))!=len(claims['scope']) or scope not in claims['scope']:
            deny('SCOPE')
        if not (claims['iat']<=claims['nbf']<=now_utc_seconds<claims['exp']) or \
           claims['exp']-claims['iat']>self.max_ttl_seconds or \
           now_utc_seconds-claims['iat']>self.max_ttl_seconds:
            deny('TIME_OR_TOKEN_LIFETIME')
        if claims['jti'] in self.seen_jti:
            deny('REPLAY')
        self.seen_jti.add(claims['jti'])
        return {'status':'PASS_SYNTHETIC_EDDSA_SCOPE_ONLY','tenant':tenant,
                'project':project,'scope':scope,'scientific_authority':False,
                'production_oidc':'NOT_DEPLOYED'}
