from itertools import product
import hashlib
ASSETS=['NQX','XAUUSD']; SIDES=['BUY','SELL']; TFS=['M1','M5','M15','M30','H1']; TRIGGERS=['CLOSE_BREAK','TICK_BREAK']; MGMTS=['M0_STRUCTURAL_SL_EOD','M1_STRUCTURAL_SL_TP1R_EOD','M2_STRUCTURAL_SL_TP2R_EOD']
def enumerate_signals():
    out=[]
    for asset,side,tf,trig in product(ASSETS,SIDES,TFS,TRIGGERS):
        out.append(f'B0|{asset}|{side}|{tf}|{trig}|SLOPE=OFF|CONTRACT=0')
        for slope in ['OFF','SIGN_ALIGNED']:
            out.append(f'B1|{asset}|{side}|{tf}|{trig}|SLOPE={slope}|CONTRACT=0')
            for c in [1,2]: out.append(f'B2|{asset}|{side}|{tf}|{trig}|SLOPE={slope}|CONTRACT={c}')
    return sorted(out)
def enumerate_configs(): return sorted(f'{s}|MGMT={m}' for s in enumerate_signals() for m in MGMTS)
def digest(xs): return hashlib.sha256(('\n'.join(xs)+'\n').encode()).hexdigest()
if __name__=='__main__':
    s=enumerate_signals(); c=enumerate_configs(); print(len(s),digest(s)); print(len(c),digest(c))
