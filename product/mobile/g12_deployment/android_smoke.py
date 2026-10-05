"""Verify the frozen G12 APK on Android 35; never classify emulator as physical."""
import argparse,hashlib,importlib.util,json,os,pathlib,re,time,xml.etree.ElementTree as ET

spec=importlib.util.spec_from_file_location('approved_probe_helpers',pathlib.Path(__file__).parents[1]/'g9/emulator_smoke.py')
helpers=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)

APK_SHA='40568dc3f612cb452513b2f933090e4549f2109d7560cfc944fb8f5f84221822'
APK_BYTES=146666789
SOURCE='217cd842cb195fa92e52aa39068b97892752e48e'
PACKAGE='app.qros.qros_mobile_studio'

def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=pathlib.Path,required=True);p.add_argument('--evidence',type=pathlib.Path,required=True);a=p.parse_args()
 out=a.evidence;out.mkdir(parents=True,exist_ok=True)
 if any(out.iterdir()): raise RuntimeError('evidence directory must be empty')
 r={'schema':'QROS_G12_ANDROID35_RUNTIME_V1','status':'FAIL','apk_source_commit':SOURCE,'harness_source_commit':os.environ.get('GITHUB_SHA'),'ci_run':os.environ.get('GITHUB_RUN_ID'),'physical_android':'NOT_RUN','public_g12_pairing':'NOT_RUN','scientific_authority':False}
 probe=helpers.EmulatorProbe();serial='emulator-5554'
 cmd=lambda *args,**kwargs:probe.cmd(serial,*args,**kwargs)
 def dump(name):
   for attempt in range(4):
     msg=cmd('shell','uiautomator','dump','/sdcard/qros_g12_ui.xml',timeout=65)
     if b'dumped to:' in msg:
       xml=cmd('exec-out','cat','/sdcard/qros_g12_ui.xml')
       helpers.inspect_hierarchy(xml)
       (out/(name+'.xml')).write_bytes(xml)
       png=cmd('exec-out','screencap','-p');helpers.inspect_png(png)
       (out/(name+'.png')).write_bytes(png)
       return ET.fromstring(xml)
     time.sleep(1)
   raise RuntimeError('hierarchy not observed')
 def texts(root):return [n.get('text','') or n.get('content-desc','') for n in root.findall('.//node')]
 def tap(root,label):
   nodes=[n for n in root.findall('.//node') if label in (n.get('text','')+' '+n.get('content-desc','')) and n.get('enabled')=='true']
   for n in nodes:
     bounds=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.get('bounds',''))
     if bounds:
       x1,y1,x2,y2=map(int,bounds.groups())
       if x2>x1 and y2>y1:
         cmd('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2));return
   raise RuntimeError('visible control absent: '+label)
 try:
   build=json.loads((a.input/'QROS_G12_ENGINEERING_RECEIPT.json').read_text())
   apk=a.input/'QROS_MOBILE_G12_TEST_ONLY.apk'
   assert build['source_commit']==SOURCE and build['apk_sha256']==APK_SHA and build['apk_bytes']==APK_BYTES
   assert apk.stat().st_size==APK_BYTES and hashlib.file_digest(apk.open('rb'),'sha256').hexdigest()==APK_SHA
   r.update(probe.emulator_only(serial));assert r['android_api']==35
   assert b'Success' in cmd('install','-r','-t',str(apk),timeout=180)
   path=cmd('shell','pm','path',PACKAGE).decode().strip().splitlines()[0].removeprefix('package:')
   installed=cmd('shell','sha256sum',path).decode().split()[0];assert installed==APK_SHA
   r['installed_apk_sha256']=installed;r['adb_install']='SUCCESS'
   cmd('shell','am','start','-W','-n',PACKAGE+'/.MainActivity')
   rendered=False
   for _ in range(24):
     png=cmd('exec-out','screencap','-p');(out/'startup.png').write_bytes(png)
     try:helpers.inspect_png(png);helpers.dark_content_fraction(png);rendered=True;break
     except helpers.SmokeDeny:time.sleep(2)
   assert rendered
   pid=cmd('shell','pidof','-s',PACKAGE).decode().strip();assert pid.isdecimal()
   home=dump('01-home');assert any('QROS' in t for t in texts(home))
   tap(home,'Más módulos y seguridad');menu=dump('02-menu');tap(menu,'Seguridad');security=dump('03-security')
   for attempt in range(10):
     if any('Vincular dispositivo G12' in t for t in texts(security)):break
     screen=cmd('shell','wm','size').decode();match=re.search(r'(\d+)x(\d+)',screen);assert match
     w,h=map(int,match.groups());cmd('shell','input','swipe',str(w//2),str(h*3//4),str(w//2),str(h//3),'350')
     security=dump('03-security-scroll-'+str(attempt))
   tap(security,'Vincular dispositivo G12');session=dump('04-session')
   observed=texts(session)
   for text in ['Identidad del dispositivo','Servidor HTTPS G12','Bootstrap temporal de un solo uso','Vincular dispositivo']:
     assert any(text in t for t in observed),text
   tap(session,'Vincular dispositivo');rejected=dump('05-empty-bootstrap-rejected')
   assert any('No se pudo crear la sesión' in t for t in texts(rejected))
   assert not any('SESIÓN ACTIVA' in t for t in texts(rejected))
   logs=cmd('logcat','-d','-t','1800','-v','brief').decode(errors='replace')
   for m in re.finditer('FATAL EXCEPTION',logs):assert ('Process: '+PACKAGE) not in logs[m.start():m.start()+650]
   r.update(status='PASS_REAL_ANDROID35_EMULATOR_TEST_ONLY',process_observed=True,g12_session_navigation='PASS',empty_bootstrap_fail_closed='PASS')
 except Exception as e:r['failure']=type(e).__name__+': '+str(e)[:200]
 finally:
   r['evidence_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}
   (out/'G12_ANDROID35_RUNTIME_RECEIPT.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps(r))
 return 0 if r['status'].startswith('PASS_') else 1

if __name__=='__main__':raise SystemExit(main())
