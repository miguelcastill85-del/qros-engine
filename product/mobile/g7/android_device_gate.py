"""G7 physical-Android USB install canary: refuses emulator/synthetic evidence.

Run on a workstation with Android Debug Bridge and a *physically attached*
Android device. No silent installation; --install must be explicitly supplied.
No token or private key is requested, read or printed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Callable

EXPECTED_G6_SHA256='2c4053a27fa5692871db717c4c5bb42e1284673b49f13fa41db6a7e2b0b52c97'
PACKAGE='app.qros.qros_mobile_studio'
SERIAL=re.compile(r'[A-Za-z0-9_.:-]{4,128}\Z')

class DeviceDeny(RuntimeError): pass

def deny(code: str): raise DeviceDeny('QROS_G7_DEVICE_DENY:'+code)

class DeviceInspector:
    def __init__(self, run: Callable[..., subprocess.CompletedProcess]=subprocess.run):
        self.run=run

    def adb(self,*args: str)->str:
        try:
            result=self.run(['adb',*args],capture_output=True,text=True,timeout=25,check=False)
        except (FileNotFoundError,subprocess.TimeoutExpired):
            deny('ADB_NOT_AVAILABLE')
        if result.returncode!=0:
            deny('ADB_ERROR')
        return result.stdout.strip()

    def validate(self, serial: str) -> dict:
        if type(serial) is not str or SERIAL.fullmatch(serial) is None:
            deny('SERIAL_EXPLICIT_REQUIRED')
        lines=self.adb('devices','-l').splitlines()[1:]
        found=[line for line in lines if line.split()[:2]==[serial,'device']]
        if len(found)!=1:
            deny('PHYSICAL_DEVICE_NOT_CONNECTED_OR_NOT_AUTHORIZED')
        prop=lambda key:self.adb('-s',serial,'shell','getprop',key).strip()
        emulator=prop('ro.kernel.qemu')
        fingerprint=prop('ro.build.fingerprint').lower()
        model=prop('ro.product.model').lower()
        if emulator=='1' or any(x in fingerprint for x in ('generic','sdk_gphone','emulator','vbox')) or any(x in model for x in ('emulator','sdk_gphone','android sdk built')):
            deny('EMULATOR_NOT_PHYSICAL_DEVICE')
        if not fingerprint or not model or not prop('ro.build.version.sdk').isdigit():
            deny('INCOMPLETE_DEVICE_PROVENANCE')
        return {'status':'PHYSICAL_ADB_PROPERTIES_OBSERVED_NOT_HUMAN_ATTESTED',
                'serial_hash_sha256':hashlib.sha256(serial.encode()).hexdigest(),
                'android_sdk':int(prop('ro.build.version.sdk')),
                'physical_install':'NOT_RUN','user_visual_pairing':'NOT_RUN'}

    def install(self,serial: str,apk_path: Path) -> dict:
        report=self.validate(serial)
        if not apk_path.is_file() or apk_path.is_symlink() or hashlib.sha256(apk_path.read_bytes()).hexdigest()!=EXPECTED_G6_SHA256:
            deny('G6_APK_EXACT_BYTES_REQUIRED')
        self.adb('-s',serial,'install','-r',str(apk_path))
        paths=self.adb('-s',serial,'shell','pm','path',PACKAGE)
        if 'package:' not in paths: deny('PACKAGE_NOT_INSTALLED')
        launch=self.adb('-s',serial,'shell','am','start','-n',PACKAGE+'/.MainActivity')
        if 'Error' in launch or ('Starting:' not in launch and 'Warning:' not in launch):
            deny('ANDROID_LAUNCH_NOT_CONFIRMED')
        report['physical_install']='ADB_INSTALL_AND_LAUNCH_OBSERVED'
        report['user_visual_pairing']='NOT_ATTESTED'
        report['apk_sha256']=EXPECTED_G6_SHA256
        return report

def main() -> int:
    a=argparse.ArgumentParser();a.add_argument('--serial',required=True)
    a.add_argument('--apk',type=Path,required=True);a.add_argument('--install',action='store_true')
    args=a.parse_args()
    try:
        item=DeviceInspector().install(args.serial,args.apk) if args.install else DeviceInspector().validate(args.serial)
        print(json.dumps(item,sort_keys=True));return 0
    except DeviceDeny as exc:
        print(json.dumps({'status':'BLOCKED_BY_INFRASTRUCTURE_DEVICE_NOT_VERIFIED','reason':str(exc),
                          'physical_install':'NOT_VERIFIED','no_fake_install':True},sort_keys=True))
        return 3
if __name__=='__main__':raise SystemExit(main())
