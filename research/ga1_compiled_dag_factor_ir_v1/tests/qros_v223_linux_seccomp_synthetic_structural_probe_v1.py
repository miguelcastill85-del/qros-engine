#!/usr/bin/env python3
"""Non-economic Linux-only canary of original V223 structural/tick/causal gates.

DO NOT call V223.process/main: these enumerate RETEST/rearm (quarantined).
The probe operates on generated, clearly SYNTHETIC 720-bar inputs, with
independent scalar oracles, and does not touch a real scientific shard.
"""
from __future__ import annotations
import hashlib, json, math, os, pathlib, shutil, signal, sys, tempfile

REPO=pathlib.Path(__file__).resolve().parents[3]
SRC=REPO/"scripts"
REF=REPO/"research/ga1_compiled_dag_factor_ir_v1"
PINNED_MAIN=REPO/"pinned-main"
SPEC=REPO/"research/public1000/seed0076/QROS_SEED0076_MACHINE_UNIVERSE_SPEC_V209_v1.json"
if not SPEC.is_file():raise RuntimeError("EXACT_FROZEN_V209_SPEC_REQUIRED")

def child():
    import numpy as np
    sys.path.insert(0,str(SRC))
    sys.path.insert(0,str(REF))
    from qros_seed0076_build_bar_cache_v220 import TICK_DTYPE,build_m1,aggregate_from_m1
    from qros_seed0076_indicators_v220 import compute_all
    from qros_seed0076_ga1_shard_worker_v223 import build_structural_cache,raw_cache_for
    from qros_seed0076_gate_engine_v221 import GateContext
    from qros_seed0076_carrier_masks_v221 import CarrierMaskEngine
    from qros_independent_event_canary import structural_states_scalar,tick_crosses_scalar
    with tempfile.TemporaryDirectory(prefix="qros-synthetic-no-economic-") as tmp:
        work=pathlib.Path(tmp);bd=work/"bars";id=work/"indicators";bd.mkdir();id.mkdir()
        n=720
        ticks=np.empty(n*4,dtype=TICK_DTYPE)
        for k in range(n):
            v=200000+round(220*math.sin(k/14.0))+round(57*math.sin(k/2.7))
            for j,delta in enumerate((-17,5,-8,19)):
                t=4*k+j
                ticks[t]=(1514851200000+k*120000+j*30000,v+delta,v+delta+3,0)
        tp=work/"SYNTHETIC_NOT_BROKER_PACKED17.bin"
        ticks.tofile(tp)
        bars=aggregate_from_m1(build_m1(tp,chunk_records=2017),"M2")
        if len(bars)!=n or int(bars["last_source_index"][-1])!=len(ticks)-1:
            raise RuntimeError("SYNTHETIC_BAR_COVERAGE_FAIL")
        np.save(bd/"NQX_M2_BID_BARS.npy",bars,allow_pickle=False)
        point=.1
        h=bars["high_bid"].astype(np.float64)*point
        l=bars["low_bid"].astype(np.float64)*point
        c=bars["close_bid"].astype(np.float64)*point
        ind=compute_all(h,l,c)
        completion=np.full(n,-1,dtype=np.int64)
        completion[:-1]=bars["first_source_index"][1:]
        ind["completion_source_index"]=completion
        np.savez(id/"NQX_M2_INDICATORS.npz",**ind)
        spec=json.loads(SPEC.read_text())
        hh,ll,cache=build_structural_cache(bars,point,spec)
        checks=0;event_counts={};gate_counts={}
        for w,tie in ((3,"STRICT_ALL_NEIGHBORS"),(5,"SOURCE_ASYMMETRIC")):
            st=cache[(w,tie)]
            refstates=structural_states_scalar(hh,ll,w,1 if tie=="STRICT_ALL_NEIGHBORS" else 0)
            for a,b in zip((st["sh"],st["sl"],st["hid"],st["lid"]),refstates):
                if not np.array_equal(a,b,equal_nan=True):
                    raise RuntimeError("FROZEN_STRUCTURAL_INDEPENDENT_ORACLE_MISMATCH:"+str((w,tie)))
                checks+=1
        st=cache[(3,"STRICT_ALL_NEIGHBORS")]
        ap=np.r_[np.nan,ind["ATR14"][:-1]]
        for side,side_name in ((1,"BUY"),(-1,"SELL")):
            level,lid,_,_,same,_=raw_cache_for(st,bars,ind,ticks,hh,ll,side,point,"TICK_BREAK")
            reference=tick_crosses_scalar(
                ticks["bid"],bars["first_source_index"],bars["last_source_index"],
                hh,ll,level,lid,ap,side,point)
            for channel,records in enumerate(same):
                idx,bar_idx,lev=records
                actual=[(int(i),int(b),int(z)) for i,b,z in zip(idx,bar_idx,lev)]
                if actual!=reference[channel]:
                    raise RuntimeError("FROZEN_TICK_INDEPENDENT_ORACLE_MISMATCH:"+side_name+":"+str(channel))
                checks+=1
            rawidx,rawbar,_=same[0]
            if len(rawidx)==0 or len(np.unique(rawidx))!=len(rawidx):
                raise RuntimeError("SYNTHETIC_NONZERO_UNIQUE_EVENT_REQUIRED:"+side_name)
            ctx=GateContext("NQX","M2",side_name,bd,id,point)
            eng=CarrierMaskEngine(ctx,rawidx,rawbar,st["sh"],st["sl"],st["boxhist"],ticks["ts"][rawidx])
            allidx=eng.selected_indices(eng.package({}))
            if not np.array_equal(allidx,rawidx):raise RuntimeError("EMPTY_GATE_IDENTITY_FAIL")
            checks+=1
            tr={"mode":"EMA_ORDER","ema_triple":[5,10,20]}
            gated=eng.selected_indices(eng.package({"TREND":tr}))
            prev=rawbar-1
            ok=prev>=0
            a=np.full(len(prev),np.nan);b=np.full(len(prev),np.nan);d=np.full(len(prev),np.nan)
            a[ok]=ind["EMA5"][prev[ok]]
            b[ok]=ind["EMA10"][prev[ok]]
            d[ok]=ind["EMA20"][prev[ok]]
            expected= (a>b)&(b>d) if side==1 else (a<b)&(b<d)
            if not np.array_equal(gated,rawidx[expected]):
                raise RuntimeError("INDEPENDENT_PREVIOUS_CLOSED_EMA_GATE_MISMATCH:"+side_name)
            checks+=1
            geom={"contraction_n":"OFF","max_box_atr":"2.00","max_midpoint_to_fast_ema_atr":"OFF"}
            combo=eng.selected_indices(eng.package({"TREND":tr,"GEOMETRY":geom}))
            atr=ap[rawbar]
            struct_ok=np.isfinite(st["sh"][rawbar])&np.isfinite(st["sl"][rawbar])
            geom_ok=struct_ok&(atr>0)&(
                np.abs(st["sh"][rawbar]-st["sl"][rawbar])/
                np.where(atr>0,atr,1.0)<=2.0)
            if not np.array_equal(combo,rawidx[expected&geom_ok]):
                raise RuntimeError("INDEPENDENT_STRUCTURAL_GEOMETRY_GATE_MISMATCH:"+side_name)
            checks+=1
            event_counts[side_name]=[int(len(records[0])) for records in same]
            gate_counts[side_name]={"all":int(len(rawidx)),"trend":int(len(gated)),"trend_plus_geometry":int(len(combo))}
        print("PASS_SYNTHETIC_FROZEN_V223_STRUCTURAL_TICK_GATE_UNDER_SECCOMP "+json.dumps({
            "source":"SYNTHETIC_NON_BROKER","bars":n,"ticks":len(ticks),
            "independent_checks":checks,"event_counts":event_counts,"gate_counts":gate_counts,
            "retest_rearm_executed":False,"ga1_shards_executed":0,
            "economic_pnl_read":False,"windows_tested":False},sort_keys=True),flush=True)

def parent():
    sys.path.insert(0,str(PINNED_MAIN/"anti_stall/scripts"))
    from qros_linux_seccomp_single_owner_v1 import launch,sha256_file
    frozen=PINNED_MAIN/"anti_stall/scripts/qros_linux_seccomp_single_process_launcher_v1.py"
    if not frozen.is_file():raise RuntimeError("PINNED_MAIN_HELPER_REQUIRED")
    with tempfile.TemporaryDirectory(prefix="qros-seccomp-v223-") as wd:
        root=pathlib.Path(wd)
        path=root/frozen.name
        shutil.copyfile(frozen,path)
        proc,proof=launch([sys.executable,str(pathlib.Path(__file__).resolve()),"--child"],
                           root,path.name,sha256_file(path),ready_budget=2.0)
        try:
            out,err=proc.communicate(timeout=200)
            if proc.returncode!=0:
                print(err.decode(errors="replace")[-6500:],file=sys.stderr)
                raise RuntimeError("SYNTHETIC_SECCOMP_WORKER_FAILED:"+str(proc.returncode))
            msg=out.decode(errors="replace")
            if "PASS_SYNTHETIC_FROZEN_V223_STRUCTURAL_TICK_GATE_UNDER_SECCOMP" not in msg:
                raise RuntimeError("SYNTHETIC_PROOF_MARKER_ABSENT:"+msg[-700:])
            if (proof["proc_seccomp"],proof["proc_no_new_privs"],proof["owns_process_group"])!=(2,1,True):
                raise RuntimeError("LINUX_KERNEL_ATTESTATION_FAILED")
            print(msg.strip())
            print("PASS_PARENT_PINNED_KERNEL_PROOF "+json.dumps(proof,sort_keys=True),flush=True)
        finally:
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            try:proc.wait(timeout=2)
            except Exception:proc.kill();proc.wait()
            for io in (proc.stdout,proc.stderr):
                if io and not io.closed:io.close()

if __name__=="__main__":
    if sys.argv[1:]==["--child"]:child()
    elif sys.argv[1:]==[]:parent()
    else:raise SystemExit("INVALID_SYNTHETIC_PROBE_MODE")
