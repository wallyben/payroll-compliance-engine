"""
Findings are sorted deterministically by rule_id then employee_id (first in employee_refs).
Same file run twice must produce identical finding list.
"""
import io
import json
from pathlib import Path

import pandas as pd
import pytest

from core.normalize.mapper import normalize
from core.rules.engine import run_all
from core.reporting.exposure_engine import build_exposure_report

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "core" / "rules" / "ie_config_2026.json"


def _load_config():
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


def test_same_file_twice_identical_findings():
    """Run the same CSV through the engine twice; findings must be identical."""
    csv = "employee_id,gross_pay,net_pay,paye,usc,prsi_ee\nE1,1000,800,100,50,50\nE2,2000,1600,200,100,100\nE3,500,300,50,25,25\n"
    df = pd.read_csv(io.StringIO(csv))
    mapping = {"employee_id": "employee_id", "gross_pay": "gross_pay", "net_pay": "net_pay", "paye": "paye", "usc": "usc", "prsi_ee": "prsi_ee"}
    config = _load_config()
    rows1, invalid1 = normalize(df, mapping)
    rows2, invalid2 = normalize(df, mapping)
    findings1 = run_all(rows1, config, invalid_rows=invalid1)
    findings2 = run_all(rows2, config, invalid_rows=invalid2)
    assert len(findings1) == len(findings2)
    for i, (f1, f2) in enumerate(zip(findings1, findings2)):
        assert f1.get("rule_id") == f2.get("rule_id"), f"position {i}: rule_id mismatch"
        assert f1.get("severity") == f2.get("severity"), f"position {i}: severity mismatch"
        assert (f1.get("employee_refs") or []) == (f2.get("employee_refs") or []), f"position {i}: employee_refs mismatch"


def test_findings_sorted_by_rule_id_then_employee():
    """Findings returned by run_all are sorted by rule_id, then first employee_ref."""
    from core.rules.engine import _sort_findings
    findings = [
        {"rule_id": "IE.PAY.001", "employee_refs": ["E2"], "severity": "HIGH"},
        {"rule_id": "IE.NET.001", "employee_refs": ["E1"], "severity": "CRITICAL"},
        {"rule_id": "IE.NET.001", "employee_refs": ["E2"], "severity": "CRITICAL"},
    ]
    sorted_f = _sort_findings(findings)
    rule_ids = [f["rule_id"] for f in sorted_f]
    assert rule_ids == ["IE.NET.001", "IE.NET.001", "IE.PAY.001"]
    assert sorted_f[0]["employee_refs"] == ["E1"]
    assert sorted_f[1]["employee_refs"] == ["E2"]
