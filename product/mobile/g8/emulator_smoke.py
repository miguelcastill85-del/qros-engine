"""G8: run the exact, immutable G6 Android APK on a REAL Android emulator.

A passing result proves emulator installation/start, PID, PNG screenshot and
runtime activity; it never proves physical-device installation, TLS pairing or
scientific fitness. No credentials, telemetry services or paid resources.
"""
from __future__ import annotations
import argparse
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import time
import xml.etree.ElementTree as ET
from PIL import Image, UnidentifiedImageError
from typing import Callable

APK_SHA256 = '2c4053a27fa5692871db717c4c5bb42e1284673b49f13fa41db6a7e2b0b52c97'
APK_BYTES = 141623410
PACKAGE = 'app.qros.qros_mobile_studio'
ACTIVITY = PACKAGE + '/.MainActivity'
SERIAL_RE = re.compile(r'emulator-[0-9]{4,6}\Z')
PNG_HEADER = b'\x89PNG\r\n\x1a\n'


class SmokeDeny(RuntimeError):
    pass


def deny(code: str) -> None:
    raise SmokeDeny('QROS_G8_FAIL_CLOSED:' + code)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_apk(apk: Path) -> str:
    if apk.is_symlink() or not apk.is_file():
        deny('G6_EXACT_APK_NOT_A_REGULAR_FILE')
    if apk.stat().st_size != APK_BYTES:
        deny('G6_APK_SIZE_DRIFT')
    h = hashlib.sha256()
    with apk.open('rb') as f:
        for chunk in iter(lambda: f.read(2 ** 20), b''):
            h.update(chunk)
    if h.hexdigest() != APK_SHA256:
        deny('G6_APK_SHA256_DRIFT')
    return h.hexdigest()


def inspect_png(data: bytes) -> tuple[int, int]:
    if not isinstance(data, bytes) or len(data) < 4096 or data[:8] != PNG_HEADER:
        deny('SCREENSHOT_PNG_INVALID_OR_EMPTY')
    if data[12:16] != b'IHDR':
        deny('SCREENSHOT_MISSING_IHDR')
    width, height = struct.unpack('>II', data[16:24])
    if not 320 <= width <= 4320 or not 480 <= height <= 4320:
        deny('SCREENSHOT_DIMENSIONS_OUT_OF_RANGE')
    return width, height



def dark_content_fraction(data: bytes) -> float:
    """Conservatively reject Flutter's observed WHITE startup splash.

    The frozen QROS G6 Flutter ThemeData scaffold is dark (#09111F). This
    color check confirms the actual rendered screen, not just Android PID.
    It does NOT prove navigation, network pairing or physical hardware.
    """
    try:
        with Image.open(BytesIO(data)) as im:
            im.verify()
        with Image.open(BytesIO(data)) as im:
            img = im.convert('RGB')
            img.thumbnail((72, 144), Image.Resampling.NEAREST)
            pixels = list(img.getdata())
    except (OSError, ValueError, UnidentifiedImageError):
        deny('SCREENSHOT_PNG_DECODE_FAILED')
    if not pixels:
        deny('SCREENSHOT_NO_PIXELS')
    dark = sum(1 for r, g, b in pixels if r < 100 and g < 110 and b < 125)
    fraction = dark / len(pixels)
    if fraction < 0.30:
        deny('QROS_DARK_FLUTTER_UI_NOT_RENDERED_SPLASH_ONLY')
    return round(fraction, 4)


def inspect_hierarchy(data: bytes) -> dict:
    if not isinstance(data, bytes) or not 40 <= len(data) <= 2_000_000:
        deny('UI_HIERARCHY_MISSING_OR_OVERSIZED')
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        deny('UI_HIERARCHY_XML_CORRUPT')
    if root.tag != 'hierarchy' or not root.findall('.//node'):
        deny('UI_HIERARCHY_EMPTY')
    nodes = root.findall('.//node')
    qros_visible = any('QROS' in (n.get('text') or '') or 'QROS' in (n.get('content-desc') or '') for n in nodes)
    return {'nodes': len(nodes), 'qros_accessibility_text_observed': qros_visible}


class EmulatorProbe:
    def __init__(self, run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                 pause: Callable[[float], None] = time.sleep):
        self.run, self.pause = run, pause

    def cmd(self, serial: str, *args: str, timeout: int = 45) -> bytes:
        try:
            proc = self.run(['adb', '-s', serial, *args], capture_output=True, timeout=timeout, check=False)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            deny('ADB_MISSING_OR_TIMEOUT')
        if proc.returncode:
            deny('ADB_COMMAND_FAILED:' + args[0])
        return proc.stdout if isinstance(proc.stdout, bytes) else proc.stdout.encode()

    def emulator_only(self, serial: str) -> dict:
        if not isinstance(serial, str) or SERIAL_RE.fullmatch(serial) is None:
            deny('EMULATOR_SERIAL_REQUIRED')
        try:
            devices = self.run(['adb', 'devices', '-l'], capture_output=True, timeout=20, check=False)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            deny('ADB_UNAVAILABLE')
        if devices.returncode:
            deny('ADB_DEVICES_ERROR')
        lines = devices.stdout.decode(errors='replace').splitlines()[1:]
        eligible = [line.split()[:2] for line in lines if line.strip()]
        if eligible.count([serial, 'device']) != 1:
            deny('EMULATOR_NOT_UNIQUELY_AUTHORIZED')
        prop = lambda key: self.cmd(serial, 'shell', 'getprop', key).decode().strip()
        if prop('ro.kernel.qemu') != '1':
            deny('PHYSICAL_DEVICE_IS_NOT_AN_EMULATOR')
        sdk = prop('ro.build.version.sdk')
        fingerprint = prop('ro.build.fingerprint')
        if not sdk.isdecimal() or not 26 <= int(sdk) <= 45 or not fingerprint:
            deny('EMULATOR_OS_IDENTITY_MISSING')
        return {'serial_class': 'EMULATOR', 'android_api': int(sdk),
                'fingerprint_sha256': sha256(fingerprint.encode())}

    def execute(self, *, serial: str, apk: Path, evidence: Path) -> dict:
        apk_hash = strict_apk(apk)
        info = self.emulator_only(serial)
        if evidence.is_symlink():
            deny('EVIDENCE_SYMLINK')
        evidence.mkdir(parents=True, exist_ok=True)
        if any(evidence.iterdir()):
            deny('EVIDENCE_DIRECTORY_NOT_EMPTY')
        installed = self.cmd(serial, 'install', '-r', '-t', str(apk), timeout=180).decode(errors='replace')
        if 'Success' not in installed:
            deny('ADB_INSTALL_NOT_CONFIRMED')
        paths = self.cmd(serial, 'shell', 'pm', 'path', PACKAGE).decode(errors='replace')
        if not any(line.startswith('package:') for line in paths.splitlines()):
            deny('APK_PACKAGE_MISSING_AFTER_INSTALL')
        launch = self.cmd(serial, 'shell', 'am', 'start', '-W', '-n', ACTIVITY, timeout=40).decode(errors='replace')
        if 'Error' in launch or ('Status: ok' not in launch and 'Starting:' not in launch and 'Warning:' not in launch):
            deny('ANDROID_MAIN_ACTIVITY_LAUNCH_FAILED')
        pid = ''
        for _ in range(15):
            try:
                pid = self.cmd(serial, 'shell', 'pidof', '-s', PACKAGE).decode().strip()
            except SmokeDeny:
                pid = ''
            if pid.isdecimal():
                break
            self.pause(2)
        if not pid.isdecimal():
            deny('ANDROID_APPLICATION_PID_NOT_OBSERVED')
        self.pause(2)
        # First CI run demonstrated that a valid PID can coexist with a WHITE
        # Flutter splash screen. Require actual dark-themed G6 UI pixels.
        png = b''
        width = height = 0
        dark_fraction = 0.0
        for _ in range(24):
            activity = self.cmd(serial, 'shell', 'dumpsys', 'activity', 'activities', timeout=45)
            resumed = any(PACKAGE.encode() in line and (b'topResumedActivity' in line or b'mResumedActivity' in line or b'ResumedActivity' in line) for line in activity.splitlines())
            if not resumed:
                self.pause(2)
                continue
            png = self.cmd(serial, 'exec-out', 'screencap', '-p', timeout=45)
            width, height = inspect_png(png)
            # Keep a raw screen on failures so the cause can be diagnosed.
            (evidence / 'G8_ANDROID_EMULATOR_SCREEN.png').write_bytes(png)
            try:
                dark_fraction = dark_content_fraction(png)
                break
            except SmokeDeny as exc:
                if 'SPLASH_ONLY' not in str(exc):
                    raise
                self.pause(2)
        if dark_fraction < 0.30:
            deny('DARK_G6_UI_NOT_RENDERED_WITHIN_BOUND')
        shot = evidence / 'G8_ANDROID_EMULATOR_SCREEN.png'
        # UIAutomator can report an error while exiting 0. Do not infer a
        # successful dump from the process code or silently skip this gate.
        xml_file = evidence / 'G8_ANDROID_UI_HIERARCHY.xml'
        hierarchy = None
        diagnostics = []
        for _ in range(4):
            raw = self.cmd(serial, 'shell', 'uiautomator', 'dump', '/sdcard/qros_g8_hierarchy.xml', timeout=65)
            message = raw.decode(errors='replace')[:1000]
            if 'UI hierchary dumped to:' not in message and 'UI hierarchy dumped to:' not in message:
                diagnostics.append('DUMP_DID_NOT_REPORT_SUCCESS:' + message[:120])
                self.pause(2)
                continue
            try:
                candidate = self.cmd(serial, 'exec-out', 'cat', '/sdcard/qros_g8_hierarchy.xml', timeout=40)
                hierarchy = inspect_hierarchy(candidate)
                xml_file.write_bytes(candidate)
                break
            except SmokeDeny as exc:
                diagnostics.append(str(exc)[:160])
                self.pause(2)
        if hierarchy is None:
            (evidence / 'G8_UI_DUMP_DIAGNOSTIC.json').write_text(json.dumps({'errors': diagnostics}, sort_keys=True)+'\n')
            deny('ANDROID_UI_HIERARCHY_UNAVAILABLE_AFTER_REAL_RENDER')
        logs = self.cmd(serial, 'logcat', '-d', '-t', '1800', '-v', 'brief', timeout=45).decode(errors='replace')
        # Only a crash attributed to the app fails the gate. Other emulator/SDK
        # errors are unrelated and not evidence of an app crash.
        for m in re.finditer('FATAL EXCEPTION', logs):
            if ('Process: ' + PACKAGE) in logs[m.start():m.start() + 650]:
                deny('APP_ATTRIBUTABLE_FATAL_EXCEPTION')
        receipt = {'schema': 'QROS_MOBILE_G8_ANDROID_EMULATOR_RUNTIME_RECEIPT_V1',
                   'status': 'PASS_REAL_EMULATOR_RUNTIME_TEST_ONLY',
                   'source_g6_apk_sha256': apk_hash,
                   'source_g6_apk_bytes': APK_BYTES,
                   'package': PACKAGE, 'launch_activity': ACTIVITY,
                   'adb_install': 'SUCCESS', 'app_process_observed': True,
                   'activity_resumed_evidence': 'ACTIVITY_DUMPSYS_PACKAGE_PRESENT',
                   'screen_png_sha256': sha256(png), 'screen_png_bytes': len(png),
                   'screen_width': width, 'screen_height': height,
                   'dark_g6_ui_fraction': dark_fraction,
                   'ui_hierarchy_sha256': sha256(xml_file.read_bytes()),
                   **hierarchy, **info,
                   'physical_device_install': 'NOT_RUN',
                   'real_tls_pairing': 'NOT_RUN',
                   'external_independent_witness': 'NOT_DEPLOYED',
                   'debug_apk_release_eligible': False,
                   'market_data': 'NONE', 'economic_backtests': 0,
                   'holdout_open': False, 'ga2_open': False, 'mt5': 'NOT_RUN'}
        out = evidence / 'G8_ANDROID_EMULATOR_RUNTIME_RECEIPT.json'
        payload = (json.dumps(receipt, sort_keys=True, indent=2) + '\n').encode()
        tmp = out.with_suffix('.json.tmp')
        with tmp.open('xb') as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, out)
        if out.read_bytes() != payload:
            deny('EVIDENCE_RECEIPT_READBACK_FAIL')
        return receipt


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--serial', default='emulator-5554')
    p.add_argument('--apk', required=True, type=Path)
    p.add_argument('--evidence', required=True, type=Path)
    args = p.parse_args()
    try:
        print(json.dumps(EmulatorProbe().execute(serial=args.serial, apk=args.apk,
                                                 evidence=args.evidence), sort_keys=True))
        return 0
    except SmokeDeny as exc:
        print(json.dumps({'status': 'BLOCKED_BY_INFRASTRUCTURE_OR_RUNTIME',
                          'reason': str(exc), 'physical_install': 'NOT_VERIFIED'}, sort_keys=True))
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
