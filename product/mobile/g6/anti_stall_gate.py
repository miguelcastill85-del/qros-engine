from __future__ import annotations
import argparse, hashlib, json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[3]
G6=ROOT/'product/mobile/g6'
PARENT='69109c6570c6cbb48f807b1b417dbdfa0b53fa54'
PRODUCT='2b1c876a7c033e6cc5309b8ad2e77c3a27600839'
G5='5f95b28caa79a15126d50b91097681d41e202b29'
REQUIRED={
 '.github/workflows/qros-mobile-g6-android-gate.yml',
 'product/mobile/g6/G6_SECURITY_CONTRACT.md','product/mobile/g6/G6_PROGRESS_HEAD.json',
 'product/mobile/g6/G6_SOURCE_MANIFEST.json','product/mobile/g6/anti_stall_gate.py',
 'product/mobile/g6/generate_fixture.py','product/mobile/g6/tests/test_fixture.py',
 'product/mobile/g6/tests/fixtures/g5_signed_snapshot_fixture.json',
 'product/mobile/flutter_app/lib/core/g5_snapshot.dart','product/mobile/flutter_app/lib/ui/g5_snapshot_screen.dart',
 'product/mobile/flutter_app/lib/main.dart','product/mobile/flutter_app/lib/ui/app_shell.dart',
 'product/mobile/flutter_app/pubspec.yaml','product/mobile/flutter_app/test/g5_snapshot_test.dart',
 'product/mobile/flutter_app/test/g5_snapshot_widget_test.dart'
}
HASHED=REQUIRED-{
 'product/mobile/g6/G6_SOURCE_MANIFEST.json','product/mobile/g6/G6_PROGRESS_HEAD.json',
 'product/mobile/flutter_app/lib/main.dart','product/mobile/flutter_app/lib/ui/app_shell.dart','product/mobile/flutter_app/pubspec.yaml'
}
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT,text=True,stderr=subprocess.PIPE).strip()
def fail(x):raise SystemExit('QROS_G6_ANTI_STALL_FAIL_CLOSED:'+x)
def run(remote=False):
 h=json.loads((G6/'G6_PROGRESS_HEAD.json').read_text());m=json.loads((G6/'G6_SOURCE_MANIFEST.json').read_text())
 if h.get('parent_exact')!=PARENT or h.get('parent_mobile_head_blob')!=PRODUCT or h.get('parent_g5_verified_head_blob')!=G5:fail('PARENT_AUTHORITY')
 if h.get('economic_tests')!=0 or h.get('holdout_open') is not False or h.get('ga2_open') is not False or h.get('scientific_authority') is not False:fail('SCIENCE_FIREWALL')
 if set(m.get('source_sha256',{})) != HASHED:fail('MANIFEST_PATH_SET')
 for name,want in m['source_sha256'].items():
  p=ROOT/name
  if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=want:fail('HASH:'+name)
 if git('hash-object','product/mobile/MOBILE_PRODUCT_HEAD.json')!=PRODUCT:fail('PRODUCT_HEAD_MUTATED')
 if git('hash-object','product/mobile/g5_verified/G5_CURRENT_HEAD.json')!=G5:fail('G5_VERIFIED_HEAD_MUTATED')
 if remote:
  changed=set(filter(None,git('diff','--name-only',PARENT+'...HEAD').splitlines()))
  if changed!=REQUIRED:fail('DELTA_SET')
 return {'status':'PASS_G6_SOURCE_DELTA_TEST_ONLY','required_paths':len(REQUIRED),'hashed':len(HASHED),'scientific_gate_pass':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--remote-git',action='store_true');a=p.parse_args();print(json.dumps(run(a.remote_git),indent=2,sort_keys=True))
