#!/usr/bin/env python3
import copy, hashlib, json, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PRIMARY=ROOT/"scripts/qros_first_gate_execution_normalizer_primary_v2.py"
ORACLE=ROOT/"scripts/qros_first_gate_execution_normalizer_oracle_v2.py"
CONTRACT="5d7006c5b54d4647113c7caab5107e8c9229d2bf"
CAMPAIGN="PUBLIC1000_WEB_SEED_0076_FRACTALBOX_3EMA"

def canon(o): return json.dumps(o,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def mh(x): return hashlib.sha256(x.encode()).hexdigest()
def manifest(mode="SYNTHETIC_VALIDATION"):
    return {"schema":"QROS_FIRST_GATE_EXECUTION_FIXTURE_1.0","mode":mode,"campaign":CAMPAIGN,"execution_contract_git_blob_sha1":CONTRACT,"synthetic_fixture":mode=="SYNTHETIC_VALIDATION"}
def anchor(name,side="BUY",stop="99",obs=900,trig=1000,close=5000):
    return {"canonical_signal_config_id":"CFG_"+name,"event_mask_sha256":mh(name),"event_id":"EV_"+name,"side":side,"signal_observable_timestamp":obs,"entry_trigger_timestamp":trig,"opposite_fractal_stop":stop,"session_close_timestamp":close}
def ticks(rows):
    return [{"carrier_sequence":i+1,"timestamp":r[0],"bid":str(r[1]),"ask":str(r[2])} for i,r in enumerate(rows)]
def scenario(name,a,rows): return {"scenario_id":name,"event_anchor":a,"ticks":ticks(rows)}
def valid_cases():
    return [
      scenario("BUY_NORMAL_STOP",anchor("BNS","BUY","99"),[(1000,"100","101"),(2000,"99","100")]),
      scenario("BUY_ADVERSE_GAP_STOP",anchor("BGS","BUY","99"),[(1000,"100","101"),(2000,"98","99")]),
      scenario("BUY_SAME_DAY_EXIT",anchor("BSD","BUY","99"),[(1000,"100","101"),(3000,"101","102"),(5000,"102","103")]),
      scenario("SELL_NORMAL_STOP",anchor("SNS","SELL","102"),[(1000,"100","101"),(2000,"101","102")]),
      scenario("SELL_ADVERSE_GAP_STOP",anchor("SGS","SELL","102"),[(1000,"100","101"),(2000,"102","103")]),
      scenario("SELL_SAME_DAY_EXIT",anchor("SSD","SELL","102"),[(1000,"100","101"),(3000,"99","100"),(5000,"98","99")]),
      {"scenario_id":"EQUAL_TIMESTAMP_ORDERED_BY_CARRIER_SEQUENCE","event_anchor":anchor("EQ","BUY","99"),"ticks":[{"carrier_sequence":1,"timestamp":1000,"bid":"100","ask":"101"},{"carrier_sequence":2,"timestamp":1000,"bid":"98","ask":"99"}]}
    ]
EXPECTED={
 "BUY_NORMAL_STOP":("STOP","-1"),"BUY_ADVERSE_GAP_STOP":("STOP","-1.5"),"BUY_SAME_DAY_EXIT":("SAME_DAY","0.5"),
 "SELL_NORMAL_STOP":("STOP","-1"),"SELL_ADVERSE_GAP_STOP":("STOP","-1.5"),"SELL_SAME_DAY_EXIT":("SAME_DAY","0.5"),
 "EQUAL_TIMESTAMP_ORDERED_BY_CARRIER_SEQUENCE":("STOP","-1.5")}

def write_bundle(root,m,rows):
    root.mkdir(parents=True,exist_ok=True); (root/"manifest.json").write_text(canon(m)+"\n"); (root/"scenarios.jsonl").write_text("".join(canon(x)+"\n" for x in rows))
def run(script,inp,out):
    p=subprocess.run([sys.executable,str(script),"--input",str(inp),"--output",str(out)],text=True,capture_output=True)
    try: payload=json.loads(p.stdout.strip().splitlines()[-1])
    except Exception: payload={"status":"UNPARSEABLE","stdout":p.stdout,"stderr":p.stderr}
    return p.returncode,payload
def both_fail(base,m,rows,code):
    inp=base/"in"; write_bundle(inp,m,rows)
    for tag,script in (("p",PRIMARY),("o",ORACLE)):
        rc,p=run(script,inp,base/tag); assert rc==2,(code,tag,rc,p); assert p.get("status")=="FAIL_CLOSED",(code,tag,p); assert p.get("error")==code,(code,tag,p)
def main():
    assert PRIMARY.read_bytes()!=ORACLE.read_bytes()
    checks=[]
    with tempfile.TemporaryDirectory() as td:
        t=Path(td); rows=valid_cases(); inp=t/"valid"; write_bundle(inp,manifest(),rows)
        rp,pp=run(PRIMARY,inp,t/"primary"); ro,po=run(ORACLE,inp,t/"oracle"); assert rp==0 and ro==0,(pp,po)
        pb=(t/"primary/normalized_trades.jsonl").read_bytes(); ob=(t/"oracle/normalized_trades.jsonl").read_bytes(); assert pb==ob
        assert (t/"primary/summary.json").read_bytes()==(t/"oracle/summary.json").read_bytes()
        got={x["scenario_id"]:x for x in map(json.loads,(t/"primary/normalized_trades.jsonl").read_text().splitlines())}
        assert set(got)==set(EXPECTED)
        for sid,(reason,rval) in EXPECTED.items():
            assert got[sid]["exit_reason"]==reason,(sid,got[sid]); assert got[sid]["R"]==rval,(sid,got[sid]); checks.append("EXPECTED_"+sid)
        sm=json.loads((t/"primary/summary.json").read_text()); assert sm["economic_decision_authorized"] is False and sm["economic_pnl_read"] is False
        checks += ["PRIMARY_ORACLE_BYTE_PARITY","SYNTHETIC_ECONOMIC_FIREWALL"]

        r=valid_cases()[:1]; r[0]["ticks"][1]["carrier_sequence"]=1; both_fail(t/"seq",manifest(),r,"NONMONOTONIC_CARRIER_SEQUENCE"); checks.append("NONMONOTONIC_SEQUENCE_FAIL")
        r=valid_cases()[:1]; r[0]["ticks"][1]["timestamp"]=900; both_fail(t/"time",manifest(),r,"BACKWARD_TIMESTAMP"); checks.append("BACKWARD_TIMESTAMP_FAIL")
        r=valid_cases()[:1]; r[0]["ticks"][0]["ask"]="99"; both_fail(t/"quote",manifest(),r,"CROSSED_OR_INVALID_QUOTE"); checks.append("CROSSED_QUOTE_FAIL")
        r=valid_cases()[:1]; r[0]["event_anchor"]["signal_observable_timestamp"]=1100; both_fail(t/"obs",manifest(),r,"SIGNAL_AFTER_TRIGGER"); checks.append("SIGNAL_AFTER_TRIGGER_FAIL")
        r=valid_cases()[:1]; r[0]["event_anchor"]["entry_trigger_timestamp"]=4000; r[0]["ticks"]=r[0]["ticks"][:1]; both_fail(t/"entry",manifest(),r,"NO_EXECUTABLE_ENTRY"); checks.append("NO_ENTRY_FAIL")
        r=valid_cases()[:1]; r[0]["event_anchor"]["opposite_fractal_stop"]="102"; both_fail(t/"stop",manifest(),r,"INVALID_STOP_DIRECTION"); checks.append("STOP_DIRECTION_FAIL")
        r=valid_cases()[:1]; r[0]["ticks"][0]["bid"]="NaN"; both_fail(t/"nan",manifest(),r,"NONFINITE_PRICE"); checks.append("NONFINITE_FAIL")
        r=valid_cases()[:2]; r[1]["scenario_id"]=r[0]["scenario_id"]; both_fail(t/"dup",manifest(),r,"DUPLICATE_SCENARIO_ID"); checks.append("DUP_SCENARIO_FAIL")
        both_fail(t/"mode",manifest("UNKNOWN"),valid_cases()[:1],"UNSUPPORTED_MODE"); checks.append("UNSUPPORTED_MODE_FAIL")
        both_fail(t/"prod",manifest("PRODUCTION"),valid_cases()[:1],"OVERLAPPING_EVENT_POLICY_UNBOUND_IN_PRODUCTION"); checks.append("PRODUCTION_OVERLAP_BINDING_FAIL")
        mm=manifest(); mm["execution_contract_git_blob_sha1"]="0"*40; both_fail(t/"pin",mm,valid_cases()[:1],"CONTRACT_PIN_MISMATCH"); checks.append("CONTRACT_PIN_FAIL")
        result_hash=hashlib.sha256(pb).hexdigest(); summary_hash=hashlib.sha256((t/"primary/summary.json").read_bytes()).hexdigest()
    receipt={"schema":"QROS_FIRST_GATE_EXECUTION_NORMALIZER_ADVERSARIAL_RECEIPT_1.0","status":"PASS","check_count":len(checks),"checks":checks,"synthetic_only":True,"economic_pnl_read":False,"primary_oracle_normalized_trades_sha256":result_hash,"primary_oracle_summary_sha256":summary_hash}
    receipt["receipt_sha256"]=hashlib.sha256(canon(receipt).encode()).hexdigest(); print(canon(receipt))
if __name__=="__main__": main()
