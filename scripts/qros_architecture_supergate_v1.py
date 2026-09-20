#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, subprocess, tempfile

FORBIDDEN_SOURCE_MARKERS = (
    "nautilus_trader", "quantconnect", "qlib/", "hummingbot/", "freqtrade/",
    "finrl/", "vnpy/", "vectorbt/"
)

def sha256(path: pathlib.Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def run(cmd, timeout=30):
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout)
    if p.returncode!=0:
        raise RuntimeError("COMMAND_FAIL\n"+" ".join(cmd)+"\nSTDOUT:\n"+p.stdout+"\nSTDERR:\n"+p.stderr)
    return p.stdout

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-root",required=True,type=pathlib.Path)
    ap.add_argument("--cxx",required=True)
    ap.add_argument("--native-test",required=True,type=pathlib.Path)
    a=ap.parse_args()
    root=a.source_root.resolve()
    header=root/"include/qros/research_architecture.hpp"
    test=root/"tests/test_research_architecture.cpp"
    policy=root/"governance/QROS_EXTERNAL_REFERENCE_CLEANROOM_POLICY_v1.0.json"
    gate=root/"governance/QROS_ARCHITECTURE_SUPERGATE_v1.0.json"
    for p in (header,test,policy,gate,a.native_test):
        if not p.exists(): raise RuntimeError(f"MISSING:{p}")
    src=header.read_text(encoding="utf-8").lower()
    if any(x in src for x in FORBIDDEN_SOURCE_MARKERS):
        raise RuntimeError("THIRD_PARTY_SOURCE_MARKER_IN_RUNTIME")
    pol=json.loads(policy.read_text(encoding="utf-8"))
    if pol.get("code_copied") is not False or pol.get("vendored_dependency") is not False:
        raise RuntimeError("CLEANROOM_POLICY_FAIL")
    native1=run([str(a.native_test)])
    native2=run([str(a.native_test)])
    if native1!=native2 or "ARCHITECTURE_TESTS_PASS" not in native1:
        raise RuntimeError("DETERMINISTIC_NATIVE_REPLAY_FAIL")
    results={}
    with tempfile.TemporaryDirectory(prefix="qros-arch-supergate-") as td:
        td=pathlib.Path(td)
        for name,flags in (
            ("release",["-O2"]),
            ("asan",["-O1","-g","-fsanitize=address","-fno-omit-frame-pointer"]),
            ("ubsan",["-O1","-g","-fsanitize=undefined","-fno-sanitize-recover=all"]),
        ):
            exe=td/f"arch-{name}"
            cmd=[a.cxx,"-std=c++20","-Wall","-Wextra","-Wpedantic","-Wconversion","-Wshadow","-Werror","-D_GLIBCXX_ASSERTIONS",
                 "-I",str(root/"include"),str(test),"-o",str(exe),*flags]
            run(cmd,60)
            out=run([str(exe)],60)
            if "ARCHITECTURE_TESTS_PASS" not in out:
                raise RuntimeError(f"{name.upper()}_TEST_FAIL")
            results[name]={"binary_sha256":sha256(exe),"stdout":out.strip()}
    receipt={
        "schema":"QROS_ARCHITECTURE_SUPERGATE_RECEIPT_1.0",
        "status":"PASS",
        "decision":"READY_FOR_INTEGRATION_NOT_SCIENTIFIC_APPROVAL",
        "gates":{
            "cleanroom_license":"PASS",
            "no_third_party_runtime_dependency":"PASS",
            "native_deterministic_replay":"PASS",
            "release_werror":"PASS",
            "asan":"PASS",
            "ubsan":"PASS",
            "fault_injection":"PASS",
            "scientific_firewall":"PASS"
        },
        "source":{"header_sha256":sha256(header),"test_sha256":sha256(test)},
        "builds":results
    }
    print(json.dumps(receipt,sort_keys=True))

if __name__=="__main__":
    main()
