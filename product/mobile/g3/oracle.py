"""Independent Python oracle for G3 synthetic exact quote mechanics.

This module does NOT infer signals, approve a scientific campaign, read broker
prices, compute historical profitability or authorize MT5 execution.
"""
from __future__ import annotations
from dataclasses import dataclass
import re
import sys

HEADER = 'QROS_G3_SYNTHETIC_TIMELINE_V1'
RESULT = 'QROS_G3_RESULTS_V1'
_ID = re.compile(r'[A-Za-z0-9_-]{1,32}\Z')
MAX_TICKS = 20_000
MAX_PLANS = 10_000
MAX_PRICE = 100_000_000

class InvalidTimeline(ValueError):
    pass

@dataclass(frozen=True)
class Tick:
    time: int
    bid: int
    ask: int
    bid_low: int
    bid_high: int
    ask_low: int
    ask_high: int
    session: int
    end: bool

@dataclass(frozen=True)
class Plan:
    name: str
    side: str
    signal: int
    entry: int
    stop: int
    target: int


def parse(raw: str) -> tuple[list[Tick], list[Plan]]:
    if not isinstance(raw, str) or '\r' in raw or len(raw)>4_000_000:
        raise InvalidTimeline('INPUT_ENCODING_OR_SIZE')
    lines=raw.splitlines()
    if not lines or lines[0] != HEADER:
        raise InvalidTimeline('HEADER')
    i=1
    def count(label: str, limit: int) -> int:
        nonlocal i
        if i>=len(lines) or not re.fullmatch(label+r'\|[1-9][0-9]*',lines[i]):
            raise InvalidTimeline('COUNT_'+label)
        n=int(lines[i].split('|')[1]);i+=1
        if not 1<=n<=limit:raise InvalidTimeline('COUNT_LIMIT_'+label)
        return n
    def number(v: str, lo: int, hi: int)->int:
        if not re.fullmatch(r'(0|[1-9][0-9]*)',v):
            raise InvalidTimeline('INTEGER_CANONICAL')
        x=int(v)
        if not lo<=x<=hi:raise InvalidTimeline('INTEGER_RANGE')
        return x
    n=count('TICKS',MAX_TICKS)
    ticks=[]
    for _ in range(n):
        if i>=len(lines):raise InvalidTimeline('TRUNCATED_TICKS')
        parts=lines[i].split('|');i+=1
        if len(parts)!=9:raise InvalidTimeline('TICK_FIELDS')
        t=number(parts[0],1,9_999_999_999_999)
        vals=[number(v,1,MAX_PRICE) for v in parts[1:7]]
        session=number(parts[7],1,9_999_999)
        end=number(parts[8],0,1)
        bid,ask,bl,bh,al,ah=vals
        if not(bl<=bid<=bh and al<=ask<=ah and ask>bid):
            raise InvalidTimeline('PRICE_OR_RANGE')
        if ticks:
            last=ticks[-1]
            if t<=last.time or session<last.session:
                raise InvalidTimeline('TEMPORAL_ORDER')
            if session!=last.session and not last.end:
                raise InvalidTimeline('UNSIGNALED_SESSION_BOUNDARY')
            if session==last.session and last.end:
                raise InvalidTimeline('SESSION_AFTER_END')
        ticks.append(Tick(t,bid,ask,bl,bh,al,ah,session,bool(end)))
    if not ticks[-1].end:raise InvalidTimeline('LAST_SESSION_NOT_CLOSED')
    m=count('PLANS',MAX_PLANS)
    plans=[]
    seen=set()
    for _ in range(m):
        if i>=len(lines):raise InvalidTimeline('TRUNCATED_PLANS')
        q=lines[i].split('|');i+=1
        if len(q)!=6:raise InvalidTimeline('PLAN_FIELDS')
        name,side=q[:2]
        if not _ID.fullmatch(name) or name in seen or side not in ('BUY','SELL'):
            raise InvalidTimeline('PLAN_ID_OR_SIDE')
        seen.add(name)
        signal=number(q[2],0,n-1)
        entry=number(q[3],0,n-1)
        stop=number(q[4],1,100_000)
        target=number(q[5],1,100_000)
        if signal>=entry or ticks[signal].session!=ticks[entry].session or ticks[entry].end:
            raise InvalidTimeline('LOOKAHEAD_OR_OVERNIGHT_ENTRY')
        plans.append(Plan(name,side,signal,entry,stop,target))
    if i!=len(lines)-1 or lines[-1]!='END':
        raise InvalidTimeline('TRAILING_DATA')
    return ticks,plans


def simulate(raw: str) -> str:
    ticks,plans=parse(raw)
    pending=sorted(plans,key=lambda p:(p.entry,p.name))
    results={}
    active=None
    entered_per_session={}
    just_exited=-1
    next_plan=0
    for ix,tick in enumerate(ticks):
        if active is not None:
            p,entry_idx,price,sl,tp=active
            if ix>entry_idx:
                if p.side=='BUY':
                    stop_hit=tick.bid_low<=sl
                    target_hit=tick.bid_high>=tp
                    if stop_hit:ex,reason=min(sl,tick.bid),'SL_FIRST'
                    elif target_hit:ex,reason=max(tp,tick.bid),'TP'
                    elif tick.end:ex,reason=tick.bid,'SESSION_CLOSE'
                    else:ex,reason=None,None
                else:
                    stop_hit=tick.ask_high>=sl
                    target_hit=tick.ask_low<=tp
                    if stop_hit:ex,reason=max(sl,tick.ask),'SL_FIRST'
                    elif target_hit:ex,reason=min(tp,tick.ask),'TP'
                    elif tick.end:ex,reason=tick.ask,'SESSION_CLOSE'
                    else:ex,reason=None,None
                if reason is not None:
                    results[p.name]=f'FILL|{p.name}|{p.side}|{entry_idx}|{price}|{sl}|{tp}|{ix}|{ex}|{reason}'
                    active=None
                    just_exited=ix
        while next_plan<len(pending) and pending[next_plan].entry==ix:
            p=pending[next_plan];next_plan+=1
            if tick.end:raise InvalidTimeline('ENTRY_ON_END_TICK')
            if active is not None:reason='POSITION_BUSY'
            elif just_exited==ix:reason='SAME_TICK_REENTRY'
            elif entered_per_session.get(tick.session,0)>=3:reason='DAILY_LIMIT'
            else:reason=None
            if reason is not None:
                results[p.name]=f'SKIP|{p.name}|{p.side}|{reason}'
                continue
            entry_price=tick.ask if p.side=='BUY' else tick.bid
            sl=entry_price-p.stop if p.side=='BUY' else entry_price+p.stop
            tp=entry_price+p.target if p.side=='BUY' else entry_price-p.target
            if sl<=0 or tp<=0:
                results[p.name]=f'SKIP|{p.name}|{p.side}|PRICE_LEVEL_INVALID'
                continue
            active=(p,ix,entry_price,sl,tp)
            entered_per_session[tick.session]=entered_per_session.get(tick.session,0)+1
    if active is not None:
        raise InvalidTimeline('UNCLOSED_POSITION')
    if len(results)!=len(plans):raise InvalidTimeline('UNRECORDED_PLAN')
    return RESULT+'\n'+'\n'.join(results[name] for name in sorted(results))+'\n'

if __name__=='__main__':
    try:sys.stdout.write(simulate(sys.stdin.read()))
    except InvalidTimeline as e:
        print('QROS_G3_REJECTED:'+str(e),file=sys.stderr)
        raise SystemExit(2)
