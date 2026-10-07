import importlib.util,pathlib,unittest
p=pathlib.Path(__file__).with_name('ci_reuse_guard.py')
spec=importlib.util.spec_from_file_location('guard',p);g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
class ReuseBoundary(unittest.TestCase):
 def setUp(self):
  self.run={'status':'completed','conclusion':'success','head_sha':g.SOURCE}
  self.artifact={'id':g.ARTIFACT,'expired':False,'digest':'sha256:'+g.ZIP_SHA}
 def test_exact_success_can_reuse(self):
  self.assertTrue(g.reusable(True,True,self.run,self.artifact))
 def test_program_or_recipe_change_requires_build(self):
  self.assertFalse(g.reusable(False,True,self.run,self.artifact));self.assertFalse(g.reusable(True,False,self.run,self.artifact))
 def test_failed_unfinished_or_other_source_cannot_reuse(self):
  for patch in [{'status':'in_progress'},{'conclusion':'failure'},{'head_sha':'0'*40}]:
   self.assertFalse(g.reusable(True,True,{**self.run,**patch},self.artifact))
 def test_missing_expired_or_different_artifact_cannot_reuse(self):
  for patch in [{'expired':True},{'id':0},{'digest':'sha256:'+'0'*64}]:
   self.assertFalse(g.reusable(True,True,self.run,{**self.artifact,**patch}))
  self.assertFalse(g.reusable(True,True,{},{}))
 def test_only_exact_scheduling_lines_are_ignored(self):
  base='\n  test-and-build:\n    runs-on: ubuntu-24.04\n    steps:\n      - run: build\n'
  guarded=base.replace('    runs-on:',"    needs: change-scope\n    if: needs.change-scope.outputs.build == 'true'\n    runs-on:")
  self.assertEqual(g.recipe(base),g.recipe(guarded))
  self.assertNotEqual(g.recipe(base),g.recipe(guarded.replace('run: build','run: altered-build')))
if __name__=='__main__': unittest.main()
