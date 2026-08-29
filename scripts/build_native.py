#!/usr/bin/env python3
"""Dependency-free build adapter; production runtime remains native C++20.

The explicit CMake identity list is authoritative. No glob/latest code selection.
Python is used only to compile/test/package, never to score strategies.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(argv: list[str], env: dict[str, str], log: Path, timeout: int = 180) -> None:
    with log.open("wb") as output:
        process = subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                   stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            status = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise RuntimeError(f"build timed out; process group stopped; log={log}") from None
    if status:
        with log.open("rb") as result:
            result.seek(max(0, log.stat().st_size - 14000))
            print(result.read().decode(errors="replace"), flush=True)
        raise RuntimeError(f"build failed: {argv[0]} status={status}; log={log}")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="build-release")
    parser.add_argument("--sanitize", choices=["address", "undefined"])
    parser.add_argument("--static", action="store_true")
    parser.add_argument("--jobs", type=int, default=3)
    args = parser.parse_args()
    if args.jobs < 1 or args.jobs > 8:
        raise SystemExit("jobs must be 1..8")
    out = (ROOT / args.out).resolve()
    if not out.is_relative_to(ROOT) or out == ROOT:
        raise SystemExit("build output must be beneath this project")
    for name in ["obj", "logs", "tmp", "generated/qros"]:
        (out / name).mkdir(parents=True, exist_ok=True)
    (out / "BUILD_RECEIPT.json").unlink(missing_ok=True)
    cmake = (ROOT / "CMakeLists.txt").read_text()
    identity = re.search(r"set\(QROS_IDENTITY_FILES\s+(.*?)\)", cmake, re.S)
    if not identity:
        raise SystemExit("explicit identity list missing")
    files = identity.group(1).split()
    if len(files) != len(set(files)):
        raise SystemExit("duplicate identity paths")
    bindings = {name: sha(ROOT / name) for name in files}
    material = "QROS_SOURCE_ROOT_V1\n" + "".join(f"{name}={bindings[name]}\n" for name in files)
    source_root = hashlib.sha256(material.encode()).hexdigest()
    compiler = shutil.which("g++")
    if not compiler:
        raise SystemExit("g++ not available")
    compiler = str(Path(compiler).resolve())
    env = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "TZ": "UTC",
           "TMPDIR": str(out / "tmp"), "SOURCE_DATE_EPOCH": "0"}
    compiler_version = subprocess.check_output([compiler, "-dumpfullversion"], env=env, text=True).strip()
    flags = ["-std=c++20", "-Wall", "-Wextra", "-Wpedantic", "-Wconversion", "-Wshadow", "-Werror",
             "-D_GLIBCXX_ASSERTIONS", "-Iinclude", "-I" + str(out / "generated"),
             f"-ffile-prefix-map={ROOT}=.", f"-fmacro-prefix-map={ROOT}=."]
    flags += ["-O1", "-g", "-fno-omit-frame-pointer", "-fsanitize=" + args.sanitize] if args.sanitize else ["-O2", "-g0"]
    link_flags = ["-Wl,--build-id=none"]
    if args.static:
        if args.sanitize:
            raise SystemExit("static sanitizer build unsupported")
        link_flags.append("-static")
    contract = {"schema": "QROS_MANUAL_BUILD_CONTRACT_V1", "source_root": source_root,
                "compiler": compiler, "compiler_sha256": sha(Path(compiler)), "compiler_version": compiler_version,
                "flags": [x.replace(str(out), "<BUILD>").replace(str(ROOT), "<SOURCE>") for x in flags],
                "link_flags": link_flags, "system": platform.system(), "machine": platform.machine(),
                "build_adapter_sha256": sha(Path(__file__))}
    contract_hash = hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    replacements = {"PROJECT_VERSION": "0.6.0", "QROS_SOURCE_ROOT_SHA256": source_root,
                    "CMAKE_BUILD_TYPE": args.sanitize or "Release", "QROS_BUILD_CONTRACT_SHA256": contract_hash,
                    "CMAKE_CXX_COMPILER_ID": "GNU", "CMAKE_CXX_COMPILER_VERSION": compiler_version,
                    "CMAKE_SYSTEM_NAME": platform.system(), "CMAKE_SYSTEM_PROCESSOR": platform.machine()}
    header = (ROOT / "cmake/build_identity.hpp.in").read_text()
    for key, value in replacements.items():
        header = header.replace("@" + key + "@", value)
    if "@" in header:
        raise SystemExit("unresolved identity template")
    (out / "generated/qros/build_identity.hpp").write_text(header)
    sources = [x for x in files if x.startswith("src/") and x.endswith(".cpp")]
    test_sources = ["tests/test_core.cpp", "tests/test_pipeline.cpp"]
    test_bindings = {name: sha(ROOT / name) for name in test_sources}
    def compile_one(name: str) -> Path:
        obj = out / "obj" / (name.replace("/", "_") + ".o")
        argv = [compiler, *flags, "-frandom-seed=" + sha(ROOT / name), "-c", name, "-o", str(obj)]
        run(argv, env, out / "logs" / (obj.stem + ".log"))
        print("COMPILED " + name, flush=True)
        return obj
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        compiled = list(pool.map(compile_one, sources + test_sources))
    objects = dict(zip(sources + test_sources, compiled))
    core = [str(objects[name]) for name in sources if name != "src/main.cpp"]
    for output_name, main_source in [("qros", "src/main.cpp"), ("qros_tests", "tests/test_core.cpp"), ("qros_pipeline_tests", "tests/test_pipeline.cpp")]:
        run([compiler, *flags, *core, str(objects[main_source]), *link_flags, "-o", str(out / output_name)], env, out / "logs" / (output_name + "_link.log"))
        print("LINKED " + output_name, flush=True)
    after = {name: sha(ROOT / name) for name in files}
    if after != bindings or test_bindings != {name: sha(ROOT / name) for name in test_sources}:
        raise SystemExit("source changed during build; binaries not promoted")
    receipt = {"status": "BUILD_PASS", "contract": contract, "build_contract_sha256": contract_hash,
               "source_root_sha256": source_root, "source_bindings": bindings,
               "test_source_bindings": test_bindings,
               "executables": {name: sha(out / name) for name in ["qros", "qros_tests", "qros_pipeline_tests"]},
               "tests_executed": False, "mt5_compiled": False}
    (out / "BUILD_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": "BUILD_PASS", "output": str(out), "entrypoint_sha256": receipt["executables"]["qros"]}), flush=True)

if __name__ == "__main__":
    main()
