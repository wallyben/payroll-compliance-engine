"""product/alerts/alert_engine.py
----------------------------------
Generates deterministic alerts from payroll review outputs.

Alert triggers (evaluated independently, multiple alerts may fire):
  HIGH_AUDIT_RISK         – audit risk band is HIGH_RISK or CRITICAL
  HIGH_SEVERITY_VIOLATIONS – one or more HIGH/CRITICAL compliance findings
  LARGE_PAYROLL_CHANGE    – gross payroll total changed by more than 15 %
  MULTIPLE_ANOMALIES      – more than one payroll anomaly detected

All alert data is derived solely from the review result dict; no compliance
or payroll logic is re-implemented here.
"""

from __future__ import annotations

from typing import Any, Dict, List

# Risk bands produced by core/scoring/risk.py that warrant an alert.
_HIGH_RISK_BANDS: frozenset[str] = frozenset({"HIGH_RISK", "CRITICAL"})

# Blocking severity labels from the compliance rules engine.
_BLOCKING_SEVERITIES: frozenset[str] = frozenset({"HIGH", "CRITICAL"})

# Payroll total change threshold (percent absolute value).
_PAYROLL_CHANGE_THRESHOLD_PCT: float = 15.0

# Minimum number of anomalies to trigger the MULTIPLE_ANOMALIES alert.
_MULTIPLE_ANOMALIES_MIN: int = 2


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_alerts(
    run_result: Dict[str, Any],
    client_id: str,
    run_id: str,
) -> List[Dict[str, Any]]:
    """Generate alerts from *run_result* for the given *client_id* / *run_id*.

    Parameters
    ----------
    run_result:
        The dict returned by ``review_payroll()``.
    client_id:
        Client identifier embedded in every alert.
    run_id:
        Run identifier embedded in every alert.

    Returns
    -------
    List of alert dicts, each containing:
        "alert_type"  – str  machine-readable category
        "client_id"   – str
        "run_id"      – str
        "message"     – str  human-readable description
        "severity"    – str  "HIGH" | "MEDIUM"
    The list is empty when no triggers fire.  Output is fully deterministic
    for identical inputs.
    """
    alerts: List[Dict[str, Any]] = []

    audit_risk: Dict[str, Any] = run_result.get("audit_risk", {})
    findings: List[Dict[str, Any]] = run_result.get("findings", [])
    anomalies: List[Dict[str, Any]] = run_result.get("anomalies", [])
    payroll_diff: Dict[str, Any] = run_result.get("payroll_diff", {})

    # ── Alert 1: HIGH audit risk band ────────────────────────────────────────
    risk_band: str = audit_risk.get("risk_band", "")
    if risk_band in _HIGH_RISK_BANDS:
        risk_points = audit_risk.get("risk_points", 0)
        alerts.append({
            "alert_type": "HIGH_AUDIT_RISK",
            "client_id": client_id,
            "run_id": run_id,
            "message": (
                f"Payroll run has {risk_band} audit risk band "
                f"with {risk_points} risk points."
            ),
            "severity": "HIGH",
        })

    # ── Alert 2: HIGH/CRITICAL severity violations ───────────────────────────
    high_findings = [
        f for f in findings
        if (f.get("severity") or "").upper() in _BLOCKING_SEVERITIES
    ]
    if high_findings:
        rule_ids = sorted({f.get("rule_id", "UNKNOWN") for f in high_findings})
        preview = ", ".join(rule_ids[:3])
        if len(rule_ids) > 3:
            preview += f", … (+{len(rule_ids) - 3} more)"
        alerts.append({
            "alert_type": "HIGH_SEVERITY_VIOLATIONS",
            "client_id": client_id,
            "run_id": run_id,
            "message": (
                f"{len(high_findings)} high-severity compliance violation(s) detected: "
                f"{preview}."
            ),
            "severity": "HIGH",
        })

    # ── Alert 3: Large payroll change > 15 % ─────────────────────────────────
    payroll_total_change: Dict[str, Any] = payroll_diff.get("payroll_total_change", {})
    percent_change = payroll_total_change.get("percent_change")
    if percent_change is not None and abs(percent_change) > _PAYROLL_CHANGE_THRESHOLD_PCT:
        direction = "increase" if percent_change > 0 else "decrease"
        alerts.append({
            "alert_type": "LARGE_PAYROLL_CHANGE",
            "client_id": client_id,
            "run_id": run_id,
            "message": (
                f"Payroll total {direction} of {abs(percent_change):.1f}% detected, "
                f"exceeding the {_PAYROLL_CHANGE_THRESHOLD_PCT:.0f}% threshold."
            ),
            "severity": "MEDIUM",
        })

    # ── Alert 4: Multiple anomalies ──────────────────────────────────────────
    if len(anomalies) >= _MULTIPLE_ANOMALIES_MIN:
        alerts.append({
            "alert_type": "MULTIPLE_ANOMALIES",
            "client_id": client_id,
            "run_id": run_id,
            "message": (
                f"{len(anomalies)} payroll anomalies detected in this run."
            ),
            "severity": "MEDIUM",
        })

    return alerts
