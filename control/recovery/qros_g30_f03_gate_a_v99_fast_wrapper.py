#!/usr/bin/env python3
"""F03 V99 infrastructure-only fast parity wrapper.
Frozen V97 science/primary path is unchanged. Independent execution is replaced
by a raw-tick-confirmed executable-minute accelerator semantically equivalent to
V98, including same-entry-tick SL-first checks. Intended for M1 runtime bounds.
"""
import qros_g30_f03_gate_a_v97 as frozen
import qros_g30_f03_execution_independent_fast_v99 as fast
frozen.eb=fast
if __name__=='__main__':frozen.main()
