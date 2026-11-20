# Handoff — where the project is

Updated: 2026-11-20. Update this file in every stage commit.

## Phase status (see `docs/PLAN.md`)
| Phase | State | Last commit |
|---|---|---|
| 0–4 Environment, sources, data, model, scenario engine | done | 44ca968 |
| 5 Report pages | done; non-specialist test still needs a person | 9813cbc |
| 6 QA | scripted checks 15/15 pass after redesign (`scripts/validate_phase6.py`); manual checks open | 8f6e407 |
| 5b Redesign (user review round) | done; reviewed; "Try these" buttons not built (open question 18) | 619c068 |
| 5c Merge parties + head to head | built; open question 22 line built 2026-11-20; full checks on the final build 2026-11-20: Phase 4 92/92, Phase 6 18/18 (after the Head to head speed query was split per visual) | see git log |
| 7 Release + docs, 8 Case study | todo | — |

## Overall progress (estimate, 2026-11-19)
About 75–80% of the whole project by effort (a judgement, not a measurement). Built: data, model, scenario engine,
12 report pages incl. redesign and coalitions, scripted QA. Left before release: the open question 22 line, full
checks on the final build, a cross-family review, person checks (hover, keyboard, screen reader, non-specialist test).
Not started: Phase 7 (release `.pbix`, clean-profile test, docs, walkthrough video) and Phase 8 (one-page case study:
question, sources, key decisions, trade-offs, what next; links to release, video, decision log, open questions).

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

### 2026-11-20: open question 22 built; full checks run on the final build
- Built: "Simulator header line" measure + a line under the simulator header (empty when the switch is Off; "Coalition
  On: results are for <Side A name>, not the candidate above." when On; "Coalition On, but not complete: fix it on Head
  to head." when the coalition is invalid). Results column re-spaced (moved down, gaps 2 px; tile grid 238 px). Box
  heights matter: Result < 92 px, settings < 60 px, deciding < 90 px or card rows < 56 px cut text (found by
  screenshots). Screenshots: `reports/screenshots/q22_2026-11-20/` (switch Off) and `q22_switch_on_2026-11-20/`
  (built with `PBIP_COALITION_ON=1`). New checks: switch_off part (line empty Off / names Side A On), invalid part
  (line says "not complete"), Phase 6 speed query for the line.
- A Desktop save of 2026-11-19 04:09 had again overwritten generated files (+ cultures, diagramLayout, cache.abf);
  rebuilt from the generator, restored the two Desktop-only files, deleted the cache.
- **Phase 4: 92/92, gate passed** (boundary 4, core 81, invalid 1, switch_off 2, simulator 1, pages 3 in 26 min).
- **Phase 6: 17/18, gate FAILED on speed only**: "Head to head table + cards" 2.008 s cold (limit 2.0 s; 1.585 s on
  2026-11-19); every other query <= 1.25 s. Not caused by this change (that page was not touched). `time_engine.py`
  right after: Head to head verdict + sentence 1.78 s cold (2.13 s on 2026-11-19), so the page sits at the limit and
  run-to-run noise decides pass/fail.
- **Fixed (same day): the speed query was mis-shaped**, not the page. It put the page-wide sentence and "States led
  by Side A" on each of the 37 state rows (worked out 37 times); the page asks for each once. Now one query per
  visual, as for the simulator (decision log). **Phase 6 re-run: 18/18, gate passed.** Slowest cold: simulator result
  sentence with the coalition On 1.542 s (1.133 s in the run before: noise; the machine was in use), Head to head
  sentence 0.95 s, state table 0.90 s. The simulator coalition-On sentence is now the closest to the 2 s limit.
- **Next:** cross-family review of the coalition + Q22 work, person checks (hover, keyboard, screen reader,
  non-specialist test), then Phase 7 (release `.pbix`, clean-profile test, docs, walkthrough video) and Phase 8.
- Run notes: the first Phase 6 attempt died with no output (log redirect lost it); the second stopped because Desktop
  had 3 dialogs open (not seen; cause unknown). Desktop was killed and reopened; third run as above. Logs:
  `reports/run_logs/`.

### 2026-11-19 (later): layout fixes, rival proof, simulator text — **full checks not yet run on this build**
**Start here next session:** close other programs (memory), `scripts/pbi_reopen.ps1 -Force`, then
`validate_phase4.py --part boundary|core|invalid|switch_off|simulator|pages` one at a time, `--combine`,
`validate_phase6.py`, `time_engine.py`. A run on 2026-11-19 03:3x was stopped by the tool for low memory (1.4 GB free)
during the boundary part (its first two checks had passed); its partial file was discarded. The committed
`reports/phase4_*.json` / `phase6_validation.json` describe 09bfb38, not this build; the build stamp makes combine and
reuse refuse them, so they cannot be mistaken for current.

Changed since 09bfb38:
- Model: `Points from 25%` shows 0 within 1E-12 of 25% (no "-0.0"); deciding-state sentence now ends "…would need to
  switch to them from other candidates." (both references in `validate_phase4.py` / `validate_phase6.py` updated to
  match); simulator coalition note shortened ("On: <A>, 100% follow, vs <B>." / "Off: uses the candidate at the top.
  Coalitions: see Head to head.").
- New check (boundary part): rival shares need no margin. Run offline 2026-11-19: no reachable rival share exactly on
  25%; smallest gap 3.1E-11 (55 s). A rival margin was tried and reverted (decision log).
- Layout: Head to head result box no longer clipped; Merge page chart 820 px shows all 37 states and the table shows
  all four columns (9 pt, wrapped names, heading "Lead"); simulator deciding-state text 9 pt. Text in these card boxes
  shows at most two lines whatever the box height. Screenshots checked by eye: `reports/screenshots/layout_2026-11-19/`
  (switch Off), `reports/screenshots/simulator_switch_on_2026-11-19/` (built with `PBIP_COALITION_ON=1`; the repo is
  built without it). Not checked by eye: the Merge table with "Out of reach" rows in view (rows below the fold).
- Open question 22 decided by the user 2026-11-19: when the simulator's coalition switch is On, add one line under the
  header, "Coalition On: results are for <name>" (header itself unchanged). **Build it next session, before the full
  checks**, so the checks run once on the final build.

### 2026-11-19: review fixes done (items 2-6 of `reports/review_2026-11-18.md`; follow-up at its end)
- Desktop's save of 2026-11-18 09:25 had overwritten the generated report files and left a `cache.abf`; rebuilt from
  `build_pbip.py` (identical to the commit apart from line endings), restored the two Desktop-only files, deleted the cache.
- Deciding-state sentence: branch from `p >= Q`, gap printed as `MAX ( 0, -g )`; new boundary check (sentence at every
  exact 25% hit made deciding; 5 placed and equal to the reference, 1 proven never deciding). Phase 4 is now 90 checks.
- Exact-hit check fails unless all reachable (hit, line) pairs are tested (12 of 12).
- Build stamp on Phase 4 parts / combined result (`scripts/build_stamp.py`); combine and Phase 6 reuse refuse a mismatch.
  Proven once: Phase 6 re-run reused the Phase 4 result ("existing result has the current build stamp").
- Speed gate timed inside one engine connection, cache cleared, gate on median cold (`pbi_engine.ps1 -Action Time`).
  Slowest: Head to head table + cards 1.585 s cold, 1.259 s warm. `scripts/time_engine.py` → `reports/engine_timings.json`.
- Results: Phase 4 parts core 81/81 (839 s), invalid 1/1 (72 s), switch_off 1/1 (30 s), simulator 1/1 (732 s),
  pages 3/3 (3,017 s), boundary 3/3 (~260 s); combined 90/90. Phase 6 18/18 (633 s).
- Not explained: the pages part took 3,017 s (1,354 s on 2026-11-18) and core / simulator were also slower. The engine was
  busy throughout (not stalled); the only model change was the deciding-state sentence. Re-time before treating as real.

**Next, in order (superseded by the section above):** full checks on the new build; open question 22; a cross-family
review before anything is published; then Phase 7.

### 2026-11-18: speed fixed, boundary bug fixed, engine rewritten — all Phase 4 checks pass (89/89)
**Next, in order:**
1. `validate_phase6.py` — **done 2026-11-18: 18/18** (speed check now one query per visual, user decision;
   decision log). Phase 4 result is reused when newer than the build (a full re-run takes ~45 min).
2. Screenshots — **done 2026-11-18**: all 12 pages, `reports/screenshots/coalition_2026-11-18/` (switch Off, preset
   NDC v APC on the coalition pages; numbers match the checks: 19 states, 7,598,220 votes). First capture of
   Merge two parties came out faded mid-load; re-taken with `--settle 9000`. Small layout fixes found:
   Head to head result sentence slightly clipped at the bottom of its box; Merge table's "Change (points)"
   column cut off at the right (needs a scroll). Not yet captured: the simulator with the switch On (needs a
   build variant).
3. Reviewer pass — **done 2026-11-18**: `reports/review_2026-11-18.md`. Verdict ship with fixes; no blocking
   finding, no wrong numbers. **Next: the six SHOULD-FIX items there** (timing evidence into `reports/`;
   build stamp on Phase 4 parts / reuse; assert every exact hit is tested; deciding-state sentence at an
   exact line; speed-gate noise noted). Then a cross-family review before anything is published.
4. All 2026-11-18 work is committed and pushed (e01a5e7, eba9aea, dd9f888, a485ed9, and the review commit).
   Also next: the two layout nits (item 2), a simulator screenshot with the switch On.
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
Measured (preset NDC v APC, switch On, cache cleared). **The "Before" column and the memory figures came from session
scripts that are no longer in the repo: not reproducible.** Current timings: `reports/engine_timings.json`
(`scripts/time_engine.py`, 2026-11-19; these queries differ, so compare with care):

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
