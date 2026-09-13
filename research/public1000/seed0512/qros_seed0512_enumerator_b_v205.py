import hashlib
axes={
 'asset':('XAUUSD','NQX'),'side':('SELL','BUY'),'tf':('H1','M30','M15','M5','M1'),
 'size':('1.50','1.25','1.00','0.75'),'max':('4','3','2'),
 'mem':('INSTANT_MULTILEVEL','CONSECUTIVE_SINGLE_STEP','PERSIST_SINGLE_STEP'),
 'pol':('SAME_SIDE','ABSOLUTE'),'vol':('SEQUENCE_START_ATR','CURRENT_BAR_ATR')
}
MGMTS=('M2_STRUCTURAL_SL_TP2R_EOD','M1_STRUCTURAL_SL_TP1R_EOD','M0_STRUCTURAL_SL_EOD')
def build(level, state, out):
    order=('asset','side','tf','size','max','mem','pol','vol')
    if level==len(order):
        out.add(f"{state['asset']}|{state['side']}|{state['tf']}|SIZE={state['size']}|MAX={state['max']}|MEM={state['mem']}|POL={state['pol']}|VOL={state['vol']}")
        return
    key=order[level]
    for value in axes[key]:
        state[key]=value
        build(level+1,state,out)
def signals():
    out=set(); build(0,{},out); return sorted(out)
def configs():
    out=set()
    for m in MGMTS:
        for s in signals():
            out.add(s+'|MGMT='+m)
    return sorted(out)
def digest(xs):
    h=hashlib.sha256()
    for x in xs: h.update((x+'\n').encode())
    return h.hexdigest()
if __name__=='__main__':
    s=signals(); c=configs()
    print(len(s),len(set(s)),digest(s))
    print(len(c),len(set(c)),digest(c))
