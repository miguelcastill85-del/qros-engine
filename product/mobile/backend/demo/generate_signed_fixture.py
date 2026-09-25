"""One-time offline test fixture publisher. Never ship private keys.

Run explicitly with --generate. Writes only synthetic public artifacts with two
independent ephemeral Ed25519 keys; private keys are discarded before exit.
Production would require an independent immutable witness and auditable key custody.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import secrets
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from protocol import canonical, sha256


def sign(private: Ed25519PrivateKey, body: dict) -> dict:
    return {"body": body, "signature_b64": base64.b64encode(private.sign(canonical(body))).decode("ascii")}


def public_b64(private: Ed25519PrivateKey) -> str:
    return base64.b64encode(private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)).decode("ascii")


def generate(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    witness = Ed25519PrivateKey.generate()
    receipt_key = Ed25519PrivateKey.generate()
    source_sha = sha256(b"QROS_MOBILE_M1_SYNTHETIC_CANONICAL_FIXTURE_V1")
    anchor = {
        "schema":"QROS_M2_WITNESS_ANCHOR_TEST_V1", "sequence":1,
        "digest":sha256(b"QROS_SYNTHETIC_LEDGER_EVENT_001"), "previous_digest":"0"*64,
        "project_id":"DEMO-001", "source_class":"TEST_ONLY_SYNTHETIC",
        "source_pin_sha256":source_sha
    }
    anchor_sha = sha256(canonical(anchor))
    receipt = {
        "schema":"QROS_MOBILE_RECEIPT_TEST_V1", "project_id":"DEMO-001",
        "source_class":"TEST_ONLY_SYNTHETIC", "scientific_state":"SIMULATED_SAMPLE",
        "scientific_approval":False, "holdout_open":False, "ga2_open":False, "mt5_executed":False,
        "anchor_sha256":anchor_sha, "anchor_sequence":1, "source_pin_sha256":source_sha,
        "project":{"id":"DEMO-001", "title":"Ruptura y recuperacion DEMO", "symbol":"XAUUSD",
                   "side":"BUY", "timeframe":"M15", "classification":"TEST_ONLY_SYNTHETIC"}
    }
    bundle={"schema":"QROS_MOBILE_SIGNED_TEST_ONLY_V1","mode":"TEST_ONLY_SYNTHETIC",
            "scientific_authority":"NONE", "anchor":sign(witness,anchor), "receipt":sign(receipt_key,receipt)}
    trust={"schema":"QROS_MOBILE_TRUST_ROOT_TEST_V1", "anchor_sha256":anchor_sha,
           "witness_public_key_b64":public_b64(witness),"receipt_public_key_b64":public_b64(receipt_key),
           "project_id":"DEMO-001","source_pin_sha256":source_sha}
    traw=(json.dumps(trust,sort_keys=True,indent=2,ensure_ascii=True)+'\n').encode()
    braw=(json.dumps(bundle,sort_keys=True,indent=2,ensure_ascii=True)+'\n').encode()
    (target/'trust_root.json').write_bytes(traw)
    (target/'signed_snapshot.json').write_bytes(braw)
    (target/'PUBLIC_PIN.txt').write_text(sha256(traw)+'\n',encoding='ascii')
    print('TEST_ONLY_TRUST_ROOT_SHA256='+sha256(traw))
    print('TEST_ONLY_ANCHOR_BODY_SHA256='+anchor_sha)
    print('TEST_ONLY_WITNESS_PUBLIC_KEY_B64='+trust['witness_public_key_b64'])
    print('TEST_ONLY_RECEIPT_PUBLIC_KEY_B64='+trust['receipt_public_key_b64'])
    # Neither private key has a serialized representation in the tree.

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--generate',action='store_true',required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();generate(a.out)
