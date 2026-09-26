"""Anti-stall G8 exact-source/delta/authority gate; fail closed on no-op work."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[3]
G8 = Path(__file__).resolve().parent
PARENT = '3210501dba05b9514efde586a4b2aa63378e6a95'
FIRST_G8_COMMIT = '9347a93c99dcbc06e67c6709ab5f49ab66fbee9a'
G8_V1_MANIFEST_BLOB = '81ff512a0b0239acce93c8c307c7af3ea34c19bf'
G7_PRODUCT_BLOB = 'eb7ff78d7861c2813dbea085e017211ce9cdb534'
G7_VERIFIED_BLOB = 'e19aab21c3e8fcd9f011b42a316d89342b81eaad'
SCIENTIFIC_MAIN_BLOB = '5a88937d571e4bcc938c9ce71570092e0abfae6d'
FILES = {
    '.github/workflows/qros-mobile-g8-emulator.yml',
    'product/mobile/g8/G8_EMULATOR_CONTRACT.md',
    'product/mobile/g8/G8_PROGRESS_HEAD.json',
    'product/mobile/g8/G8_SOURCE_MANIFEST.json',
    'product/mobile/g8/G8_SOURCE_MANIFEST_V2.json',
    'product/mobile/g8/G8_CI_INCIDENT_EARLY_SPLASH_UI_PULL_20260925.json',
    'product/mobile/g8/emulator_smoke.py',
    'product/mobile/g8/progress_gate.py',
    'product/mobile/g8/tests/test_emulator_smoke.py',
    'product/mobile/g8/tests/test_gate.py',
}


class GateDeny(RuntimeError):
    pass


def deny(code: str) -> None:
    raise GateDeny('QROS_G8_GATE_FAIL_CLOSED:' + code)


def git(*args: str) -> str:
    try:
        return subprocess.check_output(['git', *args], cwd=REPO, text=True,
                                       stderr=subprocess.PIPE).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        deny('GIT_AUTHORITY_UNAVAILABLE')


def verify(*, remote: bool) -> dict:
    try:
        h = json.loads((G8 / 'G8_PROGRESS_HEAD.json').read_bytes())
        m = json.loads((G8 / 'G8_SOURCE_MANIFEST_V2.json').read_bytes())
    except (OSError, ValueError):
        deny('UNREADABLE_HEAD_OR_MANIFEST')
    if h.get('schema') != 'QROS_MOBILE_G8_PROGRESS_HEAD_V1' or h.get('parent_exact') != PARENT:
        deny('WRONG_PARENT_HEAD')
    if h.get('phase') != 'EMULATOR_RUNTIME_TEST_PENDING' or not h.get('next_automatic_action'):
        deny('NO_TEST_DELTA_OR_FALSE_FINAL_PASS')
    if h.get('scientific_main_pointer_blob_sha1') != SCIENTIFIC_MAIN_BLOB or any(
            h.get(k) is not False for k in ('holdout_open', 'ga2_open', 'scientific_gate_pass')):
        deny('SCIENTIFIC_AUTHORITY_DRIFT')
    if m.get('schema') != 'QROS_MOBILE_G8_SOURCE_MANIFEST_V2' or m.get('parent_exact') != PARENT:
        deny('MANIFEST_PARENT_DRIFT')
    expected = FILES - {'product/mobile/g8/G8_PROGRESS_HEAD.json',
                        'product/mobile/g8/G8_SOURCE_MANIFEST.json',
                        'product/mobile/g8/G8_SOURCE_MANIFEST_V2.json'}
    hashes = m.get('source_sha256', {})
    if set(hashes) != expected or m.get('exact_required_paths') != len(FILES):
        deny('MISSING_SOURCE_TEST_OR_WORKFLOW')
    for path, want in hashes.items():
        f = REPO / path
        if not f.is_file() or f.is_symlink():
            deny('SOURCE_NOT_REGULAR_FILE:' + path)
        if hashlib.sha256(f.read_bytes()).hexdigest() != want:
            deny('SOURCE_SHA256_DRIFT:' + path)
    if remote:
        if git('hash-object', 'product/mobile/g8/G8_SOURCE_MANIFEST.json') != G8_V1_MANIFEST_BLOB:
            deny('ORIGINAL_FAILED_G8_MANIFEST_REWRITTEN')
        if git('hash-object', 'product/mobile/MOBILE_PRODUCT_HEAD.json') != G7_PRODUCT_BLOB:
            deny('MOBILE_HEAD_V10_MUTATED')
        if git('hash-object', 'product/mobile/g7_verified/G7_CURRENT_HEAD.json') != G7_VERIFIED_BLOB:
            deny('G7_VERIFIED_BASELINE_MUTATED')
        if git('rev-parse', 'HEAD^') != FIRST_G8_COMMIT:
            deny('NOT_SINGLE_CORRECTION_DESCENDANT')
        if git('rev-parse', 'HEAD^^') != PARENT:
            deny('G7_PARENT_NOT_PRESERVED')
        delta = set(filter(None, git('diff', '--name-only', PARENT, 'HEAD').splitlines()))
        if delta != FILES:
            deny('NO_OP_MISSING_OR_UNEXPECTED_FILES:' + ','.join(sorted(FILES ^ delta)))
    return {'schema': 'QROS_G8_SOURCE_GATE_RECEIPT_V1',
            'status': 'PASS_EXACT_G8_SOURCE_DELTA_ONLY',
            'new_source_files': len(FILES), 'hashed_source_files': len(expected),
            'remote_git_checks': remote, 'scientific_gate_pass': False,
            'next_action': h['next_automatic_action']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--remote-git', action='store_true')
    args = p.parse_args()
    try:
        print(json.dumps(verify(remote=args.remote_git), indent=2, sort_keys=True))
    except GateDeny as e:
        raise SystemExit(str(e))
