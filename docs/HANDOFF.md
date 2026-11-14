# Handoff — where the project is

Updated: 2026-11-14. Update this file in every stage commit.

## Phase status (see `docs/PLAN.md`)
| Phase | State | Last commit |
|---|---|---|
| 0–4 Environment, sources, data, model, scenario engine | done | 44ca968 |
| 5 Report pages | done; non-specialist test still needs a person | 9813cbc |
| 6 QA | scripted checks 9/9 pass (`scripts/validate_phase6.py`); manual checks open | 8f6e407 |
| 5b Redesign (user review round) | **in progress** — not committed | — |
| 5c Merge parties + head to head | **queued** (decisions taken, nothing built) | — |
| 7 Release + docs, 8 Case study | todo | — |

## In progress: redesign round (user requests 2026-11-14)
1. Hover shows state names, not P-codes.
2. Plain wording on all pages ("states" not "units", "the deciding state", "Result"); gaps stated in votes, not points.
3. New **Technical notes** page: terms + formulas in words and symbols (no underscores/LaTeX).
4. Colour key made of coloured lines (not a health bar); bold coloured 25% line.
5. Side photo panels (left/right varied) — freely licensed Nigerian election photos (Wikimedia Commons), neutral scenes only, credited.
6. Candidate identity on selection: free-licence candidate photo (initials badge for all if any is missing), **real party logos** (trademarks, identification only; `PBIP_NO_LOGOS=1` falls back to badges), party colours on accents only (data colours fixed), "2023 party" + "Party now" (verified with dated sources or "not confirmed").
7. Playable Simulator: "How to play" strip, sliders as everyday questions, "Try these" bookmark buttons + reset, result as a sentence.
8. State codes (ISO 3166-2:NG, e.g. LA, KN, FC) visible on tile map; geographic map labelled or a labelled locator map beside it.

After it: reviewer check → screenshots to user → commit + push → update this file.

## Queued: merge parties + head to head (user decisions 2026-11-14)
- Slider "how many of the partner's voters follow", 0–100%, default 100%; non-followers stay home (state valid totals shrink).
- Merged party name from a pick list + editable reference CSV (real mergers only if verified with dated sources).
- Two new pages: "Merge two parties", "Head to head".
- Full Simulator integration: every slider applies to a merged party → redo `docs/methodology.md`, engine, `validate_phase4.py`, blind reproduction review.
- To be written into `registers/decision-log.md` when the work starts.

## Open items needing a person
- Hover tooltips, keyboard-only path, screen reader (Narrator) in Desktop.
- Non-specialist completes the core task unaided (Phase 5 exit test).
- Release `.pbix` on a clean Windows profile (Phase 7).

## How to resume
Read `CLAUDE.md` (commands), this file, `docs/PLAN.md`, `registers/qa-log.md` tail. Open Desktop with `scripts/pbi_reopen.ps1`, run `scripts/validate_phase6.py`.
