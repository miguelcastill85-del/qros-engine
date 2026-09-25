"""G2: TEST_ONLY finite structural census with atomic shard receipts and crash recovery.

The G1 Python itertools generator is an oracle; independently authored C++20
mixed-radix generator is compared row-by-row. NO market data, PnL, holdout or
scientific state mutation. Local filesystem receipts are NOT external witnesses.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import time
from typing import Iterator

BACKEND = Path(__file__).resolve().parents[1] / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
from universe_contract import make_blueprint, canonical_json  # G1 verified contract; no reimplementation

SCHEMA = 'QROS_G2_SHARD_CHECKPOINT_TEST_ONLY_V1'
RECEIPT_SCHEMA = 'QROS_G2_SHARD_RECEIPT_TEST_ONLY_V1'
ZERO = '0' * 64
AXES = ('sides', 'timeframes', 'lookback_bars', 'confirmation_bars',
        'stop_ratios', 'maximum_holding_bars')


class IntegrityError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(obj: dict) -> bytes:
    return (canonical_json(obj) + '\n').encode('utf-8')


def axes_of(blueprint: dict) -> tuple[list, ...]:
    g = blueprint['grammar']
    return tuple(blueprint[name] if name in ('sides','timeframes') else g[name]
                 for name in AXES)


def blueprint_from_raw(raw: dict) -> dict:
    obj = make_blueprint(raw)
    if obj.get('classification') != 'SYNTHETIC_ONLY' or obj.get('scientific_authority') is not False:
        raise IntegrityError('SCIENCE_AUTHORITY_FORBIDDEN')
    if obj.get('holdout_open') is not False or obj.get('status') != 'LOCAL_DRAFT_NOT_FROZEN':
        raise IntegrityError('HOLDOUT_OR_FREEZE_NOT_PERMITTED')
    return obj


def spec_bytes(blueprint: dict) -> bytes:
    lines = ['QROS_G2_SYNTHETIC_SPEC_V1', 'symbol=' + blueprint['symbol']]
    for name, vals in zip(AXES, axes_of(blueprint)):
        lines.append(name + '=' + ','.join(str(v) for v in vals))
    lines.append('raw_births=' + str(blueprint['raw_births']))
    return ('\n'.join(lines)+'\n').encode('ascii')


def product_oracle(blueprint: dict, start: int = 0, count: int | None = None) -> Iterator[bytes]:
    """Independent itertools oracle, never loads full universe into RAM."""
    end = blueprint['raw_births'] if count is None else start + count
    if type(start) is not int or type(end) is not int or start < 0 or end > blueprint['raw_births']:
        raise IntegrityError('INVALID_ORACLE_SLICE')
    for fields in itertools.islice(itertools.product(*axes_of(blueprint)), start, end):
        yield ('|'.join(map(str, (blueprint['symbol'], *fields)))+'\n').encode('ascii')


def random_access_row(blueprint: dict, rank: int) -> bytes:
    """Shard writer uses rank unranking; test oracle uses Python itertools."""
    if type(rank) is not int or not (0 <= rank < blueprint['raw_births']):
        raise IntegrityError('RANK_OUT_OF_RANGE')
    digits: list[str] = []
    for values in reversed(axes_of(blueprint)):
        rank, remainder = divmod(rank, len(values))
        digits.append(str(values[remainder]))
    return ('|'.join((blueprint['symbol'], *reversed(digits)))+'\n').encode('ascii')


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read_regular(path: Path, max_bytes: int) -> bytes:
    try:
        st = path.lstat()
    except FileNotFoundError:
        raise IntegrityError('MISSING_FILE:' + path.name)
    if not stat.S_ISREG(st.st_mode) or st.st_size > max_bytes:
        raise IntegrityError('UNTRUSTED_FILE:' + path.name)
    return path.read_bytes()


def put_atomic(path: Path, payload: bytes, *, replace: bool = False) -> None:
    # Never reuse a partially written file, even after a process SIGKILL.
    temp = path.with_name('.tmp-' + path.name + '-' + str(os.getpid()))
    if path.exists() and not replace:
        raise IntegrityError('WRITE_COLLISION:' + path.name)
    try:
        with temp.open('xb') as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
        fsync_dir(path.parent)
    finally:
        temp.unlink(missing_ok=True)


def maybe_crash(boundary: str, at: int) -> None:
    if os.environ.get('QROS_G2_CRASH_BOUNDARY') == boundary and os.environ.get('QROS_G2_CRASH_START') == str(at):
        os._exit(75)


def report_filename(start: int, end: int, kind: str) -> str:
    return f'{kind}-{start:08d}-{end:08d}.' + ('ids' if kind == 'shard' else 'json')


def checkpoint_payload(plan_sha: str, source_sha: str, next_index: int,
                       completed: int, latest: str, total: int, chunk: int) -> dict:
    return dict(schema=SCHEMA, classification='SYNTHETIC_ONLY',
                scientific_authority=False, holdout_open=False, pnl_tests=0,
                plan_sha256=plan_sha, blueprint_sha256=source_sha,
                next_index=next_index, shards_verified=completed,
                last_receipt_sha256=latest, total_births=total, chunk_size=chunk)


def prepare(work_dir: Path, raw: dict, chunk: int) -> tuple[dict, str, str]:
    if type(chunk) is not int or chunk <= 0 or chunk > 10000:
        raise IntegrityError('INVALID_CHUNK_SIZE')
    if work_dir.is_symlink():
        raise IntegrityError('SYMLINK_WORKDIR')
    work_dir.mkdir(parents=True, exist_ok=True)
    source = blueprint_from_raw(raw)
    source_sha = digest(canonical_json(source).encode('utf-8'))
    frozen = dict(schema='QROS_G2_FINITE_PLAN_V1', blueprint_sha256=source_sha,
                  chunk_size=chunk, total_births=source['raw_births'],
                  environment='TEST_ONLY_NO_PNL')
    plan = canonical_bytes(frozen)
    plan_sha = digest(plan)
    for name, data in (('plan.json', plan), ('spec.txt', spec_bytes(source))):
        path = work_dir / name
        if path.exists():
            if read_regular(path, 16_384) != data:
                raise IntegrityError('FROZEN_IDENTITY_CHANGED:' + name)
        else:
            put_atomic(path, data)
    return source, source_sha, plan_sha


def audit_existing(work_dir: Path, blueprint: dict, chunk: int,
                   source_sha: str, plan_sha: str) -> tuple[int, int, str]:
    total = blueprint['raw_births']
    receipts = sorted(work_dir.glob('receipt-*.json'))
    verified: set[str] = set()
    seen_shards: set[str] = set()
    index = 0
    parent = ZERO
    chain = [ZERO]
    for rec_path in receipts:
        end = min(total, index + chunk)
        expected = report_filename(index, end, 'receipt')
        if rec_path.name != expected:
            raise IntegrityError('RECEIPT_GAP_OR_REPLAY:' + rec_path.name)
        rec_bytes = read_regular(rec_path, 16_384)
        try:
            rec = json.loads(rec_bytes)
        except (ValueError, UnicodeError):
            raise IntegrityError('INVALID_RECEIPT_JSON')
        expected_keys = {'schema','classification','blueprint_sha256','plan_sha256',
                         'start','end','rows','shard_filename','content_sha256',
                         'previous_receipt_sha256','holdout_open','pnl_tests'}
        if type(rec) is not dict or set(rec) != expected_keys or rec_bytes != canonical_bytes(rec):
            raise IntegrityError('NONCANONICAL_RECEIPT')
        if any((rec['schema'] != RECEIPT_SCHEMA, rec['classification'] != 'SYNTHETIC_ONLY',
                rec['blueprint_sha256'] != source_sha, rec['plan_sha256'] != plan_sha,
                rec['start'] != index, rec['end'] != end, rec['rows'] != end-index,
                rec['previous_receipt_sha256'] != parent,
                rec['holdout_open'] is not False, rec['pnl_tests'] != 0)):
            raise IntegrityError('RECEIPT_PROVENANCE_DRIFT')
        name = report_filename(index, end, 'shard')
        if rec['shard_filename'] != name:
            raise IntegrityError('SHARD_NAME_DRIFT')
        contents = read_regular(work_dir / name, (end-index)*256)
        if len(rec['content_sha256']) != 64 or digest(contents) != rec['content_sha256']:
            raise IntegrityError('SHARD_TAMPER:' + name)
        if contents != b''.join(random_access_row(blueprint, i) for i in range(index, end)):
            raise IntegrityError('SHARD_SEMANTIC_DRIFT')
        seen_shards.add(name)
        verified.add(expected)
        parent = digest(rec_bytes)
        index = end
        chain.append(parent)
    checkpoint = work_dir / 'checkpoint.json'
    if checkpoint.exists():
        contents = read_regular(checkpoint, 16_384)
        try:
            old = json.loads(contents)
        except (ValueError, UnicodeError):
            raise IntegrityError('CHECKPOINT_CORRUPT')
        if type(old) is not dict or contents != canonical_bytes(old) or set(old) != set(checkpoint_payload(plan_sha,source_sha,0,0,ZERO,total,chunk)):
            raise IntegrityError('CHECKPOINT_SCHEMA_DRIFT')
        ix = old['next_index']
        if type(ix) is not int or ix < 0 or ix > index or type(old['shards_verified']) is not int or old['shards_verified'] > len(receipts):
            raise IntegrityError('CHECKPOINT_ROLLBACK_OR_FUTURE')
        if ix != min(total, old['shards_verified']*chunk):
            raise IntegrityError('CHECKPOINT_COUNTER_MISMATCH')
        expected_old = checkpoint_payload(plan_sha,source_sha,ix,old['shards_verified'],chain[old['shards_verified']],total,chunk)
        if old != expected_old:
            raise IntegrityError('CHECKPOINT_CHAIN_MISMATCH')
    # Incomplete shard without receipt may have resulted from SIGKILL after shard
    # fsync. Quarantine and regenerate; never silently count it as PASS.
    for p in sorted(work_dir.glob('shard-*.ids')):
        if p.name not in seen_shards:
            if p.name != report_filename(index,min(total,index+chunk),'shard'):
                raise IntegrityError('UNEXPECTED_ORPHAN_SHARD:' + p.name)
            payload = read_regular(p, (min(total,index+chunk)-index)*256)
            quarantine = work_dir / 'orphan'
            quarantine.mkdir(exist_ok=True)
            dest = quarantine / (p.name + '.' + digest(payload)[:16])
            if dest.exists():
                if read_regular(dest, len(payload)+1) != payload:
                    raise IntegrityError('QUARANTINE_COLLISION')
                p.unlink()
            else:
                os.replace(p, dest)
            fsync_dir(work_dir)
    for p in work_dir.glob('.tmp-*'):
        if not p.is_file() or p.is_symlink():
            raise IntegrityError('UNSAFE_STAGING_FILE')
        p.unlink()
    return index, len(receipts), parent


def run_shards(work_dir: Path, raw: dict, chunk: int,
               max_new_shards: int | None = None) -> dict:
    blueprint, source_sha, plan_sha = prepare(work_dir, raw, chunk)
    index, verified, parent = audit_existing(work_dir,blueprint,chunk,source_sha,plan_sha)
    total = blueprint['raw_births']
    if max_new_shards is not None and (type(max_new_shards) is not int or max_new_shards < 0):
        raise IntegrityError('INVALID_SHARD_BUDGET')
    # Repair only a checkpoint that lagged behind a fully durable receipt after crash.
    cp = work_dir / 'checkpoint.json'
    current = checkpoint_payload(plan_sha,source_sha,index,verified,parent,total,chunk)
    if not cp.exists() or read_regular(cp,16_384) != canonical_bytes(current):
        put_atomic(cp, canonical_bytes(current), replace=cp.exists())
    new = 0
    while index < total and (max_new_shards is None or new < max_new_shards):
        end = min(total,index+chunk)
        shard_start = index
        sh_path=work_dir/report_filename(index,end,'shard')
        h = hashlib.sha256()
        temp = work_dir / ('.tmp-' + sh_path.name + '-' + str(os.getpid()))
        try:
            with temp.open('xb') as file:
                for j in range(index,end):
                    row = random_access_row(blueprint,j)
                    file.write(row)
                    h.update(row)
                file.flush()
                os.fsync(file.fileno())
            if sh_path.exists():
                raise IntegrityError('DUPLICATE_SHARD')
            os.replace(temp,sh_path)
            fsync_dir(work_dir)
        finally:
            temp.unlink(missing_ok=True)
        maybe_crash('AFTER_SHARD',index)
        rec = dict(schema=RECEIPT_SCHEMA,classification='SYNTHETIC_ONLY',
                   blueprint_sha256=source_sha,plan_sha256=plan_sha,
                   start=index,end=end,rows=end-index,shard_filename=sh_path.name,
                   content_sha256=h.hexdigest(),previous_receipt_sha256=parent,
                   holdout_open=False,pnl_tests=0)
        raw_receipt = canonical_bytes(rec)
        receipt_path = work_dir/report_filename(index,end,'receipt')
        put_atomic(receipt_path,raw_receipt)
        maybe_crash('AFTER_RECEIPT',index)
        parent = digest(raw_receipt)
        index=end
        verified+=1
        current=checkpoint_payload(plan_sha,source_sha,index,verified,parent,total,chunk)
        put_atomic(cp,canonical_bytes(current),replace=True)
        maybe_crash('AFTER_CHECKPOINT', shard_start)
        new+=1
    index2,count2,parent2 = audit_existing(work_dir,blueprint,chunk,source_sha,plan_sha)
    if (index2,count2,parent2)!=(index,verified,parent):
        raise IntegrityError('FINAL_REAUDIT_FAILURE')
    return dict(schema='QROS_G2_RUN_RESULT_V1', status='COMPLETE' if index==total else 'PAUSED',
                verified_births=index, total_births=total, verified_shards=verified,
                new_shards_this_run=new, last_receipt_sha256=parent,
                blueprint_sha256=source_sha,plan_sha256=plan_sha,
                holdout_open=False,pnl_tests=0, scientific_authority=False)


def native_matches(cxx_binary: Path, spec: Path, blueprint: dict,
                   start: int = 0,count: int | None = None) -> tuple[int,str]:
    if count is None:
        count=blueprint['raw_births'] - start
    command=[str(cxx_binary),'--spec',str(spec),'--start',str(start),'--count',str(count)]
    proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    h = hashlib.sha256()
    seen=0
    try:
        assert proc.stdout is not None
        for expected in product_oracle(blueprint,start,count):
            actual=proc.stdout.readline()
            if actual!=expected:
                proc.kill()
                raise IntegrityError('NATIVE_PARITY_MISMATCH_AT:' + str(start+seen))
            h.update(actual)
            seen+=1
        extra=proc.stdout.readline()
        if extra:
            proc.kill()
            raise IntegrityError('NATIVE_EXTRA_ROW')
        if proc.wait(timeout=30)!=0:
            raise IntegrityError('NATIVE_FAILED:'+proc.stderr.read(4096).decode('utf-8','replace'))
    finally:
        if proc.poll() is None:proc.kill()
        proc.wait()
        if proc.stdout:proc.stdout.close()
        if proc.stderr:proc.stderr.close()
    return seen,h.hexdigest()
