# QA log

| Date | Check | Result (pass/fail) | Evidence (file + command) | Resolution |
|------|-------|--------------------|---------------------------|------------|
| 2026-11-14 | Phase 2 exit checks (33 checks: 22 real passes, 0 fail, 6 flags, 5 info-only — recounted after review) | pass (gate) | `reports/phase2_validation.json` from `uv run python -I scripts/validate_phase2.py` | Flags are recorded as open questions 10–12 and published limitations |
| 2026-11-14 | Reconciled four-party state sums = INEC national (8,794,726 / 6,984,520 / 6,101,533 / 1,496,687). PDP and NNPP match with no hand decisions; APC and LP match because 3 cells were chosen to make them match (not independent evidence) | pass | same | — |
| 2026-11-14 | 25% count 29/21/16/1 recomputed from reconciled votes; equals Wikipedia's flags | pass | same | — |
| 2026-11-14 | Unmatched state keys | pass (0) | `reports/unmatched_keys.csv` | — |
| 2026-11-14 | Geometry valid, no overlaps | pass | `pbip/assets/geometry_manifest.json` from `uv run python -I scripts/build_geometry.py` | Akwa Ibom and Cross River repaired (decision log) |
| 2026-11-14 | OTHERS / total valid state sums = INEC national | flag (+4,858) | `reports/phase2_validation.json` | Published as a limitation (open question 10) |
| 2026-11-14 | Phase 3 thin slice opens in Desktop 2.159 (Store) from script-generated PBIP | pass | `reports/screenshots/phase3_thin_slice.png`; `powerbi-desktop reload` + `screenshot` | First open failed: measure `Votes` clashed with column `votes` (names are case-insensitive) — renamed `Total votes` |
| 2026-11-14 | Card = INEC national APC 8,794,726 | pass | same screenshot | Display units set to none (default showed "9M") |
| 2026-11-14 | Shape Map (state boundaries) and tile Shape Map render, all 37 units coloured | pass | same screenshot | — |
| 2026-11-14 | PBIR validation | pass (0 errors, 0 warnings) | `powerbi-report-author validate pbip/NaijaElectionsGap.Report` | Desktop's save strips `$schema` from `.pbip` and `definition.pbir`; the generator restores it |
| 2026-11-14 | Generator output = Desktop's saved model files | pass (all 7 TMDL files identical apart from CRLF) | diff of a Desktop-saved copy vs `build_pbip.py` output | — |
| 2026-11-14 | Phase 3 model checks on the live Desktop model (row counts, orphan keys, INEC national per candidate, 25% counts 29/21/16/1, all 185 cells = staging, disconnected candidate table, zone roll-up) | pass (8/8) | `reports/phase3_validation.json` from `uv run python -I scripts/validate_phase3.py` | — |
| 2026-11-14 | Check table and maps render | pass | `reports/screenshots/phase3_thin_slice.png` | First layout clipped the table to 2 rows; resized |
| 2026-11-14 | Phase 3 checks after review fixes (adds: computable share = 37, OTHERS row present, no/two selections blank, 25% recomputed from staging; refresh path exercised) | pass (11 pass, 0 fail, 1 info) | `reports/phase3_validation.json`; `pbi_reopen.ps1 -Force` then `validate_phase3.py` (with refresh) | Reviewer's refresh hang traced to stacked Desktop dialogs; fixed (decision log) |
