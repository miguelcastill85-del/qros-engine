#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, json
from pathlib import Path
from typing import Any

SCHEMA='QROS_PERSISTENT_FOREGROUND_GUARD_RESULT_V1'

def load(p: Path)->dict[str,Any]:
    v=json.loads(p.read_text(encoding='utf-8'))
    if not isinstance(v,dict): raise ValueError('root must be object')
    return v

def parse_time(v:str)->dt.datetime:
    x=dt.datetime.fromisoformat(v.replace('Z','+00:00'))
    if x.tzinfo is None: raise ValueError('timezone required')
    return x.astimezone(dt.timezone.utc)

def foreground_status(fg:dict[str,Any]|None, now:dt.datetime)->str:
    if not fg or fg.get('status')!='ACTIVE': return 'INACTIVE'
    until=parse_time(fg['active_until'])
    return 'ACTIVE' if now.astimezone(dt.timezone.utc) < until else 'EXPIRED'

def lease_status(state:dict[str,Any], now:dt.datetime, heartbeat_max_minutes:int)->str:
    lease=state.get('lease')
    if lease is None: return 'FREE'
    hb=parse_time(lease['heartbeat_at']); exp=parse_time(lease['expires_at']); n=now.astimezone(dt.timezone.utc)
    if exp <= n: return 'EXPIRED'
    if hb + dt.timedelta(minutes=heartbeat_max_minutes) <= n: return 'STALE_HEARTBEAT'
    return 'FRESH'

def decision(state:dict[str,Any], fg:dict[str,Any]|None, now:dt.datetime, surface:str, heartbeat_max_minutes:int=20)->dict[str,Any]:
    fs=foreground_status(fg,now); ls=lease_status(state,now,heartbeat_max_minutes)
    if surface=='automation' and fs=='ACTIVE':
        d='NO_OP_FOREGROUND_ACTIVE'
    elif ls=='FRESH':
        d='NO_OP_FRESH_LEASE'
    elif ls in {'STALE_HEARTBEAT','EXPIRED'}:
        d='RECOVERY_REQUIRED_THEN_CLAIM_ALLOWED'
    else:
        d='CLAIM_ALLOWED'
    return {'schema':SCHEMA,'surface':surface,'foreground_status':fs,'lease_status':ls,'decision':d,
            'heartbeat_max_minutes':heartbeat_max_minutes,'turn_end_requires_lease_null':True}

def turn_end_validate(state:dict[str,Any])->dict[str,Any]:
    ok=state.get('lease') is None
    return {'schema':SCHEMA,'decision':'TURN_END_PASS' if ok else 'TURN_END_FAIL_LEASE_LEAK','lease_null':ok}

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('command',choices=('decision','turn-end-validate'))
    ap.add_argument('--state',type=Path,required=True)
    ap.add_argument('--foreground',type=Path)
    ap.add_argument('--surface',choices=('manual','automation'),default='manual')
    ap.add_argument('--now')
    ap.add_argument('--heartbeat-max-minutes',type=int,default=20)
    a=ap.parse_args(); state=load(a.state)
    if a.command=='turn-end-validate': out=turn_end_validate(state)
    else:
        now=parse_time(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
        fg=load(a.foreground) if a.foreground else None
        out=decision(state,fg,now,a.surface,a.heartbeat_max_minutes)
    print(json.dumps(out,sort_keys=True,separators=(',',':')))
    return 0
if __name__=='__main__': raise SystemExit(main())
