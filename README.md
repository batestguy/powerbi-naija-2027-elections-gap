# powerbi-naija-2027-elections-gap

A Power BI scenario simulator for Nigeria's 2027 presidential election. It starts from a
candidate's 2023 results across the 774 local government areas (LGAs), lets you move swing and
turnout sliders, and shows how many states the candidate would reach 25% in — the gap between
that count and the constitutional spread requirement.

**Status:** planning. See [`docs/PLAN.md`](docs/PLAN.md) for phases and exit checks.

## What this is not
A scenario and communication tool, not an electoral authority. The 2023 baseline is a
**four-party rollup, not official INEC results**. Scenario outputs are assumptions made visible,
not forecasts.

## Report pages
Candidate overview · Path to 24 · Spread map · What-if simulator (with a "Use the coalition" switch, Off by default) ·
Merge two parties · Head to head · How to read this · Technical notes · Data sources. Details: [`docs/page-guide.md`](docs/page-guide.md).
The two coalition pages recombine 2023 votes (lead + the share of a partner's voters who follow; the rest stay home);
only "NDC (Obi + Kwankwaso)" is a real ticket, every other pairing is a what-if. Method: [`docs/methodology.md`](docs/methodology.md).

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
Photos and portraits: Wikimedia Commons, free licences only (CC0, public domain, CC BY, CC BY-SA); credits on the report's Data sources page and in `registers/sources.md`.
Party logos are trademarks of their respective parties, shown for identification only; no endorsement implied. Build with `PBIP_NO_LOGOS=1` to show abbreviation badges instead.
