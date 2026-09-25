"""Linux TEST_ONLY process-kill fault injection, running against native qros_core.

Only independent executable paths are accepted. This test never imports broker
carriers and deliberately aborts the synthetic writer after fsync #1 through #4.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile


def run(driver: pathlib.Path, shim: pathlib.Path) -> None:
    if not driver.is_file() or not shim.is_file():
        raise SystemExit('M2_CRASH_TEST_MISSING_BINARY')
    records = []
    with tempfile.TemporaryDirectory(prefix='qros-m2-process-crash-') as tmp:
        for ordinal in range(1, 5):
            directory = pathlib.Path(tmp) / f'case{ordinal}'
            env = dict(os.environ, LD_PRELOAD=str(shim),
                       QROS_M2_KILL_AFTER_FSYNC=str(ordinal))
            killed = subprocess.run([str(driver), 'write', str(directory)],
                                    env=env, capture_output=True, text=True, timeout=8)
            inspect = subprocess.run([str(driver), 'inspect', str(directory)],
                                     capture_output=True, text=True, timeout=8)
            anchor = subprocess.run([str(driver), 'anchor-genesis', str(directory)],
                                    capture_output=True, text=True, timeout=8)
            pending = list(directory.glob('*.pending'))
            committed = list(directory.glob('*.evt'))
            lock = (directory / '.writer_lock').exists()
            assert killed.returncode == -9 and 'TEST_ONLY_FSYNC_CRASH_INJECTED' in killed.stderr, (ordinal, killed.returncode, killed.stderr)
            if ordinal == 1:
                assert inspect.returncode == 0 and 'SEQUENCE=0 ' in inspect.stdout
                assert anchor.returncode == 0 and not lock and not pending and not committed
                outcome = 'GENESIS_ANCHOR_VALID'
            elif ordinal in (2, 3):
                assert inspect.returncode != 0 and 'UNRECONCILED_PENDING_EVENT' in inspect.stderr
                assert anchor.returncode != 0 and pending and lock
                outcome = 'BLOCKED_BY_UNRECONCILED_PENDING'
            else:
                assert inspect.returncode == 0 and 'SEQUENCE=1 ' in inspect.stdout
                assert anchor.returncode != 0 and 'TRUSTED_ANCHOR_MISMATCH' in anchor.stderr
                assert len(committed) == 1 and not pending and lock
                outcome = 'COMMITTED_UNANCHORED_REJECTED'
            records.append({'kill_after_fsync': ordinal, 'outcome': outcome,
                            'pending': len(pending), 'committed': len(committed)})
    print('M2_LINUX_PROCESS_CRASH_INJECTION_PASS cases=4')
    print(json.dumps(records, sort_keys=True))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: test_crash_injection.py /abs/driver /abs/libkill.so')
    run(pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2]).resolve())
