# Handoff — where the project is

Updated: 2026-11-18. Update this file in every stage commit.

## Phase status (see `docs/PLAN.md`)
| Phase | State | Last commit |
|---|---|---|
| 0–4 Environment, sources, data, model, scenario engine | done | 44ca968 |
| 5 Report pages | done; non-specialist test still needs a person | 9813cbc |
| 6 QA | scripted checks 15/15 pass after redesign (`scripts/validate_phase6.py`); manual checks open | 8f6e407 |
| 5b Redesign (user review round) | done; reviewed; "Try these" buttons not built (open question 18) | 619c068 |
| 5c Merge parties + head to head | built; speed fixed, boundary bug fixed, engine rewritten 2026-11-18; Phase 4 checks 89/89; Phase 6 + review + commit next | 1c72aa8 + uncommitted |
| 7 Release + docs, 8 Case study | todo | — |

## Redesign round (user requests 2026-11-14)
1. Hover shows state names, not P-codes.
2. Plain wording on all pages ("states" not "units", "the deciding state", "Result"); gaps stated in votes, not points.
3. New **Technical notes** page: terms + formulas in words and symbols (no underscores/LaTeX).
4. Colour key made of coloured lines (not a health bar); bold coloured 25% line.
5. Side photo panels (left/right varied) — freely licensed Nigerian election photos (Wikimedia Commons), neutral scenes only, credited.
6. Candidate identity on selection: free-licence candidate photo (initials badge for all if any is missing), **real party logos** (trademarks, identification only; `PBIP_NO_LOGOS=1` falls back to badges), party colours on accents only (data colours fixed), "2023 party" + "Party now" (verified with dated sources or "not confirmed").
7. Playable Simulator: "How to play" strip, sliders as everyday questions, "Try these" bookmark buttons + reset, result as a sentence.
8. State codes (ISO 3166-2:NG, e.g. LA, KN, FC) visible on tile map; geographic map labelled or a labelled locator map beside it.

Status 2026-11-16: all 8 built except the "Try these" / reset buttons (item 7, shown as text; open question 18). Reviewer pass done; fixes applied: full identity-text check in `validate_phase6.py`, "party now" caveat on Data sources, logo-takedown mitigation corrected in `registers/risks.md`. Rebuilt from the generator after a Desktop save had overwritten the report files.

Still open from the review (minor): Overview Kano note is about Tinubu whatever candidate is selected; a few frozen 2023 numbers in page text (4,858; Kano 506,412 / 517,341; "96 votes in Adamawa") are not tied to a validator; tile-map hover shows the code, not the name.

## Coalition build status (2026-11-16, work-in-progress commit)
Built: pages "Merge two parties" and "Head to head", simulator switch "Use the coalition?" (default Off), follow sliders, preset NDC (Obi + Kwankwaso) vs APC, `data/reference/coalition_names.csv`, method in `docs/methodology.md` "Coalitions", coalition checks in `validate_phase4.py` / `validate_phase6.py`.

Verified this session:
- `build_pbip.py` builds 12 pages (11 visible); `powerbi-report-author validate` 0 errors, 0 warnings.
- Bug fixed: the switch-On rival code used a DAX variable named `lead`, which this Desktop rejects ("The syntax for 'lead' is incorrect"); every measure built on `ON_TAB` (Leading rival, its votes, its states at 25%, Has most votes, Verdict, Result sentence) failed, even with the switch Off. Renamed to `rx`. After the fix (switch Off, APC): Result sentence = "Bola Tinubu wins outright: … 29 states (24 needed)", Verdict = "Outright win", Leading rival = PDP.
- `validate_phase3.py` pass (07:40).
- Coalition checks run on their own: **switch Off = no coalition** pass; **invalid choices → blanks + message** pass.

### 2026-11-18: speed fixed, boundary bug fixed, engine rewritten — all Phase 4 checks pass (89/89)
**Next, in order:**
1. `validate_phase6.py` — **done 2026-11-18: 18/18** (speed check now one query per visual, user decision;
   decision log). Phase 4 result is reused when newer than the build (a full re-run takes ~45 min).
2. Screenshots of the two coalition pages and the simulator with the switch On.
3. Reviewer pass on the coalition method and on today's engine rewrite (fresh eyes; the reference functions were
   written by the same author).
4. Commit + push (nothing from 2026-11-18 is committed yet).
5. Open, not started: rival "at 25% in a state" counts still compare without a margin — the margin proof covers only
   the candidate / coalition share. Decide whether to extend the proof to rival shares.

**Boundary bug (fixed):** exact 20% stored as just under 0.20 showed "Out of reach" (NNPP+LP 50% v APC+PDP 40%, NG006,
turnout −28, swing 0). Lines now compared with a 1E-12 margin (`Q`, `F` in `build_pbip.py`; decision log 2026-11-18;
`docs/methodology.md`). Proof: smallest non-zero gap between any reachable share and a line = 2.06E-10 (> 100 × margin);
all 12 exact-line settings show the right label, order, colour and 0 votes needed at 25%
(`validate_phase4.py --part boundary` → `reports/phase4_parts/boundary.json`). Reference functions were NOT given the
margin (they stay exact); the core grid has no exact-line settings, so both agree (deviation from the plan above).

**Engine rewrite (user decision 2026-11-18: "just work out arithmetic"):** the per-state engine (`Candidate is valid`,
`Engine votes`, `Engine valid votes`, `Scenario valid votes`, `Scenario share uncapped`, `Scenario share after turnout`)
now reads every slider and picker once (`ENGINE_IN`) and does the arithmetic straight from the vote tables, instead of
~10 nested measure calls per state. `Deciding state sentence` ranks states once and reads the deciding state's row
(it was re-evaluating Votes needed / to spare for every state). `Units within reach / out of reach` compute each
state's share once. Research basis: SQLBI on eager vs strict IF evaluation and on context transitions in iterators.
Measured (preset NDC v APC, switch On, cache cleared):

| Request | Before | After |
|---|---|---|
| Simulator check, one slider setting, 37 states × 4 coalitions | 11.5 s | 3.6 s |
| Simulator check, two national rows | 43 s | 4.4 s |
| Deciding state sentence | 8.9 s | 0.4 s |
| Engine memory after these | ~1,170 MB | ~790 MB |

Switch Off after the rewrite: every key national measure 0.15–0.34 s.

**Phase 4 checks after all of the above (2026-11-18, 07:17–07:57):** core 81/81 (514 s), invalid 1/1, switch_off 1/1,
boundary 2/2 (105 s), simulator 1/1 (380 s, was 1,565 s), pages 3/3 (1,354 s); combined → `reports/phase4_validation.json`
gate passed, 89/89.

**Performance (done, measured 2026-11-18, preset NDC v APC, switch On, engine cache cleared each time):**
- Cause 1: DAX evaluated the unused Off branch of `IF ( [Coalition switch on], on, off )` with the switch On, running
  its rival measures in On mode per state (~5.5 s). Fix: `OFFB()` in `build_pbip.py` pins that branch to switch Off.
  Leading rival units at 25%: 6.0 s → 0.8 s.
- Cause 2: Verdict / Result sentence (simulator) and Head to head verdict / sentence called measures that each rebuilt
  the same per-state or rival table. Fix: one pass (`_one_pass_verdicts()`, `H2H_ONE`). Verdict 7.9 s → 0.7 s;
  Result sentence ~4 s → 0.7 s; Head to head verdict 1.3 → 0.7 s, sentence 1.5 → 0.9 s. Same values, switch On and Off.
- `validate_phase4.py` now runs in parts (`--part core|pages|simulator|invalid|switch_off|boundary`, `--combine`),
  prints each result as it lands, saves after every check, and sends smaller batches (the engine reached 3.1 GB and
  two full runs were stopped for low machine memory).
- Parts passed after the fix: core 81/81 (563 s), invalid 1/1, switch_off 1/1, simulator 1/1 (1,565 s).

Superseded notes from 2026-11-16 (kept for the record):
- **Performance blocker:** with the switch On, one ROW of rival/verdict measures takes ~9–30 s (overhead subtracted not yet; PowerShell start-up ≈ 6 s). `coalition_simulator_check`'s national query (8 configs × measures) failed with "not enough memory"; `validate_phase4.py` timed out at 1,800 s inside `validate_phase6.py`. Phase 6 limit is 2 s per page query. Likely cause (unconfirmed): each of Leading rival / votes / units at 25% / code recomputes the whole `ON_TAB` per-state table, and Result sentence / Verdict / Has most votes / Leading rival name nest them. Next step: time single measures with `scratchpad`-style script (preset NDC vs APC, switch On), then compute `ON_TAB` once (e.g. one measure returning the needed values, or fewer nested calls) and re-run.
- Not yet run to completion: `coalition_pages_check` (193 pairings), `coalition_simulator_check`, `coalition_boundary_search`, rest of `validate_phase6.py`. `reports/phase4_validation.json` and `phase6_validation.json` on disk are from 03:34 / 03:47, **before** the coalition checks existed.
- No screenshots of the coalition pages; no reviewer pass on the coalition method.
- Machine memory is tight: one background run was killed for low memory; the Desktop engine uses ~2 GB.

## Next: coalition feature (user decisions 2026-11-14, updated 2026-11-16)
- Coalition = at most two 2023 candidates' parties. Head to head = coalition vs one candidate, or coalition vs coalition.
- Slider "how many of the partner's voters follow", 0–100%, default 100% (an assumption; no measured rate exists); non-followers stay home (state valid totals shrink).
- Existing pages unchanged. Own pages: "Merge two parties", "Head to head". Simulator: on/off switch, default off = today's results exactly.
- Switch on: every slider applies to the coalition → redo `docs/methodology.md`, engine, `validate_phase4.py`, blind reproduction review.
- Research done (preliminary): `docs/coalition-research.md`, `reports/coalition_2011_2015_preliminary.csv`. Real case: Obi + Kwankwaso on one NDC ticket since 2026-05-31. Atiku's ADC ticket under court challenge.
- Decisions recorded in `registers/decision-log.md`; open questions 19–21.

## Open items needing a person
- Hover tooltips, keyboard-only path, screen reader (Narrator) in Desktop.
- Non-specialist completes the core task unaided (Phase 5 exit test).
- Release `.pbix` on a clean Windows profile (Phase 7).

## How to resume
Read `CLAUDE.md` (commands), this file, `docs/PLAN.md`, `registers/qa-log.md` tail. Open Desktop with `scripts/pbi_reopen.ps1`, run `scripts/validate_phase6.py`.
