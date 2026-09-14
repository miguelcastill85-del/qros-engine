from pathlib import Path
import sys, pandas as pd, numpy as np, json

ROOT=Path(__file__).resolve().parent
REF=ROOT/"IPS_V2_MT5_PARITY_REFERENCE_EVENTS_v1.csv"
START=1609459200000
END=1660521600000
FLOAT_TOL=1e-8

if len(sys.argv)!=2:
    raise SystemExit("usage: python compare_mt5_parity_v1.py <MT5_exported_csv>")

cand_path=Path(sys.argv[1])
ref=pd.read_csv(REF)
cand=pd.read_csv(cand_path,sep=";")
cand=cand[(cand.entry_ts>=START)&(cand.entry_ts<END)].copy().reset_index(drop=True)
ref=ref.reset_index(drop=True)
required=list(ref.columns)
missing=[c for c in required if c not in cand.columns]
if missing:
    raise SystemExit("PARITY_FAIL missing columns: "+",".join(missing))
cand=cand[required]
result={"reference_events":len(ref),"mt5_events":len(cand),"mismatches":{},"max_abs_error":{}}
if len(ref)!=len(cand):
    result["decision"]="FAIL"
    print(json.dumps(result,indent=2))
    raise SystemExit(2)
string_cols=["side"]
int_cols=["entry_ts","obs_start_ts","pullback_extreme_ts","reaccel_ts","impulse_open","impulse_high","impulse_low","impulse_close","pullback_extreme","entry_bid","entry_ask","spread_cents","spread_p50_cents","eligible"]
float_cols=["atr_cents","body_atr","body_to_range","retracement","disp_q","eff_q","pullback_q","recovery_q","micro_q","spread_q","score_v2","stop_cents","target_cents","risk_cents"]
total=0
for c in string_cols:
    mis=int(np.sum(ref[c].astype(str).to_numpy()!=cand[c].astype(str).to_numpy()))
    result["mismatches"][c]=mis; total+=mis
for c in int_cols:
    a=pd.to_numeric(ref[c]).to_numpy(np.int64); b=pd.to_numeric(cand[c]).to_numpy(np.int64)
    mis=int(np.sum(a!=b)); result["mismatches"][c]=mis; total+=mis
for c in float_cols:
    a=pd.to_numeric(ref[c]).to_numpy(float); b=pd.to_numeric(cand[c]).to_numpy(float)
    d=np.abs(a-b); mx=float(np.nanmax(d)) if len(d) else 0.0
    mis=int(np.sum(d>FLOAT_TOL)); result["mismatches"][c]=mis; result["max_abs_error"][c]=mx; total+=mis
result["total_field_mismatches"]=total
result["float_tolerance"]=FLOAT_TOL
result["decision"]="PASS" if total==0 else "FAIL"
print(json.dumps(result,indent=2))
raise SystemExit(0 if total==0 else 3)
