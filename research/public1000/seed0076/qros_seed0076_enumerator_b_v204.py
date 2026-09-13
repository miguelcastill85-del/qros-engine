import hashlib
ASSETS=('NQX','XAUUSD'); SIDES=('BUY','SELL'); TFS=('M1','M5','M15','M30','H1'); TRIGGERS=('CLOSE_BREAK','TICK_BREAK'); MGMTS=('M0_STRUCTURAL_SL_EOD','M1_STRUCTURAL_SL_TP1R_EOD','M2_STRUCTURAL_SL_TP2R_EOD')
def branch_atoms():
    return [('B0','OFF',0)]+[('B1',s,0) for s in ('OFF','SIGN_ALIGNED')]+[('B2',s,c) for c in (1,2) for s in ('OFF','SIGN_ALIGNED')]
def enumerate_signals():
    return sorted(f'{b}|{a}|{d}|{tf}|{tr}|SLOPE={s}|CONTRACT={c}' for b,s,c in branch_atoms() for tf in TFS for d in SIDES for a in ASSETS for tr in TRIGGERS)
def enumerate_configs():
    out=[]
    for m in reversed(MGMTS):
        for s in reversed(enumerate_signals()): out.append(f'{s}|MGMT={m}')
    return sorted(out)
def digest(xs): return hashlib.sha256(('\n'.join(xs)+'\n').encode()).hexdigest()
if __name__=='__main__':
    s=enumerate_signals(); c=enumerate_configs(); print(len(s),digest(s)); print(len(c),digest(c))
