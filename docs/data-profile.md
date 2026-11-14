# Phase 2 data profile

Built 2026-11-14. Every figure below comes from `reports/phase2_validation.json`, produced by
`uv run python -I scripts/validate_phase2.py` after `scripts/build_staging.py` and `scripts/build_geometry.py`.
Raw snapshots: `data/raw/<source>/<date>/` (local only; manifests with URL, access time, bytes, SHA-256 are in git).

## What is in staging (`data/staging/`, local only)

| Table | Grain | Rows | Notes |
|---|---|---|---|
| `dim_state.csv` | state | 37 | Key `state_pcode` = HDX COD-AB `adm1_pcode`. FCT = NG015, flagged `is_fct`. |
| `dim_zone.csv` | zone | 6 | Zone membership from Wikipedia "Geopolitical zones of Nigeria" (revision-pinned). |
| `fact_result_2023.csv` | state × party | 185 | APC, PDP, LP, NNPP, OTHERS. Four-party votes are **reconciled** (below); `votes_rule` says how each cell was settled; Wikipedia's original value is kept in `votes_wikipedia`. |
| `fact_turnout_2023.csv` | state | 37 | `total_valid` = reconciled four parties + OTHERS. Registered voters from the 37 state pages. Reported totals from Wikipedia and AGADA kept alongside. |
| `national_totals_reported.csv` | source | 5 | Total rows of each copy plus INEC's declaration. |
| `crosscheck_sources.csv` | state × measure | 222 | Every copy's value per cell. |
| `mundx_state_rollup.csv` | state | 37 | Local only, never published (no licence). Accuracy ratios: `reports/mundx_state_accuracy.csv`. |

## Why the state results are reconciled

INEC's state collation sheet (Form EC8D) is not public. INEC's own 2023 report
(`data/raw/inec_report/`, Annexure 2) gives only national figures, transcribed to
`data/reference/inec_national_declaration_2023.csv`. Wikipedia's By-state table — the planned primary source —
does not add up to INEC's national totals: APC +10,694, PDP −4,230, LP −10,516, NNPP −16.

Five copies of the INEC state declaration were compared cell by cell (Wikipedia, AGADA-BI, thenigerialawyer.com,
ThisDay, Vanguard). ThisDay and thenigerialawyer.com share every error, so they count as one copy. 18 of 148
four-party cells are not unanimous (`reports/result_reconciliation.csv`): 14 settled by clear majority,
3 by a logged decision (`data/reference/result_cell_decisions.csv`), 1 unanimous among the copies that could be read
(Vanguard's Benue LP "30,8372" is unreadable and left blank).

Result: the reconciled state sums equal INEC's national declaration **exactly** for all four main parties
(8,794,726 / 6,984,520 / 6,101,533 / 1,496,687).

Cells where each copy differs from the chosen value: Wikipedia 9, thenigerialawyer.com 7, ThisDay 7, Vanguard 4, AGADA 1.

## Checks that pass (gate)

- 37 states, unique keys, one FCT, 6 zones; no null votes; no duplicate state × party rows.
- INEC reference: 18 candidates sum to 24,025,940 valid votes; valid + rejected (939,278) = cast (24,965,218).
- Reconciled four-party state sums = INEC national, exactly.
- 25% count, recomputed from votes: APC 29, PDP 21, LP 16, NNPP 1 — equal to the expected figures and to Wikipedia's flags.
- The Kano decision does not change the 25% outcome (APC 29.95% with 506,412; 30.40% with 517,341).
- 0 unmatched state names (`reports/unmatched_keys.csv`); both TopoJSON files carry exactly the 37 keys.
- Geometry: 0 invalid or empty shapes, 0 pairwise overlap; 39,147 → 2,437 vertices; 31,979 bytes; largest state area change 0.96%.

## Known gaps (published, not fixed)

| Gap | Size | Why it stays |
|---|---|---|
| OTHERS (14 minor candidates), state sum vs INEC | +4,858 (653,332 vs 648,474) | Only Wikipedia and AGADA give it per state, and they agree. No evidence about which states carry the excess. Total valid per state inherits it. |
| Registered voters, state sum vs INEC | −120,281 (93,348,727 vs 93,469,008) | From the 37 Wikipedia state infoboxes; no INEC per-state table found yet. |
| Accredited voters per state | 0 of 37 | Not found. National only: 25,286,616. |
| Rejected votes / total cast per state | 1 of 37 (Ekiti) | Not found. `total_cast_implied_from_turnout` = registered × turnout % is an **inference**, not a published figure. |
| Bauchi turnout | 31.1% vs 32.73% | Main table vs state page; unresolved. |
| Kano APC | 506,412 chosen; 517,341 in three copies | Chosen for consistency with the national total; not confirmed by an official state sheet. |

## Close calls for the 25% rule

Two state results sit within 0.5 percentage points of 25%: APC in Edo (24.855%) and APC in Adamawa (25.013%).
Neither cell was touched by reconciliation. Scenario sliders will move these first.

## What this profile does not claim

It does not claim the reconciled table is INEC's official state sheet; it is the best-supported reading of five
secondary copies, constrained by INEC's official national totals. It makes no LGA-level claims.
