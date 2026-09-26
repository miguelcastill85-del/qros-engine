from __future__ import annotations
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import android_device_gate as device
import release_gate as release

class MockCompleted:
    def __init__(self,stdout:str,returncode:int=0):
        self.stdout=stdout;self.stderr='';self.returncode=returncode

class DeviceCanaries(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.qemu='0'
        self.present=True
        self.fingerprint='vendor/hardware/device:16/release-keys'
        self.model='QROS Test Physical'
        self.inspector=device.DeviceInspector(self.mock)
    def mock(self,argv,**kwargs):
        self.calls.append(argv)
        a=argv
        if a[1:]==['devices','-l']:
            return MockCompleted('List of devices attached\nSERIAL1 device product:physical model:phone\n' if self.present else 'List of devices attached\n')
        if 'getprop' in a:
            prop=a[-1]
            return MockCompleted({'ro.kernel.qemu':self.qemu,'ro.build.fingerprint':self.fingerprint,
                                  'ro.product.model':self.model,'ro.build.version.sdk':'35'}.get(prop,''))
        if 'install' in a:return MockCompleted('Success')
        if 'pm' in a:return MockCompleted('package:/data/app/package.apk')
        if 'am' in a:return MockCompleted('Starting: Intent')
        return MockCompleted('',1)
    def test_adb_physical_property_inspection_does_not_install(self):
        r=self.inspector.validate('SERIAL1')
        self.assertEqual(r['physical_install'],'NOT_RUN')
        self.assertFalse(any('install' in x for x in self.calls))
    def test_refuse_emulator(self):
        self.qemu='1'
        with self.assertRaisesRegex(device.DeviceDeny,'EMULATOR'):self.inspector.validate('SERIAL1')
    def test_refuse_generic_fingerprint(self):
        self.fingerprint='generic/sdk_gphone'
        with self.assertRaisesRegex(device.DeviceDeny,'EMULATOR'):self.inspector.validate('SERIAL1')
    def test_no_device_does_not_forge_evidence(self):
        self.present=False
        with self.assertRaisesRegex(device.DeviceDeny,'NOT_CONNECTED'):self.inspector.validate('SERIAL1')
    def test_serial_is_explicit(self):
        with self.assertRaisesRegex(device.DeviceDeny,'SERIAL'):self.inspector.validate('')
    def test_wrong_apk_never_installed(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'invalid.apk';p.write_bytes(b'NOT_G6')
            with self.assertRaisesRegex(device.DeviceDeny,'EXACT_BYTES'):self.inspector.install('SERIAL1',p)
        self.assertFalse(any('install' in x for x in self.calls))
    def test_mocked_install_not_real_device_claim(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'sample.apk';p.write_bytes(b'G6_FAKE_FOR_UNIT_TEST')
            with patch.object(device,'EXPECTED_G6_SHA256',hashlib.sha256(p.read_bytes()).hexdigest()):
                r=self.inspector.install('SERIAL1',p)
                self.assertEqual(r['user_visual_pairing'],'NOT_ATTESTED')
                self.assertEqual(r['physical_install'],'ADB_INSTALL_AND_LAUNCH_OBSERVED')
        # This test is a subprocess mock, NOT real hardware evidence.

class ReleaseCanaries(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.apk=Path(self.dir.name)/'sample.apk'
        with zipfile.ZipFile(self.apk,'w') as f:f.writestr('AndroidManifest.xml',b'FAKE_FOR_CI_UNIT_TEST')
        self.patches=[patch.object(release,'EXPECTED_SHA',hashlib.sha256(self.apk.read_bytes()).hexdigest()),
                      patch.object(release,'EXPECTED_BYTES',self.apk.stat().st_size)]
        for x in self.patches:x.start();self.addCleanup(x.stop)
    def run_signer(self,*,debug=True,returncode=0,has_cert=True):
        lines=['Verifies','Signer #1 certificate DN: CN=Android Debug,O=Android,C=US' if debug else 'Signer #1 certificate DN: CN=Production']
        if has_cert: lines.append('Signer #1 certificate SHA-256 digest: '+'a'*64)
        return lambda *args,**kwargs:MockCompleted('\n'.join(lines),returncode)
    def test_debug_signature_verified_but_rejected_for_release(self):
        r=release.inspect(self.apk,run=self.run_signer())
        self.assertFalse(r['release_eligible'])
        self.assertIn('DEBUG',r['signer_class'])
    def test_non_debug_cert_not_auto_release(self):
        r=release.inspect(self.apk,run=self.run_signer(debug=False))
        self.assertFalse(r['release_eligible'])
    def test_stderr_certificate_digest_accepted_without_relaxing_release_gate(self):
        def signer(*args,**kwargs):
            response=MockCompleted('Verifies\nSigner #1 certificate DN: CN=Android Debug')
            response.stderr='Signer #1 certificate SHA-256 digest: '+'a'*64
            return response
        item=release.inspect(self.apk,run=signer)
        self.assertFalse(item['release_eligible'])
    def test_alternative_certificate_digest_label(self):
        def signer(*args,**kwargs):
            return MockCompleted('Signer #1 cert SHA-256: '+'a'*64+'\nSigner #1 certificate DN: CN=Android Debug')
        item=release.inspect(self.apk,run=signer)
        self.assertFalse(item['release_eligible'])
    def test_bad_sha_blocks_before_external_signer(self):
        with patch.object(release,'EXPECTED_SHA','0'*64):
            with self.assertRaisesRegex(release.ReleaseDeny,'SHA'):release.inspect(self.apk,run=self.run_signer())
    def test_apksigner_invalid_blocks(self):
        with self.assertRaisesRegex(release.ReleaseDeny,'SIGNATURE_INVALID'):
            release.inspect(self.apk,run=self.run_signer(returncode=1))
    def test_missing_certificate_blocks(self):
        with self.assertRaisesRegex(release.ReleaseDeny,'CERTIFICATE_MISSING'):
            release.inspect(self.apk,run=self.run_signer(has_cert=False))

if __name__=='__main__':unittest.main()
