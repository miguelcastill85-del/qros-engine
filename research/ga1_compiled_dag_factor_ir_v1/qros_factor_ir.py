from __future__ import annotations
from dataclasses import dataclass
import hashlib, json
from typing import Iterable
import numpy as np

SCHEMA = "QROS_FACTOR_IR_1.0"


def canonical_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pack_mask(mask: np.ndarray) -> bytes:
    return np.packbits(np.asarray(mask, dtype=bool), bitorder="little").tobytes()


def unpack_mask(raw: bytes, n: int) -> np.ndarray:
    return np.unpackbits(np.frombuffer(raw, dtype=np.uint8), bitorder="little")[:n].astype(bool, copy=False)


@dataclass
class FactorIR:
    source_idx: np.ndarray
    # Semantic primitive keys remain distinct even when physical bitmaps are identical.
    semantic_to_physical: dict[str, str]
    physical_bitmaps: dict[str, bytes]
    recipes: dict[str, tuple[str, ...]]

    @classmethod
    def build(cls, source_idx: np.ndarray, primitives: dict[str, np.ndarray],
              recipes: dict[str, Iterable[str]]) -> "FactorIR":
        source_idx = np.asarray(source_idx, dtype=np.uint64)
        if len(source_idx) > 1 and np.any(source_idx[1:] <= source_idx[:-1]):
            raise ValueError("SOURCE_INDEX_NOT_STRICTLY_INCREASING")
        sem_to_phys: dict[str, str] = {}
        phys: dict[str, bytes] = {}
        for key, mask in sorted(primitives.items()):
            m = np.asarray(mask, dtype=bool)
            if len(m) != len(source_idx):
                raise ValueError(f"PRIMITIVE_LENGTH_MISMATCH:{key}")
            packed = pack_mask(m)
            digest = hashlib.sha256(packed).hexdigest()
            sem_to_phys[key] = digest
            phys.setdefault(digest, packed)
        rec: dict[str, tuple[str, ...]] = {}
        for rid, keys in sorted(recipes.items()):
            ks = tuple(keys)
            if any(k not in sem_to_phys for k in ks):
                raise ValueError(f"UNKNOWN_PRIMITIVE_IN_RECIPE:{rid}")
            rec[rid] = ks
        return cls(source_idx=source_idx, semantic_to_physical=sem_to_phys,
                   physical_bitmaps=phys, recipes=rec)

    def recipe_mask(self, recipe_id: str) -> np.ndarray:
        keys = self.recipes[recipe_id]
        n = len(self.source_idx)
        if not keys:
            return np.ones(n, dtype=bool)
        first = unpack_mask(self.physical_bitmaps[self.semantic_to_physical[keys[0]]], n).copy()
        for key in keys[1:]:
            first &= unpack_mask(self.physical_bitmaps[self.semantic_to_physical[key]], n)
        return first

    def selected_source_indices(self, recipe_id: str) -> np.ndarray:
        return self.source_idx[self.recipe_mask(recipe_id)]

    def class_hash(self, recipe_id: str, domain: dict) -> str:
        ids = self.selected_source_indices(recipe_id).astype("<u8", copy=False).tobytes()
        return hashlib.sha256(canonical_bytes(domain) + b"\0" + ids).hexdigest()

    def manifest(self) -> dict:
        return {
            "schema": SCHEMA,
            "source_count": int(len(self.source_idx)),
            "source_root_sha256": hashlib.sha256(self.source_idx.astype("<u8", copy=False).tobytes()).hexdigest(),
            "semantic_primitive_count": len(self.semantic_to_physical),
            "physical_bitmap_count": len(self.physical_bitmaps),
            "recipe_count": len(self.recipes),
            "physical_bitmap_bytes": sum(len(v) for v in self.physical_bitmaps.values()),
        }
