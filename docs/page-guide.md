# Page guide (Phase 5, redesigned 2026-11-14)

The report is `pbip/NaijaElectionsGap.pbip` (Power BI Desktop). Built by `scripts/build_pbip.py` (model) and
`scripts/pbip_pages.py` (pages); photos, portraits, logos and the locator map by `scripts/build_photos.py`; state codes
by `scripts/build_state_codes.py`. Screenshots: `reports/screenshots/phase6_redesign/` (Tinubu, default build),
`reports/screenshots/phase6_redesign_obi/` (Peter Obi), `reports/screenshots/phase6_redesign_candidates/` (Atiku,
Kwankwaso, and the no-logos fallback).

## The core task (brief's exit test)

1. Pick a candidate in the **Candidate** box (top right of every data page; the choice carries across pages).
2. Go to **What-if simulator** and move a slider (or type a value into its box). Each slider is an everyday question
   ("What if they gain or lose support everywhere?").
3. Read the **Result** sentence ("Bola Tinubu wins outright: … in 29 states (24 needed).") and the deciding-state
   sentence. **Your what-if, in words** repeats every slider that is not at 0.

## Pages

| Page | Question it answers | What is on it | Photo |
|---|---|---|---|
| Candidate overview | How did this candidate do in 2023? | Votes, share, place, states won (of 37), states with results; all 37 states as columns with the bold wine 25% line and a colour key; zone table; closest calls in votes; how sure the margins are | right |
| Path to 24 | Which states carry the 25% test? | States won, needed, more needed, rule met, deciding state; the deciding state in votes; ranked columns (deciding state black); table with "Extra votes needed to reach a quarter" | left |
| Spread map | Where is the hold strong or fragile? | Boundary map (hover = state name), equal-size squares with ISO codes in each square, "Every state in words" table, grey "Where is each state?" locator with codes, colour key, counts, code list | right |
| What-if simulator | What if 2027 differs? | How to play; nine sliders as questions; result sentence; most votes / closest rival / national share; states won / more needed / hit 0% or 100%; deciding state in votes; settings in words; coded tile grid; colour key; "Try these" examples (text) | left |
| How to read this | What does this claim, and not claim? | The rule, what the numbers are, what the simulator assumes, words used, what it does not claim | right |
| Technical notes | How exactly is each number made? | Plain section titles; one formula per line in words and symbols (×, ÷, −, ≥, ≤), same mathematics as `docs/methodology.md`; state code list | left |
| Data sources | Where does each number and picture come from? | Data sources; photo and portrait credits; party-logo trademark notice and file pages; "party now" sources | right |
| Model check (hidden) | QA only | The Phase 3 check page | — |

Header of every data page: the candidate's free-licence portrait, the 2023 party logo, a box in the party's accent
colour with "2023: APC. Now: APC (Leadership, 25 May 2026)", the party-now logo, and the candidate selector.
`PBIP_NO_LOGOS=1` at build time replaces both logos with abbreviation badges.

## Design rules applied

- **Plain words** on every page except Technical notes ("states", not "units"; "the deciding state", not "tipping
  point"; "Result", not "Verdict"). Abuja (the Federal Capital Territory) counts as a state; each data page says so.
- **Gaps in people:** the deciding state and the 2023 closest calls are stated in votes (measures `Deciding state
  sentence`, `Closest calls sentence`, `Votes to spare`, `Votes needed`).
- **25% is fixed:** a solid 3 px Tol-wine (#882255) line labelled "A quarter of the vote (25%)" on both column charts;
  the map scale is fixed at −25 / 0 / +25 points.
- **Colour is never alone:** every coloured chart or map has a key of short thick coloured bars with words; tables
  spell out the status; codes are text. Data colours (blue / vermillion / grey / black / wine) never change with the
  candidate; party colours appear only as card borders and the identity box (text black/white by ≥ 4.5:1 contrast).
- **Photos are decorative:** a tall side panel per page, credited, alt text starting "Decorative photo:", last in
  tab order, never behind a chart or text.
- **Hover:** the boundary map and the column charts show the state name. The coded tile grids (matrix visuals) show
  the code on hover, not the name — names are in the list beside them (decision log 2026-11-14).

## Checks (`registers/qa-log.md`)

`powerbi-report-author validate` 0/0; `scripts/validate_phase6.py` (re-runs Phase 3 and 4, plus the redesign checks:
state names on maps, ISO codes, sentences vs an exact independent computation, result/settings sentences vs the
Phase 4 reference, identity and logos, photos).

## Known limits

- Hover tooltips have not been seen rendered (hover cannot be scripted here); the bindings are checked in the files.
- "Try these" are text examples, not buttons (open question 18).
- "Party now" is from dated news reports, not INEC's candidate list (open question 16).
- Not yet tested with a non-specialist reader.
