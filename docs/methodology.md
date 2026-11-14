# Scenario methodology (Phase 4)

One page, written before the build. Anyone should be able to reproduce every scenario number from this note and the
2023 baseline (`data/staging/fact_result_2023.csv`, `fact_turnout_2023.csv`) without opening the model.
`scripts/validate_phase4.py` re-implements this note and compares it with the model (same author — it mainly catches
slips in the model's formulas). The independence evidence is a blind reproduction by a reviewer who used only this
note and the data: 13 settings of their own choosing, all identical to the model (`registers/qa-log.md`, 2026-11-14).
That reproduction predates the "Rivals and the verdict" section below; rivals are covered by `validate_phase4.py`
(same author) and by spot checks in the Phase 5 review (3 settings, all matching).

## What the simulator does

For one selected candidate (APC, PDP, LP or NNPP) it applies three kinds of assumption to the 2023 result in each of the
37 units (36 states + FCT), then counts the units where the candidate has at least 25% of valid votes.

It is a **what-if tool, not a forecast**. It does not estimate how likely any scenario is.

## Inputs (sliders)

| Input | Symbol | Range | Neutral |
|---|---|---|---|
| Supporter turnout: how much more (or less) the candidate's 2023 voters turn out than everyone else | `t` | −50% to +50%, step 1 | 0 |
| National swing to the candidate, in percentage points of the vote | `S` | −20 to +20, step 0.5 | 0 |
| Zone swing, one slider per geopolitical zone (NC, NE, NW, SE, SS, SW), added to the national swing | `Z_zone` | −20 to +20, step 0.5 | 0 |
| Rule: number of units needed | `N` | 24 (two-thirds of the 36 states; the FCT counts as one of the 37 units) or 25 (two-thirds of 37, rounded up) | 24 |

The FCT belongs to the North Central zone for the zone slider (`data/staging/dim_state.csv`).
Sliders are shown in percent and points; in the formulas below `t` is a fraction (slider ÷ 100).
**National and zone swing add up:** a unit can move by up to ±40 points in total (±20 national plus ±20 zone).

## Calculation, per unit `s`

Baseline: candidate votes `v`, total valid votes `V` (the reconciled 2023 figures; `V` = the five party columns of
`fact_result_2023.csv` summed, which equals `total_valid` in `fact_turnout_2023.csv` for every unit; see `docs/data-profile.md`).

1. **Supporter turnout.** The candidate's votes change by `t`; everyone else's votes stay the same.
   `v1 = v × (1 + t)`, `V1 = V + v × t`, `p1 = v1 / V1`.
2. **Swing.** Add the national and zone swing, in share points, then keep the result between 0 and 1.
   `p2 = min(1, max(0, p1 + (S + Z_zone(s)) / 100))`.
   The swing moves vote share between the candidate and everyone else; it does not change `V1`.
3. **Scenario votes** (shown, never used for the test): `v2 = p2 × V1`.

Order matters: turnout first, then swing. At neutral settings (`t = 0`, all swings 0), `p2 = v / V` exactly, so the
simulator equals the 2023 baseline.

## The 25% test and the labels

| Label | Rule |
|---|---|
| **Secured** | `p2 ≥ 0.25` |
| **Within reach** | `0.20 ≤ p2 < 0.25` (up to 5 points short) |
| **Out of reach** | `p2 < 0.20` |

- **Units secured** = number of units labelled Secured. **Clears the rule** when units secured ≥ `N`.
- **Units still needed** = `max(0, N − units secured)`.
- **Tipping-point unit** = rank all 37 units by `p2`, highest first (ties broken by P-code, alphabetically); the unit
  in position `N`. It is the weakest unit the candidate would need. Its gap to 25% (`0.25 − p2`, in points) is how
  far the whole scenario is from clearing the rule.
- **Points needed** in a unit = `max(0, 0.25 − p2) × 100`. **Votes needed** = `max(0, 0.25 × V1 − v2)`, rounded up:
  votes that would have to **switch** to the candidate from others, with the unit's total held fixed — not new votes added.
  Both are per unit: blank when the page shows the whole country.
- **Units at a cap** = units whose share before capping (`p1 + swing`) is ≤ 0 or ≥ 1. Shown, so an extreme swing is
  never silently flattened.
- The tipping-point unit is blank when fewer than `N` units have a share (cannot happen with the current data: all 37 do).

**Filters on a page.** The rule is national. *Clears the rule*, *units still needed* and the *tipping-point unit* always
use all 37 units, whatever zone or state is selected on the page. The unit counts (*secured*, *within reach*, *out of
reach*, *at a cap*) follow the page's filter, so they can answer "how many units does the candidate hold in the North
West?". **Exactly 25%:** shares are compared as decimals here (the baseline count uses whole numbers). A search of every
reachable slider combination (2,406,628 in exact fractions, `reports/phase4_validation.json`) found no unit landing
exactly on 25% or 20%, so the two methods agree everywhere.

## Rivals and the verdict (added 2026-11-14, user decision)

The verdict needs the other candidates' votes. In each unit, **every other candidate gains or loses in proportion to
their 2023 share**: their votes are multiplied by `(1 − p2) / (1 − p1)` (0 if `p1 = 1`). Their 2023 votes already sit
inside `V1` after step 1, so this keeps each unit's total at `V1`.

- **National votes** = sum over units of `v2` (the candidate) or of `2023 votes × (1 − p2) / (1 − p1)` (each rival).
- **Leading rival** = the other main candidate (APC, PDP, LP, NNPP) with the most national votes (ties by party code).
  OTHERS (14 minor candidates combined) is not a candidate and is never the leading rival.
- **Has most votes** = candidate's national votes > leading rival's (equal → "Tied").
- **Verdict** (s.134 reading: most votes **and** 25% in at least `N` units):
  - most votes and clears the rule → **Outright win**;
  - most votes but does not clear the rule → **No outright winner: run-off**;
  - tied on votes → **Tie on votes: no outright winner**;
  - not most votes, and the leading rival has 25% in at least `N` units → **Loses: rival wins outright**;
  - otherwise → **No outright winner: run-off (rival has most votes)**. Who would contest a run-off is not modelled.

At neutral settings this reproduces 2023: APC 8,794,726, leading rival PDP 6,984,520, outright win
(`reports/phase4_validation.json`).

## Assumptions and their limits (shown on the report pages, not only here)

1. **Uniform swing within a zone.** Every unit in a zone moves by the same number of points. Real swings vary by
   state and are larger where races are competitive. This is an approximation, stated as such.
2. **Additive points.** A +2 swing counts the same in a unit where the candidate had 2% as in one where they had 60%.
   Near 0% this can be unrealistic; caps are counted and shown.
3. **Supporter turnout is relative.** It changes only the candidate's own 2023 voters. Equal turnout changes for
   everyone would leave every share — and the 25% count — unchanged.
4. **No new candidates, no merged parties, no boundary changes.** The 2023 field and 37 units are fixed.
5. **The baseline carries the data gaps** in `docs/data-profile.md`: valid votes are 4,858 above INEC's national total
   (unlocated, in the OTHERS column), Kano APC is a constraint-based choice, and APC's 29 rests on 96 votes in
   Adamawa. Small swings near 25% are within that uncertainty.
6. **The rule reading** (24 of 37, FCT counted as a unit) is our reading of s.134; 25 of 37 is offered as a
   sensitivity (decision log 2026-11-13; open question 1).
7. **2027 registered voters are not used.** Shares do not depend on the size of the register.
8. **Rivals move together.** When the candidate gains, every rival loses in proportion to its size in that unit;
   real swings often come mostly from one rival. The verdict inherits this assumption.

## Tests the build must pass (`scripts/validate_phase4.py`)

- Neutral settings: every unit's `p2` equals the baseline share; counts equal 29 / 21 / 16 / 1.
- Every slider at its minimum and at its maximum, alone and all together: no blank where data exists, no error,
  `0 ≤ p2 ≤ 1`, counts between 0 and 37.
- Model equals this note for every unit and every count across 25 settings (incl. odd values), for N = 24 and 25.
- With a zone filter on the page, the national measures stay national.
- More national swing never lowers units secured.
