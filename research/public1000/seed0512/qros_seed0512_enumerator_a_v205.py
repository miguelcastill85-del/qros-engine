from itertools import product
import hashlib
ASSETS=['NQX','XAUUSD']; SIDES=['BUY','SELL']; TFS=['M1','M5','M15','M30','H1']
SIZES=['0.75','1.00','1.25','1.50']; MAXES=['2','3','4']
MEMS=['PERSIST_SINGLE_STEP','CONSECUTIVE_SINGLE_STEP','INSTANT_MULTILEVEL']
POLS=['ABSOLUTE','SAME_SIDE']; VOLS=['CURRENT_BAR_ATR','SEQUENCE_START_ATR']
MGMTS=['M0_STRUCTURAL_SL_EOD','M1_STRUCTURAL_SL_TP1R_EOD','M2_STRUCTURAL_SL_TP2R_EOD']
def signals():
    return sorted(f'{a}|{d}|{tf}|SIZE={z}|MAX={mx}|MEM={mem}|POL={pol}|VOL={vol}'
                  for a,d,tf,z,mx,mem,pol,vol in product(ASSETS,SIDES,TFS,SIZES,MAXES,MEMS,POLS,VOLS))
def configs():
    return sorted(f'{s}|MGMT={m}' for s in signals() for m in MGMTS)
def digest(xs):
    return hashlib.sha256(('\n'.join(xs)+'\n').encode()).hexdigest()
if __name__=='__main__':
    s=signals(); c=configs()
    print(len(s),len(set(s)),digest(s))
    print(len(c),len(set(c)),digest(c))
