"""tests/test_alerts.py
Tests for product/alerts/alert_engine.py

Covers:
- No alerts for a clean run
- HIGH_AUDIT_RISK fires for HIGH_RISK band
- HIGH_AUDIT_RISK fires for CRITICAL band
- HIGH_AUDIT_RISK does NOT fire for LOW_RISK / MEDIUM_RISK
- HIGH_SEVERITY_VIOLATIONS fires when HIGH findings present
- HIGH_SEVERITY_VIOLATIONS fires when CRITICAL findings present
- HIGH_SEVERITY_VIOLATIONS does NOT fire for MEDIUM/LOW-only findings
- LARGE_PAYROLL_CHANGE fires for increase > 15 %
- LARGE_PAYROLL_CHANGE fires for decrease > 15 %
- LARGE_PAYROLL_CHANGE does NOT fire at exactly 15 %
- LARGE_PAYROLL_CHANGE does NOT fire when percent_change is None
- MULTIPLE_ANOMALIES fires when >= 2 anomalies present
- MULTIPLE_ANOMALIES does NOT fire for 0 or 1 anomaly
- Multiple alerts can fire simultaneously
- Alert dicts contain required keys
- client_id and run_id embedded correctly
- Determinism: same input → same alerts
"""
from __future__ import annotations

import pytest

from product.alerts.alert_engine import generate_alerts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _finding(rule_id: str, severity: str) -> dict:
    return {
        "rule_id": rule_id,
        "severity": severity,
        "title": "T",
        "description": "D",
        "evidence": {},
        "suggestion": "S",
        "amount_impact": 0.0,
        "employee_refs": [],
    }


def _anomaly(rule_id: str = "ANOMALY.001") -> dict:
    return _finding(rule_id, "MEDIUM")


def _run_result(
    risk_band: str = "LOW_RISK",
    risk_points: int = 0,
    findings: list = None,
    anomalies: list = None,
    percent_change: float | None = None,
) -> dict:
    return {
        "audit_risk": {
            "risk_band": risk_band,
            "risk_points": risk_points,
        },
        "findings": findings or [],
        "anomalies": anomalies or [],
        "payroll_diff": {
            "payroll_total_change": {
                "percent_change": percent_change,
            }
        },
    }


_CLIENT = "c1"
_RUN = "run-1"

REQUIRED_ALERT_KEYS = {"alert_type", "client_id", "run_id", "message", "severity"}


# ---------------------------------------------------------------------------
# Clean run — no alerts
# ---------------------------------------------------------------------------

def test_no_alerts_for_clean_run():
    alerts = generate_alerts(_run_result(), _CLIENT, _RUN)
    assert alerts == []


def test_no_alerts_for_low_risk_band():
    alerts = generate_alerts(_run_result(risk_band="LOW_RISK", risk_points=5), _CLIENT, _RUN)
    assert not any(a["alert_type"] == "HIGH_AUDIT_RISK" for a in alerts)


def test_no_alerts_for_medium_risk_band():
    alerts = generate_alerts(_run_result(risk_band="MEDIUM_RISK", risk_points=20), _CLIENT, _RUN)
    assert not any(a["alert_type"] == "HIGH_AUDIT_RISK" for a in alerts)


# ---------------------------------------------------------------------------
# HIGH_AUDIT_RISK
# ---------------------------------------------------------------------------

def test_high_risk_band_triggers_high_audit_risk_alert():
    alerts = generate_alerts(_run_result(risk_band="HIGH_RISK", risk_points=55), _CLIENT, _RUN)
    types = [a["alert_type"] for a in alerts]
    assert "HIGH_AUDIT_RISK" in types


def test_critical_risk_band_triggers_high_audit_risk_alert():
    alerts = generate_alerts(_run_result(risk_band="CRITICAL", risk_points=100), _CLIENT, _RUN)
    types = [a["alert_type"] for a in alerts]
    assert "HIGH_AUDIT_RISK" in types


def test_high_audit_risk_alert_severity_is_high():
    alerts = generate_alerts(_run_result(risk_band="HIGH_RISK", risk_points=55), _CLIENT, _RUN)
    alert = next(a for a in alerts if a["alert_type"] == "HIGH_AUDIT_RISK")
    assert alert["severity"] == "HIGH"


def test_high_audit_risk_embeds_risk_points_in_message():
    alerts = generate_alerts(_run_result(risk_band="HIGH_RISK", risk_points=77), _CLIENT, _RUN)
    alert = next(a for a in alerts if a["alert_type"] == "HIGH_AUDIT_RISK")
    assert "77" in alert["message"]


# ---------------------------------------------------------------------------
# HIGH_SEVERITY_VIOLATIONS
# ---------------------------------------------------------------------------

def test_high_finding_triggers_violation_alert():
    findings = [_finding("IE.PAYE.001", "HIGH")]
    alerts = generate_alerts(_run_result(findings=findings), _CLIENT, _RUN)
    types = [a["alert_type"] for a in alerts]
    assert "HIGH_SEVERITY_VIOLATIONS" in types


def test_critical_finding_triggers_violation_alert():
    findings = [_finding("IE.PRSI.001", "CRITICAL")]
    alerts = generate_alerts(_run_result(findings=findings), _CLIENT, _RUN)
    types = [a["alert_type"] for a in alerts]
    assert "HIGH_SEVERITY_VIOLATIONS" in types


def test_medium_only_findings_do_not_trigger_violation_alert():
    findings = [_finding("IE.USC.001", "MEDIUM")]
    alerts = generate_alerts(_run_result(findings=findings), _CLIENT, _RUN)
    assert not any(a["alert_type"] == "HIGH_SEVERITY_VIOLATIONS" for a in alerts)


def test_low_only_findings_do_not_trigger_violation_alert():
    findings = [_finding("IE.PRSI.004", "LOW")]
    alerts = generate_alerts(_run_result(findings=findings), _CLIENT, _RUN)
    assert not any(a["alert_type"] == "HIGH_SEVERITY_VIOLATIONS" for a in alerts)


def test_violation_alert_severity_is_high():
    findings = [_finding("IE.PAYE.001", "HIGH")]
    alerts = generate_alerts(_run_result(findings=findings), _CLIENT, _RUN)
    alert = next(a for a in alerts if a["alert_type"] == "HIGH_SEVERITY_VIOLATIONS")
    assert alert["severity"] == "HIGH"


def test_violation_alert_includes_rule_id_in_message():
    findings = [_finding("IE.PAYE.001", "HIGH")]
    alerts = generate_alerts(_run_result(findings=findings), _CLIENT, _RUN)
    alert = next(a for a in alerts if a["alert_type"] == "HIGH_SEVERITY_VIOLATIONS")
    assert "IE.PAYE.001" in alert["message"]


# ---------------------------------------------------------------------------
# LARGE_PAYROLL_CHANGE
# ---------------------------------------------------------------------------

def test_increase_above_threshold_triggers_large_change_alert():
    alerts = generate_alerts(_run_result(percent_change=25.0), _CLIENT, _RUN)
    types = [a["alert_type"] for a in alerts]
    assert "LARGE_PAYROLL_CHANGE" in types


def test_decrease_above_threshold_triggers_large_change_alert():
    alerts = generate_alerts(_run_result(percent_change=-20.0), _CLIENT, _RUN)
    types = [a["alert_type"] for a in alerts]
    assert "LARGE_PAYROLL_CHANGE" in types


def test_exactly_15_pct_does_not_trigger_large_change_alert():
    alerts = generate_alerts(_run_result(percent_change=15.0), _CLIENT, _RUN)
    assert not any(a["alert_type"] == "LARGE_PAYROLL_CHANGE" for a in alerts)


def test_just_below_threshold_does_not_trigger_large_change_alert():
    alerts = generate_alerts(_run_result(percent_change=14.99), _CLIENT, _RUN)
    assert not any(a["alert_type"] == "LARGE_PAYROLL_CHANGE" for a in alerts)


def test_none_percent_change_does_not_trigger_large_change_alert():
    alerts = generate_alerts(_run_result(percent_change=None), _CLIENT, _RUN)
    assert not any(a["alert_type"] == "LARGE_PAYROLL_CHANGE" for a in alerts)


def test_large_change_alert_severity_is_medium():
    alerts = generate_alerts(_run_result(percent_change=30.0), _CLIENT, _RUN)
    alert = next(a for a in alerts if a["alert_type"] == "LARGE_PAYROLL_CHANGE")
    assert alert["severity"] == "MEDIUM"


def test_large_change_alert_message_contains_direction_increase():
    alerts = generate_alerts(_run_result(percent_change=25.0), _CLIENT, _RUN)
    alert = next(a for a in alerts if a["alert_type"] == "LARGE_PAYROLL_CHANGE")
    assert "increase" in alert["message"].lower()


def test_large_change_alert_message_contains_direction_decrease():
    alerts = generate_alerts(_run_result(percent_change=-18.5), _CLIENT, _RUN)
    alert = next(a for a in alerts if a["alert_type"] == "LARGE_PAYROLL_CHANGE")
    assert "decrease" in alert["message"].lower()


# ---------------------------------------------------------------------------
# MULTIPLE_ANOMALIES
# ---------------------------------------------------------------------------

def test_two_anomalies_triggers_multiple_anomalies_alert():
    anomalies = [_anomaly("ANOMALY.001"), _anomaly("ANOMALY.002")]
    alerts = generate_alerts(_run_result(anomalies=anomalies), _CLIENT, _RUN)
    types = [a["alert_type"] for a in alerts]
    assert "MULTIPLE_ANOMALIES" in types


def test_three_anomalies_triggers_multiple_anomalies_alert():
    anomalies = [_anomaly(f"ANOMALY.00{i}") for i in range(1, 4)]
    alerts = generate_alerts(_run_result(anomalies=anomalies), _CLIENT, _RUN)
    types = [a["alert_type"] for a in alerts]
    assert "MULTIPLE_ANOMALIES" in types


def test_single_anomaly_does_not_trigger_multiple_anomalies_alert():
    anomalies = [_anomaly("ANOMALY.001")]
    alerts = generate_alerts(_run_result(anomalies=anomalies), _CLIENT, _RUN)
    assert not any(a["alert_type"] == "MULTIPLE_ANOMALIES" for a in alerts)


def test_zero_anomalies_does_not_trigger_multiple_anomalies_alert():
    alerts = generate_alerts(_run_result(anomalies=[]), _CLIENT, _RUN)
    assert not any(a["alert_type"] == "MULTIPLE_ANOMALIES" for a in alerts)


def test_multiple_anomalies_alert_severity_is_medium():
    anomalies = [_anomaly("ANOMALY.001"), _anomaly("ANOMALY.002")]
    alerts = generate_alerts(_run_result(anomalies=anomalies), _CLIENT, _RUN)
    alert = next(a for a in alerts if a["alert_type"] == "MULTIPLE_ANOMALIES")
    assert alert["severity"] == "MEDIUM"


# ---------------------------------------------------------------------------
# Multiple alerts firing simultaneously
# ---------------------------------------------------------------------------

def test_multiple_alerts_fire_simultaneously():
    findings = [_finding("IE.PAYE.001", "HIGH")]
    anomalies = [_anomaly("ANOMALY.001"), _anomaly("ANOMALY.002")]
    alerts = generate_alerts(
        _run_result(
            risk_band="CRITICAL",
            risk_points=110,
            findings=findings,
            anomalies=anomalies,
            percent_change=50.0,
        ),
        _CLIENT,
        _RUN,
    )
    types = {a["alert_type"] for a in alerts}
    assert "HIGH_AUDIT_RISK" in types
    assert "HIGH_SEVERITY_VIOLATIONS" in types
    assert "LARGE_PAYROLL_CHANGE" in types
    assert "MULTIPLE_ANOMALIES" in types


# ---------------------------------------------------------------------------
# Alert structure
# ---------------------------------------------------------------------------

def test_alert_contains_required_keys():
    alerts = generate_alerts(_run_result(risk_band="HIGH_RISK", risk_points=55), _CLIENT, _RUN)
    for alert in alerts:
        assert REQUIRED_ALERT_KEYS.issubset(alert.keys()), f"Missing keys in {alert}"


def test_alert_client_id_matches_input():
    alerts = generate_alerts(_run_result(risk_band="HIGH_RISK", risk_points=55), "MY-CLIENT", _RUN)
    for alert in alerts:
        assert alert["client_id"] == "MY-CLIENT"


def test_alert_run_id_matches_input():
    alerts = generate_alerts(_run_result(risk_band="HIGH_RISK", risk_points=55), _CLIENT, "MY-RUN-99")
    for alert in alerts:
        assert alert["run_id"] == "MY-RUN-99"


# ---------------------------------------------------------------------------
# Multi-client isolation
# ---------------------------------------------------------------------------

def test_multi_client_alert_isolation():
    alerts_a = generate_alerts(_run_result(risk_band="HIGH_RISK", risk_points=55), "client-A", "run-a")
    alerts_b = generate_alerts(_run_result(risk_band="LOW_RISK", risk_points=2), "client-B", "run-b")

    assert all(a["client_id"] == "client-A" for a in alerts_a)
    assert all(a["client_id"] == "client-B" for a in alerts_b)
    assert len(alerts_a) > 0
    assert len(alerts_b) == 0


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_deterministic_alerts():
    rr = _run_result(
        risk_band="HIGH_RISK",
        risk_points=55,
        findings=[_finding("IE.PAYE.001", "HIGH")],
        percent_change=20.0,
    )
    alerts1 = generate_alerts(rr, _CLIENT, _RUN)
    alerts2 = generate_alerts(rr, _CLIENT, _RUN)
    assert alerts1 == alerts2
