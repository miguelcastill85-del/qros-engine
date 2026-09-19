from qros_external_call_budget_guard_v2 import *
def expect(fn,msg):
    try:fn();raise AssertionError('expected '+msg)
    except GuardError as e:assert str(e)==msg,(str(e),msg)
def test():
    s=init_state('b','c');s=record(s,'launch',True)
    for _ in range(9):s=record(s,'status',True)
    assert decision(s,'status')=='STOP_CHECKPOINT_REQUIRED_AT_CALL_11'
    expect(lambda:record(s,'checkpoint',True,False),'CALL_11_MUST_DURABLY_PERSIST_OPEN_EXPENSIVE_UNIT')
    s=record(s,'checkpoint',True,True);assert not s['open_expensive_unit'] and s['last_durable_call']==11
    s2=init_state('b2','c');s2=record(s2,'launch',True);s2=record(s2,'persist',True,True)
    assert decision(s2,'launch')=='STOP_SECOND_EXPENSIVE_UNIT_IN_BLOCK'
    s3=init_state('b3','c');s3=record(s3,'launch',True)
    expect(lambda:record(s3,'status',True,True),'DURABLE_FLAG_REQUIRES_CHECKPOINT_OR_PERSIST')
    expect(lambda:close(s3),'CANNOT_CLOSE_WITH_UNPERSISTED_EXPENSIVE_UNIT')
    s4=init_state('b4','c')
    for _ in range(11):s4=record(s4,'status',True)
    assert decision(s4,'search')=='STOP_NEW_WORK_BUDGET_EXHAUSTED'
    for _ in range(4):s4=record(s4,'status',True)
    assert decision(s4,'status')=='STOP_HARD_CAP'
    return 12
if __name__=='__main__':print('PASS',test())
