# PHASE 4 – PRODUCTION HARDENING JOB SPEC

GLOBAL CONSTRAINTS (MANDATORY)
- Do NOT modify rule logic.
- Do NOT change scoring behavior.
- Preserve all tests.
- Minimal file changes per step.
- One step at a time.
- Run pytest after each step.
- If tests fail: fix minimally.
- Commit after each successful step.
- Commit format: phase4: <step name>

--------------------------------------------------

STEP 1 — Enforce JWT_SECRET in Production

Goal:
- If ENV=production and JWT_SECRET missing → fail at startup.
- Dev mode must not break tests.

Actions:
- Modify config layer only.
- Add validation at app startup.
- Do not modify routers.
- Run pytest.
- Commit: phase4: enforce jwt secret in production

STOP if tests fail.

--------------------------------------------------

STEP 2 — Remove Severity Aggregation Duplication

Goal:
- Move duplicated severity logic from routers into helper.
- No behavior change.
- Output format must remain identical.

Actions:
- Create helper module.
- Refactor routers to call helper.
- Run pytest.
- Commit: phase4: deduplicate severity aggregation

STOP if tests fail.

--------------------------------------------------

STEP 3 — Fix Config Path Loading

Goal:
- Eliminate CWD-relative paths.
- Use deterministic base path resolution.

Actions:
- Update config loader only.
- No behavioral changes.
- Run pytest.
- Commit: phase4: deterministic config path resolution

STOP if tests fail.

--------------------------------------------------

STEP 4 — Replace Report Path Return with Streaming Response

Goal:
- Stop returning filesystem path.
- Use secure streaming response.
- Validate report directory.

Actions:
- Modify only relevant endpoint.
- Update tests if required.
- Run pytest.
- Commit: phase4: secure report streaming response

STOP if tests fail.

--------------------------------------------------

STEP 5 — Add /health Endpoint

Goal:
- Add GET /health.
- Return JSON status.
- Add simple test.

Actions:
- Minimal router.
- Run pytest.
- Commit: phase4: add health endpoint

STOP if tests fail.

--------------------------------------------------

STEP 6 — Introduce Structured Logging Layer

Goal:
- Add centralized logging config.
- Add lightweight request middleware.
- No core engine changes.

Actions:
- Add logging module.
- Add middleware.
- Do not change rule logic.
- Run pytest.
- Commit: phase4: structured logging layer

STOP if tests fail.
