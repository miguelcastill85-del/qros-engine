#!/usr/bin/env python3
"""Package a verified source/binary tree, extract it and execute its own demos.

Creates a deterministic ZIP and a standalone audit copy with the actual archive
QA result. It never includes research data, build objects or transient runs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PREFIX="QROS_ENGINE_v0_6"
DIRECTORIES=["bin","cmake","control","docs","evidence","examples","include","profiles","reference","scripts","src","tests"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--verify-dir", type=Path, required=True)
    parser.add_argument("--audit-report", type=Path, required=True)
    args=parser.parse_args()
    archive, verify, audit=args.zip.resolve(),args.verify_dir.resolve(),args.audit_report.resolve()
    if archive.exists() or verify.exists():
        raise SystemExit("archive and verification directory must be new")
    build=json.loads((ROOT/"bin/BUILD_RECEIPT.json").read_text())
    for name,expected in build["source_bindings"].items():
        if sha(ROOT/name)!=expected:
            raise SystemExit("runtime source changed: "+name)
    for name,expected in build["executables"].items():
        if sha(ROOT/"bin"/name)!=expected:
            raise SystemExit("binary changed: "+name)
    for profile in ["release","asan","ubsan"]:
        report=json.loads((ROOT/f"evidence/verification/{profile}/VERIFICATION_REPORT.json").read_text())
        if report["status"]!="PASS" or len(report["suites"])!=12 or report["source_root_sha256"]!=build["source_root_sha256"]:
            raise SystemExit("verification not complete for current sources: "+profile)
        for name,expected in report["test_and_reference_bindings"].items():
            if sha(ROOT/name)!=expected:
                raise SystemExit("test/reference changed: "+name)
    paths=[ROOT/"README.md",ROOT/"CMakeLists.txt"]
    for directory in DIRECTORIES:
        for current, dirs, names in os.walk(ROOT/directory,followlinks=False):
            dirs[:]=sorted(d for d in dirs if d!="__pycache__" and not d.startswith("."))
            for d in dirs:
                if (Path(current)/d).is_symlink():
                    raise SystemExit("symlink in package tree")
            for name in sorted(names):
                p=Path(current)/name
                if name.startswith(".") or name.endswith(".pyc"):
                    continue
                if p.is_symlink() or not p.is_file():
                    raise SystemExit("non-regular package input: "+str(p))
                paths.append(p)
    paths.sort(key=lambda p:p.relative_to(ROOT).as_posix())
    names=[p.relative_to(ROOT).as_posix() for p in paths]
    if len(names)!=len({name.casefold() for name in names}):
        raise SystemExit("duplicate or case-colliding package paths")
    manifest="".join(sha(p)+"  "+p.relative_to(ROOT).as_posix()+"\n" for p in paths)
    (ROOT/"MANIFEST.sha256").write_text(manifest)
    (ROOT/"MANIFEST.sha256.sha256").write_text(sha(ROOT/"MANIFEST.sha256")+"  MANIFEST.sha256\n")
    paths += [ROOT/"MANIFEST.sha256",ROOT/"MANIFEST.sha256.sha256"]
    archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as bundle:
        for p in sorted(paths,key=lambda p:p.relative_to(ROOT).as_posix()):
            info=zipfile.ZipInfo(PREFIX+"/"+p.relative_to(ROOT).as_posix(),date_time=(1980,1,1,0,0,0))
            info.create_system=3
            mode=0o755 if p.parent==ROOT/"bin" and p.name!="BUILD_RECEIPT.json" else 0o644
            info.external_attr=(stat.S_IFREG|mode)<<16
            info.compress_type=zipfile.ZIP_DEFLATED
            bundle.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    verify.mkdir(parents=True)
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise RuntimeError("ZIP CRC failure")
        entries=bundle.infolist()
        if len(entries)>5000 or sum(e.file_size for e in entries)>512*1024**2:
            raise RuntimeError("package verification resource budget")
        for entry in entries:
            name=PurePosixPath(entry.filename)
            if name.is_absolute() or ".." in name.parts or name.parts[0]!=PREFIX or not stat.S_ISREG(entry.external_attr>>16):
                raise RuntimeError("unsafe archive entry")
            p=verify/Path(*name.parts);p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(bundle.read(entry));p.chmod((entry.external_attr>>16)&0o777)
    unpacked=verify/PREFIX
    for line in (unpacked/"MANIFEST.sha256").read_text().splitlines():
        expected,name=line.split("  ",1)
        if sha(unpacked/name)!=expected:
            raise RuntimeError("unpacked manifest mismatch: "+name)
    if sha(unpacked/"MANIFEST.sha256")!=(unpacked/"MANIFEST.sha256.sha256").read_text().split()[0]:
        raise RuntimeError("manifest root mismatch")
    (verify/"tmp").mkdir()
    env=dict(PATH="/usr/bin:/bin",LANG="C",LC_ALL="C",TZ="UTC",TMPDIR=str(verify/"tmp"),PYTHONDONTWRITEBYTECODE="1")
    checks=[]
    jobs=[("native_core",[unpacked/"bin/qros_tests"]),("native_pipeline",[unpacked/"bin/qros_pipeline_tests"])]
    jobs += [(asset,[sys.executable,unpacked/"scripts/run_demo.py","--example",asset,"--out",verify/("demo-"+asset)]) for asset in ["nqx","xau"]]
    for name,command in jobs:
        log=verify/(name+".log")
        with log.open("wb") as stream:
            result=subprocess.run(list(map(str,command)),cwd=unpacked,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,timeout=120)
        if result.returncode:
            raise RuntimeError("unpacked execution failed: "+name+"; log="+str(log))
        checks.append(dict(name=name,status="PASS",log_sha256=sha(log)))
    qa=dict(schema="QROS_RELEASE_PACKAGE_QA_V1",status="PASS",archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,
            archive_entries=len(paths),manifest_sha256=sha(unpacked/"MANIFEST.sha256"),entrypoint_sha256=sha(unpacked/"bin/qros"),
            unpacked_execution=checks,research_approved=False,mt5_executed=False)
    (verify/"PACKAGE_QA.json").write_text(json.dumps(qa,indent=2)+"\n")
    audit.parent.mkdir(parents=True,exist_ok=True)
    audit.write_text((ROOT/"docs/AUDITORIA_v0_6.md").read_text()+"\n## Verificación del archivo entregado\n\n"+
                    f"ZIP extraído, {qa['archive_entries']} entradas verificadas y pruebas nativas más ambas demos ejecutadas desde la copia extraída: PASS.\n\n"+
                    f"SHA-256 del ZIP: `{qa['archive_sha256']}`. Tamaño: {qa['archive_bytes']:,} bytes.\n\n"+
                    "Este apéndice corresponde al archivo de entrega ya comprobado; no es una aprobación científica.\n")
    print(json.dumps(qa,indent=2),flush=True)


if __name__=="__main__":
    main()
