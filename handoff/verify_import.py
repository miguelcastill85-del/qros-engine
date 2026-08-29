#!/usr/bin/env python3
"""Verify the original transfer before editing; integrity is not authenticity."""
from pathlib import Path, PurePosixPath
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def regular(rel):
    p = PurePosixPath(rel)
    if p.is_absolute() or '..' in p.parts or '\\' in rel:
        raise ValueError('unsafe manifest path')
    q = ROOT
    for item in p.parts:
        q = q / item
        if q.is_symlink():
            raise ValueError('symlink in manifest path')
    if not q.is_file():
        raise ValueError('missing regular file: ' + rel)
    return q

def main():
    manifest = regular('HANDOFF_MANIFEST.sha256')
    anchor = regular('HANDOFF_MANIFEST.sha256.sha256').read_text().strip().split('  ')
    if len(anchor) != 2 or anchor[1] != 'HANDOFF_MANIFEST.sha256' or sha(manifest) != anchor[0]:
        raise ValueError('manifest root mismatch')
    seen = set()
    for line in manifest.read_text().splitlines():
        expected, rel = line.split('  ', 1)
        if rel in seen or len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
            raise ValueError('invalid manifest entry')
        seen.add(rel)
        if sha(regular(rel)) != expected:
            raise ValueError('changed file: ' + rel)
    print(json.dumps({'status':'HANDOFF_IMPORT_INTEGRITY_PASS', 'verified_files':len(seen),
        'scope':'original engineering handoff before edits; not code correctness or scientific approval',
        'research_approved':False}))

if __name__ == '__main__':
    main()
