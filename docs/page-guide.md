# Page guide (Phase 5)

The report is `pbip/NaijaElectionsGap.pbip` (Power BI Desktop). Built by `scripts/build_pbip.py` (model) and
`scripts/pbip_pages.py` (pages). Screenshots of every page: `reports/screenshots/phase5/`.

## The core task (brief's exit test)

1. Pick a candidate in the **Candidate** box (top right of every page; the choice carries across pages).
2. Go to **Scenario simulator** and move a slider (or type a value into its box).
3. Read **Secured /37** and the **Verdict**. The box **Settings the engine is using** repeats every slider value the
   numbers are based on.

## Pages

| Page | Question it answers | What is on it |
|---|---|---|
| Candidate overview | How did this candidate do in 2023? | Votes, share, national rank, units at 25%+ (of 37), units with data; all 37 units ranked as columns with a fixed dashed 25% line; zone table; colour key, how units are counted, close calls and data gaps |
| Path to 24 | Which units carry the 25% test? | Units at 25%+, needed, still needed, clears the rule, tipping-point unit and how far it is from 25%; ranked columns coloured Secured / Within reach / Out of reach; table with label, share, points to 25% and votes to switch for every unit |
| Spread map | Where is the 25% hold strong or fragile? | State-boundary map and equal-size tile map, both coloured by points above (blue) or below (orange) 25% on a fixed scale; counts by label |
| Scenario simulator | What if 2027 differs? | Supporter turnout, national swing, six zone swings, rule (24 or 25); verdict; most votes, leading rival, tipping point; secured, still needed, national share, capped units; tile map; settings in force; assumptions and how to read the verdict |
| How to read this | What does this claim, and not claim? | The rule, what the numbers are, what the simulator assumes, what it does not claim |
| Data sources | Where does each number come from? | Each source with licence, access date and limitation |
| Model check (hidden) | QA only | The Phase 3 check page; hidden in reading view |

Overview, Path and Map show the 2023 baseline (sliders live only on the Simulator page, so those pages are at neutral).

## Design rules applied

- **25% is fixed:** a dashed reference line at 0.25 on both column charts; the map scale is fixed at −25 / 0 / +25 points
  (white exactly at 25%), never stretched to the data.
- **Colour is never the only signal:** blue / vermillion / grey (Okabe-Ito, colour-blind safe, no red/green). The Path
  table and the Spread map table spell out Secured / Within reach / Out of reach; chart and map tooltips carry the
  label and share (tooltips not yet seen rendered). On the Path chart the tipping-point unit is black and the table
  has a Rank column.
- **Clicks do not cross-filter:** only the slicers filter; clicking a column, row or tile cannot change the headline cards.
- **Assumptions on the page:** the Simulator shows its assumptions and a live "settings the engine is using" box;
  every page subtitle says the baseline is reconciled, not INEC's own state sheet.
- **Accessibility:** every visual has alt text and a tab order (reading order: title → candidate → content → notes);
  text is 8–18 pt in dark grey/black on a light background. Chart colours are at least 3:1 against white (blue 5.19,
  vermillion 3.87, grey 4.54). Keyboard, screen-reader and axe checks are **not yet run** (Phase 6).

## Checks done (`registers/qa-log.md`)

- PBIR validation: 0 errors, 0 warnings.
- Every page rendered in Desktop and reviewed from screenshots (Tinubu, Obi, Atiku in session; the kept set is Tinubu's).
  The review fixes of 2026-11-14 are rendered in the kept set (Tinubu).
- **Slider → engine → page:** a test build with national swing +5 and South East −3 showed those values in the engine box
  and changed every figure; all nine figures equal the independent reference
  (`reports/screenshots/phase5_probe/simulator_national_plus5_SE_minus3.png`).

## Known limits

- When a slider is pre-set to a non-zero value in the file, the slider handle was not confirmed to sit at that value
  (the number box was correct). In normal use sliders start at 0 and are moved by the reader.
- Not yet tested with a non-specialist reader (the brief's exit test needs a person).
- Overview notes on close calls and Kano are written for Tinubu's figures; they stay true for other candidates but are
  not candidate-specific.
