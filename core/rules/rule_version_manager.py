"""Rule version manager.

Selects the appropriate Irish payroll compliance configuration file based on
the year of the payroll period being processed, then returns a summary of the
loaded ruleset alongside the full configuration dict.

Public API
----------
select_config(payroll_date, config_dir=None) -> RulesetInfo
    Resolves the correct ``ie_config_{year}.json`` for the supplied payroll
    date and returns a :class:`RulesetInfo` named-tuple containing:

    * ``rule_version``  – the ``ruleset_version`` string from the config JSON
                          (e.g. ``"IE-2026.01"``)
    * ``rules_loaded``  – number of rules registered in the engine's
                          ``RULE_ORDER`` canonical execution list
    * ``config``        – the full config dict, ready to pass to ``run_all()``

list_available_years(config_dir=None) -> list[int]
    Returns the sorted list of years for which a config file exists in the
    given (or default) config directory.

Exceptions
----------
ConfigNotFoundError
    Raised by ``select_config`` when no ``ie_config_{year}.json`` exists for
    the payroll year.  Derives from ``FileNotFoundError`` so callers can catch
    the standard OSError hierarchy if preferred.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import NamedTuple, Union

from core.rules.engine import RULE_ORDER

# ---------------------------------------------------------------------------
# Default config directory — same folder as this module and the JSON files.
# ---------------------------------------------------------------------------
_DEFAULT_CONFIG_DIR = Path(__file__).parent

# Regex that matches the year embedded in the config file names.
_CONFIG_FILENAME_RE = re.compile(r"^ie_config_(\d{4})\.json$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class ConfigNotFoundError(FileNotFoundError):
    """Raised when no config file exists for the requested payroll year."""

    def __init__(self, year: int, config_dir: Path) -> None:
        self.year = year
        self.config_dir = config_dir
        available = list_available_years(config_dir)
        hint = f"Available years in {config_dir}: {available}" if available else (
            f"No ie_config_*.json files found in {config_dir}."
        )
        super().__init__(
            f"No rule configuration found for payroll year {year}. {hint}"
        )


class RulesetInfo(NamedTuple):
    """Immutable summary of the loaded ruleset."""

    rule_version: str
    """Ruleset version string from the config JSON (e.g. ``'IE-2026.01'``)."""

    rules_loaded: int
    """Number of rules in the engine's canonical ``RULE_ORDER`` list."""

    config: dict
    """Full configuration dict, ready for use with ``run_all()``."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_config_dir(config_dir: Union[str, Path, None]) -> Path:
    return Path(config_dir) if config_dir is not None else _DEFAULT_CONFIG_DIR


def _extract_year(payroll_date: Union[date, str, int]) -> int:
    """Return the calendar year from *payroll_date*.

    Accepts:
    * A :class:`datetime.date` or :class:`datetime.datetime` object.
    * An ISO-8601 date string (``"2026-03-15"``).
    * A plain integer year (``2026``).

    Raises :exc:`ValueError` for any unrecognised input.
    """
    if isinstance(payroll_date, (date, datetime)):
        return payroll_date.year
    if isinstance(payroll_date, int):
        if payroll_date < 1900 or payroll_date > 9999:
            raise ValueError(f"Year {payroll_date!r} is outside the valid range 1900–9999.")
        return payroll_date
    if isinstance(payroll_date, str):
        payroll_date = payroll_date.strip()
        # Accept full ISO dates ("2026-03-15") or bare year strings ("2026").
        if re.fullmatch(r"\d{4}", payroll_date):
            return int(payroll_date)
        try:
            return date.fromisoformat(payroll_date).year
        except ValueError:
            pass
        # Fallback: try datetime parsing for strings like "2026-03-15T00:00:00".
        try:
            return datetime.fromisoformat(payroll_date).year
        except ValueError:
            pass
        raise ValueError(
            f"Cannot parse {payroll_date!r} as a date or year. "
            "Expected an ISO-8601 date string (e.g. '2026-03-15') or a four-digit year."
        )
    raise TypeError(
        f"payroll_date must be a date, str, or int, got {type(payroll_date).__name__!r}."
    )


def _config_path_for_year(year: int, config_dir: Path) -> Path:
    return config_dir / f"ie_config_{year}.json"


def _load_json(path: Path) -> dict:
    """Load a JSON file, handling an optional UTF-8 BOM."""
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def list_available_years(config_dir: Union[str, Path, None] = None) -> list[int]:
    """Return a sorted list of years for which a config file exists.

    Parameters
    ----------
    config_dir:
        Directory to search.  Defaults to the ``core/rules/`` package
        directory where the bundled config files live.

    Returns
    -------
    list[int]
        Sorted list of available years, e.g. ``[2025, 2026]``.
    """
    resolved = _resolve_config_dir(config_dir)
    years: list[int] = []
    if resolved.is_dir():
        for p in resolved.iterdir():
            m = _CONFIG_FILENAME_RE.match(p.name)
            if m:
                years.append(int(m.group(1)))
    return sorted(years)


def select_config(
    payroll_date: Union[date, str, int],
    config_dir: Union[str, Path, None] = None,
) -> RulesetInfo:
    """Select and load the rule configuration for *payroll_date*.

    Parameters
    ----------
    payroll_date:
        The date of the payroll period.  Accepted forms:

        * :class:`datetime.date` or :class:`datetime.datetime`
        * ISO-8601 string such as ``"2026-03-15"``
        * Four-digit integer year such as ``2026``

    config_dir:
        Directory containing ``ie_config_{year}.json`` files.  Defaults to
        the bundled ``core/rules/`` package directory.

    Returns
    -------
    RulesetInfo
        A named-tuple with ``rule_version``, ``rules_loaded``, and ``config``.

    Raises
    ------
    ConfigNotFoundError
        If no config file exists for the resolved payroll year.
    ValueError
        If *payroll_date* cannot be parsed.
    """
    resolved_dir = _resolve_config_dir(config_dir)
    year = _extract_year(payroll_date)
    config_path = _config_path_for_year(year, resolved_dir)

    if not config_path.exists():
        raise ConfigNotFoundError(year, resolved_dir)

    config = _load_json(config_path)
    rule_version: str = config.get("ruleset_version", f"IE-{year}.00")
    rules_loaded: int = len(RULE_ORDER)

    return RulesetInfo(
        rule_version=rule_version,
        rules_loaded=rules_loaded,
        config=config,
    )
