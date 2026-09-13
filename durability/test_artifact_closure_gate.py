import hashlib, json, pathlib, tempfile, unittest
from qros_artifact_closure_gate import SCHEMA, evaluate, restore_canary

class GateTests(unittest.TestCase):
 def fixture(self, omit=False, corrupt=False):
  td=tempfile.TemporaryDirectory(); base=pathlib.Path(td.name); roots={"git":base/"git","cas":base/"cas"}
  for r in roots.values(): r.mkdir()
  roles=["PAYLOAD","SOURCE","INPUT_MANIFEST","OUTPUT_MANIFEST","DEPENDENCY_DAG","NEXT_STAGE_PACKET"]
  objs=[]
  for i,role in enumerate(roles):
   data=f"{role}\n".encode(); digest=hashlib.sha256(data).hexdigest(); rel=f"{i}.bin"
   for sid,r in roots.items():
    if not (omit and role=="PAYLOAD" and sid=="cas"): (r/rel).write_bytes(b"bad" if corrupt and role=="PAYLOAD" and sid=="cas" else data)
   objs.append({"id":str(i),"role":role,"sha256":digest,"bytes":len(data),"required_store_ids":["git","cas"],"store_paths":{"git":rel,"cas":rel}})
  m={"schema":SCHEMA,"stage_id":"B","next_stage_id":"C","runtime_sandbox_is_authority":False,"holdout_accessed":False,"durable_stores":[{"id":"git","independent":True},{"id":"cas","independent":True}],"objects":objs}
  return td,m,roots
 def test_pass_and_restore(self):
  td,m,r=self.fixture(); receipt=evaluate(m,r); self.assertEqual(receipt["decision"],"GATE_CLOSE_AUTHORIZED"); self.assertEqual(restore_canary(m,r,receipt)["decision"],"RESTORE_PASS"); td.cleanup()
 def test_missing_copy_fails_closed(self):
  td,m,r=self.fixture(omit=True); self.assertEqual(evaluate(m,r)["decision"],"GATE_CLOSE_FORBIDDEN"); td.cleanup()
 def test_hash_mismatch_fails_closed(self):
  td,m,r=self.fixture(corrupt=True); self.assertEqual(evaluate(m,r)["decision"],"GATE_CLOSE_FORBIDDEN"); td.cleanup()
 def test_hash_is_not_backup(self):
  td,m,r=self.fixture(); [p.unlink() for p in (r["git"] / "0.bin",r["cas"] / "0.bin")]; self.assertIn("BYTES_MISSING:0:git",evaluate(m,r)["errors"]); td.cleanup()
 def test_runtime_or_holdout_claim_fails(self):
  td,m,r=self.fixture(); m["runtime_sandbox_is_authority"]=True; m["holdout_accessed"]=True; self.assertEqual(evaluate(m,r)["decision"],"GATE_CLOSE_FORBIDDEN"); td.cleanup()
 def test_duplicate_object_fails(self):
  td,m,r=self.fixture(); m["objects"].append(dict(m["objects"][0])); self.assertIn("DUPLICATE_OBJECT_ID",evaluate(m,r)["errors"]); td.cleanup()
 def test_undeclared_store_fails(self):
  td,m,r=self.fixture(); m["objects"][0]["required_store_ids"].append("ghost"); self.assertIn("UNDECLARED_STORE:0:ghost",evaluate(m,r)["errors"]); td.cleanup()
if __name__=="__main__": unittest.main()
