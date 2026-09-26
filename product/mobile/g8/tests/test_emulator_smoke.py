"""G8 risk-driven emulator canaries using injected subprocess, no fake deployment."""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from emulator_smoke import EmulatorProbe, SmokeDeny, inspect_png, inspect_hierarchy, strict_apk, sha256


def png_bytes(w=1080, h=1920):
    return b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR' + struct.pack('>II', w, h) + b'\x08\x06\x00\x00\x00' + b'\x00' * 5000


class FakeAdb:
    def __init__(self, *, emulator=True, package_ok=True, crash=False):
        self.calls = []
        self.emulator, self.package_ok, self.crash = emulator, package_ok, crash

    def __call__(self, args, **_):
        self.calls.append(args)
        key = ' '.join(args)
        def result(data=b'', code=0):
            return subprocess.CompletedProcess(args, code, stdout=data, stderr=b'')
        if key == 'adb devices -l': return result(b'List of devices attached\nemulator-5554 device product:sdk\n')
        if 'getprop ro.kernel.qemu' in key: return result(b'1\n' if self.emulator else b'0\n')
        if 'getprop ro.build.version.sdk' in key: return result(b'35\n')
        if 'getprop ro.build.fingerprint' in key: return result(b'google/sdk_gphone64_x86_64/foobar\n')
        if ' install ' in key: return result(b'Success\n')
        if 'pm path' in key: return result(b'package:/data/app/qros/base.apk\n' if self.package_ok else b'')
        if 'am start' in key: return result(b'Starting: Intent ...\nStatus: ok\n')
        if 'pidof' in key: return result(b'923\n')
        if 'dumpsys activity' in key: return result(b'topResumedActivity: app.qros.qros_mobile_studio/.MainActivity')
        if 'screencap -p' in key: return result(png_bytes())
        if 'uiautomator dump' in key: return result(b'UI hierchary dumped\n')
        if ' pull ' in key:
            Path(args[-1]).write_bytes(b'<hierarchy><node text="QROS" content-desc="" /></hierarchy>')
            return result(b'1 file pulled\n')
        if 'logcat' in key:
            return result(b'FATAL EXCEPTION\nProcess: app.qros.qros_mobile_studio\n' if self.crash else b'I/flutter: drawing\n')
        return result(code=77)


class EmulatorUnitTests(unittest.TestCase):
    def test_sha256_known(self):
        self.assertEqual(sha256(b'abc'), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')

    def test_png_accepted(self):
        self.assertEqual(inspect_png(png_bytes()), (1080, 1920))

    def test_invalid_png_and_short_or_absurd_dimensions(self):
        for b in (b'', b'\x89PNG', png_bytes(1, 20), png_bytes(20000, 30000), b'JPEG' + b'0' * 6000):
            with self.subTest(b=b[:20]), self.assertRaises(SmokeDeny): inspect_png(b)

    def test_valid_hierarchy(self):
        self.assertEqual(inspect_hierarchy(b'<hierarchy><node text="QROS" /></hierarchy>')['nodes'], 1)

    def test_corrupt_hierarchy_rejected(self):
        for b in (b'', b'<hierarchy/>', b'<hierarchy><node>', b'<document><node /></document>'):
            with self.subTest(b=b), self.assertRaises(SmokeDeny): inspect_hierarchy(b)

    def test_emulator_strict_only(self):
        self.assertEqual(EmulatorProbe(run=FakeAdb()).emulator_only('emulator-5554')['android_api'], 35)
        with self.assertRaisesRegex(SmokeDeny, 'PHYSICAL_DEVICE_IS_NOT_AN_EMULATOR'):
            EmulatorProbe(run=FakeAdb(emulator=False)).emulator_only('emulator-5554')
        for serial in ('ABC1234', 'emulator-5554;rm -rf /', 'emulator-123', '../emulator-5554'):
            with self.assertRaises(SmokeDeny): EmulatorProbe(run=FakeAdb()).emulator_only(serial)

    def test_full_injected_android_run_and_receipts(self):
        fake = FakeAdb()
        with tempfile.TemporaryDirectory() as tmp:
            apk = Path(tmp) / 'exact.apk'
            apk.write_bytes(b'FROZEN_SYNTHETIC_PLACEHOLDER_NOT_AN_APK')
            with patch('emulator_smoke.strict_apk', return_value='a' * 64):
                out = Path(tmp) / 'evidence'
                got = EmulatorProbe(run=fake, pause=lambda _: None).execute(serial='emulator-5554', apk=apk, evidence=out)
                self.assertEqual(got['status'], 'PASS_REAL_EMULATOR_RUNTIME_TEST_ONLY')
                self.assertEqual(got['physical_device_install'], 'NOT_RUN')
                self.assertEqual(got['app_process_observed'], True)
                self.assertTrue((out / 'G8_ANDROID_EMULATOR_RUNTIME_RECEIPT.json').is_file())
                with self.assertRaisesRegex(SmokeDeny, 'EVIDENCE_DIRECTORY_NOT_EMPTY'):
                    EmulatorProbe(run=fake, pause=lambda _: None).execute(serial='emulator-5554', apk=apk, evidence=out)

    def test_wrong_package_or_app_crash_deny(self):
        with tempfile.TemporaryDirectory() as tmp:
            apk = Path(tmp) / 'placeholder.apk'; apk.write_bytes(b'x')
            with patch('emulator_smoke.strict_apk', return_value='a' * 64):
                for fake in (FakeAdb(package_ok=False), FakeAdb(crash=True)):
                    with self.subTest(fake=fake.__dict__), self.assertRaises(SmokeDeny):
                        EmulatorProbe(run=fake, pause=lambda _: None).execute(serial='emulator-5554', apk=apk, evidence=Path(tmp) / 'e' / ('first' if not fake.package_ok else 'second'))

    def test_reject_wrong_apk_no_adb_command(self):
        fake=FakeAdb()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'apk';p.write_bytes(b'wrong')
            with self.assertRaisesRegex(SmokeDeny,'G6_APK_SIZE_DRIFT'):
                EmulatorProbe(run=fake).execute(serial='emulator-5554', apk=p,evidence=Path(tmp)/'e')
            self.assertEqual(fake.calls,[])

    def test_reject_apk_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'apk';p.write_bytes(b'bad');link=Path(tmp)/'link';link.symlink_to(p)
            with self.assertRaisesRegex(SmokeDeny, 'G6_EXACT_APK_NOT_A_REGULAR_FILE'):
                strict_apk(link)

    def test_sdk_range_and_adb_errors(self):
        class Absent(FakeAdb):
            def __call__(self, args, **kwargs):
                if args==['adb','devices','-l']: raise FileNotFoundError()
                return super().__call__(args,**kwargs)
        with self.assertRaisesRegex(SmokeDeny,'ADB_UNAVAILABLE'):
            EmulatorProbe(run=Absent()).emulator_only('emulator-5554')


if __name__ == '__main__': unittest.main()
