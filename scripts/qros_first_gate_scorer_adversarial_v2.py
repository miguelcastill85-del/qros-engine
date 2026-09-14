#!/usr/bin/env python3
import copy, hashlib, json, tempfile
from pathlib import Path
import qros_first_gate_scorer_adversarial_v1 as H


def main():
    assert H.PRIMARY.read_bytes() != H.ORACLE.read_bytes()
    assert "qros_first_gate_scorer_oracle" not in H.PRIMARY.read_text()
    assert "qros_first_gate_scorer_primary" not in H.ORACLE.read_text()
    checks=[]
    with tempfile.TemporaryDirectory() as td:
        t=Path(td); m,d,rows=H.fixture(); inp=t/"base"; H.write_bundle(inp,m,d,rows)
        rc1,p1=H.run(H.PRIMARY,inp,t/"primary"); rc2,p2=H.run(H.ORACLE,inp,t/"oracle")
        assert rc1==0 and rc2==0,(p1,p2)
        assert (t/"primary/candidate_results.jsonl").read_bytes()==(t/"oracle/candidate_results.jsonl").read_bytes()
        assert (t/"primary/summary.json").read_bytes()==(t/"oracle/summary.json").read_bytes()
        s=json.loads((t/"primary/summary.json").read_text())
        assert s["mode"]=="SYNTHETIC_VALIDATION" and s["economic_decision_authorized"] is False
        results=[json.loads(x) for x in (t/"primary/candidate_results.jsonl").read_text().splitlines()]
        byid={r["canonical_signal_config_id"]:r for r in results}
        assert byid["C_INSUFFICIENT"]["raw_p"]=="1.0" and not byid["C_INSUFFICIENT"]["BY_rejected"]
        assert byid["D_ZERO"]["raw_p"]=="1.0" and not byid["D_ZERO"]["survives_first_gate"]
        checks += ["PRIMARY_ORACLE_BYTE_PARITY","SYNTHETIC_CANNOT_AUTHORIZE_ECONOMIC_DECISION","ZERO_AND_INSUFFICIENT_P1"]

        # Correct degenerate HAC fixture: every eligible synthetic date has identical daily_R=+1.
        # Therefore there are no zero no-trade dates and the full daily series is constant.
        md=H.base_manifest(1)
        rd=[H.candidate("DEGENERATE","DG",d,["1"]*len(d),eligible=len(d))]
        idg=t/"deg"; H.write_bundle(idg,md,d,rd)
        for tag,script in (("dp",H.PRIMARY),("do",H.ORACLE)):
            rc,p=H.run(script,idg,t/tag); assert rc==0,p
            r=json.loads((t/tag/"candidate_results.jsonl").read_text())
            assert r["raw_p"]=="1.0" and r["HAC_t"] is None and not r["survives_first_gate"], r
        checks.append("DEGENERATE_FULL_AXIS_HAC_P1")

        mm,dd,rr=H.fixture(); rr=copy.deepcopy(rr); rr[1]["canonical_signal_config_id"]=rr[0]["canonical_signal_config_id"]
        H.assert_both_fail(t/"dup_id",mm,dd,rr,"DUPLICATE_CANDIDATE_ID"); checks.append("DUPLICATE_ID_FAIL_CLOSED")
        mm,dd,rr=H.fixture(); rr=copy.deepcopy(rr); rr[1]["event_mask_sha256"]=rr[0]["event_mask_sha256"]
        H.assert_both_fail(t/"dup_mask",mm,dd,rr,"DUPLICATE_MASK_SHA"); checks.append("DUPLICATE_MASK_FAIL_CLOSED")
        mm,dd,rr=H.fixture(); bad=list(dd); bad[0],bad[1]=bad[1],bad[0]
        H.assert_both_fail(t/"axis",mm,bad,rr,"DATE_AXIS_NOT_SORTED_UNIQUE"); checks.append("AXIS_FAIL_CLOSED")
        mm,dd,rr=H.fixture(); rr=copy.deepcopy(rr); rr[3]["eligible_event_count"]=1
        H.assert_both_fail(t/"zero",mm,dd,rr,"ZERO_EVENT_INCONSISTENT"); checks.append("ZERO_FAIL_CLOSED")
        mm,dd,rr=H.fixture(); rr=copy.deepcopy(rr); rr[0]["trades"][0]["trading_date"]="2099-01-01"
        H.assert_both_fail(t/"outside",mm,dd,rr,"TRADE_DATE_OUTSIDE_AXIS"); checks.append("DATE_OUTSIDE_FAIL_CLOSED")
        mm,dd,rr=H.fixture(); rr=copy.deepcopy(rr); rr[0]["trades"][1]["trade_id"]=rr[0]["trades"][0]["trade_id"]
        H.assert_both_fail(t/"dup_trade",mm,dd,rr,"DUPLICATE_TRADE_ID"); checks.append("DUPLICATE_TRADE_FAIL_CLOSED")
        mm,dd,rr=H.fixture(); rr=copy.deepcopy(rr); rr[0]["trades"][0]["R"]="NaN"
        H.assert_both_fail(t/"nan",mm,dd,rr,"NONFINITE_R"); checks.append("NONFINITE_R_FAIL_CLOSED")
        mm,dd,rr=H.fixture(); mm=copy.deepcopy(mm); mm["expected_distinct_mask_classes"]+=1
        H.assert_both_fail(t/"count",mm,dd,rr,"CANDIDATE_COUNT_MISMATCH"); checks.append("COUNT_FAIL_CLOSED")
        mm,dd,rr=H.fixture(); mm=copy.deepcopy(mm); mm["scorer_contract_git_blob_sha1"]="0"*40
        H.assert_both_fail(t/"contract",mm,dd,rr,"SCORER_CONTRACT_BLOB_MISMATCH"); checks.append("CONTRACT_PIN_FAIL_CLOSED")
        mm,dd,rr=H.fixture(); mm=copy.deepcopy(mm); mm["mode"]="PRODUCTION"; mm.pop("synthetic_fixture",None)
        H.assert_both_fail(t/"prod",mm,dd,rr,"EXECUTION_PARITY_REQUIRED"); checks.append("PRODUCTION_PARITY_LATCH_FAIL_CLOSED")

        primary_hash=hashlib.sha256((t/"primary/candidate_results.jsonl").read_bytes()).hexdigest()
        summary_hash=hashlib.sha256((t/"primary/summary.json").read_bytes()).hexdigest()
    receipt={"schema":"QROS_FIRST_GATE_SCORER_ADVERSARIAL_RECEIPT_2.0","status":"PASS",
             "check_count":len(checks),"checks":checks,"synthetic_only":True,"economic_pnl_read":False,
             "primary_oracle_candidate_results_sha256":primary_hash,"primary_oracle_summary_sha256":summary_hash,
             "supersedes_fixture":"qros_first_gate_scorer_adversarial_v1.py main() degenerate assertion only"}
    raw=H.canon(receipt).encode(); receipt["receipt_sha256"]=hashlib.sha256(raw).hexdigest()
    print(H.canon(receipt))

if __name__=="__main__":
    main()
