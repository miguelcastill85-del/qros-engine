#!/usr/bin/env python3
"""Only synthetic fixtures: no broker data, strategy outcomes, MT5 or holdout."""
import hashlib, json, pathlib, sys, tempfile, unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from qros_anti_stall_v2_2_single_owner_candidate import invoke,Incident,sha_file
from qros_continuation_dispatch_v22_v3_single_owner_candidate import dispatch

AUTH={"repo":"owner/qros-fixture","branch":"engineering/frozen-fixture","base_commit":"b"*40}
LOCK={"holdout_open":False,"ga2_open":False,"new_old_shard_ga1_authorized":False}
DATA=b"exact synthetic output"
ART_SHA=hashlib.sha256(DATA).hexdigest()
WORKER=(
    "import json,pathlib\n"
    "p=pathlib.Path('result.bin');p.write_bytes(b'exact synthetic output')\n"
    "x={'job_id':'FIXTURE','spec_sha256':'"+'f'*64+"',"
    "'artifacts':[{'path':'result.bin','bytes':22,'sha256':'"+ART_SHA+"'}]}\n"
    "pathlib.Path('worker_receipt.json').write_text(json.dumps(x))\n"
)

class SingleOwnerSynthetic(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def make(self,name="FIXTURE",source=WORKER,extra_routes=None,contract_edit=None,idle=.7,log_cap=1024,timeout=2.5):
        work=self.root/name;work.mkdir()
        (work/"worker.py").write_text(source)
        (work/"input.dat").write_bytes(b"pinned non-economic input")
        contract={
          "schema":"QROS_V3_STATELESS_GUARD_CONTRACT_V1",
          "authority":dict(AUTH),"lane_id":"TEST_LANE","stage_id":"ONE_STAGE",
          "expected_receipt":{"job_id":"FIXTURE","spec_sha256":"f"*64},
          "worker_receipt":"worker_receipt.json",
          "artifacts":[{"path":"result.bin","bytes":len(DATA),"sha256":ART_SHA}],
          "proof_path":"guard_proof.json",
        }
        if contract_edit:contract_edit(contract)
        cp=work/"contract.json";cp.write_text(json.dumps(contract,sort_keys=True))
        inputs=[{"path":z,"bytes":(work/z).stat().st_size,"sha256":sha_file(work/z)}
                for z in ["worker.py","input.dat","contract.json"]]
        routes=[{"name":"frozen_primary","argv":[sys.executable,"worker.py"]}]
        if extra_routes:
            for fname,body in extra_routes:
                (work/fname).write_text(body)
                inputs.append({"path":fname,"bytes":(work/fname).stat().st_size,"sha256":sha_file(work/fname)})
                routes.append({"name":"route_"+fname.replace(".","_"),"argv":[sys.executable,fname]})
        plan={
          "schema":"QROS_ANTI_STALL_PLAN_V2_1","lane_id":"TEST_LANE","authority":AUTH,
          "scientific_firewalls":LOCK,
          "stages":[{
             "id":"ONE_STAGE","kind":"local","timeout_seconds":timeout,
             "inputs":inputs,
             "outputs":[{"path":"result.bin","bytes":len(DATA),"sha256":ART_SHA},
                        {"path":"guard_proof.json","bytes":None,"sha256":None}],
             "routes":routes,
             "stateless_guard":{
               "contract_path":"contract.json","contract_sha256":sha_file(cp),
               "proof_path":"guard_proof.json","max_log_bytes":log_cap,"idle_seconds":idle,
               "direct_worker_no_detached_descendants":True
             }
          }]
        }
        pp=work/"plan.json";pp.write_text(json.dumps(plan,sort_keys=True))
        return work,pp,sha_file(pp),plan

    def run_one(self,**kw):
        work,plan,pin,_=self.make(**kw)
        init=invoke(work,plan,pin,"init")
        self.assertEqual(init["status"],"INITIALIZED")
        return work,plan,pin,invoke(work,plan,pin,"run")

    def test_exact_artifact_and_proof_pass(self):
        work,p,pin,res=self.run_one()
        self.assertEqual(res["status"],"ONE_STAGE_PASS")
        proof=json.loads((work/"guard_proof.json").read_text())
        self.assertEqual(proof["status"],"PASS_FROZEN_PHYSICAL_ARTIFACTS")
        self.assertFalse(proof["scientific_promotion"])
        self.assertEqual(invoke(work,p,pin,"status")["cursor"],1)

    def test_no_duplicate_rerun_after_pass(self):
        work,p,pin,res=self.run_one()
        self.assertEqual(res["status"],"ONE_STAGE_PASS")
        before=(work/"guard_proof.json").read_bytes()
        self.assertEqual(invoke(work,p,pin,"run")["status"],"DONE_NOOP")
        self.assertEqual(before,(work/"guard_proof.json").read_bytes())

    def test_worker_exit_zero_but_missing_receipt_does_not_pass(self):
        source="from pathlib import Path\nPath('result.bin').write_bytes(b'exact synthetic output')\n"
        work,p,pin,res=self.run_one(source=source)
        self.assertEqual(res["status"],"HALTED_NO_FROZEN_ROUTE")
        self.assertFalse((work/"guard_proof.json").exists())

    def test_wrong_worker_identity_fails_closed(self):
        source=WORKER.replace("'job_id':'FIXTURE'","'job_id':'IMPOSTOR'")
        work,p,pin,res=self.run_one(source=source)
        self.assertEqual(res["status"],"HALTED_NO_FROZEN_ROUTE")
        self.assertIn("WORKER_IDENTITY_MISMATCH",res["error"])

    def test_forged_output_claim_without_real_bytes_fails(self):
        source=WORKER.replace("b'exact synthetic output'","b'NOT THE EXPECTED BYTES'")
        work,p,pin,res=self.run_one(source=source)
        self.assertEqual(res["status"],"HALTED_NO_FROZEN_ROUTE")
        self.assertIn("PHYSICAL_ARTIFACT_BYTES_MISMATCH",res["error"])

    def test_symlink_worker_artifact_rejected(self):
        source=("import pathlib,json\n"
          "p=pathlib.Path('actual.bin');p.write_bytes(b'exact synthetic output')\n"
          "pathlib.Path('result.bin').symlink_to(p.resolve())\n"
          "x={'job_id':'FIXTURE','spec_sha256':'"+'f'*64+"',"
          "'artifacts':[{'path':'result.bin','bytes':22,'sha256':'"+ART_SHA+"'}]}\n"
          "pathlib.Path('worker_receipt.json').write_text(json.dumps(x))\n")
        work,p,pin,res=self.run_one(source=source)
        self.assertEqual(res["status"],"HALTED_NO_FROZEN_ROUTE")
        self.assertIn("SYMLINK_FORBIDDEN",res["error"])

    def test_log_flood_terminates_with_bounded_memory(self):
        source="import sys,time\nsys.stdout.write('L'*16384);sys.stdout.flush();time.sleep(1)\n"
        work,p,pin,res=self.run_one(source=source,idle=1.4,log_cap=1024,timeout=2)
        self.assertEqual(res["status"],"HALTED_NO_FROZEN_ROUTE")
        self.assertIn("GUARDED_LOG_BUDGET_EXCEEDED",res["error"])

    def test_idle_termination_preserves_partial_bytes(self):
        source="import time,pathlib\npathlib.Path('partial.bin').write_bytes(b'partial');time.sleep(3)\n"
        work,p,pin,res=self.run_one(source=source,idle=.35,timeout=2)
        self.assertEqual(res["status"],"HALTED_NO_FROZEN_ROUTE")
        self.assertIn("GUARDED_NO_VERIFIED_BYTE_PROGRESS",res["error"])
        self.assertEqual((work/"partial.bin").read_bytes(),b"partial")

    def test_frozen_contract_tamper_rejected_before_launch(self):
        work,p,pin,_=self.make()
        (work/"contract.json").write_text('{"fake":"tampered"}')
        with self.assertRaises(Incident):
            invoke(work,p,pin,"init")
        self.assertFalse((work/"result.bin").exists())

    def test_guard_rejects_authority_drift(self):
        work,p,pin,_=self.make(contract_edit=lambda c:c["authority"].update(branch="wrong"))
        with self.assertRaisesRegex(Incident,"GUARD_CROSS_LANE_OR_STAGE_AUTHORITY"):
            invoke(work,p,pin,"init")

    def test_nested_watchdog_argument_rejected(self):
        work,p,pin,plan=self.make()
        plan["stages"][0]["routes"][0]["argv"]=[sys.executable,"qros_progress_watchdog_v2_2.py"]
        p.write_text(json.dumps(plan,sort_keys=True));pin=sha_file(p)
        with self.assertRaisesRegex(Incident,"NESTED_CONTROLLER_ROUTE_FORBIDDEN"):
            invoke(work,p,pin,"init")

    def test_pass_output_tamper_rejected_on_status(self):
        work,p,pin,res=self.run_one()
        self.assertEqual(res["status"],"ONE_STAGE_PASS")
        (work/"guard_proof.json").write_text('{"tampered":true}')
        with self.assertRaisesRegex(Incident,"ARTIFACT_(SIZE|HASH)_DRIFT"):
            invoke(work,p,pin,"status")

    def test_one_failed_then_frozen_equivalent_alternate(self):
        bad="from pathlib import Path\nPath('result.bin').write_bytes(b'exact synthetic output')\n"
        work,p,pin,plan=self.make(source=bad,extra_routes=[("good.py",WORKER)])
        job={"id":"JOB1","work":str(work),"plan":str(p),"plan_sha256":pin,"kind":"local",
             "hard_route_seconds":20,"max_distinct_routes":2,"depends_on":[]}
        q={"schema":"QROS_BOUNDED_CONTINUATION_QUEUE_V2_2","authority":AUTH,
           "control_root":str(self.root/"control"),"jobs":[job]}
        qp=self.root/"queue.json";qp.write_text(json.dumps(q,sort_keys=True))
        out=dispatch(qp,sha_file(qp),12)
        self.assertEqual(out["status"],"ONE_VERIFIED_STAGE_PASS")
        self.assertEqual([x["action"] for x in out["events"] if "details" in x],
                         ["FAILED_ROUTE_SWITCH_REQUIRED","ONE_STAGE_PASS"])
        self.assertEqual(invoke(work,p,pin,"status")["cursor"],1)
        self.assertFalse(json.loads((work/"guard_proof.json").read_text())["scientific_promotion"])

if __name__=="__main__":unittest.main(verbosity=2)
