from __future__ import annotations

import types
from typing import Dict, Final, List, Any, Tuple  # noqa: F401 — Tuple kept for existing importers

# ---------------------------------------------------------------------------
# Deterministic, auditable scoring.
# No heuristics. No model inference. Pure severity weighting.
# ---------------------------------------------------------------------------

# Immutable severity-to-points weight table.
# Any change here is a deliberate, reviewable action caught by
# tests/test_scoring_determinism.py::test_severity_weights_values.
SEVERITY_WEIGHTS: Final = types.MappingProxyType({
    "HIGH": 10,
    "MEDIUM": 4,
    "LOW": 1,
})

# Backward-compatible alias — existing callers and the risk_points() default
# parameter both reference this name.
DEFAULT_SEVERITY_WEIGHTS: Dict[str, int] = dict(SEVERITY_WEIGHTS)

# Set of all severity labels the engine recognises.  Unknown labels score 0.
KNOWN_SEVERITIES: Final[frozenset] = frozenset({"HIGH", "MEDIUM", "LOW"})

# Default denominator for compliance_score().  100 risk points → score 0.
SCORE_MAX_POINTS: Final[int] = 100

# Risk band thresholds (inclusive lower bound → label).
# Bands are evaluated from highest threshold down; the first match wins.
# Any change here requires a matching update to test_scoring_determinism.py.
RISK_BAND_THRESHOLDS: Final = types.MappingProxyType({
    81: "LOW_RISK",
    51: "MEDIUM_RISK",
    21: "HIGH_RISK",
    0:  "CRITICAL",
})


def risk_band(score: int) -> str:
    """Map a compliance score (0–100) to a deterministic risk band label.

    Uses RISK_BAND_THRESHOLDS; returns the label of the highest threshold
    that the score meets or exceeds.  Score below 0 (should never occur)
    falls through to CRITICAL.
    """
    for threshold in sorted(RISK_BAND_THRESHOLDS, reverse=True):
        if score >= threshold:
            return RISK_BAND_THRESHOLDS[threshold]
    return "CRITICAL"


def summarize_findings(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    by_rule: Dict[str, int] = {}

    for f in findings:
        sev = (f.get("severity") or "").upper()
        if sev in counts:
            counts[sev] += 1
        rid = f.get("rule_id") or "UNKNOWN"
        by_rule[rid] = by_rule.get(rid, 0) + 1

    return {
        "counts_by_severity": counts,
        "counts_by_rule": by_rule,
        "total_findings": len(findings),
    }


def risk_points(findings: List[Dict[str, Any]], weights: Dict[str, int] | None = None) -> int:
    w = weights or DEFAULT_SEVERITY_WEIGHTS
    points = 0
    for f in findings:
        sev = (f.get("severity") or "").upper()
        points += int(w.get(sev, 0))
    return points


def compliance_score(findings: List[Dict[str, Any]], max_points: int = SCORE_MAX_POINTS) -> int:
    # Deterministic score 0..100:
    # - 0 points => 100 score
    # - >= max_points => 0 score
    pts = risk_points(findings)
    score = max(0, 100 - int(round((pts / max_points) * 100)))
    return min(100, score)


def score_bundle(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary = summarize_findings(findings)
    pts = risk_points(findings)
    score = compliance_score(findings)
    band = risk_band(score)
    exposure = round(
        sum(
            float(f["amount_impact"])
            for f in findings
            if f.get("amount_impact") is not None
        ),
        2,
    )
    return {
        "risk_points": pts,
        "compliance_score": score,
        "risk_band": band,
        "exposure_total": exposure,
        **summary,
    }
