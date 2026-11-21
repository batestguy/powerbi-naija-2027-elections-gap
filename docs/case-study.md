# Case study: how far is each candidate from Nigeria's 25% rule?

**Deliverable:** a free Power BI Desktop what-if report, built from scripts so anyone can rebuild it. **Release:**
[v1.0.0](https://github.com/batestguy/powerbi-naija-2027-elections-gap/releases) (`.pbix` + frozen data vintage
2026-11-20). **Walkthrough video:** [`docs/demo/naija_demo.mp4`](demo/naija_demo.mp4) (3:41).

## The question
To win outright, a Nigerian presidential candidate needs the most votes nationwide **and** at least a quarter of the
vote in two-thirds of the states and Abuja (Constitution s.134(2)). National vote share alone hides how close a
candidate is to that second test. The report asks: starting from 2023, how many states does each candidate hold at a
quarter? Which state decides it? And how far would turnout, swings or a two-party coalition move that count in 2027?

## Sources
- 2023 state results: **five copies** of INEC's declaration (Wikipedia by-state table pinned to a revision, the AGADA-BI
  table, ThisDay, thenigerialawyer.com and Vanguard). INEC's own state collation sheets (Form EC8D) are not public.
- The national declaration, registered voters, ISO state codes, an HDX state boundary file, and dated news reports for
  "party now" and the coalition tickets.
- Every source has a URL, an access date, a SHA-256 snapshot and a row count: `registers/sources.md`, `data/raw/*/manifest.json`.

## Key modelling decisions
1. **Reconcile, don't pick a favourite.** Each independent copy gets one vote per cell; ThisDay and thenigerialawyer.com
   count as one copy because they share every error. 17 of the 148 main-party cells disagreed or had a copy missing. 14
   were settled by majority. 3 were decided by hand against INEC's national totals and listed with their reasons
   (`reports/result_reconciliation.csv`, `data/reference/result_cell_decisions.csv`). The model's national totals
   equal every independent copy (Phase 6 check, `reports/phase6_validation.json`).
2. **The rule as the courts read it.** The 2023 tribunal and Supreme Court treated Abuja as a 37th state with no special
   status, but named no number of states. Two-thirds of 37 is 24.67, so the report uses 25 and offers 24.
3. **The 25% test in whole numbers** (4 × votes ≥ valid votes), so no rounding can flip a state. Slider measures use a
   1E-12 margin. A search proves no reachable setting lies inside that margin without sitting exactly on the line.
4. **Additive swings** (national + six zones, in points) and a **supporter-turnout** slider. An equal turnout change
   leaves every share unchanged, so only a differential one is meaningful.
5. **Coalitions recombine 2023 votes:** lead + the share of the partner's voters who follow. Only "NDC (Obi +
   Kwankwaso)" is a real ticket. Every other pairing is labelled a what-if.

## Trade-offs
- **State-level, not LGA-level.** No open, complete, licensed LGA results exist. The best open file covered 266 of 774
  LGAs, and the full Mundx file has no redistribution licence. The 25% rule is judged per state anyway. Cost: one swing
  per zone is uniform across its states. The report pages state this.
- **Desktop file, not the Power BI service.** Free and needs no account. Cost: Windows only, so a video and screenshots
  carry the story for everyone else.
- **Generated, not hand-built.** Every page and measure comes from `scripts/build_pbip.py`. That makes the report
  re-runnable and diffable, and lets scripts check it: 92 scenario checks and 18 QA checks pass on the release build
  (`reports/phase4_validation.json`, `reports/phase6_validation.json`). Cost: a Desktop save overwrites generated files.
- **Plain words on every page** except one "Technical notes" page.

## What the 2023 baseline shows
Bola Tinubu (APC) reached a quarter in **29 states** (25 needed), and Adamawa is one of them by only 96 votes. Atiku
Abubakar reached 21, Peter Obi 16 and Rabiu Kwankwaso 1 (`reports/phase6_validation.json`, overview check; rule 25).

## Limits (also on the report pages)
A what-if tool, not a forecast or an electoral authority. The voters are the 2023 voters. Kano APC (506,412 vs
517,341) was chosen by consistency with the national total, not an official sheet; either figure gives the same
quarter results in Kano. The scripted checks are a re-implementation by the same author, so they mainly catch slips.
A screen-reader check was done by the author; keyboard-only and non-specialist tests are still to be done.

## What next, with more time or better data
- INEC's Form EC8D state sheets, through a Freedom of Information request, to replace the five-copy reconciliation.
- An LGA layer with zone-free swing weights, if Mundx grants permission or open LGA results appear.
- The 2026 voter register and per-state accredited voters, for turnout from real rolls.
- A person-run accessibility audit and an outside reviewer.

## Evidence of process
- **Decisions, with alternatives and reasons:** [`registers/decision-log.md`](../registers/decision-log.md).
- **Open questions, with owners and next steps:** [`registers/open-questions.md`](../registers/open-questions.md).
- **Risks:** [`registers/risks.md`](../registers/risks.md). **QA:** [`registers/qa-log.md`](../registers/qa-log.md).
- **Method:** [`docs/methodology.md`](methodology.md).
