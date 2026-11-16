# Handoff — where the project is

Updated: 2026-11-16. Update this file in every stage commit.

## Phase status (see `docs/PLAN.md`)
| Phase | State | Last commit |
|---|---|---|
| 0–4 Environment, sources, data, model, scenario engine | done | 44ca968 |
| 5 Report pages | done; non-specialist test still needs a person | 9813cbc |
| 6 QA | scripted checks 15/15 pass after redesign (`scripts/validate_phase6.py`); manual checks open | 8f6e407 |
| 5b Redesign (user review round) | done; reviewed; "Try these" buttons not built (open question 18) | see git log |
| 5c Merge parties + head to head | **queued** (decisions taken, nothing built) | — |
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
