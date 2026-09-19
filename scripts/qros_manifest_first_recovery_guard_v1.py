#!/usr/bin/env python3
from __future__ import annotations
import json, hashlib
from pathlib import Path

SCHEMA='QROS_MANIFEST_FIRST_RECOVERY_GUARD_1.0'

def validate(manifest:dict, registry:dict):
    errors=[]
    asset=manifest.get('XAUUSD') or {}
    parts=asset.get('parts') or []
    entries=registry.get('entries') or []
    if registry.get('schema')!='QROS_RUNTIME_NEUTRAL_CARRIER_LOCATOR_1.0': errors.append('REGISTRY_SCHEMA')
    if registry.get('resolution_mode')!='MANIFEST_FIRST_DIRECT_MATERIALIZE': errors.append('RESOLUTION_MODE')
    if registry.get('broad_recursive_search_allowed') is not False: errors.append('BROAD_SEARCH_NOT_FORBIDDEN')
    by={e.get('file'):e for e in entries}
    if len(by)!=len(entries): errors.append('DUPLICATE_REGISTRY_FILE')
    for p in parts:
        e=by.get(p.get('file'))
        if not e:
            errors.append('MISSING:'+str(p.get('file'))); continue
        if e.get('expected_sha256')!=p.get('zip_sha256'): errors.append('SHA:'+p['file'])
        if int(e.get('expected_bytes',-1))!=int(p.get('zip_bytes',-2)): errors.append('SIZE:'+p['file'])
        if not e.get('file_id') or not e.get('library_file_id') or not e.get('path'): errors.append('LOCATOR:'+p['file'])
    if len(entries)!=len(parts): errors.append('CARDINALITY')
    return {'schema':SCHEMA,'status':'PASS' if not errors else 'FAIL_CLOSED','errors':errors,'entries':len(entries),'manifest_parts':len(parts)}

def canonical_sha256(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()
