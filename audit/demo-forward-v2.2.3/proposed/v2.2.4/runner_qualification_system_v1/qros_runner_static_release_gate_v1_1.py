#!/usr/bin/env python3
"""
QROS Runner Static Release Gate v1.1.
Known-defect regression gate + mutation tests.
Zero external dependencies.

IMPORTANT: PASS means STATIC_QUALIFIED only. It never means native Windows/MT5 validated.
"""
from __future__ import annotations
import argparse, hashlib, json, re, zipfile
from pathlib import Path

SCHEMA="QROS_RUNNER_STATIC_RELEASE_GATE_1.1"

def sha256_bytes(b: bytes)->str:
    return hashlib.sha256(b).hexdigest()

def code_lines(text: str, lang: str):
    if lang != "mql":
        return list(enumerate(text.splitlines(),1))
    out=[]; in_block=False
    for n,s in enumerate(text.splitlines(),1):
        buf=""; i=0
        while i<len(s):
            if in_block:
                k=s.find("*/",i)
                if k<0: break
                in_block=False; i=k+2
            else:
                k_line=s.find("//",i); k_block=s.find("/*",i)
                ks=[k for k in (k_line,k_block) if k>=0]
                if not ks:
                    buf+=s[i:]; break
                k=min(ks); buf+=s[i:k]
                if k==k_line: break
                in_block=True; i=k+2
        out.append((n,buf))
    return out

def find(text: str, pattern: str, flags=re.I, lang="ps1"):
    rx=re.compile(pattern, flags)
    return [{"line":n,"text":line.strip()[:260]}
            for n,line in code_lines(text,lang) if rx.search(line)]

def function_blocks(ps1: str):
    lines=ps1.splitlines(); blocks={}; i=0
    while i<len(lines):
        m=re.match(r"\s*function\s+([A-Za-z0-9_-]+)",lines[i],re.I)
        if not m:
            i+=1; continue
        name=m.group(1); start=i; depth=0; seen=False; j=i
        while j<len(lines):
            s=re.sub(r"'[^']*'|\"[^\"]*\"","",lines[j])
            depth+=s.count("{")-s.count("}")
            if "{" in s: seen=True
            if seen and depth<=0: break
            j+=1
        blocks[name]="\n".join(lines[start:j+1]); i=j+1
    return blocks

def static_rules(ps1: str, mql: str):
    rules=[]
    def add(i,sev,desc,matches):
        rules.append({"id":i,"severity":sev,"description":desc,
                      "matches":matches,"pass":not bool(matches)})
    add("PS001","BLOCKER","Set-StrictMode Latest forbidden; freeze explicit version.",
        find(ps1,r"Set-StrictMode\s+-Version\s+Latest"))
    add("PS002","BLOCKER","Direct PSObject.Properties.Count forbidden.",
        find(ps1,r"\.PSObject\.Properties\.Count\b"))
    generic_lists=set(re.findall(r"\$([A-Za-z_]\w*)\s*=\s*New-Object\s+System\.Collections\.Generic\.List",ps1,re.I))
    unsafe=[]
    for n,line in code_lines(ps1,"ps1"):
        work=re.sub(r"@\([^\n]*?\)\.Count","",line)
        for var in re.findall(r"\$([A-Za-z_]\w*)\.Count\b",work):
            if var not in generic_lists:
                unsafe.append({"line":n,"text":line.strip()[:260]})
    add("PS003","BLOCKER","Direct .Count requires explicit arrayization or provable generic List.",unsafe)
    add("PS004","BLOCKER","Import-Csv forbidden for live evidence; exclusive snapshot helper required.",
        find(ps1,r"(?<![\w-])Import-Csv(?![\w-])"))
    broad=[]
    for n,line in code_lines(ps1,"ps1"):
        if re.search(r"Remove-Item",line,re.I) and re.search(r"(Common|\$Common)",line,re.I) and "*" in line:
            broad.append({"line":n,"text":line.strip()[:260]})
    add("PS005","BLOCKER","Broad wildcard deletion in shared FILE_COMMON forbidden.",broad)
    add("PS006","BLOCKER","taskkill forbidden.",find(ps1,r"(?<![\w-])taskkill(?:\.exe)?(?![\w-])"))
    blocks=function_blocks(ps1); stop_bad=[]
    for name,body in blocks.items():
        if re.search(r"\bStop-Process\b",body,re.I):
            if "SafeIsoPath" not in body or not re.search(r"\.Path\s+-like\s+\"\$iso\*",body,re.I):
                stop_bad.append({"line":0,"text":f"function {name}: Stop-Process lacks dual path gate"})
    add("PS007","BLOCKER","Stop-Process requires SafeIsoPath + process.Path isolated-root gate.",stop_bad)
    result_wait_bad=[]
    for n,line in code_lines(ps1,"ps1"):
        if re.search(r"(RESULT|EVIDENCE|MARKER)",line,re.I) and re.search(r"while|do|Wait",line,re.I) and "Test-Path" in line:
            result_wait_bad.append({"line":n,"text":line.strip()[:260]})
    add("PS008","BLOCKER","Evidence readiness cannot rely on Test-Path alone.",result_wait_bad)
    add("MQL001","BLOCKER","Sleep() forbidden as wall-clock hold in Strategy Tester fencing.",find(mql,r"\bSleep\s*\(",lang="mql"))
    compact=ps1.replace(" ","").replace("\t","")
    add("PS009","BLOCKER","Top-level fail-closed exception envelope required.",[] if ("try{" in compact and "catch{" in compact) else [{"line":0,"text":"missing try/catch envelope"}])
    return rules

def run_mutation_tests(base_ps1: str, base_mql: str):
    cases=[
      ("MUT_STRICTMODE_LATEST", base_ps1.replace("Set-StrictMode -Version 3.0","Set-StrictMode -Version Latest",1), base_mql, "PS001"),
      ("MUT_PSOBJECT_COUNT", base_ps1+"\n$x=$o.PSObject.Properties.Count\n", base_mql, "PS002"),
      ("MUT_DIRECT_COUNT", base_ps1+"\n$x=$rows.Count\n", base_mql, "PS003"),
      ("MUT_IMPORT_CSV", base_ps1+"\n$x=Import-Csv -LiteralPath $f\n", base_mql, "PS004"),
      ("MUT_COMMON_WILDCARD_DELETE", base_ps1+"\nRemove-Item -LiteralPath $Common\\QROS_* -Force\n", base_mql, "PS005"),
      ("MUT_TASKKILL", base_ps1+"\ntaskkill /IM terminal64.exe /F\n", base_mql, "PS006"),
      ("MUT_STOP_PROCESS_UNGATED", base_ps1+"\nfunction BadKill(){Stop-Process -Id 123 -Force}\n", base_mql, "PS007"),
      ("MUT_MQL_SLEEP", base_ps1, base_mql+"\nvoid Bad(){Sleep(90000);}\n", "MQL001"),
    ]
    results=[]
    for name,p,m,expected in cases:
        rules=static_rules(p,m)
        caught=any(r["id"]==expected and not r["pass"] for r in rules)
        results.append({"mutation":name,"expected_rule":expected,"caught":caught})
    return results

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("zip"); ap.add_argument("--runner",required=True); ap.add_argument("--harness",required=True); ap.add_argument("--out",required=True); a=ap.parse_args()
    zp=Path(a.zip)
    with zipfile.ZipFile(zp) as z:
        ps1=z.read(a.runner).decode("utf-8-sig",errors="strict"); mql=z.read(a.harness).decode("utf-8-sig",errors="strict"); bad=z.testzip()
    rules=static_rules(ps1,mql); muts=run_mutation_tests(ps1,mql)
    blockers=sum(1 for r in rules if r["severity"]=="BLOCKER" and not r["pass"]); mut_fail=sum(1 for x in muts if not x["caught"])
    rep={"schema":SCHEMA,"artifact":zp.name,"artifact_sha256":sha256_bytes(zp.read_bytes()),"runner":a.runner,"runner_sha256":sha256_bytes(ps1.encode()),"harness":a.harness,"harness_sha256":sha256_bytes(mql.encode()),"zip_crc":"PASS" if bad is None else f"FAIL:{bad}","rules":rules,"mutation_tests":muts,"summary":{"blocker_fail":blockers,"mutation_fail":mut_fail,"rules_total":len(rules),"mutations_total":len(muts)},"decision":"PASS" if bad is None and blockers==0 and mut_fail==0 else "FAIL","meaning":"STATIC_QUALIFIED_ONLY_NOT_NATIVE_VALIDATED"}
    Path(a.out).write_text(json.dumps(rep,indent=2),encoding="utf-8"); print(json.dumps(rep["summary"],sort_keys=True)); return 0 if rep["decision"]=="PASS" else 2
if __name__=="__main__": raise SystemExit(main())
