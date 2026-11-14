# Risk register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A source disappears or changes shape | Medium | High | Snapshot raw files with hash + date in Phase 2 |
| Licence unclear (Mundx) | High | High | Treat as internal use / attribution required; flag before publishing |
| LGA names don't match geometry | High | High | Unmatched-keys gate + reviewed crosswalk before any visual |
| Viewers without Windows / Power BI Desktop can't open the file | High | Medium | Walkthrough video linked from README; screenshots on the repo page |
| Threshold misread (FCT, rounding) | Medium | High | Primary-text check in Phase 1; stop and flag if ambiguous |
| No open LGA-level 2023 results exist | **Realised** | High | Escalated to user; fallback is a state-level core that the threshold test needs anyway |
| Secondary copies of the INEC state results disagree with each other and with INEC's national total | **Realised** | High | Five-copy reconciliation with logged decisions; gate check that four-party state sums equal INEC national exactly (`scripts/validate_phase2.py`) |
| A news page changes or disappears | Medium | Medium | Raw snapshots with SHA-256 in `data/raw/*/manifest.json`; Vanguard is a manual snapshot (open question 13) |
