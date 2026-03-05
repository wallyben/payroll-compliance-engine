#!/usr/bin/env python3
"""
CLI smoke test: validate a payroll CSV and print summary.
Usage: python cli/validate_payroll.py sample.csv
Run from project root. No API, no DB; deterministic.
"""
from __future__ import annotations
import sys
from pathlib import Path

# Project root for imports
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd
from core.normalize.mapper import normalize
from core.rules.engine import run_all
from core.rules.registry import RULESET_VERSION

# Config path
_CONFIG_PATH = _ROOT / "core" / "rules" / "ie_config_2026.json"


def _csv_to_mapping(df: pd.DataFrame) -> dict:
    required = {"employee_id", "gross_pay", "net_pay"}
    canon_fields = {
        "employee_id", "employee_name", "ppsn", "pay_date", "period_start", "period_end",
        "gross_pay", "net_pay", "paye", "usc", "prsi_ee", "prsi_er", "pension_ee", "pension_er", "hours",
    }
    mapping = {}
    for col in df.columns:
        c = (col or "").strip()
        if c in canon_fields:
            mapping[c] = col
    missing = required - set(mapping.keys())
    if missing:
        raise ValueError(f"CSV must include columns: {list(required)}. Found: {list(df.columns)}")
    return mapping


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python cli/validate_payroll.py <path_to.csv>", file=sys.stderr)
        return 1
    csv_path = Path(sys.argv[1])
    if not csv_path.is_file():
        print(f"File not found: {csv_path}", file=sys.stderr)
        return 1
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Invalid CSV: {e}", file=sys.stderr)
        return 1
    if df.empty:
        print("CSV has no rows", file=sys.stderr)
        return 1
    try:
        mapping = _csv_to_mapping(df)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    try:
        rows, invalid_rows = normalize(df, mapping)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    if not rows:
        print("No valid rows after normalization", file=sys.stderr)
        return 1
    config = __import__("json").loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    findings = run_all(rows, config, invalid_rows=invalid_rows)
    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        sev = (f.get("severity") or "").upper()
        if sev in severity_counts:
            severity_counts[sev] += 1
    print("Ruleset:", RULESET_VERSION)
    print("Employees processed:", len(rows))
    print("Findings:", len(findings))
    print()
    print("CRITICAL:", severity_counts["CRITICAL"])
    print("HIGH:", severity_counts["HIGH"])
    print("MEDIUM:", severity_counts["MEDIUM"])
    print("LOW:", severity_counts["LOW"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
