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
- **Votes to spare** in a unit (added 2026-11-14) = `max(0, v2 − 0.25 × V1)`, rounded down: votes that could switch
  **from** the candidate to others, unit total fixed, while the candidate keeps at least 25%. (The model adds 10⁻⁶
  before rounding down only to absorb floating-point error on whole-number margins.)
- **Plain-words sentences (2026-11-14, user decision: gaps in people, not only points).** *Deciding state sentence*:
  the tipping-point unit, its gap in points (one decimal), and — if the candidate is at or above 25% there — its votes
  to spare, otherwise its votes needed. *Closest calls* (2023 Overview, baseline only, whole-number test): the unit won
  with the smallest `4v − V ≥ 0` (margin `(4v − V) / 4`, rounded down) and the unit missed with the smallest
  `V − 4v > 0` (votes needed `(V − 4v) / 4`, rounded up); ties by P-code. `scripts/validate_phase6.py` recomputes both
  sentences, and votes needed / to spare for every unit, in exact fractions from the staging CSVs.
- **Units at a cap** = units whose share before capping (`p1 + swing`) is ≤ 0 or ≥ 1. Shown, so an extreme swing is
  never silently flattened.
- The tipping-point unit is blank when fewer than `N` units have a share (cannot happen with the current data: all 37 do).

**Filters on a page.** The rule is national. *Clears the rule*, *units still needed* and the *tipping-point unit* always
use all 37 units, whatever zone or state is selected on the page. The unit counts (*secured*, *within reach*, *out of
reach*, *at a cap*) follow the page's filter, so they can answer "how many units does the candidate hold in the North
West?". **Exactly 25%:** shares are compared as decimals here (the baseline count uses whole numbers). A search of every
reachable slider combination (2,406,628 in exact fractions, `reports/phase4_validation.json`) found no unit landing
exactly on 25% or 20%, so the two methods agree everywhere. **Margin (2026-11-18):** with the coalition switch On,
6 reachable settings do land exactly on 25% or 20%, and one showed the wrong label (a true 20% stored as just under
it). The model therefore treats a share within 10⁻¹² below a line as on it (`≥ 0.25 − 10⁻¹²`, `≥ 0.20 − 10⁻¹²`; a
secured unit always has 0 votes needed). The smallest non-zero distance between any reachable share and a line is
2.06 × 10⁻¹⁰, more than 100 times the margin, so the margin changes only shares that are exactly on a line
(`validate_phase4.py --part boundary`). **Rivals (2026-11-19):** rival "25% in a state" counts compare without a
margin, and a second exact search shows they need none: a rival's share after the rescale is `R (1 − p2) / (W − C)`
(since `V1 (1 − p1) = W − C`); over every reachable setting (switch Off and On, every pairing, follow rate, Side B,
turnout and swing step) no rival lands exactly on 25%, and the closest is 3.1 × 10⁻¹¹ from it, far above
floating-point error (about 10⁻¹⁵). A 10⁻¹² margin would have left only 31 times headroom, so none is used.

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

## Coalitions (added 2026-11-16, user decisions)

Written before the build, like the sections above (decision log 2026-11-14 and 2026-11-16; evidence in
`docs/coalition-research.md`). The sections above are unchanged: with the coalition switch **Off** (the default) every
simulator number is exactly what those sections describe. Assumption 4 above ("no merged parties") holds everywhere
except on the two coalition pages and in the simulator with the switch **On**.

### Sides and inputs

- A **side** is either one of the four 2023 main candidates' parties (APC, PDP, LP, NNPP) or a **coalition** of exactly
  two of them: a **lead** `L` (top of the ticket) and a **partner** `P`.
- **Side A** is always a coalition (lead + partner). **Side B** (Head to head page and simulator) is one party alone
  or another two-party coalition. Each of the four parties may be used at most once across both sides.
- **Follow rate** `F` (slider, 0–100%, step 5, default 100%): the percentage of the partner's 2023 voters who vote for
  the coalition. One per side that has a partner (`F_A`, `F_B`). `f = F / 100`.
- **Non-followers stay home**: they leave the valid total; none go to another party.
- OTHERS (14 minor candidates) and any main party not used on either side keep their 2023 votes.
- The coalition's name comes from `data/reference/coalition_names.csv` (one row per ordered pair, with its source).
  Only LP lead + NNPP partner has a real name: "NDC (Obi + Kwankwaso)", the joint NDC ticket since 2026-05-31. Every
  other pairing is hypothetical and called "X + Y (what-if)".

### Votes after recombination, per state `s`

With `v_X` = party X's 2023 votes and `V` = 2023 valid votes in the state:

- Side A votes: `c = v_LA + f_A × v_PA`.
- Side B votes: `b = v_LB` (+ `f_B × v_PB` if Side B has a partner).
- Valid votes on the **Merge two parties** page (Side A only): `V'_A = V − (1 − f_A) × v_PA`.
- Valid votes on the **Head to head** page and in the simulator: `V' = V − (1 − f_A) × v_PA − (1 − f_B) × v_PB`
  (the last term only if Side B has a partner).
- Shares: `c / V'_A` (Merge page), `c / V'` and `b / V'` (Head to head).

At `F_A = 100%`: `c = v_LA + v_PA` and `V'_A = V`. At `F_A = 0`: `c = v_LA` and `V'_A = V − v_PA`.

### Exact tests on the coalition pages (no floating point)

Because `F` is a whole percentage, multiplying by 100 makes every quantity a whole number:
`C = 100 v_LA + F_A v_PA`, `B = 100 v_LB + F_B v_PB`, `W = 100 V − (100 − F_A) v_PA − (100 − F_B) v_PB`
(`W_A` = the same without the Side B term).

- **Secured** (a quarter or more): `4 C ≥ W` (Merge page: `4 C ≥ W_A`); **Within reach**: `5 C ≥ W` but not secured;
  **Out of reach** otherwise. Side B and unused parties: `4 B ≥ W`, `4 × 100 v_X ≥ W`.
- **Who leads a state** (Head to head): the largest of `C`, `B` and `100 v_X` for each main party not used on either side
  (OTHERS is never a leader). If the largest value is shared, the state is a **tie**.
- **National**: votes and valid totals are sums over the 37 states (the formulas are linear, so national `C` = 100 ×
  national `v_LA` + `F_A` × national `v_PA`). The national comparison uses the same whole numbers.
- `scripts/validate_phase4.py` reproduces all of this in exact fractions (Python `fractions`) from the staging CSVs.

### Verdict on the coalition pages

Same s.134 reading as "Rivals and the verdict", with **Side A as the candidate**. Rival entities = Side B (one entity,
identified by its lead's code; shown as "lead+partner" if it has a partner, e.g. "PDP+APC") and each main party not used
on either side. OTHERS is never a rival winner. Leading rival = the rival entity with the most national votes (ties by
code). `N` = the rule slider's value (24 when the page has no rule slider, as on both coalition pages).
Outright win / run-off / tie / loses — the same five outcomes and the same tests as above, using whole-number counts
of states at 25%+ for Side A and for the leading rival. The Merge page has no verdict (it compares the coalition with
its lead alone).

### Simulator with the coalition switch On

Replace the candidate's 2023 votes `v` by `c` and `V` by `V'` (both sides, as on the Head to head page) in steps 1–3:

1. `v1 = c × (1 + t)`, `V1 = V' + c × t`, `p1 = v1 / V1` — turnout applies to the coalition's recombined voters.
2. `p2 = min(1, max(0, p1 + (S + Z_zone(s)) / 100))`.
3. `v2 = p2 × V1`.

Labels, counts, caps, tipping point, votes needed / to spare and the sentences then follow the sections above
unchanged (decimal comparison with the 10⁻¹² margin above; the exact search of every reachable setting for boundary
hits and the margin proof are in `validate_phase4.py --part boundary`). **Rivals**: Side B as one entity with votes `b`, and each unused main party with its
2023 votes, all multiplied by `(1 − p2) / (1 − p1)` (0 if `p1 = 1`); OTHERS scales the same way but is never a rival
winner. Leading rival = the rival entity with the most national votes, ties by code. Verdict as above. The candidate
picked at the top of the page is ignored while the switch is On.

**Invalid selections** (no lead or partner chosen; lead = partner; a party used on both sides or twice; Side B's
partner = Side B's lead) give **blank figures** and a plain-words message saying what to change — never a number.

### Assumptions (stated on the pages in plain words)

1. The follow rate is an assumption, not a measurement. No published rate exists; the 2011→2015 APC merger only loosely
   suggests that most partner voters followed (`docs/coalition-research.md`), and cannot give a number.
2. Partner voters who do not follow stay home; none go to a rival.
3. In the simulator, the coalition's partner voters are assumed to respond to the sliders exactly like the lead's.
4. These are 2023 votes recombined, not a 2027 forecast: 2023 votes for parties whose candidates have since moved are
   attached to the 2023 party, not to anyone's 2027 ticket.
5. "NDC (Obi + Kwankwaso)" is a real ticket (NDC release 2026-05-31; ThisDay INEC list ~2026-09-13); every other pairing
   is hypothetical.
6. Side B as one entity: when Side B is a coalition, its two parts move together under the simulator's rival rule.
