"""Bind emulator invocation to the exact artifact from this build run."""
import json,os,pathlib,re,subprocess,sys
base=pathlib.Path('/tmp/qros-g12-runtime/input')
r=json.loads((base/'QROS_G12_ENGINEERING_RECEIPT.json').read_text())
assert r['source_commit']==os.environ['GITHUB_SHA']
assert re.fullmatch('[0-9a-f]{64}',r['apk_sha256']) and isinstance(r['apk_bytes'],int)
raise SystemExit(subprocess.run([sys.executable,'product/mobile/g12_deployment/android_smoke.py',
 '--input',str(base),'--evidence','/tmp/qros-g12-runtime/evidence',
 '--source',r['source_commit'],'--apk-sha',r['apk_sha256'],'--apk-bytes',str(r['apk_bytes'])],check=False).returncode)
