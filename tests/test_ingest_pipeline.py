"""
Phase 1 ingestion pipeline tests.

Verifies that load_table():
- Accepts structurally valid files and returns the correct row count.
- Preserves raw cell values without silent type coercion.
- Rejects empty files (headers only) with a clear ValueError.
- Rejects files that are missing required columns.
- Rejects files with unsupported extensions.
- Produces identical results on repeated invocations (determinism).
- Handles large files consistently.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from core.ingest.loader import REQUIRED_COLUMNS, load_table

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PHASE1_DIR = Path(__file__).parent.parent / "phase1_test_files"


def _p(filename: str) -> str:
    """Return the absolute path string for a phase-1 test fixture file."""
    return str(PHASE1_DIR / filename)


# ---------------------------------------------------------------------------
# Valid file ingestion
# ---------------------------------------------------------------------------


def test_clean_file_loads_correct_row_count():
    df = load_table(_p("01_clean.csv"))
    assert len(df) == 3, "Expected 3 data rows from 01_clean.csv"


def test_clean_file_has_required_columns():
    df = load_table(_p("01_clean.csv"))
    for col in REQUIRED_COLUMNS:
        assert col in df.columns, f"Required column '{col}' missing from loaded frame"


def test_clean_file_raw_values_preserved():
    """Cell values must not be silently coerced at the ingestion boundary."""
    df = load_table(_p("01_clean.csv"))
    # Gross/net are numeric in the source but must arrive as strings so the
    # normalisation layer—not the loader—decides how to coerce them.
    assert df.loc[0, "gross_pay"] == "1000"
    assert df.loc[0, "net_pay"] == "800"
    # Date cell in EU format preserved verbatim.
    assert df.loc[0, "pay_date"] == "31/01/2026"
    # ISO date cell preserved verbatim.
    assert df.loc[1, "pay_date"] == "2026-01-31"
    # Excel serial number preserved as raw string (normalisation layer handles it).
    assert df.loc[2, "pay_date"] == "45500"


def test_clean_file_returns_copy():
    """Mutating the returned DataFrame must not affect a second load."""
    df1 = load_table(_p("01_clean.csv"))
    df1.loc[0, "gross_pay"] = "MUTATED"
    df2 = load_table(_p("01_clean.csv"))
    assert df2.loc[0, "gross_pay"] == "1000"


def test_clean_file_deterministic():
    """Repeated loads of the same file must produce identical DataFrames."""
    df1 = load_table(_p("01_clean.csv"))
    df2 = load_table(_p("01_clean.csv"))
    pd.testing.assert_frame_equal(df1, df2)


def test_clean_file_column_order_stable():
    """Column order must match the CSV header on every load."""
    df1 = load_table(_p("01_clean.csv"))
    df2 = load_table(_p("01_clean.csv"))
    assert list(df1.columns) == list(df2.columns)


# ---------------------------------------------------------------------------
# Malformed data rows (file is structurally valid; bad values pass through raw)
# ---------------------------------------------------------------------------


def test_broken_date_loads_raw_value():
    """02_broken_date.csv has an impossible date; loader must NOT reject it.

    Row-level value validation belongs to the normalisation layer.
    The loader's job is structural validation only.
    """
    df = load_table(_p("02_broken_date.csv"))
    assert len(df) == 3
    # The impossible date value must arrive exactly as written in the file.
    assert df.loc[1, "pay_date"] == "32/01/2026"


def test_garbage_date_loads_raw_value():
    """03_garbage_date.csv has a non-date string; loader passes it through."""
    df = load_table(_p("03_garbage_date.csv"))
    assert len(df) == 3
    assert df.loc[1, "pay_date"] == "banana"


def test_bad_gross_loads_raw_value():
    """04_bad_gross.csv has non-numeric gross; loader passes it through."""
    df = load_table(_p("04_bad_gross.csv"))
    assert len(df) == 3
    assert df.loc[1, "gross_pay"] == "abc"


def test_mixed_file_loads_all_rows():
    """06_mixed.csv has multiple error types; loader passes all 5 rows through."""
    df = load_table(_p("06_mixed.csv"))
    assert len(df) == 5


def test_corrupt_style_blank_row_passes_through():
    """07_corrupt_style.csv has a blank middle row; loader returns all rows.

    Blank-row filtering is the normalisation layer's responsibility.
    """
    df = load_table(_p("07_corrupt_style.csv"))
    # File has 2 data rows + 1 blank row = 3 rows total in the frame.
    assert len(df) == 3


# ---------------------------------------------------------------------------
# Empty file rejection
# ---------------------------------------------------------------------------


def test_empty_file_rejected():
    """05_empty.csv contains only headers; load_table must raise ValueError."""
    with pytest.raises(ValueError, match="no data rows"):
        load_table(_p("05_empty.csv"))


# ---------------------------------------------------------------------------
# Structural rejection: missing required columns
# ---------------------------------------------------------------------------


def test_missing_required_column_rejected(tmp_path):
    """A file that omits a required column must be rejected immediately."""
    bad_csv = tmp_path / "no_gross.csv"
    bad_csv.write_text("employee_id,net_pay,pay_date\nE001,800,31/01/2026\n")
    with pytest.raises(ValueError, match="Missing required columns"):
        load_table(str(bad_csv))


def test_all_required_columns_missing_rejected(tmp_path):
    """A file with an entirely unrelated header must be rejected."""
    bad_csv = tmp_path / "wrong_headers.csv"
    bad_csv.write_text("col_a,col_b\nfoo,bar\n")
    with pytest.raises(ValueError, match="Missing required columns"):
        load_table(str(bad_csv))


# ---------------------------------------------------------------------------
# Unsupported extension rejection
# ---------------------------------------------------------------------------


def test_unsupported_extension_rejected(tmp_path):
    txt_file = tmp_path / "payroll.txt"
    txt_file.write_text("employee_id,gross_pay,net_pay\nE001,1000,800\n")
    with pytest.raises(ValueError, match="Unsupported file type"):
        load_table(str(txt_file))


def test_nonexistent_file_raises():
    """Attempting to load a file that does not exist must raise an exception."""
    with pytest.raises(Exception):
        load_table("/nonexistent/path/payroll.csv")


# ---------------------------------------------------------------------------
# Large file
# ---------------------------------------------------------------------------


def test_large_file_row_count():
    """08_large.csv has 2000 data rows; all must be loaded."""
    df = load_table(_p("08_large.csv"))
    assert len(df) == 2000


def test_large_file_has_required_columns():
    df = load_table(_p("08_large.csv"))
    for col in REQUIRED_COLUMNS:
        assert col in df.columns


def test_large_file_deterministic():
    """Two sequential loads of the large file must produce identical results."""
    df1 = load_table(_p("08_large.csv"))
    df2 = load_table(_p("08_large.csv"))
    pd.testing.assert_frame_equal(df1, df2)


def test_large_file_no_dtype_inference():
    """All columns in the large file must contain raw strings, not numeric types.

    This ensures pandas has not silently coerced any column's type.
    We accept both numpy object and pandas StringDtype (pandas >= 3.x).
    """
    df = load_table(_p("08_large.csv"))
    for col in df.columns:
        assert pd.api.types.is_string_dtype(df[col]), (
            f"Column '{col}' has dtype {df[col].dtype}; expected a string dtype. "
            "Pandas must not infer numeric types at the ingestion boundary."
        )


# ---------------------------------------------------------------------------
# Encoding stability
# ---------------------------------------------------------------------------


def test_utf8_bom_file_loads(tmp_path):
    """A UTF-8 file with BOM must be decoded correctly."""
    bom_csv = tmp_path / "bom.csv"
    # Write UTF-8 BOM explicitly.
    bom_csv.write_bytes(
        b"\xef\xbb\xbfemployee_id,gross_pay,net_pay,pay_date\n"
        b"E001,1000,800,31/01/2026\n"
    )
    df = load_table(str(bom_csv))
    assert len(df) == 1
    # BOM must not contaminate the column name.
    assert "employee_id" in df.columns


def test_latin1_file_loads(tmp_path):
    """A latin-1 encoded file must fall back to that encoding correctly."""
    latin1_csv = tmp_path / "latin1.csv"
    # é is byte 0xe9 in latin-1 (invalid in strict UTF-8 without multi-byte encoding).
    latin1_csv.write_bytes(
        b"employee_id,gross_pay,net_pay,pay_date\n"
        b"E\xe9001,1000,800,31/01/2026\n"
    )
    df = load_table(str(latin1_csv))
    assert len(df) == 1
