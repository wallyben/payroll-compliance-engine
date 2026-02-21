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

