# QA log

| Date | Check | Result (pass/fail) | Evidence (file + command) | Resolution |
|------|-------|--------------------|---------------------------|------------|
| 2026-11-14 | Phase 2 exit checks (33 checks: 22 real passes, 0 fail, 6 flags, 5 info-only — recounted after review) | pass (gate) | `reports/phase2_validation.json` from `uv run python -I scripts/validate_phase2.py` | Flags are recorded as open questions 10–12 and published limitations |
| 2026-11-14 | Reconciled four-party state sums = INEC national (8,794,726 / 6,984,520 / 6,101,533 / 1,496,687). PDP and NNPP match with no hand decisions; APC and LP match because 3 cells were chosen to make them match (not independent evidence) | pass | same | — |
| 2026-11-14 | 25% count 29/21/16/1 recomputed from reconciled votes; equals Wikipedia's flags | pass | same | — |
| 2026-11-14 | Unmatched state keys | pass (0) | `reports/unmatched_keys.csv` | — |
| 2026-11-14 | Geometry valid, no overlaps | pass | `pbip/assets/geometry_manifest.json` from `uv run python -I scripts/build_geometry.py` | Akwa Ibom and Cross River repaired (decision log) |
| 2026-11-14 | OTHERS / total valid state sums = INEC national | flag (+4,858) | `reports/phase2_validation.json` | Published as a limitation (open question 10) |
