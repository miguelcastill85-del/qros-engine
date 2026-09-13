#!/usr/bin/env python3
"""Deterministic, non-economic intake audit for QROS public hypotheses.

This tool never reads market data or PnL.  It maps public-source snapshots,
normalizes causal vocabulary, compares hypotheses with the frozen prior seed
catalogues, and emits an execution-order ledger.  Scores order source audits;
they are not evidence of alpha and never discard a scientifically eligible
hypothesis by themselves.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


SCHEMA = "QROS_PUBLIC_HYPOTHESIS_CAUSAL_TRIAGE_V1"

PHRASES = {
    "opening range": "opening_range",
    "rango de apertura": "opening_range",
    "opening drive": "opening_drive",
    "mean reversion": "mean_reversion",
    "reversion a la media": "mean_reversion",
    "failed breakout": "failed_breakout",
    "false breakout": "failed_breakout",
    "support resistance": "support_resistance",
    "soporte resistencia": "support_resistance",
    "relative strength": "relative_strength",
    "fuerza relativa": "relative_strength",
    "cross pair": "cross_asset",
    "cross asset": "cross_asset",
    "multi timeframe": "multi_timeframe",
    "fair value gap": "fair_value_gap",
    "order block": "order_block",
    "day of week": "day_of_week",
    "dia de la semana": "day_of_week",
    "standard deviation": "standard_deviation",
    "desviacion estandar": "standard_deviation",
    "moving average": "moving_average",
    "media movil": "moving_average",
    "trend following": "trend_following",
    "seguimiento de tendencia": "trend_following",
    "price action": "price_action",
    "accion del precio": "price_action",
}

SYNONYMS = {
    "ruptura": "breakout", "breakthrough": "breakout", "break": "breakout",
    "reversal": "reversal", "reversion": "reversal", "reversiones": "reversal",
    "tendencia": "trend", "tendencial": "trend", "trendfollowing": "trend_following",
    "cruce": "crossover", "cross": "crossover", "crossover": "crossover",
    "volatilidad": "volatility", "volatil": "volatility",
    "divergencia": "divergence", "divergences": "divergence",
    "momento": "momentum", "impulso": "momentum",
    "liquidez": "liquidity", "estructura": "structure",
    "volumen": "volume", "flujo": "flow",
    "canal": "channel", "rango": "range",
    "sesion": "session", "calendario": "calendar",
    "adaptativo": "adaptive", "adaptativa": "adaptive", "adaptativos": "adaptive",
    "regresion": "regression", "media": "average",
    "patron": "pattern", "patrones": "pattern", "vela": "candlestick", "velas": "candlestick",
}

STOPWORDS = {
    "a", "al", "and", "con", "de", "del", "el", "en", "for", "la", "las", "los",
    "of", "on", "para", "por", "que", "the", "to", "trading", "strategy", "estrategia",
    "based", "basada", "basado", "system", "sistema", "dynamic", "dinamica", "dinamico",
    "advanced", "enhanced", "multi", "multiple", "quantitative", "public", "qros",
}

TAG_PATTERNS = {
    "opening_range": r"\b(?:orb|opening_range|opening\s+range|morning\s+candle)\b",
    "gap": r"\b(?:gap|gaps|overnight)\b",
    "breakout": r"\b(?:breakout|breakthrough|turtle|donchian)\b",
    "failed_breakout": r"\b(?:failed_breakout|fakeout|head\s*fake|failure)\b",
    "mean_reversion": r"\b(?:mean_reversion|reversal|reversion|contrarian|fade)\b",
    "trend": r"\b(?:trend|trend_following|pullback)\b",
    "momentum": r"\b(?:momentum|acceleration|roc)\b",
    "divergence": r"\bdivergence\b",
    "crossover": r"\b(?:crossover|cross)\b",
    "volatility": r"\b(?:volatility|atr|squeeze|standard_deviation|variance|vix)\b",
    "volume_flow": r"\b(?:volume|vwap|obv|mfi|cmf|pvt|flow|tick\s*intensity)\b",
    "structure_liquidity": r"\b(?:structure|liquidity|support_resistance|pivot|order_block|fair_value_gap|bos|choch|supply|demand)\b",
    "candlestick": r"\b(?:candlestick|engulfing|harami|hammer|star|doji|wick)\b",
    "session_calendar": r"\b(?:session|calendar|day_of_week|month|weekend|friday|tuesday|seasonality|lunar|moon)\b",
    "cross_asset": r"\b(?:cross_asset|relative_strength|correlation|cointegration|kalman|benchmark|ratio)\b",
    "adaptive_filter": r"\b(?:adaptive|mama|fama|ehlers|fisher|hurst|fld|gaussian|laguerre|fourier|hilbert|wavelet|kernel|nadaraya|kalman|voss)\b",
    "moving_average": r"\b(?:moving_average|ema|sma|wma|dema|tema|frama|ama|mama|fama|hma)\b",
    "oscillator": r"\b(?:rsi|stochastic|stoch|cci|macd|trix|williams|rvi|awesome|ao|adx|dmi)\b",
    "grid_martingale": r"\b(?:grid|martingale|averaging\s+down|pyramiding)\b",
    "options": r"\b(?:option|options|put|call)\b",
    "astrology": r"\b(?:lunar|moon|moon_phase)\b",
    "ichimoku": r"\b(?:ichimoku|tenkan|kijun|kumo|senkou)\b",
    "shock": r"\b(?:shock|spike|surge|explosion)\b",
}

INDICATOR_TAGS = {
    "atr", "bollinger", "cci", "cmf", "dema", "donchian", "ehlers", "ema", "fama",
    "fisher", "fourier", "fractal", "frama", "gaussian", "hma", "hurst", "ichimoku",
    "kalman", "laguerre", "macd", "mama", "mfi", "obv", "pivot", "psar", "regression",
    "rsi", "sma", "stochastic", "supertrend", "tema", "trix", "vwap", "wma", "zigzag",
}

MANUAL_OVERRIDES = {
    "FMZ:458067": {
        "review": "COVERED_G31_ICHIMOKU_STYLE",
        "classification": "COVERED_G31_ICHIMOKU",
        "wave": "PRESERVE_AS_COVERED_NOT_FIRST_DISPATCH",
        "note": "Code is a rolling-range equilibrium/cloud cross with historical displacement: a G31 Ichimoku-style descendant, despite the Magic Channel title.",
    },
    "FMZ:482888": {
        "review": "COMPONENT_RECOMBINATION_NOT_NEW_ROOT",
        "classification": "DESCENDANT_OR_OVERLAP_REVIEW",
        "wave": "PRESERVE_AS_COVERED_NOT_FIRST_DISPATCH",
        "note": "The so-called Gaussian channel is EMA plus rolling standard deviation, combined with Stochastic RSI; its causal components are already represented in prior seeds.",
    },
    "FMZ:482919": {
        "review": "COMPONENT_RECOMBINATION_NOT_NEW_ROOT",
        "classification": "DESCENDANT_OR_OVERLAP_REVIEW",
        "wave": "PRESERVE_AS_COVERED_NOT_FIRST_DISPATCH",
        "note": "TEMA price cross and Fisher-style oscillator confirmation recombine previously represented causal components.",
    },
    "FMZ:473148": {
        "review": "COVERED_MA_FAILED_BREAKOUT",
        "classification": "NEAR_DUPLICATE_PRIOR_200",
        "wave": "PRESERVE_AS_COVERED_NOT_FIRST_DISPATCH",
        "note": "SMA-trend support failure is within the frozen MA failed-breakout family; source also needs execution hardening.",
    },
    "FMZ:483087": {
        "review": "COVERED_BOLLINGER_OUTER_BAND_REVERSION",
        "classification": "NEAR_DUPLICATE_PRIOR_200",
        "wave": "PRESERVE_AS_COVERED_NOT_FIRST_DISPATCH",
        "note": "Multiple simultaneous Bollinger extremes are a parameterized descendant of the prior outer-band reversion seed.",
    },
    "FMZ:483125": {
        "review": "COVERED_DAILY_EXTREME_CONTRARIAN",
        "classification": "NEAR_DUPLICATE_PRIOR_200",
        "wave": "PRESERVE_AS_COVERED_NOT_FIRST_DISPATCH",
        "note": "The code fades daily extremes (long below the low, short above the high), overlapping the prior PDH/PDL contrarian family.",
    },
    "FMZ:430662": {
        "review": "PASS_ROOT_HYPOTHESIS_WITH_HARDENING",
        "note": "Actual source trades MAMA/FAMA crossover; EMA claims in prose are not implemented.",
    },
    "FMZ:437046": {
        "review": "DEFER_CROSS_ASSET_NUMERICAL_REDESIGN_REQUIRED",
        "note": "ROC ratio can divide by a near-zero benchmark return; synchronized dual-asset authority required.",
    },
    "FMZ:458267": {
        "review": "COVERED_OPENING_RANGE_SOURCE_BUG",
        "note": "Wrong-side stop-entry semantics and state desynchronization in the public implementation.",
    },
    "FMZ:451726": {
        "review": "COVERED_OPENING_RANGE_INCOMPLETE_EXECUTION",
        "note": "Opening-range family already covered; public code lacks complete exit/risk semantics.",
    },
    "FMZ:440076": {
        "review": "SOURCE_DESCRIPTION_MISMATCH",
        "note": "Public code does not implement the advertised previous-close/open gap condition.",
    },
    "FMZ:436753": {
        "review": "SOURCE_DESCRIPTION_MISMATCH_PROHIBITED_RISK",
        "note": "Public code is a MACD martingale, not a cross-pair Bollinger hypothesis.",
    },
    "FMZ:449810": {
        "review": "CAUSAL_LAGGED_FLD_SECOND_WAVE",
        "note": "Trading logic uses past-shifted values; plotted forward offset is not itself an executable forecast.",
    },
    "FMZ:430668": {
        "review": "DEFER_UNSUPPORTED_OPTIONS_DATA",
        "note": "Published thesis depends on option put/call data outside the certified tick universe.",
    },
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()
    text = text.replace("/", " ").replace("-", " ")
    for phrase, replacement in sorted(PHRASES.items(), key=lambda kv: -len(kv[0])):
        text = re.sub(r"\b" + re.escape(phrase) + r"\b", replacement, text)
    return re.sub(r"[^a-z0-9_+.%]+", " ", text).strip()


def tokens(text: str) -> list[str]:
    out = []
    for token in normalize(text).split():
        token = SYNONYMS.get(token, token)
        if len(token) > 1 and token not in STOPWORDS and not token.isdigit():
            out.append(token)
    return out


def tags(text: str) -> set[str]:
    norm = normalize(text)
    found = {name for name, pattern in TAG_PATTERNS.items() if re.search(pattern, norm)}
    for indicator in INDICATOR_TAGS:
        if re.search(r"\b" + re.escape(indicator) + r"\b", norm):
            found.add(indicator)
    return found


def parse_prior(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"^##\s+(\d+)\.\s+(.+)$", raw, re.M))
    rows = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        section = raw[m.end():end]
        rows.append({"number": int(m.group(1)), "name": m.group(2).strip(), "text": section.strip()})
    return rows


def source_map(repo: Path) -> dict[str, list[Path]]:
    mapping: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(repo.glob("*.md")):
        if path.name == "README.md":
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        for sid in sorted(set(re.findall(r"https?://(?:www\.)?fmz\.com/strategy/(\d+)", raw))):
            mapping[sid].append(path)
    return mapping


def extract_code(raw: str) -> tuple[str, str]:
    pos = raw.find("> Source")
    if pos < 0:
        return "", ""
    match = re.search(r"```\s*([^\n]*)\n(.*?)```", raw[pos:], re.S)
    if not match:
        return "", ""
    return match.group(1).strip(), match.group(2)


def code_flags(code: str) -> list[str]:
    rules = {
        "LOOKAHEAD_ON": r"barmerge\.lookahead_on|lookahead\s*=\s*true",
        "EXTERNAL_SYMBOL": r"request\.security\s*\(|\bsecurity\s*\(",
        "ZIGZAG_OR_PIVOT_REPAINT_RISK": r"zigzag|pivothigh|pivotlow",
        "FUTURE_OR_OFFSET_REVIEW": r"\boffset\s*=|\bfuture\b",
        "MARTINGALE_OR_GRID": r"martingale|grid|averaging\s*down",
        "PYRAMIDING": r"pyramiding\s*=\s*[2-9]",
        "NO_EXPLICIT_EXIT_CALL": r"$^",
    }
    found = [name for name, pat in rules.items() if name != "NO_EXPLICIT_EXIT_CALL" and re.search(pat, code, re.I)]
    if "strategy.entry" in code and not re.search(r"strategy\.(?:exit|close|close_all)", code):
        found.append("NO_EXPLICIT_EXIT_CALL")
    return sorted(found)


def primary_family(found: set[str]) -> str:
    if "astrology" in found:
        return "NON_MARKET_ASTROLOGY"
    if "grid_martingale" in found:
        return "GRID_OR_MARTINGALE"
    if "options" in found:
        return "OPTIONS_DERIVED"
    if "opening_range" in found:
        return "SESSION_OPENING_RANGE"
    if "ichimoku" in found:
        return "ICHIMOKU_CLOUD"
    if {"shock", "volatility", "momentum"}.issubset(found):
        return "VOLATILITY_SHOCK_MOMENTUM"
    if "cross_asset" in found:
        return "CROSS_ASSET_RELATIVE_VALUE"
    if "adaptive_filter" in found:
        return "ADAPTIVE_SIGNAL_PROCESSING"
    if "divergence" in found:
        return "DIVERGENCE"
    if "failed_breakout" in found:
        return "FAILED_BREAKOUT_REVERSION"
    if "breakout" in found and "volatility" in found:
        return "VOLATILITY_BREAKOUT"
    if "breakout" in found:
        return "BREAKOUT_CHANNEL_RANGE"
    if "mean_reversion" in found:
        return "MEAN_REVERSION"
    if "structure_liquidity" in found:
        return "STRUCTURE_LIQUIDITY"
    if "volume_flow" in found:
        return "VOLUME_FLOW_VWAP"
    if "candlestick" in found:
        return "CANDLE_PRICE_ACTION"
    if "trend" in found or "moving_average" in found:
        return "TREND_PULLBACK_CROSSOVER"
    if "momentum" in found or "oscillator" in found:
        return "MOMENTUM_OSCILLATOR"
    if "session_calendar" in found:
        return "SESSION_CALENDAR"
    return "OTHER_TECHNICAL"


def data_requirement(found: set[str]) -> str:
    if "astrology" in found:
        return "NON_MARKET_EPHEMERIS"
    if "options" in found:
        return "OPTIONS_CHAIN_OR_PUT_CALL"
    if "cross_asset" in found:
        return "SYNCHRONIZED_XAU_NQX"
    if "volume_flow" in found:
        return "VOLUME_SEMANTICS_AUTHORITY_REQUIRED"
    if "session_calendar" in found:
        return "BROKER_TIMEZONE_DST_PROOF_REQUIRED"
    return "PRICE_TICKS_ONLY"


def tfidf_vectors(doc_tokens: list[list[str]]) -> tuple[list[Counter], dict[str, float], list[float]]:
    counts = [Counter(toks) for toks in doc_tokens]
    df = Counter()
    for count in counts:
        df.update(count.keys())
    n = len(counts)
    idf = {tok: math.log((1 + n) / (1 + freq)) + 1.0 for tok, freq in df.items()}
    norms = []
    for count in counts:
        norms.append(math.sqrt(sum((freq * idf[tok]) ** 2 for tok, freq in count.items())))
    return counts, idf, norms


def cosine(a: Counter, b: Counter, idf: dict[str, float], na: float, nb: float) -> float:
    if not na or not nb:
        return 0.0
    common = set(a).intersection(b)
    return sum(a[t] * b[t] * idf[t] ** 2 for t in common) / (na * nb)


def tag_similarity(a: set[str], b: set[str]) -> float:
    core = set(TAG_PATTERNS) | INDICATOR_TAGS
    aa, bb = a & core, b & core
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / len(aa | bb)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--prior", type=Path, action="append", required=True)
    ap.add_argument("--fmz-repo", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    with args.catalog.open(encoding="utf-8-sig", newline="") as f:
        candidates = list(csv.DictReader(f))
    priors = []
    for path in args.prior:
        priors.extend(parse_prior(path))
    mapping = source_map(args.fmz_repo)

    assert len(candidates) == 1000, len(candidates)
    assert len({r["ID"] for r in candidates}) == 1000
    assert len({r["Source_ID"] for r in candidates}) == 1000
    assert len(priors) == 200, len(priors)

    candidate_docs = [" ".join([r["Nombre_publicado"], r["Categoria"], r["Subcategoria"], r["Hipotesis_causal_QROS"], r["Mecanica_base_interpretada"], r["Indicadores_eventos"]]) for r in candidates]
    prior_docs = [p["name"] + " " + p["text"] for p in priors]
    all_docs = prior_docs + candidate_docs
    all_tokens = [tokens(d) for d in all_docs]
    vectors, idf, norms = tfidf_vectors(all_tokens)
    prior_tags = [tags(d) for d in prior_docs]

    ledger = []
    for idx, (row, doc) in enumerate(zip(candidates, candidate_docs)):
        cand_idx = len(priors) + idx
        ctags = tags(doc)
        comparisons = []
        for j, prior in enumerate(priors):
            lexical = cosine(vectors[cand_idx], vectors[j], idf, norms[cand_idx], norms[j])
            causal = tag_similarity(ctags, prior_tags[j])
            hybrid = 0.55 * lexical + 0.45 * causal
            comparisons.append((hybrid, lexical, causal, prior))
        hybrid, lexical, causal, nearest = max(comparisons, key=lambda x: (x[0], -x[3]["number"]))

        fmz_id = re.search(r"(\d+)", row["Source_ID"])
        paths = mapping.get(fmz_id.group(1) if fmz_id else "", [])
        source_path = paths[0] if len(paths) == 1 else None
        source_lang = source_sha = ""
        cflags: list[str] = []
        alignment = None
        if source_path:
            raw = source_path.read_text(encoding="utf-8", errors="replace")
            source_lang, code = extract_code(raw)
            source_sha = sha256(source_path)
            cflags = code_flags(code)
            expected = ctags & INDICATOR_TAGS
            observed = tags(code) & INDICATOR_TAGS
            alignment = round(len(expected & observed) / len(expected), 6) if expected else 1.0

        family = primary_family(ctags)
        data_need = data_requirement(ctags)
        if family in {"NON_MARKET_ASTROLOGY", "GRID_OR_MARTINGALE"}:
            prior_state = "EXCLUDE_INCOMPATIBLE_CAUSAL_OR_RISK_CORE"
        elif family == "SESSION_OPENING_RANGE":
            prior_state = "COVERED_ORB_AND_NEARBY_FAMILY"
        elif family == "ICHIMOKU_CLOUD":
            prior_state = "COVERED_G31_ICHIMOKU"
        elif family == "VOLATILITY_SHOCK_MOMENTUM":
            prior_state = "COVERED_G30_SHOCK_MOMENTUM"
        elif hybrid >= 0.58:
            prior_state = "NEAR_DUPLICATE_PRIOR_200"
        elif hybrid >= 0.40:
            prior_state = "DESCENDANT_OR_OVERLAP_REVIEW"
        else:
            prior_state = "NOVELTY_REVIEW_REQUIRED"

        confidence = {"MEDIA_ALTA": 1.0, "MEDIA": 0.7, "BAJA_AMBIGUA": 0.35}.get(row["Confianza_reglas"], 0.0)
        source_score = 1.0 if source_path else 0.0
        data_score = {"PRICE_TICKS_ONLY": 1.0, "BROKER_TIMEZONE_DST_PROOF_REQUIRED": 0.65, "VOLUME_SEMANTICS_AUTHORITY_REQUIRED": 0.45, "SYNCHRONIZED_XAU_NQX": 0.35}.get(data_need, 0.0)
        novelty = max(0.0, 1.0 - hybrid)
        hazard_penalty = min(0.30, 0.05 * len(cflags))
        dispatch_score = 100.0 * (0.38 * novelty + 0.24 * confidence + 0.20 * source_score + 0.18 * data_score - hazard_penalty)

        if prior_state.startswith("EXCLUDE"):
            wave = "EXCLUDED"
        elif prior_state.startswith("COVERED") or prior_state == "NEAR_DUPLICATE_PRIOR_200":
            wave = "PRESERVE_AS_COVERED_NOT_FIRST_DISPATCH"
        elif data_need == "PRICE_TICKS_ONLY" and source_path and confidence >= 0.7 and "LOOKAHEAD_ON" not in cflags:
            wave = "WAVE_1_DEEP_CAUSAL_AUDIT"
        else:
            wave = "WAVE_2_DEPENDENCY_OR_AMBIGUITY_AUDIT"

        override = MANUAL_OVERRIDES.get(row["Source_ID"])
        if override:
            prior_state = override.get("classification", prior_state)
            wave = override.get("wave", wave)
        ledger.append({
            "id": row["ID"],
            "source_id": row["Source_ID"],
            "name": row["Nombre_publicado"],
            "catalog_category": row["Categoria"],
            "causal_family": family,
            "causal_tags": sorted(ctags),
            "data_requirement": data_need,
            "source_snapshot": {
                "mapped": bool(source_path),
                "path": str(source_path.relative_to(args.fmz_repo)) if source_path else None,
                "sha256": source_sha or None,
                "language": source_lang or None,
                "code_flags": cflags,
                "title_code_indicator_alignment": alignment,
            },
            "prior_200_comparison": {
                "nearest_seed": nearest["number"],
                "nearest_name": nearest["name"],
                "lexical_cosine": round(lexical, 6),
                "causal_tag_jaccard": round(causal, 6),
                "hybrid_overlap": round(hybrid, 6),
                "classification": prior_state,
            },
            "catalog_similarity_reported": float(row["Similitud_max_con_previas_200"]),
            "dispatch_wave": wave,
            "dispatch_score_non_economic": round(dispatch_score, 6),
            "manual_source_audit": override,
            "scientific_status": "HYPOTHESIS_ONLY_NO_ALPHA_CLAIM_NO_PNL_READ",
        })

    ledger.sort(key=lambda x: (-x["dispatch_score_non_economic"], x["id"]))
    summary = {
        "schema": SCHEMA,
        "status": "TRIAGE_COMPLETE_NO_RESULTS",
        "scope": "Hypothesis intake, causal deduplication, source mapping and dispatch order only",
        "inputs": {
            "catalog": {"path": args.catalog.name, "sha256": sha256(args.catalog), "rows": len(candidates)},
            "prior_catalogs": [{"path": p.name, "sha256": sha256(p)} for p in args.prior],
            "fmz_repo": {"path": str(args.fmz_repo), "readme_sha256": sha256(args.fmz_repo / "README.md")},
        },
        "controls": {
            "pnl_read": False,
            "market_data_read": False,
            "holdout_opened": False,
            "score_meaning": "Dispatch order for deeper source audit only; not alpha, approval or scientific rejection",
            "all_nonexcluded_hypotheses_preserved": True,
        },
        "coverage": {
            "catalog_rows": len(candidates),
            "unique_ids": len({r["ID"] for r in candidates}),
            "prior_seeds_parsed": len(priors),
            "source_snapshots_mapped": sum(x["source_snapshot"]["mapped"] for x in ledger),
            "source_snapshots_unmapped": sum(not x["source_snapshot"]["mapped"] for x in ledger),
        },
        "dispatch_waves": dict(sorted(Counter(x["dispatch_wave"] for x in ledger).items())),
        "causal_families": dict(sorted(Counter(x["causal_family"] for x in ledger).items())),
        "top_wave_1": [{k: x[k] for k in ("id", "source_id", "name", "causal_family", "dispatch_score_non_economic")} for x in ledger if x["dispatch_wave"] == "WAVE_1_DEEP_CAUSAL_AUDIT"][:30],
        "unmapped_sources": [{"id": x["id"], "source_id": x["source_id"], "name": x["name"]} for x in ledger if not x["source_snapshot"]["mapped"]],
        "next_action": "Deep-audit Wave-1 sources, select first root hypothesis, freeze G32 ontology, then run RISE fixed-point before market/PnL access.",
    }

    ledger_path = args.out_dir / "QROS_1000_HYPOTHESIS_CAUSAL_TRIAGE_V1.jsonl"
    summary_path = args.out_dir / "QROS_1000_HYPOTHESIS_CAUSAL_TRIAGE_SUMMARY_V1.json"
    with ledger_path.open("w", encoding="utf-8", newline="\n") as f:
        for row in ledger:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    summary["outputs"] = {
        "ledger": {"path": ledger_path.name, "rows": len(ledger), "sha256": sha256(ledger_path)},
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
