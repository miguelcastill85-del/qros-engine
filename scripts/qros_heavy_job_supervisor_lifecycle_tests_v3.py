#!/usr/bin/env python3
"""Exercise the unchanged v1 TEST_ONLY lifecycle corpus against opt-in v3."""
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import qros_heavy_job_supervisor_tests_v1 as corpus

corpus.SUP = Path(__file__).with_name('qros_heavy_job_supervisor_v3.py').resolve()
original_spec = corpus.make_spec
original_load = corpus.load_sup


def bounded_spec(*args, **kwargs):
    path, counter = original_spec(*args, **kwargs)
    spec = json.loads(path.read_text())
    spec.update(max_runtime_seconds=10, max_log_bytes=65536)
    path.write_text(json.dumps(spec, sort_keys=True, indent=2)+'\n')
    return path, counter


def load_for_legacy_lock_fixture():
    module = original_load()
    # Corpus case 11 constructs a legacy directory lock explicitly. Remove only
    # that synthetic fixture; v3 itself never steals/migrates a legacy lock.
    def release(lock):
        if isinstance(lock, Path):shutil.rmtree(lock)
        else:module.release_controller_lock(lock)
    return SimpleNamespace(process_alive=module.process_alive,
        process_birth=module.process_birth, atomic_write_json=module.atomic_write_json,
        release_controller_lock=release)


if __name__ == '__main__':
    corpus.make_spec = bounded_spec
    corpus.load_sup = load_for_legacy_lock_fixture
    corpus.main()
