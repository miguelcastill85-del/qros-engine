#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, re, subprocess, sys, uuid
from pathlib import Path
from typing import Any

SCHEMA="QROS_RECURSIVE_EFFECT_EXECUTOR_1.0"
INTENT_SCHEMA="QROS_RECURSIVE_EFFECT_INTENT_1.0"
CHUNK=8*1024*1024

def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00","Z")

def canonical(x:Any)->bytes:
    return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(CHUNK),b""): h.update(b)
    return h.hexdigest()

def sha256_obj(x)->str:
    return hashlib.sha256(canonical(x)).hexdigest()

def atomic_json(p:Path,obj:dict):
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+".tmp."+uuid.uuid4().hex)
    data=json.dumps(obj,sort_keys=True,indent=2,ensure_ascii=False).encode()+b"\n"
    with tmp.open("wb") as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)

def load_json(p:Path)->dict:
    v=json.loads(p.read_text())
    if not isinstance(v,dict): raise RuntimeError("JSON_ROOT_NOT_OBJECT")
    return v

def process_birth(pid:int):
    if pid<=0 or os.name!="posix": return None
    try:
        raw=Path(f"/proc/{pid}/stat").read_text()
        rest=raw[raw.rfind(") ")+2:].split()
        if not rest or rest[0]=="Z": return None
        boot=Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        return f"linux:{boot}:{rest[19]}"
    except Exception:
        return None

def process_alive(pid:int,birth):
    return birth is not None and process_birth(pid)==birth

def validate_intent(intent:dict)->str:
    req={"schema","effect_id","command","expected_receipt"}
    if not req.issubset(intent): raise RuntimeError("INTENT_FIELDS_MISSING")
    if intent["schema"]!=INTENT_SCHEMA: raise RuntimeError("INTENT_SCHEMA")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{8,128}",str(intent["effect_id"])): raise RuntimeError("EFFECT_ID")
    if not isinstance(intent["command"],list) or not intent["command"] or not all(isinstance(x,str) for x in intent["command"]): raise RuntimeError("COMMAND")
    if not isinstance(intent["expected_receipt"],dict): raise RuntimeError("EXPECTED_RECEIPT")
    return sha256_obj(intent)

def expand_command(command:list[str],effect_dir:Path):
    repl={"{effect_dir}":str(effect_dir),"{receipt}":str(effect_dir/"worker_receipt.json")}
    out=[]
    for a in command:
        for k,v in repl.items(): a=a.replace(k,v)
        out.append(a)
    return out

def validate_receipt(effect_dir:Path,intent:dict):
    rp=effect_dir/"worker_receipt.json"
    if not rp.is_file(): return False,"RECEIPT_MISSING",None
    try:r=load_json(rp)
    except Exception as e:return False,"RECEIPT_PARSE_"+type(e).__name__,None
    for k,v in intent["expected_receipt"].items():
        if r.get(k)!=v:return False,"RECEIPT_EXPECTATION:"+k,r
    arts=r.get("artifacts",[])
    if intent.get("artifacts_required",True):
        if not isinstance(arts,list) or not arts:return False,"ARTIFACT_LIST",r
        for a in arts:
            rel=a.get("path")
            pth=Path(rel) if isinstance(rel,str) else None
            if pth is None or pth.is_absolute() or ".." in pth.parts:return False,"ARTIFACT_PATH",r
            p=effect_dir/pth
            if not p.is_file():return False,"ARTIFACT_MISSING:"+str(rel),r
            if p.stat().st_size!=a.get("bytes"):return False,"ARTIFACT_SIZE:"+str(rel),r
            if sha256_file(p)!=a.get("sha256"):return False,"ARTIFACT_SHA:"+str(rel),r
    return True,"PASS",r

def spawn_bootstrap(script:Path,effect_dir:Path,token:str):
    out=(effect_dir/"bootstrap.stdout.txt").open("ab",buffering=0)
    err=(effect_dir/"bootstrap.stderr.txt").open("ab",buffering=0)
    cmd=[sys.executable,str(script),"--bootstrap","--effect-dir",str(effect_dir),"--claim-token",token]
    p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=out,stderr=err,close_fds=True,start_new_session=(os.name=="posix"))
    out.close();err.close()
    return p.pid

def bootstrap(effect_dir:Path,token:str):
    claim=load_json(effect_dir/"claim.json")
    if claim.get("claim_token")!=token:return 91
    birth=process_birth(os.getpid())
    if birth is None:return 92
    atomic_json(effect_dir/"bootstrap_identity.json",{"pid":os.getpid(),"birth":birth,"started_at":utc_now(),"claim_token":token})
    claim2=load_json(effect_dir/"claim.json")
    if claim2.get("claim_token")!=token:return 93
    out=(effect_dir/"worker.stdout.txt").open("ab",buffering=0)
    err=(effect_dir/"worker.stderr.txt").open("ab",buffering=0)
    try:
        p=subprocess.Popen(claim["command"],stdin=subprocess.DEVNULL,stdout=out,stderr=err,close_fds=True)
        wb=process_birth(p.pid)
        if wb is None:
            try:p.terminate()
            except Exception:pass
            return 94
        atomic_json(effect_dir/"worker_identity.json",{"pid":p.pid,"birth":wb,"started_at":utc_now()})
        rc=p.wait()
    finally:
        out.close();err.close()
    atomic_json(effect_dir/"exit.json",{"returncode":rc,"ended_at":utc_now(),"claim_token":token})
    return int(rc)

def controller(intent_path:Path,work_root:Path):
    intent=load_json(intent_path); spec_sha=validate_intent(intent)
    effect_dir=work_root/intent["effect_id"];effect_dir.mkdir(parents=True,exist_ok=True)
    done=effect_dir/"done.json"
    if done.exists():
        ok,why,_=validate_receipt(effect_dir,intent)
        return {"state":"PASS" if ok else "FAIL","action":"REUSE_DONE" if ok else "DONE_INVALID","reason":why,"effect_id":intent["effect_id"],"spec_sha256":spec_sha}
    claim_p=effect_dir/"claim.json"
    if not claim_p.exists():
        token=uuid.uuid4().hex
        cmd=expand_command(intent["command"],effect_dir)
        claim={"schema":SCHEMA,"effect_id":intent["effect_id"],"spec_sha256":spec_sha,"claim_token":token,"command":cmd,"command_sha256":sha256_obj(cmd),"created_at":utc_now()}
        atomic_json(claim_p,claim)
        pid=spawn_bootstrap(Path(__file__).resolve(),effect_dir,token)
        pb=process_birth(pid)
        atomic_json(effect_dir/"launch_identity.json",{"pid":pid,"birth":pb,"started_at":utc_now(),"claim_token":token})
        return {"state":"RUNNING","action":"LAUNCHED","effect_id":intent["effect_id"],"bootstrap_pid":pid,"spec_sha256":spec_sha}
    claim=load_json(claim_p)
    if claim.get("spec_sha256")!=spec_sha:return {"state":"FAIL","action":"INTENT_MISMATCH","effect_id":intent["effect_id"]}
    li=effect_dir/"launch_identity.json"
    if li.exists():
        x=load_json(li)
        if x.get("claim_token")==claim.get("claim_token") and process_alive(int(x["pid"]),x.get("birth")):
            return {"state":"RUNNING","action":"ADOPT_LAUNCH","effect_id":intent["effect_id"]}
    bi=effect_dir/"bootstrap_identity.json"
    if bi.exists():
        x=load_json(bi)
        if process_alive(int(x["pid"]),x.get("birth")):return {"state":"RUNNING","action":"ADOPT_BOOTSTRAP","effect_id":intent["effect_id"]}
    wi=effect_dir/"worker_identity.json"
    if wi.exists():
        x=load_json(wi)
        if process_alive(int(x["pid"]),x.get("birth")):return {"state":"RUNNING","action":"ADOPT_WORKER","effect_id":intent["effect_id"]}
    ok,why,r=validate_receipt(effect_dir,intent)
    if ok:
        atomic_json(done,{"schema":SCHEMA,"status":"PASS","effect_id":intent["effect_id"],"spec_sha256":spec_sha,"worker_receipt_sha256":sha256_file(effect_dir/"worker_receipt.json"),"promoted_at":utc_now()})
        return {"state":"PASS","action":"PROMOTE_DONE","effect_id":intent["effect_id"],"spec_sha256":spec_sha}
    if (effect_dir/"exit.json").exists():
        ex=load_json(effect_dir/"exit.json")
        return {"state":"DEAD","action":"DEAD_NO_VALID_RECEIPT","effect_id":intent["effect_id"],"returncode":ex.get("returncode"),"reason":why}
    return {"state":"UNKNOWN","action":"NO_LIVE_IDENTITY_NO_RECEIPT","effect_id":intent["effect_id"],"reason":why}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--bootstrap",action="store_true")
    ap.add_argument("--effect-dir",type=Path);ap.add_argument("--claim-token")
    ap.add_argument("--intent",type=Path);ap.add_argument("--work-root",type=Path)
    a=ap.parse_args()
    if a.bootstrap:
        if not a.effect_dir or not a.claim_token:return 90
        return bootstrap(a.effect_dir,a.claim_token)
    if not a.intent or not a.work_root:ap.error("--intent and --work-root required")
    try:out=controller(a.intent,a.work_root)
    except Exception as e:out={"state":"FAIL","action":"EXECUTOR_EXCEPTION","reason":f"{type(e).__name__}:{e}"}
    print(json.dumps(out,sort_keys=True,separators=(",",":")))
    return 0 if out["state"] in {"PASS","RUNNING","UNKNOWN","DEAD"} else 2
if __name__=="__main__":raise SystemExit(main())
