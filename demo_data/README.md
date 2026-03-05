# Demo data

Example payroll CSV files for demonstration and testing. All use canonical column names (e.g. `employee_id`, `gross_pay`, `net_pay`, `hours`, `paye`, `usc`, `prsi_ee`, `prsi_er`, `pension_ee`, `pension_er`, `prsi_class`). Required minimum: `employee_id`, `gross_pay`, `net_pay`.

## Files and expected results

| File | Expected findings | Severity | Result | Certificate |
|------|-------------------|----------|--------|-------------|
| **clean_payroll.csv** | **0** | — | PASSED | Available |
| **minor_issues_payroll.csv** | **2–3** | MEDIUM/HIGH (no CRITICAL) | Issues | Not available |
| **severe_issues_payroll.csv** | **Multiple** (≥3) | CRITICAL + HIGH | Large exposure | Not available |

### clean_payroll.csv

- Three employees, valid amounts: net < gross, net > 0, hourly rate ≥ minimum wage (€12.70), PRSI class A, PRSI/USC within statutory bounds and plausibility.
- **Expected:** 0 findings → PASSED banner → Compliance certificate available.

### minor_issues_payroll.csv

- One employee below minimum wage (gross 400, 40 hours → €10/hr); one duplicate `employee_id` (E102 twice).
- **Expected:** 2–3 findings (IE.MINWAGE.001, IE.DATA.001). No CRITICAL. No certificate.

### severe_issues_payroll.csv

- Net > gross (E201), negative net (E202), duplicate employee (E203), minimum wage breach (E204).
- **Expected:** Multiple findings including CRITICAL (e.g. IE.NET.001, IE.NET.002), IE.DATA.001, IE.MINWAGE.001. Total exposure non-zero. No certificate.

## Usage

Upload any file via the UI (Upload → Run Validation) or call `POST /scan/` with the file. See [docs/demo_walkthrough.md](../docs/demo_walkthrough.md) for a 5-minute demo script.

Automated checks: run `pytest tests/test_demo_datasets.py` to assert demo datasets behave as above after rule or config changes.
