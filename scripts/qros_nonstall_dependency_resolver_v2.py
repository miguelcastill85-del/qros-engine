#!/usr/bin/env python3
"""QROS non-stall dependency resolver v2.

Pure decision engine for bounded, content-addressed dependency recovery.
It never fetches data itself. Callers persist the ledger between attempts/chats.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable


class ResolverError(Exception):
    pass


def _canon(v: Any) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(v: Any) -> str:
    return hashlib.sha256(_canon(v)).hexdigest()


def query_fingerprint(source: str, query: str, scope: str = "", authority_sha: str = "") -> str:
    return sha256_json({"source": source, "query": query.strip(), "scope": scope.strip(), "authority_sha": authority_sha})


def evidence_fingerprint(items: Iterable[dict[str, Any]]) -> str:
    normalized = []
    for x in items:
        normalized.append({
            "path": x.get("path"),
            "blob_sha": x.get("blob_sha"),
            "sha256": x.get("sha256"),
            "status": x.get("status"),
        })
    return sha256_json(sorted(normalized, key=lambda x: _canon(x)))


@dataclass(frozen=True)
class ResolverDecision:
    action: str
    reason: str
    terminal_for_dependency: bool
    caller_may_search: bool
    must_checkpoint: bool


REQUIRED_LEDGER_FIELDS = {
    "dependency_id",
    "required_identity",
    "authority_sha",
    "unique_query_budget",
    "unique_queries_used",
    "seen_query_fingerprints",
    "attempted_sources",
    "evidence_fingerprint",
    "state",
    "essential",
    "orthogonal_work_available",
}


def validate_ledger(ledger: dict[str, Any]) -> None:
    missing = REQUIRED_LEDGER_FIELDS - set(ledger)
    if missing:
        raise ResolverError("LEDGER_FIELDS_MISSING:" + ",".join(sorted(missing)))
    if ledger["unique_query_budget"] < 1:
        raise ResolverError("INVALID_QUERY_BUDGET")
    if ledger["unique_queries_used"] < 0:
        raise ResolverError("INVALID_QUERY_COUNT")
    if ledger["unique_queries_used"] > ledger["unique_query_budget"]:
        raise ResolverError("QUERY_COUNT_EXCEEDS_BUDGET")
    if ledger["state"] not in {"ACTIVE", "RESOLVED", "FROZEN_BLOCKER", "BLOCKED_BY_INFRASTRUCTURE"}:
        raise ResolverError("INVALID_STATE")


def exact_identity_match(required: dict[str, Any], candidate: dict[str, Any]) -> bool:
    """Every non-null required identity field must match exactly."""
    if not required:
        raise ResolverError("EMPTY_REQUIRED_IDENTITY")
    for k, v in required.items():
        if v is None:
            continue
        if candidate.get(k) != v:
            return False
    return True


def preflight_query(ledger: dict[str, Any], *, source: str, query: str, scope: str = "") -> ResolverDecision:
    """Decide whether an external lookup is allowed BEFORE issuing it."""
    validate_ledger(ledger)
    if ledger["state"] != "ACTIVE":
        return ResolverDecision("STOP", "DEPENDENCY_NOT_ACTIVE", True, False, True)
    qfp = query_fingerprint(source, query, scope, ledger["authority_sha"])
    if qfp in set(ledger["seen_query_fingerprints"]):
        return ResolverDecision("SKIP_DUPLICATE_QUERY", "IDENTICAL_QUERY_ALREADY_ATTEMPTED", False, False, True)
    if ledger["unique_queries_used"] >= ledger["unique_query_budget"]:
        return exhaustion_decision(ledger, "UNIQUE_QUERY_BUDGET_EXHAUSTED")
    return ResolverDecision("ALLOW_QUERY", "NEW_BOUNDED_QUERY", False, True, False)


def record_query(ledger: dict[str, Any], *, source: str, query: str, scope: str = "") -> dict[str, Any]:
    """Return a new ledger with one unique query recorded. Duplicate recording is forbidden."""
    d = preflight_query(ledger, source=source, query=query, scope=scope)
    if d.action != "ALLOW_QUERY":
        raise ResolverError("QUERY_NOT_ALLOWED:" + d.reason)
    out = json.loads(json.dumps(ledger))
    qfp = query_fingerprint(source, query, scope, ledger["authority_sha"])
    out["seen_query_fingerprints"].append(qfp)
    out["unique_queries_used"] += 1
    if source not in out["attempted_sources"]:
        out["attempted_sources"].append(source)
    return out


def classify_candidate(ledger: dict[str, Any], candidate: dict[str, Any]) -> ResolverDecision:
    validate_ledger(ledger)
    if exact_identity_match(ledger["required_identity"], candidate):
        return ResolverDecision("ACCEPT_EXACT", "EXACT_IDENTITY_MATCH", True, False, True)
    return ResolverDecision("REJECT_CANDIDATE", "IDENTITY_MISMATCH_NO_SUBSTITUTION", False, False, True)


def classify_progress(ledger: dict[str, Any], new_evidence_items: Iterable[dict[str, Any]]) -> ResolverDecision:
    validate_ledger(ledger)
    new_fp = evidence_fingerprint(new_evidence_items)
    if new_fp != ledger["evidence_fingerprint"]:
        return ResolverDecision("PROGRESS", "EVIDENCE_SET_CHANGED", False, True, True)
    return ResolverDecision("NO_PROGRESS", "EVIDENCE_SET_UNCHANGED", False, False, True)


def exhaustion_decision(ledger: dict[str, Any], reason: str = "RESOLUTION_EXHAUSTED") -> ResolverDecision:
    validate_ledger(ledger)
    if ledger["orthogonal_work_available"]:
        return ResolverDecision(
            "FREEZE_BLOCKER_CONTINUE_ORTHOGONAL",
            reason,
            True,
            False,
            True,
        )
    if ledger["essential"]:
        return ResolverDecision(
            "BLOCKED_BY_INFRASTRUCTURE",
            reason + ":ESSENTIAL_NO_ORTHOGONAL_ROUTE",
            True,
            False,
            True,
        )
    return ResolverDecision("FREEZE_NONESSENTIAL", reason, True, False, True)


def next_authority_source(ledger: dict[str, Any], ordered_sources: list[str]) -> ResolverDecision:
    """Pick first unattempted source; never cycle back to an attempted source."""
    validate_ledger(ledger)
    attempted = set(ledger["attempted_sources"])
    for source in ordered_sources:
        if source not in attempted:
            return ResolverDecision("TRY_SOURCE:" + source, "NEXT_UNATTEMPTED_AUTHORITY_SOURCE", False, True, False)
    return exhaustion_decision(ledger, "AUTHORITY_SOURCE_SET_EXHAUSTED")


def checkpoint_payload(ledger: dict[str, Any], decision: ResolverDecision, *, next_action: str) -> dict[str, Any]:
    validate_ledger(ledger)
    return {
        "schema": "QROS_NONSTALL_DEPENDENCY_RESOLUTION_CHECKPOINT_2.0",
        "dependency_id": ledger["dependency_id"],
        "authority_sha": ledger["authority_sha"],
        "required_identity": ledger["required_identity"],
        "resolver_state": ledger["state"],
        "unique_query_budget": ledger["unique_query_budget"],
        "unique_queries_used": ledger["unique_queries_used"],
        "seen_query_fingerprints": list(ledger["seen_query_fingerprints"]),
        "attempted_sources": list(ledger["attempted_sources"]),
        "evidence_fingerprint": ledger["evidence_fingerprint"],
        "decision": decision.action,
        "reason": decision.reason,
        "must_checkpoint": decision.must_checkpoint,
        "next_action": next_action,
    }
