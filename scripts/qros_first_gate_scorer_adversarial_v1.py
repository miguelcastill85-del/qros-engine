#!/usr/bin/env python3
import copy, hashlib, json, subprocess, sys, tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIMARY = ROOT / "scripts/qros_first_gate_scorer_primary_v1.py"
ORACLE = ROOT / "scripts/qros_first_gate_scorer_oracle_v1.py"
CONTRACT_BLOB = "bc7f859c31f7de0584b8abecbe22641fdac2ceab"
MULT_BLOB = "bc5ce2b52ca5734328283fb3c1d67ee1d93905c1"
EMPTY_SHA = hashlib.sha256(b"").hexdigest()

def canon(o): return json.dumps(o, sort_keys=True, separators=(",",":"), ensure_ascii=False)
def mask(name): return hashlib.sha256(name.encode()).hexdigest()

def axis(n=80):
    start=date(2030,1,1)
    return [(start+timedelta(days=i)).isoformat() for i in range(n)]

def base_manifest(count=5):
    return {"schema":"QROS_FIRST_GATE_NORMALIZED_INPUT_1.0","mode":"SYNTHETIC_VALIDATION","synthetic_fixture":True,
            "campaign":"PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA","asset":"XAUUSD","side":"BUY","timeframe":"M1",
            "shard_id":"aa2e1ab0ecd6cd08d18e98288e70847d6ff863c6790f0928b9109138abe24070","first_gate_order":1,
            "expected_distinct_mask_classes":count,"per_shard_q_exact":"1/1200",
            "multiplicity_contract_git_blob_sha1":MULT_BLOB,"scorer_contract_git_blob_sha1":CONTRACT_BLOB,
            "semantic_class_root_sha256":"cf28be12f7dd94a9551fe018a4679d129d4373e6e186e17ef628f418d9b91ce4",
            "alias_root_sha256":"4151cccd363d4d71b29d123952dc5c4dd355fb2ea27806c09cb16a5cf3c1d458"}

def candidate(cid, name, dates, values, eligible=None):
    trades=[{"trade_id":f"{cid}-T{i:03d}","trading_date":dates[i],"R":str(v)} for i,v in enumerate(values)]
    return {"canonical_signal_config_id":cid,"event_mask_sha256":mask(name),"eligible_event_count":eligible if eligible is not None else max(1,len(values)),"zero_event":False,"trades":trades}

def fixture():
    d=axis()
    a=["1.0" if i%2==0 else "1.2" for i in range(60)]
    e=["0.8" if i%2==0 else "1.1" for i in range(60)]
    b=["0.1" if i%3==0 else "-0.25" for i in range(60)]
    c=["0.5"]*10
    rows=[candidate("A_STRONG","A",d,a), candidate("B_NEGATIVE","B",d,b), candidate("C_INSUFFICIENT","C",d,c),
          {"canonical_signal_config_id":"D_ZERO","event_mask_sha256":EMPTY_SHA,"eligible_event_count":0,"zero_event":True,"trades":[]},
          candidate("E_STRONG","E",d,e)]
    return base_manifest(len(rows)),d,rows

def write_bundle(root,m,d,rows):
    root.mkdir(parents=True,exist_ok=True)
    (root/"manifest.json").write_text(canon(m)+"\n")
    (root/"date_axis.json").write_text(canon(d)+"\n")
    (root/"candidates.jsonl").write_text("".join(canon(r)+"\n" for r in rows))

def run(script,inp,out):
    p=subprocess.run([sys.executable,str(script),"--input",str(inp),"--output",str(out)],text=True,capture_output=True)
    try: payload=json.loads(p.stdout.strip().splitlines()[-1])
    except Exception: payload={"status":"UNPARSEABLE","stdout":p.stdout,"stderr":p.stderr}
    return p.returncode,payload

def assert_both_fail(tmp,m,d,rows,code):
    inp=tmp/"in"; write_bundle(inp,m,d,rows)
    for tag,script in (("p",PRIMARY),("o",ORACLE)):
        rc,pay=run(script,inp,tmp/tag)
        assert rc==2,(code,tag,rc,pay)
        assert pay.get("status")=="FAIL_CLOSED",(code,tag,pay)
        assert pay.get("error")==code,(code,tag,pay)

def main():
    assert PRIMARY.read_bytes()!=ORACLE.read_bytes()
    assert "qros_first_gate_scorer_oracle" not in PRIMARY.read_text()
    assert "qros_first_gate_scorer_primary" not in ORACLE.read_text()
    checks=[]
    with tempfile.TemporaryDirectory() as td:
        t=Path(td); m,d,rows=fixture(); inp=t/"base"; write_bundle(inp,m,d,rows)
        rc1,p1=run(PRIMARY,inp,t/"primary"); rc2,p2=run(ORACLE,inp,t/"oracle")
        assert rc1==0 and rc2==0,(p1,p2)
        assert (t/"primary/candidate_results.jsonl").read_bytes()==(t/"oracle/candidate_results.jsonl").read_bytes()
        assert (t/"primary/summary.json").read_bytes()==(t/"oracle/summary.json").read_bytes()
        s=json.loads((t/"primary/summary.json").read_text())
        assert s["mode"]=="SYNTHETIC_VALIDATION" and s["economic_decision_authorized"] is False
        results=[json.loads(x) for x in (t/"primary/candidate_results.jsonl").read_text().splitlines()]
        byid={r["canonical_signal_config_id"]:r for r in results}
        assert byid["C_INSUFFICIENT"]["raw_p"]=="1.0" and not byid["C_INSUFFICIENT"]["BY_rejected"]
        assert byid["D_ZERO"]["raw_p"]=="1.0" and not byid["D_ZERO"]["survives_first_gate"]
        checks.append("PRIMARY_ORACLE_BYTE_PARITY")
        checks.append("SYNTHETIC_CANNOT_AUTHORIZE_ECONOMIC_DECISION")
        checks.append("ZERO_AND_INSUFFICIENT_P1")

        # HAC degenerate: 30 identical daily positive observations => SE<=0 => p=1.
        md=base_manifest(1); rd=[candidate("DEGENERATE","DG",d,["1"]*30)]
        idg=t/"deg"; write_bundle(idg,md,d,rd)
        for tag,script in (("dp",PRIMARY),("do",ORACLE)):
            rc,p=run(script,idg,t/tag); assert rc==0,p
            r=json.loads((t/tag/"candidate_results.jsonl").read_text())
            assert r["raw_p"]=="1.0" and not r["survives_first_gate"]
        checks.append("DEGENERATE_HAC_P1")

        # Fail-closed mutation matrix. Each mutation must fail for the intended reason in both implementations.
        mm,dd,rr=fixture(); rr=copy.deepcopy(rr); rr[1]["canonical_signal_config_id"]=rr[0]["canonical_signal_config_id"]
        assert_both_fail(t/"dup_id",mm,dd,rr,"DUPLICATE_CANDIDATE_ID"); checks.append("DUPLICATE_ID_FAIL_CLOSED")
        mm,dd,rr=fixture(); rr=copy.deepcopy(rr); rr[1]["event_mask_sha256"]=rr[0]["event_mask_sha256"]
        assert_both_fail(t/"dup_mask",mm,dd,rr,"DUPLICATE_MASK_SHA"); checks.append("DUPLICATE_MASK_FAIL_CLOSED")
        mm,dd,rr=fixture(); bad=list(dd); bad[0],bad[1]=bad[1],bad[0]
        assert_both_fail(t/"axis",mm,bad,rr,"DATE_AXIS_NOT_SORTED_UNIQUE"); checks.append("AXIS_FAIL_CLOSED")
        mm,dd,rr=fixture(); rr=copy.deepcopy(rr); rr[3]["eligible_event_count"]=1
        assert_both_fail(t/"zero",mm,dd,rr,"ZERO_EVENT_INCONSISTENT"); checks.append("ZERO_FAIL_CLOSED")
        mm,dd,rr=fixture(); rr=copy.deepcopy(rr); rr[0]["trades"][0]["trading_date"]="2099-01-01"
        assert_both_fail(t/"outside",mm,dd,rr,"TRADE_DATE_OUTSIDE_AXIS"); checks.append("DATE_OUTSIDE_FAIL_CLOSED")
        mm,dd,rr=fixture(); rr=copy.deepcopy(rr); rr[0]["trades"][1]["trade_id"]=rr[0]["trades"][0]["trade_id"]
        assert_both_fail(t/"dup_trade",mm,dd,rr,"DUPLICATE_TRADE_ID"); checks.append("DUPLICATE_TRADE_FAIL_CLOSED")
        mm,dd,rr=fixture(); rr=copy.deepcopy(rr); rr[0]["trades"][0]["R"]="NaN"
        assert_both_fail(t/"nan",mm,dd,rr,"NONFINITE_R"); checks.append("NONFINITE_R_FAIL_CLOSED")
        mm,dd,rr=fixture(); mm=copy.deepcopy(mm); mm["expected_distinct_mask_classes"]+=1
        assert_both_fail(t/"count",mm,dd,rr,"CANDIDATE_COUNT_MISMATCH"); checks.append("COUNT_FAIL_CLOSED")
        mm,dd,rr=fixture(); mm=copy.deepcopy(mm); mm["scorer_contract_git_blob_sha1"]="0"*40
        assert_both_fail(t/"contract",mm,dd,rr,"SCORER_CONTRACT_BLOB_MISMATCH"); checks.append("CONTRACT_PIN_FAIL_CLOSED")
        mm,dd,rr=fixture(); mm=copy.deepcopy(mm); mm["mode"]="PRODUCTION"; mm.pop("synthetic_fixture",None)
        assert_both_fail(t/"prod",mm,dd,rr,"EXECUTION_PARITY_REQUIRED"); checks.append("PRODUCTION_PARITY_LATCH_FAIL_CLOSED")

        primary_hash=hashlib.sha256((t/"primary/candidate_results.jsonl").read_bytes()).hexdigest()
        summary_hash=hashlib.sha256((t/"primary/summary.json").read_bytes()).hexdigest()
    receipt={"schema":"QROS_FIRST_GATE_SCORER_ADVERSARIAL_RECEIPT_1.0","status":"PASS",
             "check_count":len(checks),"checks":checks,"synthetic_only":True,"economic_pnl_read":False,
             "primary_oracle_candidate_results_sha256":primary_hash,"primary_oracle_summary_sha256":summary_hash}
    raw=canon(receipt).encode(); receipt["receipt_sha256"]=hashlib.sha256(raw).hexdigest()
    print(canon(receipt))

if __name__=="__main__":
    main()
