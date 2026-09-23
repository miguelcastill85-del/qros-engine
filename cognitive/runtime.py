"""Deterministic, read-only verification for QROS. Python 3.10+, stdlib only.

Contracts are supplied by the host, separately from untrusted packets. A successful
check proves only the stated predicate. This module cannot dispatch trading work,
grant holdout access, promote scientific state or alter a repository.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping

MANIFEST = "control/CONTROL_AUTHORITY_MANIFEST_v3.json"
PATHS = {"head": "control/HEAD.json", "state": "control/persistent_execution/STATE.json",
         "run_queue": "control/persistent_execution/RUN_QUEUE.json"}
MODEL_VERSION = "QRCEL_VERIFICATION_CANDIDATE_0.2.1"
JSON_INTEGER_LIMIT = 10 ** 1024


class ContractError(ValueError):
    """Machine-readable failure; no acceptance on malformed input."""

    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(f"{code}:{detail}" if detail else code)


def require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise ContractError(code, detail)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def require_hash(value: Any, length: int = 64) -> str:
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{" + str(length) + "}", value) is not None,
            "INVALID_HASH")
    return value


def nonempty(value: Any, field: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), "MISSING_ID", field)
    return value


def canonical(value: Any) -> bytes:
    # Fixed contract limit; do not inherit a process-global recursion setting.
    stack = [(value, 0)]
    while stack:
        node, depth = stack.pop()
        if type(node) is int:
            require(-JSON_INTEGER_LIMIT < node < JSON_INTEGER_LIMIT, "INVALID_JSON_INTEGER_SIZE")
        if isinstance(node, (dict, list, tuple)):
            require(depth <= 128, "INVALID_JSON_VALUE", "NESTING_LIMIT")
            children = node.values() if isinstance(node, dict) else node
            stack.extend((child, depth + 1) for child in children)
    try:
        return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                           allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ContractError("INVALID_JSON_VALUE", type(exc).__name__) from exc


def parse_json(data: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_KEY", key)
            result[key] = value
        return result

    def constant(value):
        raise ContractError("NONFINITE_JSON_NUMBER", value)

    def integer(value):
        require(len(value.lstrip('-')) <= 1024, "INVALID_JSON_INTEGER_SIZE")
        return int(value)

    try:
        obj = json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                         parse_constant=constant, parse_int=integer)
    except ContractError:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ContractError("INVALID_JSON", type(exc).__name__) from exc
    require(isinstance(obj, dict), "JSON_ROOT_NOT_OBJECT")
    # json.loads can overflow a finite literal (1e999) to infinity.
    canonical(obj)
    return obj


def relative_parts(path: str) -> list[str]:
    require(isinstance(path, str) and path and "\\" not in path and "\0" not in path,
            "UNSAFE_PATH")
    parts = path.split("/")
    require(all(part not in ("", ".", "..") for part in parts), "UNSAFE_PATH", path)
    return parts


class Snapshot:
    """Read regular files via no-follow directory descriptors, with bounded reads.

    This is a local path boundary, not a sandbox for arbitrary Python or the host.
    Hashes bind the exact bytes read. Caller must separately pin the remote commit.
    """
    def __init__(self, root: Path):
        self.root = Path(root)

    def read(self, relative: str, limit: int = 4 * 1024 * 1024) -> bytes:
        parts = relative_parts(relative)
        require(type(limit) is int and limit > 0, "INVALID_READ_LIMIT")
        handles = []
        try:
            flags = os.O_RDONLY | os.O_NOFOLLOW
            fd = os.open(self.root, flags | os.O_DIRECTORY)
            handles.append(fd)
            for part in parts[:-1]:
                fd = os.open(part, flags | os.O_DIRECTORY, dir_fd=fd)
                handles.append(fd)
            fd = os.open(parts[-1], flags | os.O_NONBLOCK, dir_fd=fd)
            handles.append(fd)
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode), "NOT_REGULAR_FILE", relative)
            require(info.st_size <= limit, "FILE_TOO_LARGE", relative)
            chunks = []
            total = 0
            while True:
                chunk = os.read(fd, min(65536, limit + 1 - total))
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                require(total <= limit, "FILE_TOO_LARGE", relative)
            return b"".join(chunks)
        except OSError as exc:
            raise ContractError("FILE_UNAVAILABLE_OR_UNSAFE", relative) from exc
        finally:
            for fd in reversed(handles):
                os.close(fd)

    def json(self, relative: str) -> tuple[dict, bytes]:
        data = self.read(relative)
        return parse_json(data), data


@dataclass(frozen=True)
class AuthorityObservation:
    manifest_bytes: bytes
    head_bytes: bytes
    state_bytes: bytes
    queue_bytes: bytes
    manifest_blob: str

    @property
    def manifest(self):
        return parse_json(self.manifest_bytes)

    @property
    def head(self):
        return parse_json(self.head_bytes)

    @property
    def state(self):
        return parse_json(self.state_bytes)

    @property
    def queue(self):
        return parse_json(self.queue_bytes)


def observe_authority(snapshot: Snapshot, expected_manifest_blob: str,
                      repository: str = "miguelcastill85-del/qros-engine") -> AuthorityObservation:
    """Authenticate supplied bytes against a host-pinned manifest blob, not itself."""
    require_hash(expected_manifest_blob, 40)
    m, mb = snapshot.json(MANIFEST)
    require(git_blob(mb) == expected_manifest_blob, "MANIFEST_ANCHOR_MISMATCH")
    require(m.get("schema") == "QROS_CONTROL_AUTHORITY_MANIFEST_V3", "MANIFEST_SCHEMA")
    require(m.get("status") == "SOLE_ACTIVE_CONTROL_AND_SCIENTIFIC_CONTINUITY_AUTHORITY",
            "MANIFEST_NOT_ACTIVE")
    require(m.get("repository") == repository, "REPOSITORY_MISMATCH")
    campaign = nonempty(m.get("campaign"), "campaign")
    epoch = m.get("authority_epoch")
    require(type(epoch) is int and epoch > 0, "INVALID_AUTHORITY_EPOCH")
    require(type(m.get("scientific_execution_authorized")) is bool, "AUTHORIZATION_NOT_BOOLEAN")
    refs = m.get("single_active_authority")
    require(isinstance(refs, dict) and set(refs) == set(PATHS), "INVALID_DELEGATION_SET")
    schemas = {"head": f"QROS_PERSISTENT_CONTROL_HEAD_V{epoch}",
               "state": f"QROS_PERSISTENT_EXECUTION_STATE_V{epoch}",
               "run_queue": f"QROS_PERSISTENT_RUN_QUEUE_V{epoch}"}
    blobs = {}
    for role, path in PATHS.items():
        ref = refs[role]
        require(isinstance(ref, dict) and ref.get("path") == path, "DELEGATED_PATH_MISMATCH", role)
        require_hash(ref.get("git_blob_sha1"), 40)
        obj, data = snapshot.json(path)
        require(git_blob(data) == ref["git_blob_sha1"], "DELEGATED_BLOB_MISMATCH", role)
        require(obj.get("schema") == schemas[role], "DELEGATED_SCHEMA_MISMATCH", role)
        require(obj.get("campaign") == campaign, "CAMPAIGN_MISMATCH", role)
        require(type(obj.get("authority_epoch")) is int and obj["authority_epoch"] == epoch,
                "EPOCH_MISMATCH", role)
        require(obj.get("scientific_execution_authorization_source") == MANIFEST,
                "AUTHORIZATION_SOURCE_MISMATCH", role)
        require("scientific_execution_authorized" not in obj,
                "PARALLEL_AUTHORIZATION_SWITCH", role)
        blobs[role] = data
    return AuthorityObservation(mb, blobs["head"], blobs["state"], blobs["run_queue"], expected_manifest_blob)


def revalidate_observation(obs: AuthorityObservation) -> None:
    """A public dataclass is data, not proof that validation already happened."""
    require(type(obs) is AuthorityObservation, "INVALID_AUTHORITY_OBSERVATION")
    data = {MANIFEST: obs.manifest_bytes, PATHS['head']: obs.head_bytes,
            PATHS['state']: obs.state_bytes, PATHS['run_queue']: obs.queue_bytes}
    require(all(type(value) is bytes for value in data.values()), "INVALID_OBSERVATION_BYTES")

    class BoundBytes:
        def json(self, relative):
            return parse_json(data[relative]), data[relative]

    observe_authority(BoundBytes(), obs.manifest_blob)


def authority_receipt(obs: AuthorityObservation) -> dict:
    revalidate_observation(obs)
    return {"schema": "QRCEL_AUTHORITY_INSPECTION_V1", "status": "PASS",
            "predicate": "PINNED_MANIFEST_AND_THREE_DELEGATED_OBJECTS_VALID",
            "manifest_blob_sha1": obs.manifest_blob,
            "authority_epoch": obs.manifest["authority_epoch"],
            "scientific_execution_authorized_observed": obs.manifest["scientific_execution_authorized"],
            "scientific_effect_authorized_by_this_receipt": False,
            "full_bootstrap_certified": False,
            "remaining_external_requirements": ["Legacy-role scope resolution", "Fresh runtime capability",
                                                 "Exact scientific runner/input preflights"]}


def check_dag(tasks: list[dict], satisfied_external: frozenset[str] = frozenset()) -> list[str]:
    """Kahn topology; all dependency namespaces count, cycles are rejected."""
    require(isinstance(tasks, list), "TASKS_NOT_ARRAY")
    require(isinstance(satisfied_external, frozenset), "EXTERNAL_CAPABILITIES_NOT_FROZEN")
    for ext in satisfied_external:
        nonempty(ext, "external_dependency")
    nodes = {}
    for task in tasks:
        require(isinstance(task, dict), "TASK_NOT_OBJECT")
        identity = nonempty(task.get("item_id"), "item_id")
        require(identity not in nodes and identity not in satisfied_external, "DUPLICATE_TASK_ID", identity)
        dependencies = task.get("prerequisites")
        require(isinstance(dependencies, list), "DEPENDENCIES_NOT_ARRAY", identity)
        for dep in dependencies:
            nonempty(dep, "dependency")
        require(len(set(dependencies)) == len(dependencies), "DUPLICATE_DEPENDENCY", identity)
        nodes[identity] = set(dependencies)
    for identity, deps in nodes.items():
        require(deps <= set(nodes) | satisfied_external, "UNKNOWN_DEPENDENCY", identity)
    incoming = {key: deps - satisfied_external for key, deps in nodes.items()}
    order = []
    ready = sorted(key for key, deps in incoming.items() if not deps)
    while ready:
        node = ready.pop(0)
        order.append(node)
        del incoming[node]
        for key, deps in incoming.items():
            if node in deps:
                deps.remove(node)
                if not deps:
                    ready.append(key)
        ready.sort()
    require(not incoming, "DEPENDENCY_CYCLE")
    return order


def next_ready(tasks: list[dict], satisfied_external: frozenset[str] = frozenset()) -> dict | None:
    check_dag(tasks, satisfied_external)
    states = {"READY", "COMPLETED", "WAITING_PREREQUISITE", "IN_PROGRESS", "BLOCKED", "INVALID"}
    require(all(isinstance(t.get("status"), str) and t["status"] in states for t in tasks),
            "UNKNOWN_TASK_STATUS")
    completed = {task["item_id"] for task in tasks if task["status"] == "COMPLETED"}
    for task in tasks:
        if task["status"] in {"COMPLETED", "IN_PROGRESS"}:
            require(set(task["prerequisites"]) <= completed | satisfied_external,
                    "IMPOSSIBLE_TASK_STATE", task["item_id"])
    for task in tasks:
        if task["status"] == "READY" and set(task["prerequisites"]) <= completed | satisfied_external:
            return json.loads(canonical(task))
    return None


def inspect_active_queue(obs: AuthorityObservation) -> dict:
    """V189 adapter: inspect its exact next-item proposal; do not invent a DAG.

    V189 lacks explicit per-item runtime prerequisites, so its next item is a
    preflight hint. Missing dispatch contracts are reported, never set to [].
    """
    revalidate_observation(obs)
    require(obs.manifest["authority_epoch"] == 189, "UNSUPPORTED_QUEUE_ADAPTER_EPOCH")
    queue, state, head = obs.queue, obs.state, obs.head
    require(state.get("enabled") is True, "EXECUTION_STATE_DISABLED")
    require(state.get("queue_ref") == PATHS["run_queue"], "QUEUE_REFERENCE_MISMATCH")
    rows = queue.get("queue")
    require(isinstance(rows, list) and rows, "EMPTY_OR_INVALID_QUEUE")
    ids = []
    for row in rows:
        require(isinstance(row, dict), "QUEUE_ITEM_NOT_OBJECT")
        ids.append(nonempty(row.get("item_id"), "item_id"))
        nonempty(row.get("status"), "item_status")
    require(len(set(ids)) == len(ids), "DUPLICATE_TASK_ID")
    hint = nonempty(queue.get("next_item"), "next_item")
    require(hint == state.get("next_item") and hint in ids, "NEXT_ITEM_MISMATCH")
    scientific_state = head.get("scientific_state")
    require(isinstance(scientific_state, dict), "INVALID_HEAD_SCIENTIFIC_STATE")
    require(scientific_state.get("current_gate") == hint, "HEAD_GATE_MISMATCH")
    guard = queue.get("guards")
    require(isinstance(guard, dict), "MISSING_QUEUE_GUARDS")
    for key in ("holdout_open_authorized", "live_authorized", "mt5_authorized", "retuning_authorized",
                "supergate_authorized", "stage_c_2022_2024_strategy_pnl_authorized",
                "stage_d_2025_2026_partial_strategy_pnl_authorized", "aggregate_2020_2026_first_pass_authorized"):
        require(guard.get(key) is False, "QUEUE_GUARD_MISMATCH", key)
    require(state.get("locked_economic_source_clock_years") == [2022, 2023, 2024, 2025, 2026],
            "EXPOSURE_GUARD_MISMATCH")
    row = rows[ids.index(hint)]
    require(row["status"] == "READY_AUTHORIZED_NOT_STARTED", "NEXT_ITEM_NOT_READY")
    return {"schema": "QRCEL_QUEUE_INSPECTION_V1", "status": "PASS",
            "next_item_hint": hint, "source_status": row["status"],
            "decision": "PREFLIGHT_REQUIRED_NO_DISPATCH", "dispatch_authorized": False,
            "scientific_state_observed": state.get("scientific_state"),
            "runtime_prerequisites_materialized": False, "manifest_blob_sha1": obs.manifest_blob}


@dataclass(frozen=True)
class EvidenceContract:
    """Host-selected requirement, never taken from the packet being checked."""
    path: str
    sha256: str
    schema: str
    campaign_id: str
    root_genealogy_id: str
    role: str
    scope: str
    authority_manifest_sha256: str
    required_claims: tuple[tuple[str, bool], ...] = ()


def inspect_evidence(snapshot: Snapshot, contract: EvidenceContract) -> dict:
    """Check typed content. PASS is evidence inspection, never scientific approval."""
    require_hash(contract.sha256)
    require_hash(contract.authority_manifest_sha256)
    for field in ("schema", "campaign_id", "root_genealogy_id", "role", "scope"):
        nonempty(getattr(contract, field), field)
    doc, data = snapshot.json(contract.path)
    require(sha256(data) == contract.sha256, "EVIDENCE_HASH_MISMATCH")
    require(doc.get("schema") == contract.schema == "QROS_BOUND_EVIDENCE_V1", "UNSUPPORTED_EVIDENCE_SCHEMA")
    require(doc.get("status") == "PASS", "EVIDENCE_RESULT_NOT_PASS")
    for field in ("campaign_id", "root_genealogy_id", "role", "scope", "authority_manifest_sha256"):
        require(doc.get(field) == getattr(contract, field), "EVIDENCE_SCOPE_MISMATCH", field)
    require(doc.get("failures") == [], "EVIDENCE_HAS_FAILURES")
    claims = doc.get("claims")
    require(isinstance(claims, dict), "EVIDENCE_CLAIMS_MISSING")
    require(isinstance(contract.required_claims, tuple), "INVALID_CLAIM_CONTRACT")
    keys = []
    for key, value in contract.required_claims:
        nonempty(key, "claim_key")
        require(type(value) is bool, "CLAIM_EXPECTATION_NOT_BOOLEAN")
        keys.append(key)
        require(claims.get(key) is value, "EVIDENCE_CLAIM_FAILED", key)
    require(len(set(keys)) == len(keys), "DUPLICATE_CLAIM_CONTRACT")
    return {"schema": "QRCEL_EVIDENCE_INSPECTION_V1", "status": "PASS",
            "source_sha256": contract.sha256, "role": contract.role, "scope": contract.scope,
            "scientific_effect_authorized": False, "economic_read_authorized": False}


def check_bound_packet(snapshot: Snapshot, contracts: Mapping[str, EvidenceContract], packet: dict) -> dict:
    """Packet references must exactly match the separately supplied contracts."""
    require(isinstance(packet, dict) and bool(contracts), "EMPTY_EVIDENCE_BINDING")
    refs, hashes = packet.get("authority_refs"), packet.get("authority_sha256")
    require(isinstance(refs, dict) and isinstance(hashes, dict), "MISSING_EVIDENCE_BINDING")
    require(set(refs) == set(hashes) == set(contracts), "EVIDENCE_BINDING_KEYS_MISMATCH")
    receipts = {}
    for key, contract in contracts.items():
        require(refs[key] == contract.path and hashes[key] == contract.sha256, "UNDELEGATED_EVIDENCE", key)
        require(packet.get("campaign_id") == contract.campaign_id and
                packet.get("root_genealogy_id") == contract.root_genealogy_id,
                "PACKET_GENEALOGY_MISMATCH")
        receipts[key] = inspect_evidence(snapshot, contract)
    return {"schema": "QRCEL_EVIDENCE_BUNDLE_INSPECTION_V1", "status": "PASS", "receipts": receipts,
            "decision": "EVIDENCE_INSPECTED_NO_AUTHORIZATION", "economic_read_authorized": False}


def rational(value: Any) -> Fraction:
    require(type(value) in (str, int), "DIMENSION_REQUIRES_EXACT_NUMBER")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ContractError("INVALID_DIMENSION") from exc
    require(result > 0, "NONPOSITIVE_DIMENSION")
    return result


def inspect_units(snapshot: Snapshot, contract: EvidenceContract, packet: dict) -> dict:
    """Extract dimensions from typed bound authority content, never packet numbers alone.

    The envelope describes frozen semantics and binding attestations. This checks
    dimensions and exact source identity; it cannot prove arbitrary runner code.
    Scientific runner parity remains a separate prerequisite.
    """
    require(contract.role == "execution_unit_binding", "UNIT_EVIDENCE_WRONG_ROLE")
    inspect_evidence(snapshot, contract)
    doc, source_bytes = snapshot.json(contract.path)
    require(sha256(source_bytes) == contract.sha256, "EVIDENCE_CHANGED_DURING_INSPECTION")
    fields = ("frozen_semantics", "unit_contract", "runner_bindings")
    for field in fields:
        require(isinstance(doc.get(field), dict), "UNIT_SOURCE_FIELD_MISSING", field)
        require(canonical(packet.get(field)) == canonical(doc[field]), "UNIT_PACKET_SOURCE_MISMATCH", field)
    frozen, units, runners = (doc[k] for k in fields)
    require(frozen.get("stop_family") == "ATR_FIXED", "UNSUPPORTED_STOP_FAMILY")
    stop = rational(frozen.get("atr_stop_mult"))
    reward = rational(frozen.get("reward_r_multiple"))
    cache = rational(units.get("atr_storage_units_per_raw_quote_unit"))
    price = rational(units.get("execution_price_units_per_raw_quote_unit"))
    require(set(runners) == {"primary", "independent"}, "RUNNER_BINDING_SET")
    source_hashes = []
    for role, runner in runners.items():
        require(isinstance(runner, dict), "RUNNER_BINDING_NOT_OBJECT", role)
        require_hash(runner.get("source_sha256"))
        source = snapshot.read(runner.get("source_path"))
        require(sha256(source) == runner["source_sha256"], "RUNNER_SOURCE_HASH_MISMATCH", role)
        source_hashes.append(runner["source_sha256"])
        effective = rational(runner.get("atr_multiplier")) * cache / (rational(runner.get("atr_divisor")) * price)
        require(effective == stop, "UNIT_STOP_MISMATCH", role)
        require(rational(runner.get("take_r_multiple")) == reward, "UNIT_REWARD_MISMATCH", role)
    require(len(set(source_hashes)) == 2, "IDENTICAL_RUNNERS_NOT_INDEPENDENT")
    return {"schema": "QRCEL_UNIT_INSPECTION_V1", "status": "PASS", "effective_atr_stop_mult": str(stop),
            "reward_r_multiple": str(reward), "source_sha256": source_hashes,
            "runner_semantic_parity_certified": False, "economic_scoring_authorized": False}


def verify_checkpoint(snapshot: Snapshot, checkpoint: dict, *, expected_inputs: dict,
                      expected_authority_blob: str, expected_dispatch_id: str,
                      expected_holdout_exposure: str, expected_parent_commit: str,
                      expected_total_count: int) -> dict:
    """Inspect a zero-based prefix bound to host-selected provenance and extent.

    Required expected values must come from the frozen host task contract, never
    from the checkpoint being inspected. This does not validate domain output rows.
    """
    require(isinstance(checkpoint, dict), "CHECKPOINT_NOT_OBJECT")
    require_hash(expected_authority_blob, 40)
    require(checkpoint.get("dispatch_id") == nonempty(expected_dispatch_id, "dispatch_id"),
            "CHECKPOINT_DISPATCH_MISMATCH")
    require(checkpoint.get("authority_manifest_blob_sha1") == expected_authority_blob,
            "CHECKPOINT_AUTHORITY_MISMATCH")
    require_hash(checkpoint.get("parent_commit"), 40)
    require_hash(expected_parent_commit, 40)
    require(checkpoint["parent_commit"] == expected_parent_commit, "CHECKPOINT_PARENT_MISMATCH")
    require(type(expected_total_count) is int and expected_total_count >= 0, "INVALID_EXPECTED_TOTAL")
    require(checkpoint.get("execution_state") in ("COMPLETED", "PENDING_RESUMABLE", "CONTROL_CANARY"),
            "CHECKPOINT_STATE_INVALID")
    require(checkpoint.get("holdout_exposure") in ("SEALED_NO_ACCESS", "EXPOSED_OBSERVATIONAL_ONLY"),
            "CHECKPOINT_EXPOSURE_UNDECLARED")
    require(checkpoint["holdout_exposure"] == expected_holdout_exposure, "CHECKPOINT_EXPOSURE_MISMATCH")
    require(isinstance(expected_inputs, dict) and expected_inputs, "CHECKPOINT_INPUTS_MISSING")
    actual_inputs = checkpoint.get("input_and_source_sha256")
    require(actual_inputs == expected_inputs, "CHECKPOINT_INPUT_BINDING_MISMATCH")
    for path, identity in expected_inputs.items():
        require_hash(identity)
        require(sha256(snapshot.read(path)) == identity, "CHECKPOINT_INPUT_BYTES_MISMATCH", path)
    output_hash = require_hash(checkpoint.get("output_sha256"))
    output_path = checkpoint.get("output_path")
    require(sha256(snapshot.read(output_path)) == output_hash, "CHECKPOINT_OUTPUT_BYTES_MISMATCH")
    ranges = checkpoint.get("completed_ranges")
    require(isinstance(ranges, list), "CHECKPOINT_RANGES_MISSING")
    end = 0
    for interval in ranges:
        require(isinstance(interval, list) and len(interval) == 2 and all(type(x) is int for x in interval),
                "INVALID_RANGE")
        require(interval[0] == end and interval[1] > interval[0], "RANGE_GAP_OR_OVERLAP")
        end = interval[1]
    require(type(checkpoint.get("completed_count")) is int and checkpoint["completed_count"] == end,
            "CHECKPOINT_COUNT_MISMATCH")
    require(end <= expected_total_count, "CHECKPOINT_EXTENT_EXCEEDED")
    if checkpoint["execution_state"] == "COMPLETED":
        require(end == expected_total_count, "CHECKPOINT_INCOMPLETE_COMPLETION")
    if checkpoint["execution_state"] == "PENDING_RESUMABLE":
        require(end < expected_total_count, "CHECKPOINT_NOTHING_TO_RESUME")
    nonempty(checkpoint.get("exact_resume_action"), "exact_resume_action")
    return {"schema": "QRCEL_CHECKPOINT_INSPECTION_V1", "status": "PASS", "completed_count": end,
            "output_sha256": output_hash, "expected_total_count": expected_total_count,
            "parent_commit": expected_parent_commit, "scientific_effect_authorized": False}


def compress_state(state: dict) -> bytes:
    """Lossless structured compression; zlib is an encoding, not semantic inference."""
    import zlib
    data = canonical(state)
    return canonical({"schema": "QRCEL_STATE_ENCODING_V1", "sha256": sha256(data),
                      "bytes": len(data), "zlib_hex": zlib.compress(data).hex()})


def reconstruct_state(encoded: bytes, expected_sha256: str, max_bytes: int = 4 * 1024 * 1024) -> dict:
    import zlib
    require_hash(expected_sha256)
    require(type(max_bytes) is int and max_bytes > 0, "INVALID_RECONSTRUCTION_LIMIT")
    envelope = parse_json(encoded)
    require(envelope.get("schema") == "QRCEL_STATE_ENCODING_V1", "STATE_ENCODING_SCHEMA")
    require(envelope.get("sha256") == expected_sha256, "STATE_ANCHOR_MISMATCH")
    require(type(envelope.get("bytes")) is int and 0 <= envelope["bytes"] <= max_bytes,
            "STATE_SIZE_INVALID")
    try:
        decompressor = zlib.decompressobj()
        data = decompressor.decompress(bytes.fromhex(envelope["zlib_hex"]), max_bytes + 1)
    except (ValueError, KeyError, TypeError, zlib.error) as exc:
        raise ContractError("STATE_DECODE_ERROR") from exc
    require(len(data) <= max_bytes and decompressor.eof and not decompressor.unused_data,
            "STATE_TRUNCATED_OR_OVERSIZE")
    require(len(data) == envelope["bytes"] and sha256(data) == expected_sha256, "STATE_HASH_MISMATCH")
    return parse_json(data)
