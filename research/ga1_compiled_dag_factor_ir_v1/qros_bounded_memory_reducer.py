from __future__ import annotations
import hashlib
from dataclasses import dataclass
import numpy as np
from qros_factor_ir import FactorIR, canonical_bytes

SCHEMA = "QROS_BOUNDED_MEMORY_REDUCER_1.0"

@dataclass(frozen=True)
class ReductionResult:
    schema: str
    recipe_id: str
    selected_count: int
    class_hash: str
    chunk_rows_max: int
    bitmap_chunk_bytes: int

def _validate_chunk_bytes(bitmap_chunk_bytes: int) -> int:
    if not isinstance(bitmap_chunk_bytes, int) or isinstance(bitmap_chunk_bytes, bool) or bitmap_chunk_bytes <= 0:
        raise ValueError("BITMAP_CHUNK_BYTES_POSITIVE_INT_REQUIRED")
    return bitmap_chunk_bytes

def iter_selected_source_chunks(ir: FactorIR, recipe_id: str, *, bitmap_chunk_bytes: int = 65536):
    bitmap_chunk_bytes = _validate_chunk_bytes(bitmap_chunk_bytes)
    if recipe_id not in ir.recipes:
        raise KeyError(recipe_id)
    n = len(ir.source_idx)
    keys = ir.recipes[recipe_id]
    rows_per_chunk = bitmap_chunk_bytes * 8
    if not keys:
        for start in range(0, n, rows_per_chunk):
            yield ir.source_idx[start:min(n, start + rows_per_chunk)].astype("<u8", copy=False)
        return
    raw_masks = [ir.physical_bitmaps[ir.semantic_to_physical[k]] for k in keys]
    expected_bytes = (n + 7) // 8
    if any(len(raw) != expected_bytes for raw in raw_masks):
        raise ValueError("BITMAP_LENGTH_MISMATCH")
    for byte_start in range(0, expected_bytes, bitmap_chunk_bytes):
        byte_end = min(expected_bytes, byte_start + bitmap_chunk_bytes)
        acc = np.frombuffer(raw_masks[0], dtype=np.uint8, count=byte_end-byte_start, offset=byte_start).copy()
        for raw in raw_masks[1:]:
            acc &= np.frombuffer(raw, dtype=np.uint8, count=byte_end-byte_start, offset=byte_start)
        bits = np.unpackbits(acc, bitorder="little")
        row_start = byte_start * 8
        row_end = min(n, byte_end * 8)
        bits = bits[:row_end-row_start].astype(bool, copy=False)
        if np.any(bits):
            yield ir.source_idx[row_start:row_end][bits].astype("<u8", copy=False)

def reduce_recipe(ir: FactorIR, recipe_id: str, domain: dict, *, bitmap_chunk_bytes: int = 65536) -> ReductionResult:
    bitmap_chunk_bytes = _validate_chunk_bytes(bitmap_chunk_bytes)
    digest = hashlib.sha256()
    digest.update(canonical_bytes(domain))
    digest.update(b"\0")
    selected_count = 0
    max_rows = 0
    for chunk in iter_selected_source_chunks(ir, recipe_id, bitmap_chunk_bytes=bitmap_chunk_bytes):
        chunk = np.asarray(chunk, dtype="<u8")
        selected_count += int(len(chunk))
        max_rows = max(max_rows, int(len(chunk)))
        digest.update(chunk.tobytes())
    return ReductionResult(
        schema=SCHEMA,
        recipe_id=recipe_id,
        selected_count=selected_count,
        class_hash=digest.hexdigest(),
        chunk_rows_max=max_rows,
        bitmap_chunk_bytes=bitmap_chunk_bytes,
    )
