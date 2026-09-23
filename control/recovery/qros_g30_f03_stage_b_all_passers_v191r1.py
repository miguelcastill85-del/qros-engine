#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, sys
from pathlib import Path
import numpy as np

STAGE_START = np.int64(1577836800000)
STAGE_END = np.int64(1640995200000)

PREFIX_AUTH = {
    "NQX": {
        "prefix_sha256": "d2530ae084311e0b454f30a5d7a2bc0d0f4ca932bb81d9dd2252ba7295491a05",
        "cache_sha256": "2bad94f5051c41f00a5e6fd9f39efa4278488f12b0b2f6d95737386cddecf598",
        "passers_total": 1069,
        "shards": {
            "H1_BID": (97,"97b57fadbb6fe1a4f4f9d6b376b9edaf89c01b022a428404b2bcd01d3918ca45"),
            "H1_MID": (95,"f18c31a6248a0fb6ae9d3a5621cae1f7460fcde9958bcf73a32159484d57d951"),
            "M30_BID": (44,"0e0988313984916df25ac421cac7407380101229118af741fdd88829bcb368d0"),
            "M30_MID": (41,"e7df0661f3f9cb87dfcdc2dfb4af0dfa4c99fa74e4da4e0424237ad4b8ebc66d"),
            "M15_BID": (143,"107d7ed9d76ca5c111e87fd6b037e69f22590d31897ba04aa777d976ca6ede77"),
            "M15_MID": (146,"924be2c8b1a1ae2549054b87024c5a6fbad3ae3faf565d14343dce730796b085"),
            "M10_BID": (185,"40118438ae626c4d2cd36685203929bc77d809681dfa31b933e3de39ebe37552"),
            "M10_MID": (223,"34a33fe6ac29faec3b0b556b30c94d2a743997521db3236339b03ef8ed0655e0"),
            "M5_BID": (42,"e176f3bd7047b91390290bb91d17b8693fb9419478464da9581f58cbb88ddb73"),
            "M5_MID": (53,"0f9eca2d8dc3dc8844c02c6331b33b790f8c37629ef602e9622582e7a23805b3"),
            "M1_BID": (0,"7fe8a5f01b46514097112ffd25b7e73b91cd4745a5a109f51c0f0466aeb40889"),
            "M1_MID": (0,"c27bde739d0bfe9d974ea3652dbe7b08485369a8c1ec72be38c6e9567efc1cad"),
        },
    },
    "XAUUSD": {
        "prefix_sha256": "77da8423b07d7d33168d8b713ef691627f0698760461c7349fa5ccc5e49ceaeb",
        "cache_sha256": "35abe473cfb9b02c51f525ccd3ef870bff51106005f94236e8197a9f4a2d8bfd",
        "passers_total": 859,
        "shards": {
            "H1_BID": (53,"cc1e969a57a0c9f926ae606dbf4eda98f3f6939ad3d00e0b7f1bd43c49f40d9b"),
            "H1_MID": (44,"70c6727474320826e117b1390a30899399c753468d3bd48d47caf308b7960266"),
            "M30_BID": (151,"bf4c889ce3a086c01241fb5e7b1b81f8ee9968dd6e0745e484b65e2d685fb5fe"),
            "M30_MID": (134,"c7ecf8dc0b13c47ee59d63c5f4d1666d9819d6d4faa601067dbe4f44148222b7"),
            "M15_BID": (147,"0901950729e66a08f8fdba16be625a5fb185ed400d714e570538658a6515fe1c"),
            "M15_MID": (109,"4ed34d51e7444b20664fb6463ef97d5d4767923b5c0b735a02b83993dbbd7c22"),
            "M10_BID": (85,"17c1141859a9515ab293f3db1e33ed5de258301bde98c4e1b9b928ae117418ca"),
            "M10_MID": (87,"480460341ad9d460c978b0e080f577a0e3ca1e111f327c88bca9f0b952f0b6ca"),
            "M5_BID": (24,"8ad1c3f562b42b4b42fd223a84bb8693611372396a3f3a2710cabc0c804d54b9"),
            "M5_MID": (25,"b90ea9cf61d56fd1f113377dff11a34a404f947d39150c9cb3f3c9e016222223"),
            "M1_BID": (0,"dca11a9d01f8dc04bc87a5190d0ab61906b439df9e56daf44a6467325753c313"),
            "M1_MID": (0,"bded588b1e4f513fda69b5952fdfe643aa7419f8986da476c0fdae11617108f1"),
        },
    },
}

def sha_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(8<<20),b""):
            h.update(b)
    return h.hexdigest()

def safe(v):
    if isinstance(v,float) and not math.isfinite(v):
        return "INF" if v>0 else ("-INF" if v<0 else "NAN")
    if isinstance(v,dict): return {k:safe(x) for k,x in v.items()}
    if isinstance(v,list): return [safe(x) for x in v]
    return v

def pf(a: np.ndarray) -> float:
    gp=float(a[a>0].sum()); gl=float(-a[a<0].sum())
    if gl==0: return float("inf") if gp>0 else 0.0
    return gp/gl

def parse_spec(key: str):
    parts=key.split("|")
    if len(parts)!=5 or not parts[0].startswith("ATR"):
        raise ValueError("BAD_F03_KEY "+key)
    p=int(parts[0][3:]); timing=parts[1]; thr=float(parts[2]); fam=parts[3]; n=int(parts[4])
    return p,timing,thr,fam,n

def ledger_sha(ch,et,xt,rr):
    h=hashlib.sha256()
    for q in ch:
        h.update(np.int64(et[q]).tobytes())
        h.update(np.int64(xt[q]).tobytes())
        h.update(np.float64(rr[q]).tobytes())
    return h.hexdigest()

def run(a):
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    import qros_g30_f03_gate_a_v97 as g
    import qros_g30_f03_signal_primary_v97 as sa
    import qros_g30_f03_signal_independent_v97 as sb
    import qros_g30_f03_execution_primary_v97 as ea
    import qros_g30_f03_execution_independent_fast_v99 as eb
    import qros_g30_f03_gate_a_fastscore_v101 as v101

    auth=PREFIX_AUTH[a.asset]
    shard=("H1" if a.tf==60 else f"M{a.tf}")+"_"+a.feature_side
    if shard not in auth["shards"]: raise SystemExit("UNAUTHORIZED_SHARD")
    expected_passers,expected_gate_sha=auth["shards"][shard]
    if sha_file(a.prefix)!=auth["prefix_sha256"]: raise SystemExit("PREFIX_SHA_MISMATCH")
    if sha_file(a.cache)!=auth["cache_sha256"]: raise SystemExit("PREFIX_CACHE_SHA_MISMATCH")
    if sha_file(a.gate_a_result)!=expected_gate_sha: raise SystemExit("GATE_A_RESULT_SHA_MISMATCH")

    dev=json.loads(a.gate_a_result.read_text(encoding="utf-8"))
    if dev.get("asset")!=a.asset or dev.get("shard")!=shard or dev.get("status")!="PASS":
        raise SystemExit("GATE_A_RESULT_IDENTITY_MISMATCH")
    passers=dev.get("passers")
    if not isinstance(passers,list) or len(passers)!=expected_passers or dev.get("passed")!=expected_passers:
        raise SystemExit("GATE_A_PASSER_COUNT_MISMATCH")

    if expected_passers==0:
        obj={"schema":"QROS_G30_F03_STAGE_B_ALL_PASSERS_SHARD_V191R1_v1","campaign":"QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1",
             "frontier":"F03_ATR_PERIOD","asset":a.asset,"shard":shard,"stage":"G30-OBS-STAGE-B-2020_2021",
             "gate_a_result_sha256":expected_gate_sha,"gate_a_passers_in":0,"evaluated":0,"passed":0,"rejected":0,
             "parity":"PASS_VACUOUS","records":[],"2022_plus_pnl_read":False,"retuning":False,"status":"PASS"}
        a.out.write_text(json.dumps(obj,separators=(",",":"),sort_keys=True),encoding="utf-8")
        print(json.dumps({"asset":a.asset,"shard":shard,"evaluated":0,"passed":0,"parity":"PASS_VACUOUS"},sort_keys=True))
        return

    mm=np.memmap(a.prefix,dtype=g.DT,mode="r")
    with np.load(a.cache) as z:
        mb=z["mb"]; ks=("bo","bh","bl","bc") if a.feature_side=="BID" else ("mo","mh","ml","mc"); vals=[z[k] for k in ks]
        A=sa.bars(mb,*vals,a.tf); B=sb.bars(mb,*vals,a.tf)
        if g.digest_arrays(A)!=g.digest_arrays(B): raise SystemExit("BAR_PARITY_FAIL")
        pa=sa.prepare(*A); pb=sb.prepare(*B)
        atrA=sa.atr(A[2],A[3],A[4],14); atrB=sb.atr(B[2],B[3],B[4],14)
        if not np.array_equal(np.nan_to_num(atrA,nan=-1.0),np.nan_to_num(atrB,nan=-1.0)):
            raise SystemExit("MANAGEMENT_ATR14_PARITY_FAIL")
        uB=np.zeros(len(A[0]),bool); uS=np.zeros(len(A[0]),bool); masks={}
        for rec in passers:
            key=rec["id"]; side=rec["side"]; sp=parse_spec(key)
            bA,sA=sa.mask(pa,*A[1:],*sp); bB,sB=sb.mask(pb,*B[1:],*sp)
            if not np.array_equal(bA,bB) or not np.array_equal(sA,sB): raise SystemExit("SIGNAL_PARITY_FAIL "+key)
            mA=bA if side=="BUY" else sA; mB=bB if side=="BUY" else sB
            if not np.array_equal(mA,mB): raise SystemExit("SIDE_MASK_PARITY_FAIL "+key+" "+side)
            masks[(key,side)]=mA
            if side=="BUY": uB|=mA
            elif side=="SELL": uS|=mA
            else: raise SystemExit("BAD_SIDE")
        ex=[z[k] for k in ("eb","ebh","ebl","eah","eal","first","last")]; step=a.tf*60000
        outcomes={}
        for side,u,code in (("BUY",uB,1),("SELL",uS,-1)):
            if not u.any(): continue
            OA=ea.outcome(mm["ts"],mm["bid"],mm["ask"],A[0],atrA,step,*ex,u,code)
            OB=eb.outcome_core(mm["ts"],mm["bid"],mm["ask"],B[0],atrB,step,*ex,u,code)
            q=np.flatnonzero(u)
            for k in range(6):
                if not np.array_equal(OA[k][q],OB[k][q]): raise SystemExit("RAW_OUTCOME_PARITY_FAIL "+side+" "+str(k))
            outcomes[side]=(OA,OB)

        stage_bar=((A[0]+step)>=STAGE_START)&((A[0]+step)<STAGE_END)
        records=[]
        for rec in passers:
            key=rec["id"]; side=rec["side"]; mask=masks[(key,side)]&stage_bar; OA,OB=outcomes[side]
            ids=np.flatnonzero(mask).astype(np.int64)
            chA=v101.select_idx_A(ids,OA[0],OA[1]); chB=v101.select_idx_B(ids,OB[0],OB[1])
            if not np.array_equal(chA,chB): raise SystemExit("SELECT_PARITY_FAIL "+key+" "+side)
            for k in range(6):
                if not np.array_equal(OA[k][chA],OB[k][chB]): raise SystemExit("TRADE_PARITY_FAIL "+key+" "+side+" "+str(k))
            rr=OA[5][chA].astype(float); ei=OA[2][chA]; xi=OA[3][chA]; dist=OA[4][chA]; et=OA[0][chA]
            if len(chA):
                spread=(mm["ask"][ei]-mm["bid"][ei]).astype(float)+(mm["ask"][xi]-mm["bid"][xi]).astype(float)
                extra=np.divide(spread,dist,out=np.zeros(len(spread)),where=dist>0)
                cons=rr-0.5*extra; sev=rr-extra
            else:
                cons=rr.copy(); sev=rr.copy()
            r20=float(rr[et<1609459200000].sum()); r21=float(rr[et>=1609459200000].sum())
            pfc=pf(rr); pfk=pf(cons); pfs=pf(sev)
            passed=len(chA)>=20 and pfc>=1.20 and pfk>=1.10 and pfs>=1.00 and rr.sum()>0 and cons.sum()>0 and sev.sum()>0 and r20>0 and r21>0
            stable=f"{shard}:{side}:{key}"
            records.append({"stable_id":stable,"dev_signal_sha256":rec.get("signal_sha256"),"aliases":rec.get("aliases",[]),"side":side,
                            "n":int(len(chA)),"net_c":float(rr.sum()),"net_k":float(cons.sum()),"net_s":float(sev.sum()),
                            "pf_c":pfc,"pf_k":pfk,"pf_s":pfs,"r2020":r20,"r2021":r21,
                            "ledger_sha256":ledger_sha(chA,OA[0],OA[1],OA[5]),"pass":bool(passed)})
    obj={"schema":"QROS_G30_F03_STAGE_B_ALL_PASSERS_SHARD_V191R1_v1","campaign":"QROS_G30_PUBLIC_VOLATILITY_SHOCK_MOMENTUM_v1",
         "frontier":"F03_ATR_PERIOD","asset":a.asset,"shard":shard,"stage":"G30-OBS-STAGE-B-2020_2021",
         "gate_a_result_sha256":expected_gate_sha,"gate_a_passers_in":expected_passers,"evaluated":len(records),
         "passed":sum(x["pass"] for x in records),"rejected":sum(not x["pass"] for x in records),
         "passed_buy":sum(x["pass"] and x["side"]=="BUY" for x in records),
         "passed_sell":sum(x["pass"] and x["side"]=="SELL" for x in records),
         "parity":"PASS_EXACT","gate":{"min_trades":20,"pf_central_min":1.20,"pf_conservative_min":1.10,"pf_severe_min":1.00,
         "net_positive_all_costs":True,"positive_full_years_central":[2020,2021]},
         "stage_membership":"CAUSAL_SIGNAL_CLOSE; PROVEN_EQUIVALENT_TO_ENTRY_TIME_UNDER_SAME_DAY_CONTRACT",
         "records":records,"2022_plus_pnl_read":False,"retuning":False,"status":"PASS"}
    a.out.write_text(json.dumps(safe(obj),separators=(",",":"),allow_nan=False),encoding="utf-8")
    print(json.dumps({"asset":a.asset,"shard":shard,"evaluated":len(records),"passed":obj["passed"],
                      "passed_buy":obj["passed_buy"],"passed_sell":obj["passed_sell"],"parity":obj["parity"],
                      "sha256":sha_file(a.out)},sort_keys=True))

def selftest():
    if parse_spec("ATR28|LAGGED_ONE_BAR_PRE_SHOCK|2.5|STRICT_MONOTONIC_N_CLOSE_SEQUENCE|4")!=(28,"LAGGED_ONE_BAR_PRE_SHOCK",2.5,"STRICT_MONOTONIC_N_CLOSE_SEQUENCE",4):
        raise SystemExit("SELFTEST_PARSE_FAIL")
    if abs(pf(np.array([2.0,-1.0,1.0,-1.0]))-1.5)>1e-12: raise SystemExit("SELFTEST_PF_FAIL")
    if sum(v[0] for v in PREFIX_AUTH["NQX"]["shards"].values())!=1069: raise SystemExit("SELFTEST_NQX_COUNT_FAIL")
    if sum(v[0] for v in PREFIX_AUTH["XAUUSD"]["shards"].values())!=859: raise SystemExit("SELFTEST_XAU_COUNT_FAIL")
    print(json.dumps({"schema":"QROS_G30_F03_STAGE_B_ALL_PASSERS_V191R1_SELFTEST_v1","tests":4,"passed":4,"status":"PASS"}))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--asset",choices=["NQX","XAUUSD"])
    ap.add_argument("--prefix",type=Path); ap.add_argument("--cache",type=Path); ap.add_argument("--gate-a-result",type=Path)
    ap.add_argument("--tf",type=int,choices=[1,5,10,15,30,60]); ap.add_argument("--feature-side",choices=["BID","MID"])
    ap.add_argument("--out",type=Path)
    a=ap.parse_args()
    if a.selftest: selftest(); return
    if any(x is None for x in (a.asset,a.prefix,a.cache,a.gate_a_result,a.tf,a.feature_side,a.out)):
        raise SystemExit("ALL_RUNTIME_ARGUMENTS_REQUIRED")
    run(a)

if __name__=="__main__":
    main()
