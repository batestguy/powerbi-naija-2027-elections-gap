# Project plan — Nigeria 2027 Scenario Simulator (Power BI)

Source brief: `details.txt`. This plan turns the brief into working phases with a concrete
deliverable and a pass/fail exit check for each. Phase numbers match the brief.

Status key: `todo` · `doing` · `done` · `blocked`

| # | Phase | Status | Exit check (must pass before the next phase) |
|---|-------|--------|----------------------------------------------|
| 0 | Environment audit | done | `docs/environment.md` lists tools, versions, publish tier and its limits |
| 1 | Source validation + licence | blocked | Every source in `registers/sources.md` marked approved / conditional / rejected |
| 2 | Acquisition + profiling | todo | Unmatched-keys report shows LGA join coverage across all three tables; every gap explained |
| 3 | Model design (thin slice first) | todo | One state works end-to-end in Desktop; then full model diagram + rationale |
| 4 | Scenario engine | todo | Methodology note reproduces results by hand; extreme-slider tests pass |
| 5 | Report pages | todo | A non-specialist completes the core task unaided |
| 6 | QA | todo | `registers/qa-log.md` all pass, or each failure has a resolution |
| 7 | Publish + docs | todo | Live link opens; methodology and limits reachable from inside the report |
| 8 | Case study | todo | One-page case study + live link |

---

## Phase 0 — Environment audit
**Goal:** know what is actually possible before promising anything.
- Record Power BI Desktop version; confirm PBIP / PBIR (folder-based project) saving is enabled.
- Decide the publish target: Power BI free tier, "Publish to web", or desktop-only. Record its limits
  (dataset size, refresh, Shape Map / Azure Map availability, Publish-to-web allowed by tenant?).
- Choose and pin the data-prep environment (Python version + env path). Record it in `CLAUDE.md`.
- Confirm we can fetch a URL and save the response to `data/raw/`.

**Deliverable:** `docs/environment.md`. **Risk to resolve early:** if Publish-to-web is not available
on the account, Phase 7 changes shape — find out now.

## Phase 1 — Source validation and licence
**Goal:** each planned source is live, usable, and legally publishable.

| Source | Needed for | Key question |
|---|---|---|
| Mundx `lgas.json` | 2023 LGA baseline (four-party rollup) | Still published? All 774 LGAs? Licence? |
| Nigeria2 API | Cross-check / extra detail | Auth needed? Granularity? |
| CredibleVoteNG | Registered voters | Per LGA directly, or aggregate from polling units? |
| LGA GeoJSON (World Bank / GitHub) | Map geometry | Cleanest LGA names? FCT a distinct unit? Licence? |
| INEC / reputable aggregator | Independent check of state + national totals | Which figures are published officially? |

- Research the constitutional threshold (Constitution s.134) from the primary text: exact wording,
  how "two-thirds of all the States" rounds (24 of 36), and how the FCT is treated. Log in
  `registers/decision-log.md`. **Stop and flag** if the reading changes the headline metric.

**Deliverable:** `registers/sources.md` filled (URL, access date, format, grain, licence, confidence).

## Phase 2 — Acquisition and profiling
**Goal:** raw data landed unmodified and understood.
- `scripts/pull_*.py` save responses exactly as received to `data/raw/<source>/<YYYY-MM-DD>/`,
  plus a manifest (URL, access date, row count, file hash).
- Profile each table: rows vs expected (774 LGAs, 37 incl. FCT), nulls, duplicates, ranges, encoding.
- **Join-key check (gate):** match LGA names across baseline, registered voters and geometry.
  Write `reports/unmatched_keys.csv` + a summary. Build a reviewed name-crosswalk; never fuzzy-match silently.
- Reconcile state party totals against the independent source within a stated tolerance.
- Simplify geometry (target size noted in Phase 0) and record the tool + tolerance used.

**Deliverable:** raw snapshots + manifests, profiling summary, unmatched-keys report, crosswalk.

## Phase 3 — Model design
**Goal:** a clean star model with geography as the spine.
- **Thin slice first:** one state, baseline only, map + one card. Generate the `.pbip` by script and confirm Desktop opens it: the real proof that PBIP + Shape Map work on this build.
- Then full model: `dim_state`, `dim_lga`, `dim_party` (disconnected, drives slicers),
  `fact_result_2023` (grain: LGA × party, immutable), `fact_registered_voters` (grain: LGA).
- Single-direction relationships only, unless justified in the decision log.

**Deliverable:** model diagram + short rationale in `docs/model.md`.

## Phase 4 — Scenario engine
**Goal:** transparent, parameter-driven simulation.
- Write the method first (`docs/methodology.md`): how swing applies (state-uniform vs LGA-weighted),
  what turnout changes (denominator, candidate votes, or both), threshold test per state,
  and definitions of "secured", "tipping point", "out of reach".
- Implement as What-If parameters + measures only. No scenario columns in fact tables.
- Tests: sliders at min / max / neutral; no divide-by-zero, no shares below 0 or above 100%;
  at neutral settings the simulator equals the baseline exactly.

**Deliverable:** methodology note + test results in `registers/qa-log.md`.

## Phase 5 — Report pages
Build order: **Overview → State-by-State Path → LGA Vulnerability Map → Scenario Simulator**,
then **How to read this** and **Data Sources**.
- 25% is a fixed reference line; colour scale anchored at 0.25; colour-blind safe with labels/patterns.
- Every page states its assumptions on the page, not only in DAX comments.
- Accessibility: keyboard order, alt text on visuals, contrast checked.

**Deliverable:** report in `pbip/` + written page guide `docs/page-guide.md`.

## Phase 6 — QA
National totals vs independent source; LGA-geometry matches re-checked after import;
baseline page = simulator at neutral; refresh from clean cache; published version tested in a
fresh browser. Results in `registers/qa-log.md`.

## Phase 7 — Publish and documentation
Publish to the target from Phase 0. Data Sources page (source, access date, licence, limitation)
and How-to-read page (threshold, assumptions, what the report does not claim). Freeze the data
vintage used; corrections ship as a new vintage.

## Phase 8 — Case study
One page: the question, sources, key modelling decisions, trade-offs (state vs LGA swing),
what next. Links to the live report, decision log and open-questions register.

---

## Stop-and-flag rules (from the brief)
Unclear licence on a public source · two sources disagree on a headline figure beyond tolerance ·
threshold wording ambiguous in a way that changes the headline · LGA key coverage low for
unexplained reasons.
