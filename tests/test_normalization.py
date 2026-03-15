"""
Phase 2 normalisation hardening tests.

Covers:
- Valid rows normalise correctly end-to-end via mapper.normalize.
- Schema-level validators reject NaN/Infinity in float fields.
- Schema-level validator rejects empty/whitespace employee_id.
- Mapper rejects missing required mappings before row processing.
- Mapper rejects a mapped column that is absent from the DataFrame.
- Bad numeric strings are rejected with row context.
- Invalid and impossible dates are rejected with row context.
- New optional schema fields (hourly_rate, prsi_class) pass through cleanly.
- Repeated normalisations of the same input produce identical output.
- Duplicate rows both normalise (no implicit deduplication at this layer).
- Mixed batches (some valid, some invalid) split correctly.
"""

from __future__ import annotations

import math
from datetime import date

import pandas as pd
import pytest
from pydantic import ValidationError

from core.normalize.mapper import normalize
from core.normalize.schema import CanonicalPayrollRow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_MAPPING = {
    "employee_id": "employee_id",
    "gross_pay": "gross_pay",
    "net_pay": "net_pay",
}


def _df(*rows: dict) -> pd.DataFrame:
    """Build a DataFrame from dicts; all values are strings to mirror Phase 1 loader output."""
    return pd.DataFrame([{k: str(v) for k, v in r.items()} for r in rows])


def _valid_row(**overrides) -> dict:
    base = {"employee_id": "E001", "gross_pay": "1000", "net_pay": "800"}
    base.update({k: str(v) for k, v in overrides.items()})
    return base


# ---------------------------------------------------------------------------
# Valid rows
# ---------------------------------------------------------------------------


def test_single_valid_row_normalizes():
    df = _df(_valid_row())
    valid, invalid = normalize(df, BASE_MAPPING)
    assert len(valid) == 1
    assert len(invalid) == 0


def test_valid_row_field_values():
    df = _df(_valid_row())
    valid, _ = normalize(df, BASE_MAPPING)
    row = valid[0]
    assert row.employee_id == "E001"
    assert row.gross_pay == 1000.0
    assert row.net_pay == 800.0


def test_valid_row_with_all_numeric_fields():
    mapping = {**BASE_MAPPING, "paye": "paye", "usc": "usc",
                "prsi_ee": "prsi_ee", "prsi_er": "prsi_er",
                "pension_ee": "pension_ee", "pension_er": "pension_er"}
    df = _df({
        "employee_id": "E001", "gross_pay": "1000", "net_pay": "688",
        "paye": "200", "usc": "30", "prsi_ee": "42", "prsi_er": "114",
        "pension_ee": "20", "pension_er": "20",
    })
    valid, invalid = normalize(df, mapping)
    assert len(valid) == 1
    assert len(invalid) == 0
    row = valid[0]
    assert row.paye == 200.0
    assert row.prsi_ee == 42.0


def test_valid_row_with_pay_date_eu_format():
    mapping = {**BASE_MAPPING, "pay_date": "pay_date"}
    df = _df(_valid_row(pay_date="31/01/2026"))
    valid, invalid = normalize(df, mapping)
    assert len(valid) == 1
    assert valid[0].pay_date == date(2026, 1, 31)


def test_valid_row_with_pay_date_iso_format():
    mapping = {**BASE_MAPPING, "pay_date": "pay_date"}
    df = _df(_valid_row(pay_date="2026-01-31"))
    valid, invalid = normalize(df, mapping)
    assert len(valid) == 1
    assert valid[0].pay_date == date(2026, 1, 31)


def test_valid_row_with_hours():
    mapping = {**BASE_MAPPING, "hours": "hours"}
    df = _df(_valid_row(hours="40"))
    valid, invalid = normalize(df, mapping)
    assert len(valid) == 1
    assert valid[0].hours == 40.0


def test_valid_row_with_hourly_rate():
    mapping = {**BASE_MAPPING, "hourly_rate": "hourly_rate"}
    df = _df(_valid_row(hourly_rate="12.70"))
    valid, invalid = normalize(df, mapping)
    assert len(valid) == 1
    assert valid[0].hourly_rate == 12.70


def test_valid_row_with_prsi_class():
    mapping = {**BASE_MAPPING, "prsi_class": "prsi_class"}
    df = _df(_valid_row(prsi_class="A"))
    valid, invalid = normalize(df, mapping)
    assert len(valid) == 1
    assert valid[0].prsi_class == "A"


def test_optional_fields_absent_are_none():
    df = _df(_valid_row())
    valid, _ = normalize(df, BASE_MAPPING)
    row = valid[0]
    assert row.pay_date is None
    assert row.hours is None
    assert row.hourly_rate is None
    assert row.prsi_class is None


def test_default_deduction_fields_are_zero():
    df = _df(_valid_row())
    valid, _ = normalize(df, BASE_MAPPING)
    row = valid[0]
    assert row.paye == 0.0
    assert row.usc == 0.0
    assert row.prsi_ee == 0.0
    assert row.pension_ee == 0.0


# ---------------------------------------------------------------------------
# Required mapping validation (mapper pre-flight, raises before row iteration)
# ---------------------------------------------------------------------------


def test_missing_employee_id_mapping_raises():
    df = _df(_valid_row())
    with pytest.raises(ValueError, match="Missing required mappings"):
        normalize(df, {"gross_pay": "gross_pay", "net_pay": "net_pay"})


def test_missing_gross_pay_mapping_raises():
    df = _df(_valid_row())
    with pytest.raises(ValueError, match="Missing required mappings"):
        normalize(df, {"employee_id": "employee_id", "net_pay": "net_pay"})


def test_missing_net_pay_mapping_raises():
    df = _df(_valid_row())
    with pytest.raises(ValueError, match="Missing required mappings"):
        normalize(df, {"employee_id": "employee_id", "gross_pay": "gross_pay"})


def test_mapped_column_absent_from_df_raises():
    df = _df(_valid_row())  # has employee_id, gross_pay, net_pay
    with pytest.raises(ValueError, match="Mapped column not found in file"):
        normalize(df, {**BASE_MAPPING, "paye": "tax_column_that_does_not_exist"})


# ---------------------------------------------------------------------------
# Bad numeric values — caught by explicit float() coercion in mapper
# ---------------------------------------------------------------------------


def test_bad_gross_string_produces_invalid_row():
    df = _df(_valid_row(gross_pay="abc"))
    valid, invalid = normalize(df, BASE_MAPPING)
    assert len(valid) == 0
    assert len(invalid) == 1
    assert invalid[0]["row_number"] == 1


def test_bad_net_string_produces_invalid_row():
    df = _df(_valid_row(net_pay="???"))
    valid, invalid = normalize(df, BASE_MAPPING)
    assert len(valid) == 0
    assert len(invalid) == 1


def test_empty_string_gross_produces_invalid_row():
    """Empty string from a blank cell (as delivered by Phase 1 loader) must be rejected."""
    df = _df(_valid_row(gross_pay=""))
    valid, invalid = normalize(df, BASE_MAPPING)
    assert len(valid) == 0
    assert len(invalid) == 1


def test_bad_hours_string_produces_invalid_row():
    mapping = {**BASE_MAPPING, "hours": "hours"}
    df = _df(_valid_row(hours="not_a_number"))
    valid, invalid = normalize(df, mapping)
    assert len(valid) == 0
    assert len(invalid) == 1


def test_bad_hourly_rate_string_produces_invalid_row():
    mapping = {**BASE_MAPPING, "hourly_rate": "hourly_rate"}
    df = _df(_valid_row(hourly_rate="N/A"))
    valid, invalid = normalize(df, mapping)
    assert len(valid) == 0
    assert len(invalid) == 1


# ---------------------------------------------------------------------------
# NaN and Infinity — rejected at the schema boundary by field validators
# ---------------------------------------------------------------------------


def test_nan_gross_rejected_by_schema():
    with pytest.raises(ValidationError, match="finite number"):
        CanonicalPayrollRow(employee_id="E1", gross_pay=float("nan"), net_pay=800.0)


def test_inf_gross_rejected_by_schema():
    with pytest.raises(ValidationError, match="finite number"):
        CanonicalPayrollRow(employee_id="E1", gross_pay=float("inf"), net_pay=800.0)


def test_negative_inf_net_rejected_by_schema():
    with pytest.raises(ValidationError, match="finite number"):
        CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=float("-inf"))


def test_nan_hours_rejected_by_schema():
    with pytest.raises(ValidationError, match="finite number"):
        CanonicalPayrollRow(
            employee_id="E1", gross_pay=1000.0, net_pay=800.0, hours=float("nan")
        )


def test_nan_hourly_rate_rejected_by_schema():
    with pytest.raises(ValidationError, match="finite number"):
        CanonicalPayrollRow(
            employee_id="E1", gross_pay=1000.0, net_pay=800.0, hourly_rate=float("nan")
        )


def test_nan_paye_rejected_by_schema():
    with pytest.raises(ValidationError, match="finite number"):
        CanonicalPayrollRow(
            employee_id="E1", gross_pay=1000.0, net_pay=800.0, paye=math.nan
        )


def test_none_optional_float_not_rejected():
    """None is valid for Optional float fields — NaN/Inf guard must not block None."""
    row = CanonicalPayrollRow(
        employee_id="E1", gross_pay=1000.0, net_pay=800.0,
        hours=None, hourly_rate=None,
    )
    assert row.hours is None
    assert row.hourly_rate is None


# ---------------------------------------------------------------------------
# Empty / whitespace employee_id — rejected by schema validator
# ---------------------------------------------------------------------------


def test_empty_employee_id_rejected_by_schema():
    with pytest.raises(ValidationError, match="employee_id must not be empty"):
        CanonicalPayrollRow(employee_id="", gross_pay=1000.0, net_pay=800.0)


def test_whitespace_employee_id_rejected_by_schema():
    with pytest.raises(ValidationError, match="employee_id must not be empty"):
        CanonicalPayrollRow(employee_id="   ", gross_pay=1000.0, net_pay=800.0)


def test_empty_employee_id_produces_invalid_row_via_mapper():
    """An empty employee_id string in the source DataFrame must produce an invalid row."""
    df = _df(_valid_row(employee_id=""))
    valid, invalid = normalize(df, BASE_MAPPING)
    assert len(valid) == 0
    assert len(invalid) == 1


# ---------------------------------------------------------------------------
# Invalid dates — rejected by safe_parse_date (raised as ValueError in mapper)
# ---------------------------------------------------------------------------


def test_garbage_date_produces_invalid_row():
    mapping = {**BASE_MAPPING, "pay_date": "pay_date"}
    df = _df(_valid_row(pay_date="banana"))
    valid, invalid = normalize(df, mapping)
    assert len(valid) == 0
    assert len(invalid) == 1


def test_impossible_date_produces_invalid_row():
    mapping = {**BASE_MAPPING, "pay_date": "pay_date"}
    df = _df(_valid_row(pay_date="32/01/2026"))
    valid, invalid = normalize(df, mapping)
    assert len(valid) == 0
    assert len(invalid) == 1


def test_invalid_period_start_produces_invalid_row():
    mapping = {**BASE_MAPPING, "period_start": "period_start"}
    df = _df(_valid_row(period_start="not-a-date"))
    valid, invalid = normalize(df, mapping)
    assert len(valid) == 0
    assert len(invalid) == 1


# ---------------------------------------------------------------------------
# Mixed batches
# ---------------------------------------------------------------------------


def test_mixed_batch_splits_correctly():
    """Valid and invalid rows must be separated accurately, not discarded wholesale."""
    rows = [
        _valid_row(employee_id="E001"),          # valid
        _valid_row(employee_id="E002", gross_pay="abc"),  # bad gross
        _valid_row(employee_id="E003"),          # valid
        _valid_row(employee_id="E004", net_pay=""),       # empty net
        _valid_row(employee_id="E005"),          # valid
    ]
    df = _df(*rows)
    valid, invalid = normalize(df, BASE_MAPPING)
    assert len(valid) == 3
    assert len(invalid) == 2


def test_invalid_row_number_is_1_indexed():
    """Row numbers in invalid_rows must be 1-based (human-readable, matching spreadsheet rows)."""
    rows = [_valid_row(employee_id="E001"), _valid_row(employee_id="E002", gross_pay="bad")]
    df = _df(*rows)
    _, invalid = normalize(df, BASE_MAPPING)
    assert invalid[0]["row_number"] == 2


def test_invalid_row_contains_error_messages():
    df = _df(_valid_row(gross_pay="bad"))
    _, invalid = normalize(df, BASE_MAPPING)
    assert "errors" in invalid[0]
    assert len(invalid[0]["errors"]) > 0


# ---------------------------------------------------------------------------
# Duplicate rows — no implicit deduplication at this layer
# ---------------------------------------------------------------------------


def test_duplicate_rows_both_normalise():
    """Duplicate rows must both pass through; deduplication is not this layer's concern."""
    row = _valid_row(employee_id="E001")
    df = _df(row, row)
    valid, invalid = normalize(df, BASE_MAPPING)
    assert len(valid) == 2
    assert len(invalid) == 0
    assert valid[0].employee_id == valid[1].employee_id == "E001"


# ---------------------------------------------------------------------------
# Determinism — repeated runs on identical input must produce identical output
# ---------------------------------------------------------------------------


def test_normalisation_is_deterministic():
    """Two calls with identical DataFrames must return identical CanonicalPayrollRow lists."""
    rows = [
        _valid_row(employee_id="E001"),
        _valid_row(employee_id="E002", gross_pay="500", net_pay="400"),
        _valid_row(employee_id="E003", gross_pay="abc"),  # invalid
    ]
    df = _df(*rows)

    valid1, invalid1 = normalize(df, BASE_MAPPING)
    valid2, invalid2 = normalize(df, BASE_MAPPING)

    assert len(valid1) == len(valid2)
    assert len(invalid1) == len(invalid2)

    for r1, r2 in zip(valid1, valid2):
        assert r1.model_dump() == r2.model_dump()

    for e1, e2 in zip(invalid1, invalid2):
        assert e1["row_number"] == e2["row_number"]


# ---------------------------------------------------------------------------
# Schema field contract — new fields present and queryable
# ---------------------------------------------------------------------------


def test_canonical_row_has_hourly_rate_field():
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=800.0)
    assert hasattr(row, "hourly_rate")
    assert row.hourly_rate is None


def test_canonical_row_has_prsi_class_field():
    row = CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0, net_pay=800.0)
    assert hasattr(row, "prsi_class")
    assert row.prsi_class is None


def test_canonical_row_required_fields_cannot_be_omitted():
    """Pydantic must reject construction without required fields."""
    with pytest.raises(ValidationError):
        CanonicalPayrollRow(employee_id="E1", gross_pay=1000.0)  # missing net_pay

    with pytest.raises(ValidationError):
        CanonicalPayrollRow(employee_id="E1", net_pay=800.0)  # missing gross_pay

    with pytest.raises(ValidationError):
        CanonicalPayrollRow(gross_pay=1000.0, net_pay=800.0)  # missing employee_id
