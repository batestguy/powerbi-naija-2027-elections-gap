# Project plan — Nigeria 2027 Scenario Simulator (Power BI)

Source brief: `details.txt`. This plan turns the brief into working phases with a concrete
deliverable and a pass/fail exit check for each. Phase numbers match the brief.

> **Scope change (2026-11-13): state-level core.** No open, complete LGA-level 2023 result set exists
> (see `registers/sources.md`). The simulator is built on complete official **state** results
> (36 states + FCT = 37 units), which is also the grain at which the 25% rule is judged.
> Mundx's LGA rollup is an optional add-on page, only if Mundx grants written permission.
> Delivery: desktop file (PBIP in git, `.pbix` as release asset) + walkthrough video.

Status key: `todo` · `doing` · `done` · `blocked`

| # | Phase | Status | Exit check (must pass before the next phase) |
|---|-------|--------|----------------------------------------------|
| 0 | Environment audit | done | `docs/environment.md` lists tools, versions, publish tier and its limits |
| 1 | Source validation + licence | done | Every source in `registers/sources.md` marked approved / conditional / rejected |
| 2 | Acquisition + profiling | done | 37 units join across results, registered voters, zones and geometry with zero unmatched keys; state sums equal the INEC national totals exactly |
| 3 | Model design (thin slice first) | doing | One state works end-to-end in Desktop; then full model diagram + rationale |
| 4 | Scenario engine | todo | Methodology note reproduces results by hand; extreme-slider tests pass |
| 5 | Report pages | todo | A non-specialist completes the core task unaided |
| 6 | QA | todo | `registers/qa-log.md` all pass, or each failure has a resolution |
| 7 | Release + docs | todo | Release `.pbix` opens on a clean profile; video linked; methodology and limits reachable from inside the report |
| 8 | Case study | todo | One-page case study + release + video links |

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
  plus a manifest (URL, access date, Wikipedia revision ID where relevant, bytes, SHA-256).
- **State results (primary):** Wikipedia "2023 Nigerian presidential election" → *By state* table,
  pinned to a revision ID (INEC declared figures; CC BY-SA 4.0). Per state: APC/PDP/LP/NNPP/others votes,
  total valid votes, turnout %.
- **Registered + accredited voters per state:** infoboxes of the 37 "2023 Nigerian presidential election in
  <State>" pages (pinned revisions); cross-check against turnout % above.
- **Independent cross-check:** the INEC declaration copy on thenigerialawyer.com and the AGADA-BI state table.
- **Geopolitical zones:** 37 units → 6 zones, from a cited source.
- **Geometry:** HDX COD-AB admin1 (states) → simplified TopoJSON, plus a hand-built equal-size tile grid
  TopoJSON for the tile map.
- **Mundx (optional, local only):** snapshot to `data/raw/` (never committed), state-by-state accuracy report.
- Profile: 37 rows, no nulls, no duplicates; party votes + others = total valid; per-party state sums =
  national declared totals exactly; 25%-count per candidate = 29 / 21 / 16 / 1 (APC/PDP/LP/NNPP).
- **Join-key gate:** one canonical state key (HDX `adm1_pcode`) across all tables; `reports/unmatched_keys.csv` must be empty.

**Deliverable:** raw snapshots + manifests, `data/staging/` tables, `reports/phase2_validation.json`, profiling summary.

**Outcome (2026-11-14):** Wikipedia's By-state rows did not sum to INEC's national declaration, so state results are a five-copy reconciliation (decision log 2026-11-14). Gate passed: four-party state sums equal INEC national exactly (independent evidence for PDP and NNPP; for APC and LP the match was used to choose 3 cells); 0 unmatched keys; 25% count 29/21/16/1, with APC's 29 resting on a 96-vote margin in Adamawa. Published gaps: OTHERS +4,858, registered voters −120,281. See `docs/data-profile.md`.

## Phase 3 — Model design
**Goal:** a clean star model with geography as the spine.
- **Thin slice first:** baseline only, state map + tile map + one card. Generate the `.pbip` by script and confirm
  Desktop opens it: the real proof that PBIP + Shape Map (incl. the tile grid) work on this build.
- Then full model: `dim_state` (37 units, P-code, zone), `dim_zone` (6), `dim_party` (disconnected, drives slicers),
  `fact_result_2023` (grain: state x party, immutable), `fact_turnout_2023` (grain: state: registered, accredited, valid, rejected).
- Optional, only with Mundx permission: `dim_lga`, `fact_mundx_lga_2023` (labelled unofficial).
- Single-direction relationships only, unless justified in the decision log.

**Deliverable:** model diagram + short rationale in `docs/model.md`.

**Thin slice (2026-11-14): passed.** `scripts/build_pbip.py` → `pbip/NaijaElectionsGap.*`; opens in Desktop 2.159; card reads 8,794,726; both Shape Maps (state boundaries, 37 tiles) render with every unit coloured (`reports/screenshots/phase3_thin_slice.png`). Next: full model (`dim_zone`, `dim_party`), `docs/model.md`.

## Phase 4 — Scenario engine
**Goal:** transparent, parameter-driven simulation.
- Write the method first (`docs/methodology.md`): how swing applies (national + six zone sliders, applied per state),
  what turnout changes (denominator, candidate votes, or both), threshold test per state,
  and definitions of "secured", "tipping point", "out of reach".
- Implement as What-If parameters + measures only. No scenario columns in fact tables.
- Tests: sliders at min / max / neutral; no divide-by-zero, no shares below 0 or above 100%;
  at neutral settings the simulator equals the baseline exactly.

**Deliverable:** methodology note + test results in `registers/qa-log.md`.

## Phase 5 — Report pages
Build order: **Overview → Path to 24 → Spread Map → Scenario Simulator**, then **How to read this** and **Data Sources**.

| Page | Answers | Main visuals |
|---|---|---|
| Candidate Overview | How did this candidate do in 2023? | KPI cards (votes, share, units at 25%+, rank); share by state with fixed 25% line; zone breakdown |
| Path to 24 | Which states carry the spread test? | 37 units ranked by share; 25% line; 24th-unit marker (tipping point); secured / within reach / out of reach labels; tooltip: votes needed to reach 25% |
| Spread Map | Where is the 25% hold strong or fragile? | Toggle: geographic state map / equal-size tile map; coloured by distance from 25% |
| Scenario Simulator | What if 2027 differs? | Sliders: national swing, six zone swings, turnout; live States Secured counter; plurality check; verdict (outright win / run-off / loses); rule toggle 24-of-37 vs 25-of-37 |
| How to read this | What does this claim, and not claim? | Plain-language rule, assumptions, limits |
| Data Sources | Where does each number come from? | Source, access date, licence, limitation |
| *Inside a state (optional)* | *Local picture* | *Only with Mundx permission; labelled unofficial, accuracy shown* |
- 25% is a fixed reference line; colour scale anchored at 0.25; colour-blind safe with labels/patterns.
- Every page states its assumptions on the page, not only in DAX comments.
- Accessibility: keyboard order, alt text on visuals, contrast checked.

**Deliverable:** report in `pbip/` + written page guide `docs/page-guide.md`.

## Phase 6 — QA
National totals vs independent source; state-geometry matches re-checked after import;
baseline page = simulator at neutral; refresh from clean cache; release `.pbix` opened on a clean
Windows profile; video checked against the QA list. Results in `registers/qa-log.md`.

## Phase 7 — Publish and documentation
Tag a GitHub release with the `.pbix`, the frozen data vintage and the video link. Data Sources page (source, access date, licence, limitation)
and How-to-read page (threshold, assumptions, what the report does not claim). Freeze the data
vintage used; corrections ship as a new vintage.

## Phase 8 — Case study
One page: the question, sources, key modelling decisions, trade-offs (state vs LGA swing),
what next (LGA layer). Links to the release, video, decision log and open-questions register.

---

## Stop-and-flag rules (from the brief)
Unclear licence on a public source · two sources disagree on a headline figure beyond tolerance ·
threshold wording ambiguous in a way that changes the headline · state key coverage below 37/37.
