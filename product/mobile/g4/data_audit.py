"""G4 strict licensed data gate. Synthetic canaries only until source entitlement is independently proved.

No market prices, broker timezones, or contractual rights are silently inferred.
The original raw stream is retained unchanged. Financial results are never computed.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import base64
import hashlib
import json
import re
from typing import Any
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

HEX64 = re.compile(r"[0-9a-f]{64}\Z")
TOKEN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,95}\Z")

class AuditReject(ValueError):
    pass

def deny(code: str) -> None:
    raise AuditReject("QROS_G4_FAIL_CLOSED:" + code)

def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for k, v in items:
        if k in obj:
            deny("DUPLICATE_JSON_KEY")
        obj[k] = v
    return obj

def _bad_constant(s: str) -> None:
    deny("INVALID_JSON_NUMBER_" + s)

def strict_json(data: bytes, *, max_size: int = 4_000_000) -> Any:
    if len(data) > max_size or not data:
        deny("JSON_SIZE")
    try:
        return json.loads(data.decode("utf-8", "strict"), object_pairs_hook=_pairs,
                          parse_constant=_bad_constant)
    except (UnicodeError, ValueError, TypeError) as exc:
        if isinstance(exc, AuditReject):
            raise
        deny("JSON_INVALID")

def exact(obj: Any, keys: set[str], label: str) -> dict[str, Any]:
    if type(obj) is not dict or set(obj) != keys:
        deny("SCHEMA_" + label)
    return obj

def hex64(x: Any, label: str) -> str:
    if type(x) is not str or HEX64.fullmatch(x) is None:
        deny("HASH_" + label)
    return x

def ident(x: Any, label: str) -> str:
    if type(x) is not str or TOKEN.fullmatch(x) is None:
        deny("IDENT_" + label)
    return x

def _instant(x: Any) -> datetime:
    if type(x) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", x):
        deny("TIME_FORMAT")
    try:
        return datetime.strptime(x, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        deny("TIME_INVALID")

def validate_entitlement(envelope: Any, *, trusted_issuer_public_key: bytes,
                         expected_tenant: str, expected_source_hash: str,
                         purpose: str, current_utc: str) -> dict[str, Any]:
    """Verify independent Ed25519 entitlement against explicitly pinned key.

    The caller supplies tenant identity from authenticated server context, not a request body.
    Private signing keys are never included in QROS source, mobile assets or receipts.
    """
    exact(envelope, {"body", "signature_b64"}, "ENTITLEMENT_ENVELOPE")
    body = exact(envelope["body"], {"schema", "issuer", "tenant", "source_sha256", "source_id",
                                    "license_id", "purpose", "expires_utc", "redistribution",
                                    "source_class"}, "ENTITLEMENT_BODY")
    if body["schema"] != "QROS_G4_SIGNED_ENTITLEMENT_TEST_V1":
        deny("ENTITLEMENT_VERSION")
    for key in ("issuer", "tenant", "source_id", "license_id"):
        ident(body[key], key)
    if body["tenant"] != ident(expected_tenant, "EXPECTED_TENANT"):
        deny("CROSS_TENANT")
    if body["source_sha256"] != hex64(expected_source_hash, "EXPECTED_SOURCE"):
        deny("SOURCE_LICENSE_MISMATCH")
    if body["purpose"] != purpose or purpose not in ("SYNTHETIC_SECURITY_TEST", "RESEARCH_PRIVATE"):
        deny("UNLICENSED_PURPOSE")
    if body["redistribution"] is not False or body["source_class"] not in ("SYNTHETIC_ONLY", "LICENSED_PRIVATE"):
        deny("RIGHTS_OR_SOURCE_CLASS")
    if body["source_class"] == "SYNTHETIC_ONLY" and purpose != "SYNTHETIC_SECURITY_TEST":
        deny("SYNTHETIC_CANNOT_BECOME_LIVE")
    if _instant(body["expires_utc"]) <= _instant(current_utc):
        deny("LICENSE_EXPIRED")
    if len(trusted_issuer_public_key) != 32:
        deny("PINNED_ISSUER_KEY_REQUIRED")
    try:
        signature = base64.b64decode(envelope["signature_b64"], validate=True)
        if len(signature) != 64:
            deny("ENTITLEMENT_SIGNATURE_LENGTH")
        Ed25519PublicKey.from_public_bytes(trusted_issuer_public_key).verify(signature, canonical(body))
    except (ValueError, InvalidSignature, TypeError):
        deny("ENTITLEMENT_SIGNATURE_INVALID")
    return body

ROW_KEYS = {"local_time", "utc_offset_minutes", "fold", "bid_u", "ask_u", "session", "session_end"}
SPEC_KEYS = {"schema", "symbol", "source_sha256", "broker_timezone", "max_gap_ms", "max_rows", "source_class"}

def _local_epoch(row: dict[str, Any], tz: ZoneInfo) -> int:
    value = row["local_time"]
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}", value):
        deny("LOCAL_DATETIME_REQUIRED")
    try:
        naive = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        deny("LOCAL_DATETIME_INVALID")
    fold = row["fold"]
    offset = row["utc_offset_minutes"]
    if type(fold) is not int or fold not in (0, 1) or type(offset) is not int or not -14*60 <= offset <= 14*60:
        deny("DST_FOLD_OR_OFFSET_REQUIRED")
    selected = naive.replace(tzinfo=tz, fold=fold)
    derived = selected.utcoffset()
    if derived is None or int(derived.total_seconds()) != offset * 60:
        deny("TIMEZONE_OFFSET_MISMATCH")
    utc = selected.astimezone(timezone.utc)
    alternative = naive.replace(tzinfo=tz, fold=1-fold)
    if alternative.utcoffset() == derived and fold == 1:
        deny("UNNECESSARY_FOLD_ONE")
    back = utc.astimezone(tz)
    if back.replace(tzinfo=None) != naive or back.fold != fold:
        deny("NONEXISTENT_OR_AMBIGUOUS_LOCAL_TIME")
    return (utc.toordinal() - datetime(1970, 1, 1).toordinal())*86_400_000 + (utc.hour*3600+utc.minute*60+utc.second)*1000+utc.microsecond//1000

def audit(raw: bytes, spec: Any, entitlement: Any, *, trusted_issuer_public_key: bytes,
          authenticated_tenant: str, purpose: str, current_utc: str) -> dict[str, Any]:
    """Audit original JSONL bytes; never impute or optimize. Report diagnostics without erasing defects."""
    spec = exact(spec, SPEC_KEYS, "SPEC")
    if spec["schema"] != "QROS_G4_DATA_SPEC_TEST_V1":
        deny("DATA_SPEC_VERSION")
    ident(spec["symbol"], "SYMBOL")
    expected_hash = hex64(spec["source_sha256"], "RAW_SOURCE")
    if digest(raw) != expected_hash:
        deny("RAW_SOURCE_HASH_MISMATCH")
    if spec["source_class"] not in ("SYNTHETIC_ONLY", "LICENSED_PRIVATE"):
        deny("DATA_SOURCE_CLASS")
    body = validate_entitlement(entitlement, trusted_issuer_public_key=trusted_issuer_public_key,
                                expected_tenant=authenticated_tenant, expected_source_hash=expected_hash,
                                purpose=purpose, current_utc=current_utc)
    if body["source_class"] != spec["source_class"]:
        deny("SOURCE_CLASS_MISMATCH")
    name = spec["broker_timezone"]
    if type(name) is not str or name in ("UTC", "Etc/UTC"):
        deny("EXPLICIT_BROKER_LOCAL_TIMEZONE_REQUIRED")
    try:
        tz = ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        deny("UNKNOWN_TIMEZONE")
    max_gap = spec["max_gap_ms"]
    limit = spec["max_rows"]
    if type(max_gap) is not int or max_gap < 1 or type(limit) is not int or not 1 <= limit <= 1_000_000:
        deny("DATA_LIMIT_POLICY")
    lines = raw.splitlines(keepends=True)
    if not raw.endswith(b"\n") or not lines or len(lines) > limit:
        deny("RAW_NEWLINE_OR_ROW_LIMIT")
    previous_ms: int | None = None
    previous_session: int | None = None
    previous_end = False
    diagnostics = {"zero_spread_preserved": 0, "crossed_spread_preserved": 0, "large_gaps": 0,
                   "session_transitions": 0, "invalid_execution_quotes": 0}
    for index, line in enumerate(lines):
        if not line.endswith(b"\n") or b"\r" in line:
            deny("ROW_ENCODING_OR_LINE_ENDING")
        row = exact(strict_json(line, max_size=8192), ROW_KEYS, "ROW")
        ms = _local_epoch(row, tz)
        if previous_ms is not None and ms <= previous_ms:
            deny("DUPLICATE_OR_OUT_OF_ORDER_UTC")
        session = row["session"]
        if type(session) is not int or session < 1 or type(row["session_end"]) is not bool:
            deny("SESSION_SCHEMA")
        if previous_session is not None:
            if session != previous_session:
                if not previous_end or session <= previous_session:
                    deny("SESSION_BOUNDARY_OR_ORDER")
                diagnostics["session_transitions"] += 1
            elif previous_end:
                deny("TICKS_AFTER_SESSION_END")
        bid, ask = row["bid_u"], row["ask_u"]
        if type(bid) is not int or type(ask) is not int or bid <= 0 or ask <= 0:
            deny("PRICE_TYPE_OR_RANGE")
        if ask == bid:
            diagnostics["zero_spread_preserved"] += 1
            diagnostics["invalid_execution_quotes"] += 1
        elif ask < bid:
            diagnostics["crossed_spread_preserved"] += 1
            diagnostics["invalid_execution_quotes"] += 1
        if previous_ms is not None and ms-previous_ms > max_gap:
            diagnostics["large_gaps"] += 1
        previous_ms, previous_session, previous_end = ms, session, row["session_end"]
    if not previous_end:
        deny("UNSEALED_LAST_SESSION")
    return {"schema": "QROS_G4_DATA_AUDIT_TEST_RECEIPT_V1", "classification": "TEST_ONLY_NO_SCIENTIFIC_AUTHORITY",
            "tenant": authenticated_tenant, "source_id": body["source_id"], "source_sha256": expected_hash,
            "license_id": body["license_id"], "source_class": spec["source_class"],
            "broker_timezone": name, "rows": len(lines), "diagnostics": diagnostics,
            "execution_eligible": diagnostics["invalid_execution_quotes"] == 0,
            "imputation": "NONE", "economic_tests": 0, "holdout_open": False, "ga2_open": False,
            "audit_spec_sha256": digest(canonical(spec))}
