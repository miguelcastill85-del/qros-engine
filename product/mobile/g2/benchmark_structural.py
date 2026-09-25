"""Predeclared exactly 1M SYNTHETIC structural births, no G1 universe expansion.
C++ mixed-radix vs independent Python itertools streaming to avoid memory blowups.
No PnL, no tick prices, no forecasts. Prints machine-readable measured evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import os
import platform
import resource
import subprocess
import time


def independently_generated_rows():
    for values in itertools.product(range(10),repeat=6):
        yield ('SYNTHETIC_STRESS_NOT_G1|'+'|'.join(map(str,values))+'\n').encode('ascii')


def run(native_path: str) -> dict:
    # Strictly separate from G1's valid finite grammar: this tests structural throughput only.
    expected_births=1_000_000
    command=[native_path,'--synthetic-stress','--count',str(expected_births)]
    t0=time.perf_counter()
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=2**18)
    observed=0
    sha=hashlib.sha256()
    try:
        assert process.stdout is not None
        for expected in independently_generated_rows():
            got=process.stdout.readline()
            if got!=expected:
                process.kill()
                raise ValueError('MILLION_BIRTH_PARITY_MISMATCH_AT:'+str(observed))
            sha.update(got)
            observed+=1
        if process.stdout.readline():
            process.kill()
            raise ValueError('EXTRA_NATIVE_ROWS')
        if process.wait(timeout=60)!=0:
            raise ValueError('NATIVE_FAILURE:'+process.stderr.read(1000).decode('utf-8','replace'))
    finally:
        if process.poll() is None:process.kill()
        process.wait()
        if process.stdout:process.stdout.close()
        if process.stderr:process.stderr.close()
    seconds=time.perf_counter()-t0
    if observed!=expected_births:
        raise ValueError('INCOMPLETE_COUNT')
    return dict(schema='QROS_G2_MEASURED_SYNTHETIC_STRUCTURAL_BENCH_V1',
                classification='MEASURED_LOCAL_RUNTIME_ONLY_NOT_PNL',
                g1_economic_tests=0, simulated_market_data='NONE',
                declared_raw_structural_births=expected_births, verified_row_parity=observed,
                output_sha256=sha.hexdigest(), seconds_wall_round=round(seconds,5),
                rows_per_wall_second_round=round(observed/seconds,1),
                peak_self_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                cpu_architecture=platform.machine(), os_name=platform.system(),
                python_version=platform.python_version(),
                native_compiler_command='g++ -std=c++20 -O2 -Wall -Wextra -Wpedantic -Wconversion -Wshadow -Werror',
                native_compiler_version=subprocess.check_output(['g++','--version'],text=True).splitlines()[0],
                scientific_state_modified=False,holdout_open=False,ga2_open=False,
                public_throughput_guarantee=False)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--native',required=True)
    args=p.parse_args()
    print(json.dumps(run(args.native),sort_keys=True,indent=2))
