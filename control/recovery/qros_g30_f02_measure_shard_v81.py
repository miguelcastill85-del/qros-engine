#!/usr/bin/env python3
"""Infrastructure-only F02 measure shard wrapper.
Runs one preregistered shock_measure at a time to bound M1 memory/time.
Scientific formulas, Gate-A, costs and independent execution are inherited unchanged from qros_g30_f02_gate_a_v80.
Cross-measure exact-mask dedupe is performed by a separate deterministic reconciler in frozen MEAS order.
"""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_f02_gate_a_v80 as f
ALLOWED=['TRUE_RANGE_OVER_ATR','ABS_CLOSE_TO_CLOSE_RETURN_OVER_ATR','BODY_OVER_ATR']

def main():
 ap=argparse.ArgumentParser(add_help=False);ap.add_argument('--measure',choices=ALLOWED,required=True)
 ns,rest=ap.parse_known_args()
 f.MEAS=[ns.measure]
 sys.argv=[sys.argv[0]]+rest
 f.main()
if __name__=='__main__':main()
