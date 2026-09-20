#!/usr/bin/env python3
from __future__ import annotations
import argparse, subprocess

EXPECTED = """BUY_ENTRY=103
SELL_ENTRY=98
BUY_EXIT=98
SELL_EXIT=103
BUY_AMBIG_REASON=1
BUY_AMBIG_PRICE=90
BUY_GAP_PRICE=85
ADMIT1=1
ADMIT_WHILE_OPEN=0
ADMIT2=1
RECONNECT_FILLED=1
"""

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--probe",required=True)
    a=ap.parse_args()
    p=subprocess.run([a.probe],capture_output=True,text=True,timeout=10,check=True)
    if p.stdout != EXPECTED:
        raise SystemExit("INDEPENDENT_ORACLE_MISMATCH\nEXPECTED:\n"+EXPECTED+"GOT:\n"+p.stdout)
    print("INDEPENDENT_ORACLE_PASS")

if __name__=="__main__":
    main()
