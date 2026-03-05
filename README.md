# Payroll Compliance OS (Ireland) — v1 Scaffold

This repo is a production-ready scaffold for an **independent payroll compliance validator** focused on Ireland.

## What v1 does
- Upload CSV/XLSX payroll exports
- Map columns → normalize to a canonical payroll schema
- Run deterministic compliance checks (rates/bands stored in versioned config)
- Generate:
  - JSON findings (High/Med/Low)
  - A PDF compliance report
- Security guardrails:
  - RBAC (admin/auditor/viewer)
  - Audit log
  - PII encryption at rest for sensitive fields (PPSN)

## Quick start (Docker)
```bash
docker compose up --build
```

Open:
- API docs: http://localhost:8080/docs

## Create a first admin user
```bash
docker compose exec api python -m apps.api.scripts.seed_admin admin@example.com "ChangeMe123!"
```

## Run tests
```bash
pip install -e ".[dev]"
pytest -q
```

## Important: rates/bands & compliance
Rates and thresholds are stored in `core/rules/ie_config_2026.json` and versioned with `RULESET_VERSION`.
Update these on regulatory changes and bump `RULESET_VERSION` (e.g. `IE-2026.02`).

## API flow (minimal)
1. `POST /auth/login` → token
2. `POST /uploads` → upload file
3. `POST /mappings/{upload_id}` → column mapping
4. `POST /runs` → run compliance checks
5. `GET /runs/{run_id}/report.pdf` → download report

## Demo Data

Example payroll CSV files for demos and testing are in **`demo_data/`**:

| File | Purpose | Expected outcome |
|------|---------|------------------|
| **clean_payroll.csv** | Valid payroll: no net>gross, no negative net, no duplicates, min wage OK, PRSI class present. | Zero or few findings; when 0 findings: PASSED banner and Compliance Certificate available. |
| **minor_issues_payroll.csv** | Small issues: one minimum-wage breach, one duplicate employee_id. | MEDIUM/HIGH findings; no certificate. |
| **severe_issues_payroll.csv** | Multiple violations: net>gross, negative net, duplicate employee, minimum wage breach. | CRITICAL/HIGH findings; large exposure; no certificate. |

**How to run the examples**

1. Start the backend: `uvicorn apps.api.main:app --reload` (port 8000).
2. Start the frontend: from `frontend/` run `npm run dev` (port 5173).
3. Open http://localhost:5173 → **Upload** → choose a file from `demo_data/` → **Run Validation**.
4. Use **Results** to see findings and **Summary** to see exposure and export report or certificate (when 0 findings).

For a guided 5-minute demo, see **[docs/demo_walkthrough.md](docs/demo_walkthrough.md)**.

