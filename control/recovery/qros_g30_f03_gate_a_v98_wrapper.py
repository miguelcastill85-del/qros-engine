#!/usr/bin/env python3
"""F03 V98 parity-correction wrapper.
Keeps the frozen V97 Gate-A implementation and replaces only the independent
execution implementation with V98, which checks SL/TP on the entry tick as
required by the frozen preregistration. No strategy/economic rule changes.
"""
import qros_g30_f03_gate_a_v97 as frozen
import qros_g30_f03_execution_independent_v98 as corrected
frozen.eb = corrected
if __name__ == '__main__':
    frozen.main()
