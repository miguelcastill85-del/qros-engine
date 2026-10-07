"""Reuse only an exact successful build; uncertainty requests a build."""
import hashlib,json,os,pathlib,subprocess,urllib.request
SOURCE='463e68af09c2dc9c689160284b70d6fb7458148e'
RUN=37619093151
ARTIFACT=11481206837
ZIP_SHA='5ad5ff2c7a68dc27e2c1e6bb359ed6ae76678d75cf71f7cd863dca936ede0674'
REPO='miguelcastill85-del/qros-engine'
WORKFLOW='.github/workflows/qros-mobile-g12.yml'
INPUTS=['product/mobile/flutter_app','product/mobile/g12/worker','product/mobile/g12/tests',
 'product/mobile/g12/package.json','product/mobile/g12/package-lock.json','product/mobile/g12/wrangler.jsonc',
 'product/mobile/g9','product/mobile/g12_deployment/android_smoke.py',
 'product/mobile/g12_deployment/android_smoke_current.py','product/mobile/g12_deployment/build_native_probe.py',
 'product/mobile/g12_deployment/native_probe','product/mobile/g12_deployment/startup_state.py']
def recipe(text):
 body=text[text.index('\n  test-and-build:\n'):]
 body=body.replace('    needs: change-scope\n','')
 body=body.replace("    if: needs.change-scope.outputs.build == 'true'\n",'')
 return hashlib.sha256(body.encode()).hexdigest()
def reusable(source_equal,recipe_equal,run,artifact):
 return (source_equal and recipe_equal and run.get('status')=='completed'
  and run.get('conclusion')=='success' and run.get('head_sha')==SOURCE
  and artifact.get('id')==ARTIFACT and artifact.get('expired') is False
  and artifact.get('digest')=='sha256:'+ZIP_SHA)
def main():
 reuse=False;reason='VERIFIED_INPUTS_CHANGED_OR_VERIFICATION_UNAVAILABLE'
 try:
  source_equal=subprocess.run(['git','diff','--quiet',SOURCE,'HEAD','--',*INPUTS]).returncode==0
  prior=subprocess.check_output(['git','show',SOURCE+':'+WORKFLOW],text=True)
  recipe_equal=recipe(prior)==recipe(pathlib.Path(WORKFLOW).read_text())
  token=os.environ.pop('GH_TOKEN')
  def get(path):
   req=urllib.request.Request('https://api.github.com/repos/'+REPO+path,headers={
    'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
   with urllib.request.urlopen(req,timeout=15) as response:
    assert response.status==200
    raw=response.read(1024*1024+1);assert len(raw)<=1024*1024
   return json.loads(raw)
  reuse=reusable(source_equal,recipe_equal,get('/actions/runs/'+str(RUN)),get('/actions/artifacts/'+str(ARTIFACT)))
  if reuse: reason='EXACT_VERIFIED_BUILD_REUSED_NO_NEW_APK'
 except Exception:
  # Never serialize URL, response, credential or exception text.
  reason='REUSE_NOT_ESTABLISHED_RUN_BUILD'
 value='false' if reuse else 'true'
 pathlib.Path(os.environ['GITHUB_OUTPUT']).open('a').write('build='+value+'\n')
 receipt={'schema':'QROS_G12_CI_BUILD_REUSE_V1','build_required':not reuse,'reason':reason,
  'verified_source_commit':SOURCE,'verified_run':RUN,'verified_artifact':ARTIFACT,
  'verified_zip_sha256':ZIP_SHA,'current_commit':os.environ['GITHUB_SHA']}
 pathlib.Path('/tmp/qros-g12-build-reuse.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(reason)
if __name__=='__main__': main()
