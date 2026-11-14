# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## State of the project
Pre-build. The only source of truth is `details.txt` (the agent brief). No code, data, PBIP project, environment or git repo exists yet. Read `details.txt` before planning any phase; treat it as directional — adapt where evidence points elsewhere and log why.

## What this is
A free-tier Power BI report: a candidate's 2023 baseline across Nigeria's 774 LGAs (37 states incl. FCT), 2027 scenarios via swing + turnout sliders, and a live "States Secured" count against the 25%-in-24-states (two-thirds of states) rule. Four pages: Candidate Overview, LGA Vulnerability Map, Scenario Simulator, State-by-State Path — plus "How to read this" and "Data Sources" pages. It is a scenario/communication tool, not an electoral authority.

## Phases (from the brief)
0 environment audit → 1 source validation + licence → 2 raw acquisition + profiling → 3 model design → 4 scenario engine → 5 report pages (build order: Overview → Path → Map → Simulator) → 6 QA → 7 publish + docs → 8 case study. Each phase has exit criteria in `details.txt`; do not skip to visuals before Phase 2's join-key check passes.

Planned sources (all unverified): Mundx `lgas.json` (four-party rollup), Nigeria2 API, CredibleVoteNG (registered voters), LGA GeoJSON (World Bank / GitHub).

## Non-negotiables
- Never fabricate, interpolate or fill missing results — null it and show it.
- Every Mundx-derived baseline is labelled "four-party rollup, not official INEC results". Mundx licence is unclear → "internal use / attribution required" until confirmed.
- Every table records source URL, access/snapshot date, row count, transform.
- Baseline fact tables are immutable; scenario logic lives only in measures / clearly labelled calculated layers. One grain per table. No bidirectional relationships unless justified in the decision log.
- LGA keys must match the shapefile's name property exactly. Count unmatched keys before building any visual — the most likely silent failure.
- Simplify geometry before import.
- State-level uniform swing is an approximation — say so in the report, or move to LGA-level weights explicitly.
- Confirm constitutional threshold wording (incl. whether FCT counts) before encoding it.
- Sliders bind to What-If parameters, never hard-coded values. Assumptions are stated on report pages, not only in DAX comments.
- 25% is a fixed semantic boundary (reference line; scale anchored at 0.25); colour-blind safe — not red/green alone.

## Stop and flag (don't proceed) when
a public source's licence is unclear; two sources disagree on a headline figure beyond tolerance; threshold wording is ambiguous in a way that changes the headline; LGA key coverage is low for unexplained reasons.

## Plan and registers
Working plan with per-phase exit checks: `docs/PLAN.md` (update the status column as phases move).
Registers live in `registers/`: `decision-log.md`, `open-questions.md`, `risks.md`, `sources.md`, `qa-log.md`.

## Layout
`data/{raw,staging,presentation}` (gitignored except manifests) · `scripts/` · `pbip/` (Power BI project) · `docs/` · `registers/` · `reports/` (generated checks).
Repo: GitHub `batestguy/powerbi-naija-2027-elections-gap` (public).
Scope: state-level core (37 units); LGA layer optional (Mundx, needs permission). See `docs/PLAN.md`.
Delivery: desktop file (PBIP in git, `.pbix` as a GitHub Release asset) + walkthrough video. No Power BI service publishing.

## Environment and remaining blanks
- Pinned environment: CPython 3.12.13 in project `.venv`, managed by uv (`uv sync`, `uv run`). Never use the system 3.14 or conda. Details: `docs/environment.md`.
- Commands: see `## Commands` below. PBIR validate: Phase 3.
- Where large data lives (>5 MB goes to Hugging Face Datasets or LFS, not git).

## Commands
Run from the repo root, in the pinned environment:
- `uv run python -I scripts/pull_sources.py [--skip-mundx] [--only src1,src2]` — raw snapshots to `data/raw/<source>/<date>/` with manifests. Vanguard is a manual snapshot (not fetched).
- `uv run python -I scripts/build_staging.py` — staging tables, five-copy reconciliation (`reports/result_reconciliation.csv`), `reports/unmatched_keys.csv`.
- `uv run python -I scripts/build_geometry.py` — TopoJSON for the Shape Map + `pbip/assets/geometry_manifest.json`.
- `uv run python -I scripts/validate_phase2.py` — Phase 2 gate → `reports/phase2_validation.json`, `reports/mundx_state_accuracy.csv`; exits 1 on a gate failure.
- `uv run python -I scripts/build_pbip.py [--data-folder <abs path to data/staging>]` — writes the TMDL model + PBIR visuals into `pbip/NaijaElectionsGap.*`. Then `powerbi-report-author validate pbip/NaijaElectionsGap.Report`.
- Desktop (Store edition): set `PBI_DESKTOP_PATH` to `C:\Program Files\WindowsApps\Microsoft.MicrosoftPowerBIDesktop_<version>_x64__8wekyb3d8bbwe\bin\pbidesktop.exe`, then `powerbi-desktop open <.pbip>`; after opening, refresh data with `scripts/pbi_engine.ps1 -Action Refresh` (never ask the user to click). `powerbi-desktop reload --pid <pid>` only when `status` shows `hasUnsavedChanges: false`; save in Desktop first, then re-run the generator (a Desktop save overwrites generated report files).
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/pbi_reopen.ps1 [-Force]` — close and reopen Desktop on the PBIP and refresh data (needed after model/TMDL changes; `-Force` discards unsaved Desktop state).
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/pbi_engine.ps1 -Action Refresh|Query|Info [-Dax "..."]` — refresh or query the live model through Desktop's local engine.
- `uv run python -I scripts/validate_phase3.py [--no-refresh]` — Phase 3 model checks against the live model → `reports/phase3_validation.json`.
- `uv run python -I scripts/validate_phase4.py` — scenario engine vs an independent re-implementation of `docs/methodology.md` → `reports/phase4_validation.json`.
- Report pages live in `scripts/pbip_pages.py` (called by `build_pbip.py`). After report-only changes: `powerbi-desktop reload --pid <pid>`; after model changes: `scripts/pbi_reopen.ps1 -Force`. Screenshots: `powerbi-desktop screenshot-all --pid <pid> --output-dir reports/screenshots/phase5`. Test variants: `PBIP_SLIDER_PROBE=1` (sliders preset +5 national / −3 SE) and `PBIP_CANDIDATE="Peter Obi"`; always rebuild without them before committing.

