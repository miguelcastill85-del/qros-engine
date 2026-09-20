"""Read-only candidate integrity check. The verifier must itself be host-trusted.

Use a verified Git checkout and supply the release manifest blob independently.
This checks package integrity; it is not a sandbox or scientific authorization.
"""
import argparse
import json
import os
from pathlib import Path
from .runtime import ContractError, Snapshot, require, require_hash, git_blob, sha256, relative_parts

MANIFEST = 'cognitive/COGNITIVE_MANIFEST.json'


def verify(root: Path, expected_manifest_blob: str, *, captured: dict | None = None) -> dict:
    require_hash(expected_manifest_blob, 40)
    snapshot = Snapshot(root)
    manifest, raw = snapshot.json(MANIFEST)
    require(git_blob(raw) == expected_manifest_blob, 'RELEASE_ANCHOR_MISMATCH')
    require(manifest.get('schema') == 'QRCEL_SOURCE_AND_ENGINEERING_EVIDENCE_MANIFEST_V1', 'RELEASE_SCHEMA')
    require(manifest.get('scientific_authority') is False, 'RELEASE_CANNOT_BE_SCIENTIFIC_AUTHORITY')
    files = manifest.get('files_sha256')
    require(isinstance(files, dict) and 0 < len(files) <= 2048, 'RELEASE_FILES_MISSING')
    verified = {MANIFEST: raw}
    total = len(raw)
    for path, digest in files.items():
        parts = relative_parts(path)
        require(len(parts) > 1 and parts[0] == 'cognitive' and path != MANIFEST, 'RELEASE_SCOPE_VIOLATION')
        require_hash(digest)
        data = snapshot.read(path)
        require(sha256(data) == digest, 'RELEASE_FILE_MISMATCH', path)
        verified[path] = data
        total += len(data)
        require(total <= 64 * 1024 * 1024, 'RELEASE_SIZE_LIMIT')
    # Unlisted code could otherwise be imported while all listed hashes match.
    sources = set()
    for directory, dirs, names in os.walk(root / 'cognitive', followlinks=False):
        for name in dirs + names:
            require(not (Path(directory) / name).is_symlink(), 'RELEASE_SYMLINK', name)
        for name in names:
            require(not name.lower().endswith(('.pyc','.pyo','.so','.pyd','.dll','.dylib','.zip','.pth')),
                    'RELEASE_UNLISTED_CODE', name)
            if name.endswith('.py'):
                sources.add((Path(directory) / name).relative_to(root).as_posix())
    require(sources == {p for p in files if p.endswith('.py')}, 'RELEASE_UNLISTED_CODE')
    if captured is not None:
        captured.clear()
        captured.update(verified)
    return {'schema': 'QRCEL_RELEASE_INTEGRITY_V1', 'status': 'PASS',
            'manifest_blob_sha1': expected_manifest_blob, 'files_verified': len(files),
            'source_files_verified': len(sources), 'tests_executed_by_this_check': False,
            'runtime_capability_inherited': False, 'scientific_dispatch_authorized': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', required=True, type=Path)
    parser.add_argument('--manifest-blob', required=True)
    args = parser.parse_args()
    try:
        result = verify(args.repo_root, args.manifest_blob)
    except ContractError as error:
        result = {'schema': 'QRCEL_RELEASE_INTEGRITY_V1', 'status': 'FAIL',
                  'error': error.code, 'detail': str(error), 'scientific_dispatch_authorized': False}
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
