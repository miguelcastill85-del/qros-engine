"""G7 exact G6 APK audit. Tests Android debug artifact, never re-labels release.

The Android apksigner must independently verify the APK signature. A verified
*debug* certificate is a deliberate non-release result. No keystore is created.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

EXPECTED_SHA='2c4053a27fa5692871db717c4c5bb42e1284673b49f13fa41db6a7e2b0b52c97'
EXPECTED_BYTES=141623410
SHA_RE=re.compile(r'(?i)Signer #1 certificate SHA-256 digest:\s*([0-9a-f]{64})')

class ReleaseDeny(RuntimeError): pass

def deny(why: str): raise ReleaseDeny('QROS_G7_RELEASE_DENY:'+why)

def inspect(apk: Path, *, apksigner: str='apksigner',
            run=subprocess.run) -> dict:
    if not apk.is_file() or apk.is_symlink(): deny('APK_FILE_REQUIRED')
    if apk.stat().st_size!=EXPECTED_BYTES: deny('G6_BYTES_MISMATCH')
    with apk.open('rb') as handle:
        sha=hashlib.file_digest(handle,'sha256').hexdigest()
    if sha!=EXPECTED_SHA: deny('G6_SHA_MISMATCH')
    if not zipfile.is_zipfile(apk): deny('APK_ZIP_INVALID')
    try:
        result=run([apksigner,'verify','--verbose','--print-certs',str(apk)],
                   capture_output=True,text=True,timeout=45,check=False)
    except (FileNotFoundError,subprocess.TimeoutExpired):
        deny('APK_SIGNER_INFRASTRUCTURE_MISSING')
    if result.returncode!=0: deny('ANDROID_PACKAGE_SIGNATURE_INVALID')
    output=result.stdout+'\n'+result.stderr
    found=SHA_RE.search(output)
    if found is None:
        # Different build-tools versions may label the cert digest differently.
        # Require an actual explicit certificate digest, never use APK digest as fallback.
        found=re.search(r'(?im)^(?=[^\n]*cert(?:ificate)?)(?=[^\n]*sha[- ]?256)[^\n]*?([0-9a-f]{64})(?:\s|$)',output)
    if found is None: deny('APK_SIGNER_CERTIFICATE_MISSING_RETAIN_RAW_DIAGNOSTIC')
    if re.search(r'(?im)^(?:V[1-4](?:\.\d+)? Signer: certificate DN:|Signer #\d+ certificate DN:).*Android Debug\s*$',output):
        kind='ANDROID_DEBUG_CERTIFICATE_REJECTED_FOR_RELEASE'
    else:
        kind='UNVERIFIED_NONDEBUG_CERTIFICATE_REJECTED_FOR_RELEASE'
    return {'schema':'QROS_G7_G6_APK_AUTHENTICITY_CANARY_V1',
            'status':'PASS_G6_APK_SIGNATURE_VERIFIED_TEST_ONLY',
            'apk_sha256':sha,'apk_bytes':EXPECTED_BYTES,
            'certificate_sha256':found.group(1).lower(),
            'signer_class':kind,'release_eligible':False,
            'physical_install':'NOT_RUN','test_only':True}

def main() -> int:
    p=argparse.ArgumentParser();p.add_argument('--apk',type=Path,required=True)
    p.add_argument('--apksigner',default='apksigner');a=p.parse_args()
    try: report=inspect(a.apk,apksigner=a.apksigner)
    except ReleaseDeny as exc:
        print(json.dumps({'status':'BLOCKED_BY_INFRASTRUCTURE_OR_APK_MISMATCH','reason':str(exc),
                          'release_eligible':False}));return 3
    print(json.dumps(report,sort_keys=True,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
