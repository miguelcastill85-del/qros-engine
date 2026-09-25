"""G6 executable no-op/source-tamper gate. Verifies SHA bytes, baseline and real delta."""
from __future__ import annotations
import argparse,hashlib,json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[3]
G6=ROOT/'product/mobile/g6'
PARENT='69109c6570c6cbb48f807b1b417dbdfa0b53fa54'
PINS={
 'product/mobile/MOBILE_PRODUCT_HEAD.json':'2b1c876a7c033e6cc5309b8ad2e77c3a27600839',
 'product/mobile/g5_verified/G5_CURRENT_HEAD.json':'5f95b28caa79a15126d50b91097681d41e202b29',
 'product/mobile/receipts/QROS_MOBILE_G5_VERIFIED_ENGINEERING_PASS_20260925.json':'28cc55db632ac03c2a58c6412decd664769e3895',
 'product/mobile/flutter_app/lib/core/verified_demo.dart':'1e9f2c7e0cacf20ea912db0ce3e345fa04b921d0',
 'product/mobile/flutter_app/lib/core/universe_ir.dart':'636a8a7ec5cc00cc0ad1c64354ae74fffeaa5c5e',
 'product/mobile/flutter_app/lib/ui/app_shell.dart':'08fac5169c0377a8b1f03a802d5e0f202321efae'
}
REQUIRED={
'.github/workflows/qros-mobile-g6-android-proof.yml',
'product/mobile/g6/DELIVERY_CONTRACT.md',
'product/mobile/g6/G6_PROGRESS_HEAD.json',
'product/mobile/g6/G6_SOURCE_MANIFEST.json',
'product/mobile/g6/anti_stall_gate.py',
'product/mobile/g6/generate_signed_fixture.py',
'product/mobile/g6/tests/test_g6_fixture.py',
'product/mobile/g6/tests/test_gate.py',
'product/mobile/flutter_app/lib/core/g6_signed_snapshot.dart',
'product/mobile/flutter_app/lib/core/g6_demo_transport.dart',
'product/mobile/flutter_app/lib/ui/g6_proof_screen.dart',
'product/mobile/flutter_app/lib/main.dart',
'product/mobile/flutter_app/lib/core/g6_snapshot_verifier.dart',
'product/mobile/flutter_app/pubspec.yaml',
'product/mobile/flutter_app/assets/g6_signed_snapshot.json',
'product/mobile/flutter_app/assets/g6_offline_trust.json',
'product/mobile/flutter_app/test/g6_snapshot_test.dart',
'product/mobile/flutter_app/test/g6_widget_test.dart'
}
class GateReject(RuntimeError):pass
def deny(code):raise GateReject('QROS_G6_FAIL_CLOSED:'+code)
def git(*args):
 try:return subprocess.check_output(['git',*args],cwd=ROOT,text=True,stderr=subprocess.PIPE).strip()
 except (OSError,subprocess.CalledProcessError):deny('GIT_AUTHORITY_UNAVAILABLE')
def verify(root: pathlib.Path=ROOT,remote:bool=False):
 head=json.loads((root/'product/mobile/g6/G6_PROGRESS_HEAD.json').read_text())
 manifest=json.loads((root/'product/mobile/g6/G6_SOURCE_MANIFEST.json').read_text())
 if head.get('schema')!='QROS_MOBILE_G6_PROGRESS_HEAD_V1' or head.get('phase')!='G6_ANDROID_SIGNED_G5_SYNTHETIC_PROOF_CI_PENDING' or head.get('parent_exact')!=PARENT or not head.get('next_automatic_action'):deny('MISSING_PENDING_AUTHORITY')
 if head.get('g5_mobile_product_head_blob')!=PINS['product/mobile/MOBILE_PRODUCT_HEAD.json'] or head.get('g5_verified_head_blob')!=PINS['product/mobile/g5_verified/G5_CURRENT_HEAD.json']:deny('PIN_DRIFT')
 if head.get('economic_tests')!=0 or head.get('holdout_open') is not False or head.get('ga2_open') is not False or head.get('scientific_authority') is not False:deny('SCIENTIFIC_FIREWALL_DRIFT')
 expected=REQUIRED-{'product/mobile/g6/G6_PROGRESS_HEAD.json','product/mobile/g6/G6_SOURCE_MANIFEST.json'}
 if manifest.get('schema')!='QROS_MOBILE_G6_SOURCE_MANIFEST_V1' or manifest.get('parent_exact')!=PARENT or set(manifest.get('source_sha256',{}))!=expected or head.get('expected_required_delta_files')!=len(REQUIRED):deny('MANIFEST_INCOMPLETE_NOOP')
 for name,sha in manifest['source_sha256'].items():
  p=root/name
  if p.is_symlink() or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=sha:deny('SOURCE_MISSING_OR_HASH_DRIFT:'+name)
 if remote:
  for name,sha in PINS.items():
   if git('hash-object',name)!=sha:deny('VERIFIED_PARENT_MUTATED:'+name)
  if git('rev-parse',PARENT)!=PARENT:deny('PARENT_UNAVAILABLE')
  delta=set(filter(None,git('diff','--name-only',PARENT+'...HEAD').splitlines()))
  if delta!=REQUIRED:deny('NO_OP_OR_SCOPE_DRIFT:missing='+','.join(sorted(REQUIRED-delta))+';extra='+','.join(sorted(delta-REQUIRED)))
  main=git('show','origin/main:control/QROS_PUBLIC_1000_CURRENT_FRONTIER_POINTER.json')
  science=json.loads(main)
  if science.get('holdout_open') is not False or science.get('ga2_open') is not False or science.get('scientific_state')!='PREREGISTERED_NO_RESULTS':deny('SCIENTIFIC_MAIN_AUTHORITY_DRIFT')
 return {'schema':'QROS_G6_ANTI_STALL_GATE_RECEIPT_V1','status':'PASS_SOURCE_SCOPE_AND_HASH_ONLY','new_required_files':len(REQUIRED),'source_files_hashed':len(expected),'parent_exact':PARENT,'remote_git':remote,'scientific_gate_pass':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--remote-git',action='store_true');args=p.parse_args()
 try:print(json.dumps(verify(remote=args.remote_git),indent=2,sort_keys=True))
 except GateReject as e:raise SystemExit(str(e))
