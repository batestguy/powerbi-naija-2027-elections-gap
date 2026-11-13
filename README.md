# powerbi-elections-gap

A Power BI scenario simulator for Nigeria's 2027 presidential election. It starts from a
candidate's 2023 results across the 774 local government areas (LGAs), lets you move swing and
turnout sliders, and shows how many states the candidate would reach 25% in — the gap between
that count and the constitutional spread requirement.

**Status:** planning. See [`docs/PLAN.md`](docs/PLAN.md) for phases and exit checks.

## What this is not
A scenario and communication tool, not an electoral authority. The 2023 baseline is a
**four-party rollup, not official INEC results**. Scenario outputs are assumptions made visible,
not forecasts.

## Layout
```
data/        raw / staging / presentation — not committed (see .gitignore); manifests are
scripts/     pull, profile and validate scripts
pbip/        Power BI project (PBIP/PBIR)
docs/        plan, environment, model, methodology, page guide
registers/   decision log, open questions, risks, sources, QA log
reports/     generated checks (e.g. unmatched LGA keys)
```

## Licence
Code: to be decided. Data: each source keeps its own terms — see `registers/sources.md`.
