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
ThisDay, Vanguard). ThisDay and thenigerialawyer.com share every error, so they count as one copy. 17 of 148
four-party cells are not unanimous: 14 settled by clear majority and 3 by a logged hand decision
(`data/reference/result_cell_decisions.csv`). `reports/result_reconciliation.csv` lists these 17 plus one cell
that is unanimous among the copies that could be read (Vanguard's Benue LP "30,8372" is unreadable and left blank).

Result: the reconciled state sums equal INEC's national declaration exactly for all four main parties
(8,794,726 / 6,984,520 / 6,101,533 / 1,496,687). **How much of that is evidence:** PDP and NNPP match with no
hand decisions — independent confirmation. APC and LP match *because* the three hand-decided cells were chosen to
make them match, so for those two parties the match is a constraint we imposed, not a confirmation. With the
majority value in Kano, APC would be +10,929; the two LP cells are ties (no majority), and of the four combinations
of tied values only the chosen one hits INEC — the others miss by 20, 2,925 or 2,945 votes.

Cells where each copy differs from the chosen value: Wikipedia 9, thenigerialawyer.com 7, ThisDay 7, Vanguard 4, AGADA 1.

## Checks that pass (gate)

Summary of the run: 33 checks — 22 pass, 0 fail, 6 flags (known gaps below), 5 info-only findings that cannot fail.

- 37 states, unique keys, one FCT, 6 zones; no null votes; no duplicate state × party rows.
- INEC reference: 18 candidates sum to 24,025,940 valid votes; valid + rejected (939,278) = cast (24,965,218).
- Reconciled four-party state sums = INEC national, exactly (independent for PDP and NNPP; imposed for APC and LP — see above).
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
| Kano APC | 506,412 chosen; 517,341 in three of four independent copies | Chosen for consistency with the national total. 517,341 may be the figure INEC announced at state level; 506,412 is what makes the national sum work. Not confirmed by an official state sheet (open question 14). |

## Close calls for the 25% rule

Two state results sit within 0.5 percentage points of 25%. Neither cell was touched by reconciliation.

| State | Party | Share | Votes above (+) / below (−) 25% |
|---|---|---|---|
| Adamawa | APC | 25.013% | **+96** |
| Edo | APC | 24.855% | −845.5 (Edo would cross if about 3,380 fewer valid votes were counted there) |

**The APC count of 29 rests on 96 votes in Adamawa.** The unlocated OTHERS excess (+4,858 nationally) sits in the
denominator and is larger than either margin, so a correction in Adamawa or Edo could move APC to 28 or 30. A single
cell matters too: if Zamfara PDP were the minority value 93,978 instead of 193,978, PDP would drop from 21 to 20
(majority and the PDP national match both support 193,978). The report must show these margins wherever the
29/21/16/1 count appears, including the scenario page.

## What this profile does not claim

It does not claim the reconciled table is INEC's official state sheet; it is the best-supported reading of five
secondary copies, constrained by INEC's official national totals. It makes no LGA-level claims.
