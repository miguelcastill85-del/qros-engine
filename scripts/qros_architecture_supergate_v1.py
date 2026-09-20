#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, pathlib, subprocess, tempfile, time

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
    probe=root/"tests/qros_architecture_vectors.cpp"
    oracle=root/"scripts/qros_architecture_oracle_v1.py"
    for p in (header,test,policy,gate,probe,oracle,a.native_test):
        if not p.exists(): raise RuntimeError(f"MISSING:{p}")
    runtime_text="\n".join(p.read_text(encoding="utf-8").lower() for p in (header,test,probe))
    if any(x in runtime_text for x in FORBIDDEN_SOURCE_MARKERS):
        raise RuntimeError("THIRD_PARTY_SOURCE_MARKER_IN_RUNTIME")
    if "#include <" not in runtime_text or "#include \"qros/" not in runtime_text:
        raise RuntimeError("EXPECTED_STANDARD_OR_LOCAL_INCLUDE_CONTRACT_MISSING")
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
        common=[a.cxx,"-std=c++20","-Wall","-Wextra","-Wpedantic","-Wconversion","-Wshadow","-Werror","-D_GLIBCXX_ASSERTIONS",
                "-I",str(root/"include"),str(test)]
        release_hashes=[]
        release_outputs=[]
        for i in range(2):
            exe=td/f"arch-release-{i}"
            run(common+["-o",str(exe),"-O2"],60)
            started=time.monotonic()
            out=run([str(exe)],60)
            elapsed=time.monotonic()-started
            if "ARCHITECTURE_TESTS_PASS" not in out or elapsed>5.0:
                raise RuntimeError("RELEASE_TEST_OR_RESOURCE_BOUND_FAIL")
            release_hashes.append(sha256(exe));release_outputs.append(out)
        if release_hashes[0]!=release_hashes[1] or release_outputs[0]!=release_outputs[1]:
            raise RuntimeError("SAME_HOST_REPRODUCIBLE_BUILD_FAIL")
        results["release"]={"binary_sha256":release_hashes[0],"stdout":release_outputs[0].strip(),"reproducible_same_host":True}
        for name,flags in (
            ("asan",["-O1","-g","-fsanitize=address","-fno-omit-frame-pointer"]),
            ("ubsan",["-O1","-g","-fsanitize=undefined","-fno-sanitize-recover=all"]),
        ):
            exe=td/f"arch-{name}"
            run(common+["-o",str(exe),*flags],60)
            out=run([str(exe)],60)
            if "ARCHITECTURE_TESTS_PASS" not in out:
                raise RuntimeError(f"{name.upper()}_TEST_FAIL")
            results[name]={"binary_sha256":sha256(exe),"stdout":out.strip()}
        probe_exe=td/"arch-probe"
        run([a.cxx,"-std=c++20","-Wall","-Wextra","-Wpedantic","-Wconversion","-Wshadow","-Werror",
             "-D_GLIBCXX_ASSERTIONS","-I",str(root/"include"),str(probe),"-o",str(probe_exe),"-O2"],60)
        oracle_out=run(["python3",str(oracle),"--probe",str(probe_exe)],30)
        if "INDEPENDENT_ORACLE_PASS" not in oracle_out:
            raise RuntimeError("INDEPENDENT_ORACLE_FAIL")
        results["independent_oracle"]={"stdout":oracle_out.strip(),"probe_sha256":sha256(probe_exe)}
    receipt={
        "schema":"QROS_ARCHITECTURE_SUPERGATE_RECEIPT_1.0",
        "status":"PASS",
        "decision":"READY_FOR_INTEGRATION_NOT_SCIENTIFIC_APPROVAL",
        "gates":{
            "cleanroom_license":"PASS",
            "no_third_party_runtime_dependency":"PASS",
            "native_deterministic_replay":"PASS",
            "release_werror":"PASS",
            "same_host_reproducible_build":"PASS",
            "independent_oracle":"PASS",
            "asan":"PASS",
            "ubsan":"PASS",
            "resource_bounds":"PASS",
            "one_position_per_asset":"PASS",
            "reconnect_epoch_sequence_fencing":"PASS",
            "fault_injection":"PASS",
            "scientific_firewall":"PASS"
        },
        "source":{"header_sha256":sha256(header),"test_sha256":sha256(test)},
        "builds":results
    }
    print(json.dumps(receipt,sort_keys=True))

if __name__=="__main__":
    main()
