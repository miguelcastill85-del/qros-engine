from __future__ import annotations
import hashlib, json, platform
from pathlib import Path
import numpy as np
from qros_factor_ir import FactorIR, canonical_bytes
from qros_bounded_memory_reducer import reduce_recipe

OUT = Path(__file__).with_name("bounded_memory_reducer_canary_output_v1.json")

def scalar_oracle(source_idx, primitives, keys, domain):
    selected = []
    for i, src in enumerate(source_idx):
        if all(bool(primitives[k][i]) for k in keys):
            selected.append(int(src))
    ids = np.asarray(selected, dtype="<u8").tobytes()
    return len(selected), hashlib.sha256(canonical_bytes(domain) + b"\0" + ids).hexdigest()

def main():
    rng = np.random.default_rng(20260921)
    comparisons = 0
    chunk_invariance = 0
    factor_ir_parity = 0
    cases = []
    ns = [0, 1, 7, 8, 9, 31, 64, 257, 4097, 11078]
    domains = [
        {"asset":"XAUUSD","side":"BUY","tf":"M1","scientific_context":"SYNTHETIC_NON_ECONOMIC"},
        {"asset":"NQX","side":"SELL","tf":"H4","scientific_context":"SYNTHETIC_NON_ECONOMIC"},
    ]
    chunk_sizes = [1, 2, 7, 64, 4096]
    for n in ns:
        if n:
            source_idx = np.cumsum(rng.integers(1, 6, size=n, dtype=np.uint64), dtype=np.uint64)
        else:
            source_idx = np.array([], dtype=np.uint64)
        primitives = {
            "ALL": np.ones(n, dtype=bool),
            "NONE": np.zeros(n, dtype=bool),
            "A": rng.random(n) < 0.57,
            "B": rng.random(n) < 0.31,
            "C": rng.random(n) < 0.83,
        }
        primitives["A_ALIAS"] = primitives["A"].copy()
        recipes = {
            "EMPTY": (),
            "A": ("A",),
            "AB": ("A","B"),
            "ABC": ("A","B","C"),
            "ALIAS": ("A","A_ALIAS"),
            "NONE_A": ("NONE","A"),
            "ALL_C": ("ALL","C"),
        }
        ir = FactorIR.build(source_idx, primitives, recipes)
        for domain in domains:
            for rid, keys in recipes.items():
                expected_count, expected_hash = scalar_oracle(source_idx, primitives, keys, domain)
                library_hash = ir.class_hash(rid, domain)
                if library_hash != expected_hash:
                    raise AssertionError(f"FACTOR_IR_ORACLE_MISMATCH:n={n}:recipe={rid}")
                factor_ir_parity += 1
                observed = []
                for cb in chunk_sizes:
                    r = reduce_recipe(ir, rid, domain, bitmap_chunk_bytes=cb)
                    if r.selected_count != expected_count or r.class_hash != expected_hash:
                        raise AssertionError(f"REDUCER_MISMATCH:n={n}:recipe={rid}:chunk={cb}")
                    if n and r.chunk_rows_max > cb * 8:
                        raise AssertionError("BOUNDED_MEMORY_CONTRACT_VIOLATION")
                    observed.append((r.selected_count, r.class_hash))
                    comparisons += 1
                if len(set(observed)) != 1:
                    raise AssertionError(f"CHUNK_INVARIANCE_FAIL:n={n}:recipe={rid}")
                chunk_invariance += 1
        cases.append({"n":n,"physical_bitmaps":ir.manifest()["physical_bitmap_count"],"recipes":len(recipes)})
    bad = 0
    one = FactorIR.build(np.array([1],dtype=np.uint64), {"A":np.array([True])}, {"A":("A",)})
    for invalid in (0, True):
        try:
            reduce_recipe(one,"A",domains[0],bitmap_chunk_bytes=invalid)
        except ValueError:
            bad += 1
    if bad != 2:
        raise AssertionError("INVALID_CHUNK_GUARDS_FAIL")
    output = {
        "schema":"QROS_BOUNDED_MEMORY_REDUCER_CANARY_1.0",
        "status":"PASS",
        "seed":20260921,
        "synthetic_non_economic":True,
        "n_values":ns,
        "domains":domains,
        "chunk_sizes_bytes":chunk_sizes,
        "recipes_per_n":7,
        "factor_ir_scalar_oracle_parity_checks":factor_ir_parity,
        "reducer_parity_comparisons":comparisons,
        "chunk_invariance_checks":chunk_invariance,
        "invalid_parameter_rejections":bad,
        "bounded_memory_contract":"selected chunks never exceed bitmap_chunk_bytes*8 rows; no full recipe mask is materialized by reducer",
        "cases":cases,
        "environment":{"python":platform.python_version(),"implementation":platform.python_implementation(),"numpy":np.__version__,"platform":platform.platform()},
    }
    OUT.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
    raw=OUT.read_bytes()
    print(json.dumps({"status":"PASS","output":str(OUT),"sha256":hashlib.sha256(raw).hexdigest(),
                      "comparisons":comparisons,"oracle_checks":factor_ir_parity,"chunk_invariance":chunk_invariance},sort_keys=True))

if __name__ == "__main__":
    main()
