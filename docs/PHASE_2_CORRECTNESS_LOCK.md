# PHASE 2 — COMPLIANCE CORRECTNESS HARDENING (LOCK)

Ruleset: IE-2026.01

## Phase 2 Constraints (Locked)
- Deterministic only (no inference, no tolerance heuristics in deterministic rules)
- No API contract changes
- No normalization signature changes
- No canonical model changes
- No changes to versioning system
- Findings schema remains structured and stable

## Phase 2 Deterministic Rules Added (HIGH)
- IE.PRSI.002 — PRSI deterministic bounds (config-anchored)
- IE.USC.002 — USC deterministic bounds (non-negative, <= gross, gross<=0 => usc==0)
- IE.NET.002 — Net cannot exceed gross minus known deductions (PAYE/USC/PRSI(EE)/pension(EE))
- IE.PAYE.002 — PAYE deterministic bounds (non-negative, <= gross, <= gross*higher_rate)
- IE.MINWAGE.001 — Minimum wage (if hours provided): gross/hours >= config minimum
- IE.AUTOENROL.001 — Auto-enrolment eligibility (conservative annualisation) + pension present

## Phase 1 Heuristic Rules Preserved (LOW)
- IE.USC.001 — USC plausibility outliers (heuristic)
- IE.PRSI.001 — PRSI plausibility outliers (heuristic)

## Engine Order (Locked Intent)
Structural integrity → Deterministic bounds → Plausibility rules
