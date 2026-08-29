#!/usr/bin/env python3
"""Run only the packaged synthetic example through the native C++20 engine.

Python computes file bindings and invokes the CLI. Features, execution, mining
and statistics are evaluated by qros, never by this adapter.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, default=ROOT/"bin/qros")
    parser.add_argument("--example", choices=["nqx", "xau"], default="nqx")
    parser.add_argument("--out", type=Path, required=True)
    args=parser.parse_args()
    binary=args.binary.resolve(); out=args.out.resolve()
    if out.exists():
        raise SystemExit("choose a new output directory; existing results are immutable")
    fixture=ROOT/"examples/pipeline"/args.example
    program=fixture/"program.qros"; data=fixture/"dataset.qdata"; vault=fixture/"vault.policy"
    if "\npurpose=TEST_ONLY\n" not in program.read_text() or "\nexposure=SYNTHETIC\n" not in data.read_text():
        raise SystemExit("demo accepts only the packaged synthetic scope")
    (out/"input").mkdir(parents=True)
    local_program=out/"input/program.qros"; local_program.write_bytes(program.read_bytes())
    def native(*argv):
        subprocess.run([str(binary),*map(str,argv)],check=True,stdin=subprocess.DEVNULL,timeout=120)
    native("compile",local_program,sha(local_program),0,out/"candidate.ir")
    native("features",local_program,sha(local_program),0,data,sha(data),vault,sha(vault),out/"features.csv")
    run=out/"run"
    native("mine",local_program,sha(local_program),data,sha(data),vault,sha(vault),run,7,2,100000)
    native("mine",local_program,sha(local_program),data,sha(data),vault,sha(vault),run,11,100,100000)
    completion=run/"final/COMPLETED.receipt"; ledger=run/"final/trades.csv"
    fields=dict(program_path="input/program.qros",program_sha256=sha(local_program),completion_path="run/final/COMPLETED.receipt",
        completion_sha256=sha(completion),min_trades=1,min_pf_ppm=1000000,max_dd_u=10000,max_negative_years=1,min_positive_years=1,
        alpha_ppm=50000,n_tests=96,correction="BY",repetitions=999,rng_seed=70493,method="YEAR_BLOCK_SIGN_FLIP_V1")
    policy=out/"screen.policy"
    policy.write_text("QROS_GATE_POLICY_V1\n"+"".join(f"{k}={fields[k]}\n" for k in sorted(fields)))
    native("gates",ledger,sha(ledger),policy,sha(policy),out/"screen.receipt")
    print("DEMO_SINTETICA_COMPLETA; research_approved=0; background_running=0; output="+str(out),flush=True)


if __name__=="__main__":
    main()
