"""Compile a CI-only native evidence probe with already installed Android SDK tools."""
import os, pathlib, subprocess, zipfile


def build_probe(out):
    out = pathlib.Path(out); out.mkdir(parents=True, exist_ok=False)
    sdk = pathlib.Path(os.environ['ANDROID_HOME'])
    jars = list((sdk/'platforms').glob('android-*/android.jar'))
    jar = max(jars, key=lambda p: int(p.parent.name.split('-')[-1]))
    candidates = [p for p in (sdk/'build-tools').iterdir() if (p/'aapt').is_file() and (p/'d8').is_file()]
    bt = max(candidates, key=lambda p: tuple(int(v) for v in p.name.split('.') if v.isdigit()))
    source = pathlib.Path(__file__).parent/'native_probe'
    def run(*args):
        try:
            subprocess.run([str(v) for v in args], check=True, timeout=120, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as error:
            raise RuntimeError('native probe build failed: '+error.stderr.decode(errors='replace')[:1800]) from error
    classes=out/'classes';classes.mkdir();dex=out/'dex';dex.mkdir()
    run('javac','-source','8','-target','8','-classpath',jar,'-d',classes,source/'NativeProbe.java')
    run(bt/'d8','--lib',jar,'--min-api','26','--output',dex,*classes.rglob('*.class'))
    unsigned=out/'unsigned.apk'
    run(bt/'aapt','package','-f','-M',source/'AndroidManifest.xml','-I',jar,'-F',unsigned)
    with zipfile.ZipFile(unsigned,'a') as z:z.write(dex/'classes.dex','classes.dex')
    aligned=out/'aligned.apk';run(bt/'zipalign','-f','4',unsigned,aligned)
    # Ephemeral synthetic probe signer; unrelated to app or backend production keys.
    key=out/'probe-test.jks'
    run('keytool','-genkeypair','-keystore',key,'-storepass','android','-keypass','android','-alias','probe-test','-dname','CN=QROS CI TEST_ONLY','-keyalg','RSA','-validity','1')
    apk=out/'native-probe.apk'
    try:
        run(bt/'apksigner','sign','--ks',key,'--ks-pass','pass:android','--key-pass','pass:android','--out',apk,aligned)
        run(bt/'apksigner','verify',apk)
    finally:key.unlink(missing_ok=True)
    return apk
