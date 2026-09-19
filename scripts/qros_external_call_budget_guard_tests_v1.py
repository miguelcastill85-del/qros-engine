#!/usr/bin/env python3
import importlib.util
from pathlib import Path
P=Path(__file__).with_name('qros_external_call_budget_guard_v1.py')
s=importlib.util.spec_from_file_location('g',P); g=importlib.util.module_from_spec(s); s.loader.exec_module(g)
def fresh(): return g.init_state('T','cp')
checks=[]
for used in range(0,10):
    st=fresh(); st['calls_used']=used; checks.append(g.decision(st,'search')=='ALLOW')
st=fresh(); st['calls_used']=10; checks.append(g.decision(st,'search')=='STOP_NEW_WORK_BUDGET_EXHAUSTED')
st=fresh(); st['calls_used']=10; checks.append(g.decision(st,'checkpoint')=='ALLOW')
st=fresh(); st['calls_used']=11; checks.append(g.decision(st,'checkpoint')=='STOP_CHECKPOINT_TOO_LATE')
st=fresh(); st['calls_used']=11; checks.append(g.decision(st,'validate')=='ALLOW'); checks.append(g.decision(st,'search')=='STOP_NEW_WORK_BUDGET_EXHAUSTED')
st=fresh(); st['calls_used']=15; checks.append(g.decision(st,'validate')=='STOP_HARD_CAP')
st=fresh(); st['open_expensive_unit']=True; checks.append(g.decision(st,'launch')=='STOP_EXPENSIVE_UNIT_ALREADY_OPEN')
st=fresh(); st['open_expensive_unit']=True
try: g.close(st); checks.append(False)
except g.GuardError: checks.append(True)
st=fresh(); st=g.record(st,'launch',True); st=g.record(st,'persist',True,True); checks.append(st['open_expensive_unit'] is False and st['checkpoint_persisted'] is True); checks.append(g.close(st)['status']=='CLOSED')
print({'tests':len(checks),'passed':sum(checks),'status':'PASS' if all(checks) else 'FAIL'})
raise SystemExit(0 if all(checks) else 2)
