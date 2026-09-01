#!/usr/bin/env python3
"""Launch V69 Gate-A wrapper with corrected independent path-B immediate-entry-tick semantics."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import qros_g30_xau_gate_a_v68 as core
from qros_g30_xau_outcome_b_v70 import outcome_B
core.outcome_B=outcome_B
import qros_g30_xau_gate_a_v69_wrapper as wrapper
if __name__=='__main__': wrapper.main()
