"""Phase 3 thin slice. Writes the semantic model (TMDL) and report visuals (PBIR) for pbip/NaijaElectionsGap.

The report shell (pbip/NaijaElectionsGap.pbip, .Report/definition.pbir, version.json, base theme) was created once
with `powerbi-report-author scaffold`; this script owns everything else and is safe to re-run.

The model imports data/staging CSVs (local only) through one Power Query parameter, DataFolder. A stranger
re-runs the Phase 2 scripts, then sets DataFolder (Transform data > Edit parameters) to their own data/staging path.

Thin slice = baseline only: one card (APC national votes; must read 8,794,726) + Shape Map on the state
TopoJSON + Shape Map on the equal-size tile TopoJSON (both colour = APC share of valid votes).

Usage (repo root):  uv run python -I scripts/build_pbip.py [--data-folder D:\\path\\to\\data\\staging]
"""
import hashlib, json, shutil, sys, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PBIP = ROOT / "pbip"
NAME = "NaijaElectionsGap"
SM, RPT = PBIP / f"{NAME}.SemanticModel", PBIP / f"{NAME}.Report"
DATA_FOLDER = (sys.argv[sys.argv.index("--data-folder") + 1] if "--data-folder" in sys.argv
               else str(ROOT / "data" / "staging"))
VC_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json"


def stable_id(*parts, n=20):
    """Deterministic ids so re-runs produce identical files (clean git diffs)."""
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:n]


def stable_uuid(*parts):
    return str(uuid.UUID(hashlib.md5("|".join(parts).encode()).hexdigest()))


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def wjson(path, obj):
    write(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


# ---------------- semantic model (TMDL) ----------------

TABLES = {
    # table: (csv, [(column, tmdl dataType, M type, summarizeBy)])
    # Grain: dim_zone = zone (6); dim_state = state (37); dim_party = candidate (5, incl. OTHERS);
    # fact_result_2023 = state x party (185, immutable baseline); fact_turnout_2023 = state (37).
    "dim_zone": ("dim_zone.csv", [("zone_code", "string", "type text", "none"),
                                  ("zone", "string", "type text", "none"),
                                  ("state_count", "int64", "Int64.Type", "none")]),
    "dim_party": ("dim_party.csv", [("party", "string", "type text", "none"),
                                    ("candidate", "string", "type text", "none"),
                                    ("party_name", "string", "type text", "none"),
                                    ("sort_order", "int64", "Int64.Type", "none"),
                                    ("colour_hex", "string", "type text", "none")]),
    "dim_state": ("dim_state.csv", [("state_pcode", "string", "type text", "none"),
                                    ("state_name", "string", "type text", "none"),
                                    ("zone", "string", "type text", "none"),
                                    ("zone_code", "string", "type text", "none"),
                                    ("is_fct", "int64", "Int64.Type", "none"),
                                    # display only (2026-11-14): ISO 3166-2:NG code and equal-size tile position
                                    ("state_code", "string", "type text", "none"),
                                    ("tile_row", "int64", "Int64.Type", "none"),
                                    ("tile_col", "int64", "Int64.Type", "none")]),
    "fact_result_2023": ("fact_result_2023.csv", [("state_pcode", "string", "type text", "none"),
                                                  ("party", "string", "type text", "none"),
                                                  ("candidate", "string", "type text", "none"),
                                                  ("votes", "int64", "Int64.Type", "sum"),
                                                  ("votes_rule", "string", "type text", "none")]),
    "fact_turnout_2023": ("fact_turnout_2023.csv", [("state_pcode", "string", "type text", "none"),
                                                    ("registered", "int64", "Int64.Type", "sum"),
                                                    ("total_valid", "int64", "Int64.Type", "sum"),
                                                    ("turnout_pct_reported", "double", "type number", "none")]),
}
SORT_BY = {("dim_party", "party"): "sort_order", ("dim_party", "candidate"): "sort_order"}
# dim_party is deliberately DISCONNECTED: a candidate selection must never filter the valid-vote denominator
# (fact_turnout_2023) or other candidates' rows; measures read the selection with SELECTEDVALUE / TREATAS.
SEL = "SELECTEDVALUE ( dim_party[party] )"
MEASURES: dict = {
    "fact_result_2023": [
        ("Total votes", "SUM ( fact_result_2023[votes] )", "#,0"),
        ("Valid votes", "SUM ( fact_turnout_2023[total_valid] )", "#,0"),
        ("APC votes", 'CALCULATE ( [Total votes], fact_result_2023[party] = "APC" )', "#,0"),
        ("APC share", "DIVIDE ( [APC votes], [Valid votes] )", "0.0%"),
        ("Candidate votes", f"VAR p = {SEL} RETURN IF ( NOT ISBLANK ( p ), "
                            "CALCULATE ( [Total votes], fact_result_2023[party] = p ) )", "#,0"),
        ("Candidate share", "DIVIDE ( [Candidate votes], [Valid votes] )", "0.00%"),
        # Constitutional test per unit (36 states + FCT, 37 units - decision log 2026-11-13): at least one-quarter of
        # valid votes, tested in whole numbers (4 x votes >= valid) so no floating-point rounding at the boundary.
        # Only units where the share is computable are counted; see 'States with a computable share'. Blank for OTHERS.
        ("States at 25% or more", f"VAR p = {SEL} RETURN IF ( NOT ISBLANK ( p ) && p <> \"OTHERS\", "
                                  "COUNTROWS ( FILTER ( VALUES ( dim_state[state_pcode] ), "
                                  "NOT ISBLANK ( [Candidate votes] ) && NOT ISBLANK ( [Valid votes] ) && [Valid votes] > 0 "
                                  "&& 4 * [Candidate votes] >= [Valid votes] ) ) + 0 )", "0"),
        # Companion: units where the test could be applied at all. Must be shown next to the count, so a missing state
        # is visible instead of silently counting as 'below 25%'.
        ("States with a computable share", f"VAR p = {SEL} RETURN IF ( NOT ISBLANK ( p ) && p <> \"OTHERS\", "
                                           "COUNTROWS ( FILTER ( VALUES ( dim_state[state_pcode] ), "
                                           "NOT ISBLANK ( [Candidate votes] ) && NOT ISBLANK ( [Valid votes] ) "
                                           "&& [Valid votes] > 0 ) ) + 0 )", "0"),
    ]
}
RELATIONSHIPS = [("fact_result_2023", "state_pcode", "dim_state", "state_pcode"),
                 ("fact_turnout_2023", "state_pcode", "dim_state", "state_pcode"),
                 ("dim_state", "zone_code", "dim_zone", "zone_code")]

# ---- Phase 4: scenario engine (docs/methodology.md). What-If parameters are disconnected calculated tables;
# all scenario logic lives in measures of the 'scenario' table. Baseline facts are never touched.
ZONES = ["NC", "NE", "NW", "SE", "SS", "SW"]
ZONE_NAMES = {"NC": "North Central and Abuja", "NE": "North East", "NW": "North West", "SE": "South East",
              "SS": "South South", "SW": "South West"}
PARAMS = {  # table: (DAX series, default, format, dataType)
    "param_turnout": ("GENERATESERIES ( -50, 50, 1 )", 0, "0", "int64"),
    "param_swing_national": ("GENERATESERIES ( -20, 20, 0.5 )", 0, "0.0", "double"),
    **{f"param_swing_{z}": ("GENERATESERIES ( -20, 20, 0.5 )", 0, "0.0", "double") for z in ZONES},
    "param_rule": ("GENERATESERIES ( 24, 25, 1 )", 24, "0", "int64"),
    # coalition follow rates (user decision 2026-11-16): % of a partner's 2023 voters who follow, default 100
    "param_follow_a": ("GENERATESERIES ( 0, 100, 5 )", 100, "0", "int64"),
    "param_follow_b": ("GENERATESERIES ( 0, 100, 5 )", 100, "0", "int64"),
}
CALC_TABLES = {**{t: (src, "Value", dt, fmt, False) for t, (src, _, fmt, dt) in PARAMS.items()},
               "scenario": ('{ "Scenario measures - see docs/methodology.md" }', "Value", "string", None, True)}
OK = f'VAR c = {SEL} RETURN NOT ISBLANK ( c ) && c <> "OTHERS"'   # a single real candidate is selected
ON = "[Coalition switch on]"   # simulator coalition switch (default Off = today's engine exactly)
SHARE = "[Scenario share]"
NATIONAL = "REMOVEFILTERS ( dim_state ), REMOVEFILTERS ( dim_zone )"   # all 37 units, whatever the page filters
# the three other main candidates, each with national scenario votes = sum over units of 2023 votes x Rival scale
RIVALS = ('VAR c = SELECTEDVALUE ( dim_party[party] ) '
          'VAR tab = ADDCOLUMNS ( FILTER ( { "APC", "PDP", "LP", "NNPP" }, [Value] <> c ), "@v", VAR r = [Value] RETURN '
          'CALCULATE ( SUMX ( VALUES ( dim_state[state_pcode] ), CALCULATE ( SUM ( fact_result_2023[votes] ), '
          'fact_result_2023[party] = r ) * [Rival scale] ), ' + NATIONAL + ' ) ) ')


def VOTES(x):
    """2023 votes of party code x (a DAX expression) in the current state filter; blank for "NONE"."""
    return f"CALCULATE ( SUM ( fact_result_2023[votes] ), fact_result_2023[party] = {x} )"


SIDES = ("VAR al = [Side A lead] VAR ap = [Side A partner] VAR bl = [Side B lead] VAR bp = [Side B partner] ")
# Switch On: rival entities = Side B (one entity, identified by its lead's code, partner's followers added) and every
# main party on neither side, each scaled by the rival rule (docs/methodology.md "Coalitions"). Computed in ONE pass
# over a per-state table (a nested-measure form, like RIVALS, took ~3 s per call and ~20 s for the verdict). Steps 1-2 repeated inline with the same operation order as [Engine votes],
# [Engine valid votes], [Scenario share uncapped] and [Rival scale]. With two sides using 3 or 4 of the 4 main parties,
# at most one main party (uu) is on neither side, so the rival entities are Side B and uu.
ON_TAB = (SIDES + "VAR fa = [Follow A] VAR fb = [Follow B] VAR t = [Supporter turnout] VAR sw = [National swing] "
          + "".join(f"VAR z{z} = SELECTEDVALUE ( param_swing_{z}[Value], 0 ) " for z in ZONES)
          + 'VAR uu = CONCATENATEX ( FILTER ( { "APC", "PDP", "LP", "NNPP" }, [Value] <> al && [Value] <> ap && '
          '[Value] <> bl && [Value] <> bp ), [Value] ) '
          "VAR tb = CALCULATETABLE ( ADDCOLUMNS ( SUMMARIZE ( dim_state, dim_state[state_pcode], dim_state[zone_code] ), "
          f'"@cv", ( 100 * {VOTES("al")} + fa * {VOTES("ap")} + 0 ) / 100, '
          f'"@tv", ( 100 * [Valid votes] - ( 100 - fa ) * {VOTES("ap")} + 0 - IF ( bp <> "NONE", ( 100 - fb ) * '
          f'{VOTES("bp")}, 0 ) ) / 100, '
          f'"@vb", {VOTES("bl")} + IF ( bp <> "NONE", fb / 100 * {VOTES("bp")} ), '
          f'"@vu", IF ( uu <> "", {VOTES("uu")} ), '
          '"@z", SWITCH ( dim_state[zone_code], ' + ", ".join(f'"{z}", z{z}' for z in ZONES) + " ) ), "
          + NATIONAL + " ) "
          'VAR t2 = ADDCOLUMNS ( tb, "@V1", [@tv] + [@cv] * t, "@p1", DIVIDE ( [@cv] * ( 1 + t ), [@tv] + [@cv] * t ) ) '
          'VAR t3 = ADDCOLUMNS ( t2, "@p2", MIN ( 1, MAX ( 0, [@p1] + ( sw + [@z] ) / 100 ) ) ) '
          'VAR t4 = ADDCOLUMNS ( t3, "@sc", IF ( [@p1] < 1, DIVIDE ( 1 - [@p2], 1 - [@p1] ), 0 ) ) '
          'VAR nb = SUMX ( t4, [@vb] * [@sc] ) VAR nu = IF ( uu <> "", SUMX ( t4, [@vu] * [@sc] ) ) '
          'VAR rx = IF ( uu = "" || nb > nu || ( nb = nu && bl < uu ), bl, uu ) ')
MEASURES["scenario"] = [
    # inputs
    ("Supporter turnout", "SELECTEDVALUE ( param_turnout[Value], 0 ) / 100", "0%"),
    ("National swing", "SELECTEDVALUE ( param_swing_national[Value], 0 )", "+0.0;-0.0;0.0"),
    ("Zone swing", "SWITCH ( SELECTEDVALUE ( dim_state[zone_code] ), "
                   + ", ".join(f'"{z}", SELECTEDVALUE ( param_swing_{z}[Value], 0 )' for z in ZONES) + " )",
     "+0.0;-0.0;0.0"),
    ("Units needed (rule)", "SELECTEDVALUE ( param_rule[Value], 24 )", "0"),
    # switch On: the "candidate" is Side A's coalition (docs/methodology.md "Coalitions"); Off: unchanged
    ("Candidate is valid", f"IF ( {ON}, [Head to head is valid], {OK} )", None),
    ("Candidate selected", OK, None),   # the candidate picker alone (identity header), whatever the switch
    # base votes for steps 1-3: the candidate's 2023 votes v and valid votes V (Off), or c and V' (On)
    ("Engine votes", f"IF ( {ON}, IF ( [Head to head is valid], [Side A x100] / 100 ), [Candidate votes] )", "#,0"),
    ("Engine valid votes", f"IF ( {ON}, IF ( [Head to head is valid], [Valid x100 (head to head)] / 100 ), [Valid votes] )", "#,0"),
    ("Engine candidate name", f"IF ( {ON}, [Side A name], SELECTEDVALUE ( dim_party[candidate] ) )", None),
    # per unit (one state in context), steps 1-3 of the note
    # DAX names are case-insensitive: candidate votes = cv, valid votes = tv (never v / V)
    ("Scenario valid votes", "VAR cv = [Engine votes] VAR tv = [Engine valid votes] RETURN IF ( [Candidate is valid] && "
                             "HASONEVALUE ( dim_state[state_pcode] ) && NOT ISBLANK ( cv ) && tv > 0, tv + cv * [Supporter turnout] )",
     "#,0"),
    ("Scenario share uncapped", "VAR cv = [Engine votes] VAR tv = [Engine valid votes] VAR t = [Supporter turnout] "
                                "RETURN IF ( [Candidate is valid] && HASONEVALUE ( dim_state[state_pcode] ) && NOT ISBLANK ( cv ) "
                                "&& tv > 0, DIVIDE ( cv * ( 1 + t ), tv + cv * t ) + ( [National swing] + [Zone swing] ) / 100 )",
     "0.00%"),
    ("Scenario share", "VAR u = [Scenario share uncapped] RETURN IF ( NOT ISBLANK ( u ), MIN ( 1, MAX ( 0, u ) ) )", "0.00%"),
    ("Scenario votes", f"{SHARE} * [Scenario valid votes]", "#,0"),
    ("Scenario label", f'VAR p = {SHARE} RETURN SWITCH ( TRUE (), ISBLANK ( p ), BLANK (), p >= 0.25, "Secured", '
                       'p >= 0.20, "Within reach", "Out of reach" )', None),
    ("Scenario label order", f"VAR p = {SHARE} RETURN SWITCH ( TRUE (), ISBLANK ( p ), BLANK (), p >= 0.25, 1, p >= 0.20, 2, 3 )",
     "0"),
    ("Points needed", f"VAR p = {SHARE} RETURN IF ( NOT ISBLANK ( p ), MAX ( 0, 0.25 - p ) * 100 )", "0.0"),
    ("Votes needed", "VAR p = [Scenario share] RETURN IF ( NOT ISBLANK ( p ), "
                     "ROUNDUP ( MAX ( 0, 0.25 * [Scenario valid votes] - [Scenario votes] ), 0 ) )", "#,0"),
    # national counts (iterate the 37 units)
    ("Units secured", f"IF ( [Candidate is valid], COUNTROWS ( FILTER ( VALUES ( dim_state[state_pcode] ), {SHARE} >= 0.25 ) ) + 0 )", "0"),
    ("Units within reach", f"IF ( [Candidate is valid], COUNTROWS ( FILTER ( VALUES ( dim_state[state_pcode] ), "
                           f"{SHARE} >= 0.20 && {SHARE} < 0.25 ) ) + 0 )", "0"),
    ("Units out of reach", f"IF ( [Candidate is valid], COUNTROWS ( FILTER ( VALUES ( dim_state[state_pcode] ), "
                           f"NOT ISBLANK ( {SHARE} ) && {SHARE} < 0.20 ) ) + 0 )", "0"),
    ("Units with a scenario", f"IF ( [Candidate is valid], COUNTROWS ( FILTER ( VALUES ( dim_state[state_pcode] ), "
                              f"NOT ISBLANK ( {SHARE} ) ) ) + 0 )", "0"),
    ("Units at a cap", "IF ( [Candidate is valid], COUNTROWS ( FILTER ( VALUES ( dim_state[state_pcode] ), "
                       "VAR u = [Scenario share uncapped] RETURN NOT ISBLANK ( u ) && ( u <= 0 || u >= 1 ) ) ) + 0 )", "0"),
    # The rule is national: these measures ignore any state or zone filter on the page (methodology: "all 37 units").
    # The unit counts above deliberately follow such filters (e.g. "units secured in the North West").
    ("Units secured (national)", f"CALCULATE ( [Units secured], {NATIONAL} )", "0"),
    ("Units still needed", "IF ( [Candidate is valid], MAX ( 0, [Units needed (rule)] - [Units secured (national)] ) )", "0"),
    ("Clears the rule", 'IF ( [Candidate is valid], IF ( [Units secured (national)] >= [Units needed (rule)], "Yes", "No" ) )',
     None),
    # tipping point: rank all 37 units by scenario share desc, ties by P-code asc; the unit in position N
    ("Tipping-point P-code", "IF ( [Candidate is valid], VAR n = [Units needed (rule)] RETURN CALCULATE ( "
                             f"VAR tb = FILTER ( ADDCOLUMNS ( VALUES ( dim_state[state_pcode] ), \"@p\", {SHARE} ), NOT ISBLANK ( [@p] ) ) "
                             "VAR tp = TOPN ( n, tb, [@p], DESC, dim_state[state_pcode], ASC ) "
                             "RETURN IF ( COUNTROWS ( tb ) >= n, MAXX ( TOPN ( 1, tp, [@p], ASC, dim_state[state_pcode], DESC ), "
                             f"dim_state[state_pcode] ) ), {NATIONAL} ) )", None),
    ("Tipping-point unit", 'VAR k = [Tipping-point P-code] RETURN IF ( NOT ISBLANK ( k ), '
                           'LOOKUPVALUE ( dim_state[state_name], dim_state[state_pcode], k ) )', None),
    ("Tipping-point share", f"VAR k = [Tipping-point P-code] RETURN IF ( NOT ISBLANK ( k ), "
                            f"CALCULATE ( {SHARE}, {NATIONAL}, dim_state[state_pcode] = k ) )", "0.00%"),
    ("Tipping-point gap (points)", "VAR p = [Tipping-point share] RETURN IF ( NOT ISBLANK ( p ), ( 0.25 - p ) * 100 )",
     "+0.0;-0.0;0.0"),
    # ---- rivals and verdict (user decision 2026-11-14: other candidates scale with their 2023 shares) ----
    ("Scenario share after turnout", "VAR cv = [Engine votes] VAR tv = [Engine valid votes] VAR t = [Supporter turnout] "
                                     "RETURN IF ( [Candidate is valid] && HASONEVALUE ( dim_state[state_pcode] ) && NOT ISBLANK ( cv ) "
                                     "&& tv > 0, DIVIDE ( cv * ( 1 + t ), tv + cv * t ) )", "0.00%"),
    # every other candidate's votes in the unit are multiplied by this factor: (1 - p2) / (1 - p1)
    ("Rival scale", "VAR p1 = [Scenario share after turnout] VAR p2 = [Scenario share] RETURN IF ( NOT ISBLANK ( p2 ), "
                    "IF ( p1 < 1, DIVIDE ( 1 - p2, 1 - p1 ), 0 ) )", "0.0000"),
    ("Scenario national votes", f"IF ( [Candidate is valid], CALCULATE ( SUMX ( VALUES ( dim_state[state_pcode] ), "
                                f"[Scenario votes] ), {NATIONAL} ) )", "#,0"),
    ("Scenario national valid votes", f"IF ( [Candidate is valid], CALCULATE ( SUMX ( VALUES ( dim_state[state_pcode] ), "
                                      f"[Scenario valid votes] ), {NATIONAL} ) )", "#,0"),
    ("Scenario national share", "DIVIDE ( [Scenario national votes], [Scenario national valid votes] )", "0.00%"),
    # Off branch = the 2026-11-14 measure verbatim; On branch = rival entities (Side B as one, unused main parties)
    ("Leading rival", f"IF ( {ON}, IF ( [Candidate is valid], " + ON_TAB
                      + 'RETURN IF ( rx = bl && bp <> "NONE", bl & "+" & bp, rx ) ), '
                      "IF ( [Candidate is valid], " + RIVALS + "VAR top1 = TOPN ( 1, tab, [@v], DESC, [Value], ASC ) "
                      "RETURN MAXX ( top1, [Value] ) ) )", None),
    # the leading rival entity's own party code (Side B = its lead's code); equals [Leading rival] when Off
    ("Leading rival code", f"IF ( {ON}, IF ( [Candidate is valid], " + ON_TAB + "RETURN rx ), [Leading rival] )", None),
    ("Leading rival votes", f"IF ( {ON}, IF ( [Candidate is valid], " + ON_TAB + "RETURN IF ( rx = bl, nb, nu ) ), "
                            "IF ( [Candidate is valid], " + RIVALS + "RETURN MAXX ( tab, [@v] ) ) )", "#,0"),
    ("Leading rival units at 25%", f"IF ( {ON}, IF ( [Candidate is valid], " + ON_TAB
                                   + "RETURN COUNTROWS ( FILTER ( t4, IF ( rx = bl, [@vb], [@vu] ) * [@sc] >= 0.25 * [@V1] ) ) + 0 ), "
                                   "VAR r = [Leading rival] RETURN IF ( NOT ISBLANK ( r ), CALCULATE ( COUNTROWS ( FILTER ( "
                                   "VALUES ( dim_state[state_pcode] ), CALCULATE ( SUM ( fact_result_2023[votes] ), "
                                   "fact_result_2023[party] = r ) * [Rival scale] >= 0.25 * [Scenario valid votes] ) ), "
                                   f"{NATIONAL} ) + 0 ) )", "0"),
    ("Has most votes", 'VAR a = [Scenario national votes] VAR b = [Leading rival votes] RETURN IF ( NOT ISBLANK ( a ), '
                       'IF ( a > b, "Yes", IF ( a = b, "Tied", "No" ) ) )', None),
    ("Verdict", 'VAR m = [Has most votes] VAR c = [Clears the rule] VAR r = [Leading rival] '
                'VAR rc = [Leading rival units at 25%] >= [Units needed (rule)] RETURN SWITCH ( TRUE (), ISBLANK ( m ), BLANK (), '
                'm = "Yes" && c = "Yes", "Outright win", '
                'm = "Yes", "No outright winner: run-off (most votes, but not 25% in enough states)", '
                'm = "Tied", "Tie on votes: no outright winner", '
                'rc, "Loses: " & r & " wins outright", '
                '"No outright winner: run-off (" & r & " has most votes)" )', None),
    # ---- display helpers for the report pages (Phase 5) ----
    ("Points from 25%", f"VAR p = {SHARE} RETURN IF ( NOT ISBLANK ( p ), ( p - 0.25 ) * 100 )", "+0.0;-0.0;0.0"),
    ("Scenario label colour", f'VAR p = {SHARE} RETURN SWITCH ( TRUE (), ISBLANK ( p ), BLANK (), p >= 0.25, "#0072B2", '
                              'p >= 0.20, "#D55E00", "#767676" )', None),
    ("Baseline label colour", 'VAR cv = [Candidate votes] VAR tv = [Valid votes] RETURN SWITCH ( TRUE (), '
                              'ISBLANK ( cv ) || ISBLANK ( tv ) || tv = 0, BLANK (), 4 * cv >= tv, "#0072B2", '
                              '5 * cv >= tv, "#D55E00", "#767676" )', None),
    ("Candidate national rank", 'CALCULATE ( VAR c = SELECTEDVALUE ( dim_party[party] ) VAR mine = [Candidate votes] RETURN '
                                'IF ( [Candidate is valid] && NOT ISBLANK ( mine ), COUNTROWS ( FILTER ( { "APC", "PDP", "LP", "NNPP" }, '
                                'VAR r = [Value] RETURN r <> c && CALCULATE ( [Total votes], fact_result_2023[party] = r ) > mine ) ) + 1 ), '
                                f'{NATIONAL} )', "0"),
    ("Baseline label", 'VAR cv = [Candidate votes] VAR tv = [Valid votes] RETURN SWITCH ( TRUE (), '
                       'ISBLANK ( cv ) || ISBLANK ( tv ) || tv = 0, BLANK (), 4 * cv >= tv, "Secured", '
                       '5 * cv >= tv, "Within reach", "Out of reach" )', None),
    # rank of the unit among all 37 by scenario share (ties by P-code) - same order as the tipping point
    ("Unit rank", f'VAR me = SELECTEDVALUE ( dim_state[state_pcode] ) VAR p = {SHARE} RETURN IF ( NOT ISBLANK ( p ) && NOT ISBLANK ( me ), '
                  f'CALCULATE ( COUNTROWS ( FILTER ( VALUES ( dim_state[state_pcode] ), VAR q = {SHARE} RETURN q > p || '
                  f'( q = p && dim_state[state_pcode] < me ) ) ), {NATIONAL} ) + 1 )', "0"),
    ("Path column colour", 'VAR k = [Tipping-point P-code] RETURN IF ( NOT ISBLANK ( k ) && SELECTEDVALUE ( dim_state[state_pcode] ) = k, '
                           '"#1F1F1F", [Scenario label colour] )', None),
    # Settings in force, as a plain sentence (user request 2026-11-14): only the sliders that are not at 0 are named.
    ("Assumptions in force", 'IF ( [Candidate is valid], VAR t = [Supporter turnout] VAR sw = [National swing] '
                             'VAR z = CONCATENATEX ( FILTER ( { ' + ", ".join(
                                 f'( {i}, "{ZONE_NAMES[zc]}", SELECTEDVALUE ( param_swing_{zc}[Value], 0 ) )'
                                 for i, zc in enumerate(ZONES)) + ' }, [Value3] <> 0 ), '
                             'FORMAT ( [Value3], "+0.0;-0.0" ) & " in the " & [Value2], ", ", [Value1], ASC ) '
                             'VAR parts = { ( 1, IF ( sw <> 0, FORMAT ( sw, "+0.0;-0.0" ) & " points everywhere" ) ), ( 2, z ), '
                             '( 3, IF ( t <> 0, FORMAT ( t, "+0%;-0%" ) & IF ( ' + ON + ', " turnout among the coalition\'s 2023 voters", " turnout among the candidate\'s 2023 voters" ) ) ) } '
                             'VAR s = CONCATENATEX ( FILTER ( parts, [Value2] <> "" ), [Value2], "; ", [Value1], ASC ) '
                             'RETURN IF ( s = "", "No changes: this is the 2023 result", s ) & ". " & [Units needed (rule)] '
                             '& " states needed to win." )', None),
    # ---- plain-words sentences (user decision 2026-11-14: gaps in people, not only percentage points) ----
    # Votes to spare in a unit: votes that could switch from the candidate to others (unit total fixed) while the
    # candidate keeps at least 25%: max(0, v2 - 0.25 x V1), rounded down (docs/methodology.md). The 1E-6 only absorbs
    # floating-point error when the margin is a whole number (e.g. exactly 96 votes); it never changes a true fraction.
    ("Votes to spare", f"VAR p = {SHARE} RETURN IF ( NOT ISBLANK ( p ), "
                       "ROUNDDOWN ( MAX ( 0, [Scenario votes] - 0.25 * [Scenario valid votes] ) + 1E-6, 0 ) )", "#,0"),
    ("Deciding state sentence", 'VAR k = [Tipping-point P-code] RETURN IF ( NOT ISBLANK ( k ), '
                                'VAR c = [Engine candidate name] VAR g = [Tipping-point gap (points)] '
                                f'VAR need = CALCULATE ( [Votes needed], {NATIONAL}, dim_state[state_pcode] = k ) '
                                f'VAR spare = CALCULATE ( [Votes to spare], {NATIONAL}, dim_state[state_pcode] = k ) '
                                'RETURN [Tipping-point unit] & " is the deciding state. " & IF ( g <= 0, '
                                'c & " is " & FORMAT ( -g, "0.0" ) & " points above a quarter of the vote there: about " '
                                '& FORMAT ( spare, "#,0" ) & " votes could switch to other candidates before the state is lost.", '
                                'c & " is " & FORMAT ( g, "0.0" ) & " points short of a quarter of the vote there: about " '
                                '& FORMAT ( need, "#,0" ) & " more votes would need to switch from other candidates to " & c & "." ) )',
     None),
    # 2023 baseline only (whole-number test, as 'States at 25% or more'): the narrowest state won and the narrowest miss.
    # 4 x votes - valid votes is a whole number, so margins of a quarter are exact: spare = rounded down, needed = rounded up.
    # Result as a sentence (user request 2026-11-14); same logic as [Verdict] (docs/methodology.md "Rivals and the verdict")
    ("Result sentence", 'VAR m = [Has most votes] VAR c = [Clears the rule] VAR k = [Units secured (national)] '
                        'VAR n = [Units needed (rule)] VAR nm = [Engine candidate name] VAR r = [Leading rival] '
                        'VAR rn = CALCULATE ( MAX ( dim_party[candidate] ), REMOVEFILTERS ( dim_party ), dim_party[party] = r ) '
                        f'VAR rl = IF ( {ON}, [Leading rival name], rn & " (" & r & ")" ) '
                        'VAR rc = [Leading rival units at 25%] >= n RETURN SWITCH ( TRUE (), ISBLANK ( m ), BLANK (), '
                        'm = "Yes" && c = "Yes", nm & " wins outright: the most votes nationwide and a quarter of the vote in " '
                        '& k & " states (" & n & " needed).", '
                        'm = "Yes", "No outright winner: " & nm & " has the most votes but a quarter of the vote in only " & k '
                        '& " states (" & n & " needed). This would go to a run-off.", '
                        'm = "Tied", "Tie on votes: no outright winner.", '
                        'rc, nm & " loses: " & rl & " has the most votes and a quarter of the vote in enough states.", '
                        '"No outright winner: " & rl & " has the most votes but not a quarter of the vote in enough '
                        'states. This would go to a run-off." )', None),
    ("Closest calls sentence", 'IF ( [Candidate is valid], VAR c = SELECTEDVALUE ( dim_party[candidate] ) '
                               'VAR tb = CALCULATETABLE ( FILTER ( ADDCOLUMNS ( SUMMARIZE ( dim_state, dim_state[state_pcode], '
                               'dim_state[state_name] ), "@v", [Candidate votes], "@t", [Valid votes] ), NOT ISBLANK ( [@v] ) '
                               f'&& [@t] > 0 ), {NATIONAL} ) '
                               'VAR won = TOPN ( 1, FILTER ( tb, 4 * [@v] >= [@t] ), 4 * [@v] - [@t], ASC, dim_state[state_pcode], ASC ) '
                               'VAR miss = TOPN ( 1, FILTER ( tb, 4 * [@v] < [@t] ), [@t] - 4 * [@v], ASC, dim_state[state_pcode], ASC ) '
                               'VAR a = IF ( COUNTROWS ( won ) > 0, MAXX ( won, dim_state[state_name] ) & ", the narrowest state won, was about " '
                               '& FORMAT ( MAXX ( won, ROUNDDOWN ( ( 4 * [@v] - [@t] ) / 4, 0 ) ), "#,0" ) & " votes above a quarter of the vote.", '
                               '"No state reached a quarter of the vote." ) '
                               'VAR b = IF ( COUNTROWS ( miss ) > 0, " " & MAXX ( miss, dim_state[state_name] ) & ", the narrowest miss, needed about " '
                               '& FORMAT ( MAXX ( miss, ROUNDUP ( ( [@t] - 4 * [@v] ) / 4, 0 ) ), "#,0" ) '
                               '& " more votes switching to " & c & " from other candidates.", " Every state reached a quarter of the vote." ) '
                               'RETURN c & " in 2023: " & a & b )', None),
]


# ---- candidate identity (user request 2026-11-14): portrait, party badge, party colour accents, party now ----
def _identity_measures():
    import csv as _csv
    cands = {c["party"]: c for c in json.loads((PBIP / "assets" / "photos" / "candidates_manifest.json")
                                                 .read_text(encoding="utf-8"))["candidates"]}
    with open(ROOT / "data" / "reference" / "party_display.csv", encoding="utf-8") as f:
        colours = {r["party"]: r["colour_hex"] for r in _csv.DictReader(l for l in f if not l.startswith("#"))}
    with open(ROOT / "data" / "reference" / "party_now.csv", encoding="utf-8") as f:
        now = {r["party_2023"]: r for r in _csv.DictReader(l for l in f if not l.startswith("#"))}

    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    def contrast(a, b):
        hi, lo = sorted((lum(a), lum(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)
    text = {}
    for party, hexc in colours.items():   # white or ink text, whichever passes 4.5:1 with more margin
        best = max(("#FFFFFF", "#1F1F1F"), key=lambda tc: contrast(hexc, tc))
        assert contrast(hexc, best) >= 4.5, (party, hexc)
        text[party] = best
    sel = "SELECTEDVALUE ( dim_party[party] )"

    def switch(values, default='""'):
        return f"SWITCH ( {sel}, " + ", ".join(f'"{k}", "{v}"' for k, v in values.items()) + f", {default} )"

    def nice(d):
        y, m, dd = d.split("-")
        return f"{int(dd)} {['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][int(m)]} {y}"
    # 2026-11-16 (open question 20): role (e.g. running mate) and a short dated note (e.g. court challenge) added
    def ident_text(p, r):
        t = f"2023: {p}. Now: {r['party_now']}" + (f", {r['role']}" if r.get("role") else "")
        t += f" ({r['source_publisher'].split(' (')[0]}, {nice(r['as_of'])})"
        if r.get("note_short"):
            t += f". {r['note_short']} ({r['note_source_publisher'].split(' (')[0]}, {nice(r['note_date'])})"
        return t
    ident = {p: ident_text(p, r) for p, r in now.items()}
    logos = {l["party"]: l["data_uri"] for l in json.loads((PBIP / "assets" / "photos" / "logos_manifest.json")
                                                             .read_text(encoding="utf-8"))["logos"]}
    return [("Party accent colour", f'IF ( [Candidate selected], {switch(colours)}, "#505050" )', None),
            ("Party accent text colour", f'IF ( [Candidate selected], {switch(text)}, "#FFFFFF" )', None),
            ("Party badge", f"IF ( [Candidate selected], {sel} )", None),
            ("Party identity", f"IF ( [Candidate selected], {switch(ident)} )", None),
            ("Candidate photo", f"IF ( [Candidate selected], {switch({p: c['data_uri'] for p, c in cands.items()})} )",
             None),
            ("Party now badge", f"IF ( [Candidate selected], {switch({p: r['party_now'] for p, r in now.items()})} )", None),
            # party logos: trademarks, identification only (user decision 2026-11-14); PBIP_NO_LOGOS=1 -> badges
            ("Party logo", f"IF ( [Candidate selected], {switch({p: logos[p] for p in now})} )", None),
            ("Party now logo", f"IF ( [Candidate selected], {switch({p: logos[r['party_now']] for p, r in now.items()})} )",
             None)]


MEASURES["scenario"] += _identity_measures()
# tile chart helpers (2026-11-14): the equal-size tile map drawn as a scatter chart so each tile can carry its code
MEASURES["scenario"] += [
    ("Grid column", "IF ( HASONEVALUE ( dim_state[state_pcode] ), MIN ( dim_state[tile_col] ) )", "0"),
    ("Grid row", "IF ( HASONEVALUE ( dim_state[state_pcode] ), 10 - MIN ( dim_state[tile_row] ) )", "0"),
    ("State name", "SELECTEDVALUE ( dim_state[state_name] )", None),
    # tile grid as a matrix (simulator page): code in each cell, cell colour = the same fixed 3-colour scale as the maps
    # (vermillion at -25 points, #F2F2F2 at 0, blue at +25, linear in each RGB channel), text black or white,
    # whichever contrasts more with that cell (always >= 4.5:1)
    ("Tile code", "IF ( [Candidate is valid] && HASONEVALUE ( dim_state[state_pcode] ), MIN ( dim_state[state_code] ) )", None),
    ("Tile fill", "VAR p = [Points from 25%] RETURN IF ( NOT ISBLANK ( p ) && HASONEVALUE ( dim_state[state_pcode] ), "
                  "VAR f = MIN ( 1, ABS ( p ) / 25 ) "
                  "VAR r = ROUND ( IF ( p < 0, 242 + ( 213 - 242 ) * f, 242 + ( 0 - 242 ) * f ), 0 ) "
                  "VAR g = ROUND ( IF ( p < 0, 242 + ( 94 - 242 ) * f, 242 + ( 114 - 242 ) * f ), 0 ) "
                  "VAR b = ROUND ( IF ( p < 0, 242 + ( 0 - 242 ) * f, 242 + ( 178 - 242 ) * f ), 0 ) "
                  'VAR hx = "0123456789ABCDEF" '
                  'RETURN "#" & MID ( hx, INT ( r / 16 ) + 1, 1 ) & MID ( hx, MOD ( r, 16 ) + 1, 1 ) '
                  "& MID ( hx, INT ( g / 16 ) + 1, 1 ) & MID ( hx, MOD ( g, 16 ) + 1, 1 ) "
                  "& MID ( hx, INT ( b / 16 ) + 1, 1 ) & MID ( hx, MOD ( b, 16 ) + 1, 1 ) )", None),
    ("Tile text colour", "VAR p = [Points from 25%] RETURN IF ( NOT ISBLANK ( p ) && HASONEVALUE ( dim_state[state_pcode] ), "
                         "VAR f = MIN ( 1, ABS ( p ) / 25 ) "
                         "VAR r = ROUND ( IF ( p < 0, 242 + ( 213 - 242 ) * f, 242 + ( 0 - 242 ) * f ), 0 ) / 255 "
                         "VAR g = ROUND ( IF ( p < 0, 242 + ( 94 - 242 ) * f, 242 + ( 114 - 242 ) * f ), 0 ) / 255 "
                         "VAR b = ROUND ( IF ( p < 0, 242 + ( 0 - 242 ) * f, 242 + ( 178 - 242 ) * f ), 0 ) / 255 "
                         "VAR lr = IF ( r <= 0.03928, r / 12.92, POWER ( ( r + 0.055 ) / 1.055, 2.4 ) ) "
                         "VAR lg = IF ( g <= 0.03928, g / 12.92, POWER ( ( g + 0.055 ) / 1.055, 2.4 ) ) "
                         "VAR lb = IF ( b <= 0.03928, b / 12.92, POWER ( ( b + 0.055 ) / 1.055, 2.4 ) ) "
                         "VAR l = 0.2126 * lr + 0.7152 * lg + 0.0722 * lb "
                         'RETURN IF ( 1.05 / ( l + 0.05 ) > ( l + 0.05 ) / 0.05, "#FFFFFF", "#000000" ) )', None),
]
# ---- coalitions (user decisions 2026-11-16; docs/methodology.md "Coalitions"). Disconnected picker tables; every
# coalition number is a measure. Whole-number scaling: x100 measures are 100 x votes, exact because follow rates are
# whole percentages, so the 25% test and "who leads" compare whole numbers (no floating point).
def _read_ref(name):
    import csv as _csv
    with open(ROOT / "data" / "reference" / name, encoding="utf-8") as f:
        return list(_csv.DictReader(l for l in f if not l.startswith("#")))


MAIN = ["APC", "PDP", "LP", "NNPP"]
CAND_NAME = {r["party"]: r["candidate"] for r in _read_ref("party_display.csv")}
COAL_NAMES = _read_ref("coalition_names.csv")
BLUE_H, ORANGE_H, GREY_H = "#0072B2", "#D55E00", "#767676"


def _nice(d):
    y, m, dd = d.split("-")
    return f"{int(dd)} {['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][int(m)]} {y}"


def _q(t):
    return '"' + t.replace('"', '""') + '"'


def CNAME(x):
    return f"SWITCH ( {x}, " + ", ".join(f'"{p}", "{CAND_NAME[p]}"' for p in MAIN) + " )"


def _choices(extra=()):
    rows = [(p, f"{CAND_NAME[p]} ({p})", i + 1) for i, p in enumerate(MAIN)] + list(extra)
    return ('DATATABLE ( "party", STRING, "choice", STRING, "sort", INTEGER, { '
            + ", ".join(f"{{ {_q(p)}, {_q(c)}, {i} }}" for p, c, i in rows) + " } )")


NOBODY = "Nobody: one party alone"
CHOICE_COLS = [("party", "string", None), ("choice", "string", "sort"), ("sort", "int64", None)]
COAL_TABLES = {  # table: (DAX source, [(column, dataType, sortByColumn)])
    "coal_a_lead": (_choices(), CHOICE_COLS),
    "coal_a_partner": (_choices(), CHOICE_COLS),
    "coal_b_lead": (_choices(), CHOICE_COLS),
    "coal_b_partner": (_choices([("NONE", NOBODY, 5)]), CHOICE_COLS),
    "coal_switch": ('DATATABLE ( "Value", STRING, "sort", INTEGER, { { "Off", 1 }, { "On", 2 } } )',
                    [("Value", "string", "sort"), ("sort", "int64", None)]),
    # the editable name list (data/reference/coalition_names.csv), one row per ordered pair
    "coalition_names": ('DATATABLE ( "lead", STRING, "partner", STRING, "display_name", STRING, "status", STRING, '
                        '"source_label", STRING, { ' + ", ".join(
                            f"{{ {_q(r['lead'])}, {_q(r['partner'])}, {_q(r['display_name'])}, {_q(r['status'])}, "
                            + _q(f"{r['source_publisher'].split(' (')[0]}, {_nice(r['as_of'])}" if r["status"] == "real" else "")
                            + " }" for r in COAL_NAMES) + " } )",
                        [("lead", "string", None), ("partner", "string", None), ("display_name", "string", None),
                         ("status", "string", None), ("source_label", "string", None)]),
}


def _text_on(hexc):
    """White or black text on a fill, whichever contrasts more (>= 4.5:1 asserted)."""
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    w, k = 1.05 / (lum(hexc) + 0.05), (lum(hexc) + 0.05) / 0.05
    best, ratio = ("#FFFFFF", w) if w >= k else ("#000000", k)
    assert ratio >= 4.5, (hexc, ratio)
    return best


VA = "[Side A x100]"
WM, WH = "[Valid x100 (merge)]", "[Valid x100 (head to head)]"
# main parties on neither side, as a one-column table of codes
UNUSED = 'FILTER ( { "APC", "PDP", "LP", "NNPP" }, [Value] <> al && [Value] <> ap && [Value] <> bl && [Value] <> bp )'
# rival entities on the coalition pages: Side B (by its lead's code) and unused main parties, national x100 votes
H2H_RIVALS = (SIDES + 'VAR tab = ADDCOLUMNS ( FILTER ( { "APC", "PDP", "LP", "NNPP" }, [Value] <> al && [Value] <> ap '
              '&& [Value] <> bp ), "@v", VAR r = [Value] RETURN CALCULATE ( IF ( r = bl, [Side B x100], 100 * '
              + VOTES("r") + ' ), ' + NATIONAL + ' ) ) ')


def _states(cond):
    return f"CALCULATE ( COUNTROWS ( FILTER ( VALUES ( dim_state[state_pcode] ), {cond} ) ), {NATIONAL} ) + 0"


def _lookup(c, l, p):
    return f"LOOKUPVALUE ( coalition_names[{c}], coalition_names[lead], {l}, coalition_names[partner], {p} )"


def _coalition_measures():
    lead_lbl = "IF ( r = bl, [Side B name], " + CNAME("r") + ' & " (" & r & ")" )'
    side_a_msg = ('VAR al = [Side A lead] VAR ap = [Side A partner] RETURN SWITCH ( TRUE (), '
                  'ISBLANK ( al ), "Choose Side A\'s lead party (top of the ticket).", '
                  'ISBLANK ( ap ), "Choose Side A\'s partner party.", '
                  'al = ap, "Side A\'s lead and partner are the same party: choose two different parties.", '
                  '[Side A name] & ": " & ' + CNAME("al") + ' & " (" & al & ") leads, " & ' + CNAME("ap")
                  + ' & " (" & ap & ") is the partner. " & IF ( [Side A is real], "A real joint ticket (" & [Side A source] '
                  '& ").", "A what-if pairing: no such joint ticket exists." ) & " " & [Follow A] & "% of " & '
                  + CNAME("ap") + ' & "\'s 2023 voters follow; the rest stay home." )')
    side_b_msg = (SIDES + 'RETURN SWITCH ( TRUE (), '
                  'ISBLANK ( bl ), "Choose Side B\'s main party.", '
                  'ISBLANK ( bp ), "Choose Side B\'s partner, or Nobody.", '
                  'bl = al || bl = ap, bl & " is already on Side A: choose another party for Side B.", '
                  'bp <> "NONE" && bp = bl, "Side B\'s main party and partner are the same: choose two different parties, '
                  'or Nobody.", '
                  'bp <> "NONE" && ( bp = al || bp = ap ), bp & " is already on Side A: choose another partner for Side B, '
                  'or Nobody.", '
                  'bp = "NONE", ' + CNAME("bl") + ' & " (" & bl & ") alone, with all of their 2023 votes.", '
                  '[Side B name] & ": " & ' + CNAME("bl") + ' & " (" & bl & ") leads, " & ' + CNAME("bp")
                  + ' & " (" & bp & ") is the partner. " & IF ( [Side B is real], "A real joint ticket (" & [Side B source] '
                  '& ").", "A what-if pairing: no such joint ticket exists." ) & " " & [Follow B] & "% of " & '
                  + CNAME("bp") + ' & "\'s 2023 voters follow; the rest stay home." )')
    led = lambda k: _states('[Head to head leader code] = "' + k + '"')
    m = [
        # ---- inputs ----
        ("Coalition switch on", 'SELECTEDVALUE ( coal_switch[Value], "Off" ) = "On"', None),
        ("Side A lead", "SELECTEDVALUE ( coal_a_lead[party] )", None),
        ("Side A partner", "SELECTEDVALUE ( coal_a_partner[party] )", None),
        ("Side B lead", "SELECTEDVALUE ( coal_b_lead[party] )", None),
        ("Side B partner", "SELECTEDVALUE ( coal_b_partner[party] )", None),   # "NONE" = Side B is one party alone
        ("Follow A", "SELECTEDVALUE ( param_follow_a[Value], 100 )", "0"),
        ("Follow B", "SELECTEDVALUE ( param_follow_b[Value], 100 )", "0"),
        ("Side A is valid", "VAR al = [Side A lead] VAR ap = [Side A partner] RETURN NOT ISBLANK ( al ) && NOT ISBLANK ( ap ) "
                            "&& al <> ap", None),
        ("Head to head is valid", SIDES + 'RETURN [Side A is valid] && NOT ISBLANK ( bl ) && NOT ISBLANK ( bp ) && bl <> al '
                                  '&& bl <> ap && ( bp = "NONE" || ( bp <> bl && bp <> al && bp <> ap ) )', None),
        # ---- names (pick list from data/reference/coalition_names.csv) ----
        ("Side A name", "VAR al = [Side A lead] VAR ap = [Side A partner] RETURN IF ( [Side A is valid], "
                        + _lookup("display_name", "al", "ap") + " )", None),
        ("Side A is real", "VAR al = [Side A lead] VAR ap = [Side A partner] RETURN [Side A is valid] && "
                           + _lookup("status", "al", "ap") + ' = "real"', None),
        ("Side A source", "VAR al = [Side A lead] VAR ap = [Side A partner] RETURN IF ( [Side A is valid], "
                          + _lookup("source_label", "al", "ap") + " )", None),
        ("Side B name", SIDES + 'RETURN IF ( [Head to head is valid], IF ( bp = "NONE", ' + CNAME("bl") + ' & " (" & bl & ")", '
                        + _lookup("display_name", "bl", "bp") + " ) )", None),
        ("Side B is real", SIDES + 'RETURN [Head to head is valid] && bp <> "NONE" && '
                           + _lookup("status", "bl", "bp") + ' = "real"', None),
        ("Side B source", SIDES + 'RETURN IF ( [Head to head is valid] && bp <> "NONE", '
                          + _lookup("source_label", "bl", "bp") + " )", None),
        ("Side A message", side_a_msg, None),
        ("Side B message", side_b_msg, None),
        # ---- whole-number (x100) votes and valid totals, any state filter (linear, so national = sum of states) ----
        ("Side A x100", "VAR al = [Side A lead] VAR ap = [Side A partner] VAR fa = [Follow A] RETURN IF ( [Side A is valid], "
                        f"100 * {VOTES('al')} + fa * {VOTES('ap')} + 0 )", "#,0"),
        ("Valid x100 (merge)", "VAR ap = [Side A partner] VAR fa = [Follow A] RETURN IF ( [Side A is valid], "
                               f"100 * [Valid votes] - ( 100 - fa ) * {VOTES('ap')} + 0 )", "#,0"),
        ("Side B x100", SIDES + "VAR fb = [Follow B] RETURN IF ( [Head to head is valid], 100 * " + VOTES("bl")
                        + ' + IF ( bp <> "NONE", fb * ' + VOTES("bp") + ", 0 ) + 0 )", "#,0"),
        ("Valid x100 (head to head)", SIDES + "VAR fb = [Follow B] RETURN IF ( [Head to head is valid], " + WM
                                      + ' - IF ( bp <> "NONE", ( 100 - fb ) * ' + VOTES("bp") + ", 0 ) )", "#,0"),
        # ---- Merge two parties page (Side A only, no swing) ----
        ("Side A votes", f"{VA} / 100", "#,0"),
        ("Side A share (merge)", f"DIVIDE ( {VA}, {WM} )", "0.00%"),
        ("Side A lead votes", "VAR al = [Side A lead] RETURN IF ( [Side A is valid], " + VOTES("al") + " + 0 )", "#,0"),
        ("Side A lead share", "DIVIDE ( [Side A lead votes], [Valid votes] )", "0.00%"),
        ("Side A change (points)", "VAR a = [Side A share (merge)] VAR b = [Side A lead share] RETURN IF ( NOT ISBLANK ( a ) "
                                   "&& NOT ISBLANK ( b ), ( a - b ) * 100 )", "+0.0;-0.0;0.0"),
        ("Side A status (merge)", f'VAR c = {VA} VAR w = {WM} RETURN IF ( NOT ISBLANK ( c ) && w > 0, IF ( 4 * c >= w, '
                                  '"Secured", IF ( 5 * c >= w, "Within reach", "Out of reach" ) ) )', None),
        ("Side A status colour (merge)", f'VAR c = {VA} VAR w = {WM} RETURN IF ( NOT ISBLANK ( c ) && w > 0, IF ( 4 * c >= w, '
                                         f'"{BLUE_H}", IF ( 5 * c >= w, "{ORANGE_H}", "{GREY_H}" ) ) )', None),
        ("Side A states at 25% (merge)", f"IF ( [Side A is valid], {_states(f'4 * {VA} >= {WM}')} )", "0"),
        ("Side A lead states at 25%", "VAR al = [Side A lead] RETURN IF ( [Side A is valid], "
                                      + _states(f"4 * {VOTES('al')} >= [Valid votes]") + " )", "0"),
        ("Side A national votes", f"CALCULATE ( [Side A votes], {NATIONAL} )", "#,0"),
        ("Side A national share (merge)", f"CALCULATE ( [Side A share (merge)], {NATIONAL} )", "0.00%"),
        ("Side A lead national votes", f"CALCULATE ( [Side A lead votes], {NATIONAL} )", "#,0"),
        ("Side A lead national share", f"CALCULATE ( [Side A lead share], {NATIONAL} )", "0.00%"),
        # ---- Head to head page (both sides, no swing) ----
        ("Side A share (head to head)", f"IF ( [Head to head is valid], DIVIDE ( {VA}, {WH} ) )", "0.00%"),
        ("Side B votes", "[Side B x100] / 100", "#,0"),
        ("Side B share (head to head)", f"DIVIDE ( [Side B x100], {WH} )", "0.00%"),
        ("Side A at 25% (head to head)", f'VAR c = {VA} VAR w = {WH} RETURN IF ( NOT ISBLANK ( w ) && w > 0, '
                                         'IF ( 4 * c >= w, "Yes", "No" ) )', None),
        ("Side B at 25% (head to head)", f'VAR c = [Side B x100] VAR w = {WH} RETURN IF ( NOT ISBLANK ( w ) && w > 0, '
                                         'IF ( 4 * c >= w, "Yes", "No" ) )', None),
        # who leads a state: largest of Side A, Side B and each unused main party (x100, exact); shared largest = tie
        ("Head to head leader code", SIDES + "RETURN IF ( [Head to head is valid] && HASONEVALUE ( dim_state[state_pcode] ), "
                                     f"VAR a = {VA} VAR b = [Side B x100] "
                                     f"VAR o = MAXX ( {UNUSED}, VAR r = [Value] RETURN 100 * {VOTES('r')} ) "
                                     "VAR oo = IF ( ISBLANK ( o ), -1, o ) "
                                     'RETURN SWITCH ( TRUE (), a > b && a > oo, "A", b > a && b > oo, "B", '
                                     'oo > a && oo > b, "O", "T" ) )', None),
        ("Who leads (head to head)", SIDES + 'VAR k = [Head to head leader code] RETURN SWITCH ( k, "A", "Side A", "B", '
                                     f'"Side B", "T", "Tie", "O", MAXX ( TOPN ( 1, ADDCOLUMNS ( {UNUSED}, "@v", VAR r = [Value] '
                                     f'RETURN {VOTES("r")} ), [@v], DESC, [Value], ASC ), [Value] ) & " (on neither side)" )',
         None),
        ("Head to head leader colour", f'SWITCH ( [Head to head leader code], "A", "{BLUE_H}", "B", "{ORANGE_H}", "O", '
                                       f'"{GREY_H}", "T", "{GREY_H}" )', None),
        ("Head to head leader text colour", f'SWITCH ( [Head to head leader code], "A", "{_text_on(BLUE_H)}", "B", '
                                            f'"{_text_on(ORANGE_H)}", "O", "{_text_on(GREY_H)}", "T", "{_text_on(GREY_H)}" )',
         None),
        ("Head to head tile code", "IF ( [Head to head is valid] && HASONEVALUE ( dim_state[state_pcode] ), "
                                   "MIN ( dim_state[state_code] ) )", None),
        ("States led by Side A", f"IF ( [Head to head is valid], {led('A')} )", "0"),
        ("States led by Side B", f"IF ( [Head to head is valid], {led('B')} )", "0"),
        ("Side A states at 25% (head to head)", f"IF ( [Head to head is valid], {_states(f'4 * {VA} >= {WH}')} )", "0"),
        ("Side B states at 25% (head to head)", f"IF ( [Head to head is valid], {_states(f'4 * [Side B x100] >= {WH}')} )",
         "0"),
        ("Side A national votes (head to head)", f"IF ( [Head to head is valid], CALCULATE ( {VA} / 100, {NATIONAL} ) )",
         "#,0"),
        ("Side B national votes", f"CALCULATE ( [Side B votes], {NATIONAL} )", "#,0"),
        ("Side A national share (head to head)", f"CALCULATE ( [Side A share (head to head)], {NATIONAL} )", "0.00%"),
        ("Side B national share (head to head)", f"CALCULATE ( [Side B share (head to head)], {NATIONAL} )", "0.00%"),
        # verdict: Side A as the candidate; rivals = Side B (by its lead's code) and unused main parties; ties by code
        ("Head to head rival code", "IF ( [Head to head is valid], " + H2H_RIVALS
                                    + "RETURN MAXX ( TOPN ( 1, tab, [@v], DESC, [Value], ASC ), [Value] ) )", None),
        ("Head to head rival x100", "IF ( [Head to head is valid], " + H2H_RIVALS + "RETURN MAXX ( tab, [@v] ) )", "#,0"),
        ("Head to head rival", SIDES + 'VAR r = [Head to head rival code] RETURN IF ( r = bl && bp <> "NONE", '
                               'r & "+" & bp, r )', None),
        ("Head to head rival name", SIDES + "VAR r = [Head to head rival code] RETURN IF ( NOT ISBLANK ( r ), "
                                    + lead_lbl + " )", None),
        ("Head to head rival states at 25%", SIDES + "VAR r = [Head to head rival code] RETURN IF ( NOT ISBLANK ( r ), "
                                             + _states(f"4 * IF ( r = bl, [Side B x100], 100 * {VOTES('r')} ) >= {WH}")
                                             + " )", "0"),
        ("Head to head most votes", f'IF ( [Head to head is valid], VAR a = CALCULATE ( {VA}, {NATIONAL} ) '
                                    'VAR b = [Head to head rival x100] RETURN IF ( a > b, "Yes", IF ( a = b, "Tied", "No" ) ) )',
         None),
        ("Head to head verdict", 'VAR m = [Head to head most votes] VAR n = [Units needed (rule)] '
                                 'VAR c = [Side A states at 25% (head to head)] >= n VAR r = [Head to head rival] '
                                 'VAR rc = [Head to head rival states at 25%] >= n RETURN SWITCH ( TRUE (), ISBLANK ( m ), '
                                 'BLANK (), m = "Yes" && c, "Outright win", '
                                 'm = "Yes", "No outright winner: run-off (most votes, but not 25% in enough states)", '
                                 'm = "Tied", "Tie on votes: no outright winner", '
                                 'rc, "Loses: " & r & " wins outright", '
                                 '"No outright winner: run-off (" & r & " has most votes)" )', None),
        ("Head to head sentence", 'VAR m = [Head to head most votes] VAR n = [Units needed (rule)] '
                                  'VAR k = [Side A states at 25% (head to head)] VAR nm = [Side A name] '
                                  'VAR rl = [Head to head rival name] VAR rc = [Head to head rival states at 25%] >= n '
                                  'RETURN SWITCH ( TRUE (), ISBLANK ( m ), BLANK (), '
                                  'm = "Yes" && k >= n, nm & " wins outright: the most votes nationwide and a quarter of '
                                  'the vote in " & k & " states (" & n & " needed).", '
                                  'm = "Yes", "No outright winner: " & nm & " has the most votes but a quarter of the vote '
                                  'in only " & k & " states (" & n & " needed). This would go to a run-off.", '
                                  'm = "Tied", "Tie on votes: no outright winner.", '
                                  'rc, nm & " loses: " & rl & " has the most votes and a quarter of the vote in enough '
                                  'states.", '
                                  '"No outright winner: " & rl & " has the most votes but not a quarter of the vote in '
                                  'enough states. This would go to a run-off." )', None),
        # ---- simulator: the leading rival entity's name with the switch On; what the switch is doing ----
        ("Leading rival name", SIDES + "VAR r = [Leading rival code] RETURN IF ( NOT ISBLANK ( r ), " + lead_lbl + " )",
         None),
        ("Simulator coalition sentence", SIDES + f'RETURN IF ( {ON}, IF ( [Head to head is valid], "On: " & [Side A name] '
                                         '& ", " & [Follow A] & "% of partner voters follow, vs " & [Side B name] '
                                         '& IF ( bp <> "NONE", " (" & [Follow B] & "% follow)" ) & ". Candidate picker not '
                                         'used.", "On, but not complete: " & IF ( [Side A is valid], '
                                         '[Side B message], [Side A message] ) & " Fix it on Head to head." ), '
                                         '"Off: uses the candidate picked at the top. Pick a coalition on Head to head, '
                                         'then switch On." )', None),
    ]
    # side portraits (the same free-licence crops as the candidate photo)
    cands = {c["party"]: c for c in json.loads((PBIP / "assets" / "photos" / "candidates_manifest.json")
                                                 .read_text(encoding="utf-8"))["candidates"]}
    for nm, ref in (("Side A lead photo", "[Side A lead]"), ("Side A partner photo", "[Side A partner]"),
                    ("Side B lead photo", "[Side B lead]"), ("Side B partner photo", "[Side B partner]")):
        m.append((nm, f"VAR x = {ref} RETURN IF ( NOT ISBLANK ( x ), SWITCH ( x, "
                  + ", ".join(f'"{p}", "{cands[p]["data_uri"]}"' for p in MAIN) + " ) )", None))
    return m


MEASURES["scenario"] += _coalition_measures()
COAL_PHOTOS = ("Side A lead photo", "Side A partner photo", "Side B lead photo", "Side B partner photo")


def coal_table_tmdl(name):
    src, cols = COAL_TABLES[name]
    out = [f"table {name}", f"\tlineageTag: {stable_uuid('table', name)}", ""]
    for c, dt, sort in cols:
        out += [f"\tcolumn {c}", f"\t\tdataType: {dt}", f"\t\tlineageTag: {stable_uuid('col', name, c)}",
                "\t\tsummarizeBy: none", f"\t\tsourceColumn: [{c}]"] + ([f"\t\tsortByColumn: {sort}"] if sort else []) + [""]
    out += [f"\tpartition {name} = calculated", "\t\tmode: import", f"\t\tsource = {src}", ""]
    return "\n".join(out)


DATA_CATEGORY = {("scenario", m): "ImageUrl" for m in ("Candidate photo", "Party logo", "Party now logo") + COAL_PHOTOS}
for t, (_, dflt, fmt, _dt) in PARAMS.items():
    MEASURES[t] = [(f"{t} value", f"SELECTEDVALUE ( {t}[Value], {dflt} )", fmt)]


def calc_table_tmdl(name):
    src, col, dt, fmt, hidden = CALC_TABLES[name]
    out = [f"table {name}", f"\tlineageTag: {stable_uuid('table', name)}", ""]
    for mname, expr, mfmt in MEASURES.get(name, []):
        out += [f"\tmeasure '{mname}' = {expr}"] + ([f"\t\tformatString: {mfmt}"] if mfmt else []) + \
               ([f"\t\tdataCategory: {DATA_CATEGORY[(name, mname)]}"] if (name, mname) in DATA_CATEGORY else []) + \
               [f"\t\tlineageTag: {stable_uuid('measure', name, mname)}", ""]
    out += [f"\tcolumn {col}", f"\t\tdataType: {dt}"] + ([f"\t\tformatString: {fmt}"] if fmt else []) + \
           (["\t\tisHidden"] if hidden else []) + \
           [f"\t\tlineageTag: {stable_uuid('col', name, col)}", "\t\tsummarizeBy: none", f"\t\tsourceColumn: [{col}]", ""]
    out += [f"\tpartition {name} = calculated", "\t\tmode: import", f"\t\tsource = {src}", ""]
    return "\n".join(out)


def m_query(csv_name, cols):
    names = ", ".join(f'"{c}"' for c, *_ in cols)
    types = ", ".join(f'{{"{c}", {mt}}}' for c, _, mt, _ in cols)
    lines = ["let",
             f'    Source = Csv.Document(File.Contents(DataFolder & "\\{csv_name}"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
             "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
             f"    Selected = Table.SelectColumns(Promoted, {{{names}}}),",
             f"    Typed = Table.TransformColumnTypes(Selected, {{{types}}})",
             "in",
             "    Typed"]
    return "\n".join("\t\t\t\t" + l for l in lines)


def table_tmdl(name, csv_name, cols):
    out = [f"table {name}", f"\tlineageTag: {stable_uuid('table', name)}", ""]
    for mname, expr, fmt in MEASURES.get(name, []):
        out += [f"\tmeasure '{mname}' = {expr}"] + ([f"\t\tformatString: {fmt}"] if fmt else []) + \
               [f"\t\tlineageTag: {stable_uuid('measure', name, mname)}", ""]
    for c, dt, _, summ in cols:
        out += [f"\tcolumn {c}", f"\t\tdataType: {dt}", f"\t\tlineageTag: {stable_uuid('col', name, c)}",
                f"\t\tsummarizeBy: {summ}", f"\t\tsourceColumn: {c}"]
        if (name, c) in SORT_BY:
            out += [f"\t\tsortByColumn: {SORT_BY[(name, c)]}"]
        out += [""]
    out += [f"\tpartition {name} = m", "\t\tmode: import", "\t\tsource =", m_query(csv_name, cols), ""]
    return "\n".join(out)


def build_model():
    wjson(SM / ".platform", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": stable_uuid("semanticmodel", NAME)}})
    # Model files match what Desktop 2.159 writes on save (content-wise; Desktop uses CRLF, git normalises),
    # so a Desktop save followed by a script re-run produces no diff.
    wjson(SM / "definition.pbism", {"version": "4.2", "settings": {}})
    d = SM / "definition"
    write(d / "database.tmdl", "database\n\tcompatibilityLevel: 1606\n\n")
    order = json.dumps(list(TABLES) + ["DataFolder"], separators=(",", ":"))
    write(d / "model.tmdl", "\n".join(["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
                                       "\tsourceQueryCulture: en-US", "\tdataAccessOptions", "\t\tlegacyRedirects",
                                       "\t\treturnErrorValuesAsNull", "", f"annotation PBI_QueryOrder = {order}", "",
                                       'annotation PBI_ProTooling = ["DevMode"]', ""]
                                      + [f"ref table {t}" for t in list(TABLES) + list(CALC_TABLES) + list(COAL_TABLES)]) + "\n\n")
    path = DATA_FOLDER.replace('"', '""')
    write(d / "expressions.tmdl",
          f'expression DataFolder = "{path}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n'
          f"\tlineageTag: {stable_uuid('expr', 'DataFolder')}\n\n\tannotation PBI_ResultType = Text\n\n")
    for t, (csv_name, cols) in TABLES.items():
        write(d / "tables" / f"{t}.tmdl", table_tmdl(t, csv_name, cols) + "\n")
    for t in CALC_TABLES:
        write(d / "tables" / f"{t}.tmdl", calc_table_tmdl(t) + "\n")
    for t in COAL_TABLES:
        write(d / "tables" / f"{t}.tmdl", coal_table_tmdl(t) + "\n")
    rel = []
    for ft, fc, dt, dc in RELATIONSHIPS:
        rel += [f"relationship {stable_uuid('rel', ft, dt)}", f"\tfromColumn: {ft}.{fc}", f"\ttoColumn: {dt}.{dc}", ""]
    write(d / "relationships.tmdl", "\n".join(rel) + "\n")


# ---------------- report (PBIR) ----------------

def proj(kind, table, prop):
    return {"field": {kind: {"Expression": {"SourceRef": {"Entity": table}}, "Property": prop}},
            "queryRef": f"{table}.{prop}", "nativeQueryRef": prop, "active": True}


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def title(text):
    return {"title": [{"properties": {"show": lit("true"), "text": lit(f"'{text}'")}}]}


def shape_map(vid, x, y, w, h, resource, label):
    return {"$schema": VC_SCHEMA, "name": vid,
            "position": {"x": x, "y": y, "z": 0, "height": h, "width": w, "tabOrder": 0},
            "visual": {"visualType": "shapeMap",
                       "query": {"queryState": {
                           # bound to the state name (TopoJSON property state_name = dim_state[state_name] for all 37,
                           # checked by validate_phase6), so hover shows the name, not the P-code
                           "Category": {"projections": [proj("Column", "dim_state", "state_name")]},
                           "Value": {"projections": [proj("Measure", "fact_result_2023", "APC share")]}}},
                       "objects": {"shape": [{"properties": {
                           "map": {"geoJson": {
                               "type": lit("'packaged'"),
                               "name": lit(f"'{resource}'"),
                               "content": {"expr": {"ResourcePackageItem": {
                                   "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": resource}}}}},
                           "projectionEnum": lit("'mercator'")}}],
                                   # single-hue light-to-dark gradient on APC share (colour-blind safe; not red/green)
                                   "dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": {"FillRule": {
                                       "Input": {"Measure": {"Expression": {"SourceRef": {"Entity": "fact_result_2023"}},
                                                             "Property": "APC share"}},
                                       "FillRule": {"linearGradient2": {
                                           "min": {"color": {"Literal": {"Value": "'#DEEBF7'"}}},
                                           "max": {"color": {"Literal": {"Value": "'#08306B'"}}},
                                           "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'noColor'"}}}}}}}}}}},
                                       "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]},
                       "visualContainerObjects": title(label)}}


SCHEMAS = {  # Desktop drops "$schema" from these two on save; powerbi-report-author validate requires it
    PBIP / f"{NAME}.pbip": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
    RPT / "definition.pbir": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
}


def build_report():
    for path, schema in SCHEMAS.items():
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
        wjson(path, {"$schema": schema, **{k: v for k, v in obj.items() if k != "$schema"}})
    pid = CHECK_PAGE   # the Phase 3 thin-slice page, kept as a hidden "Model check" page for QA
    # register the two TopoJSON files as report resources
    rr = RPT / "StaticResources" / "RegisteredResources"
    rr.mkdir(parents=True, exist_ok=True)
    items = []
    for f in ("nga_states.topo.json", "nga_tiles.topo.json"):
        shutil.copyfile(PBIP / "assets" / f, rr / f)
        items.append({"name": f, "path": f, "type": "ShapeMap"})
    # decorative side-panel photos (scripts/build_photos.py; credits in photos_manifest.json)
    for old in rr.glob("photo_*.jpg"):
        old.unlink()
    for ph in json.loads((PBIP / "assets" / "photos" / "photos_manifest.json").read_text(encoding="utf-8"))["photos"]:
        f = Path(ph["output"]).name
        shutil.copyfile(PBIP / "assets" / "photos" / f, rr / f)
        items.append({"name": f, "path": f, "type": "Image"})
    shutil.copyfile(PBIP / "assets" / "photos" / "locator_states.png", rr / "locator_states.png")   # "Where is each state?"
    items.append({"name": "locator_states.png", "path": "locator_states.png", "type": "Image"})
    rep_path = RPT / "definition" / "report.json"
    rep = json.loads(rep_path.read_text(encoding="utf-8"))
    rep["resourcePackages"] = [p for p in rep["resourcePackages"] if p["name"] != "RegisteredResources"]
    rep["resourcePackages"].append({"name": "RegisteredResources", "type": "RegisteredResources", "items": items})
    wjson(rep_path, rep)

    card = {"$schema": VC_SCHEMA, "name": stable_id(pid, "card"),
            "position": {"x": 20, "y": 20, "z": 0, "height": 120, "width": 300, "tabOrder": 0},
            "visual": {"visualType": "cardVisual",
                       "query": {"queryState": {"Data": {"projections": [proj("Measure", "fact_result_2023", "APC votes")]}}},
                       # display units "1" = none, so the exact figure shows (must read 8,794,726)
                       "objects": {"value": [{"properties": {"labelDisplayUnits": lit("1D")}, "selector": {"id": "default"}}]},
                       "visualContainerObjects": title("APC votes, 2023 (INEC national: 8,794,726)")}}
    # Model check: one row per candidate from the disconnected dim_party. Must read 29 / 21 / 16 / 1 states at 25%+
    # and the INEC national votes per candidate.
    check = {"$schema": VC_SCHEMA, "name": stable_id(pid, "check_matrix"),
             "position": {"x": 340, "y": 10, "z": 0, "height": 215, "width": 920, "tabOrder": 0},
             "visual": {"visualType": "pivotTable",
                        "query": {"queryState": {
                            "Rows": {"projections": [proj("Column", "dim_party", "candidate")]},
                            "Values": {"projections": [proj("Measure", "fact_result_2023", "Candidate votes"),
                                                       proj("Measure", "fact_result_2023", "Candidate share"),
                                                       proj("Measure", "fact_result_2023", "States at 25% or more"),
                                                       proj("Measure", "fact_result_2023", "States with a computable share")]}}},
                        "objects": {"columnHeaders": [{"properties": {"columnAdjustment": lit("'growToFit'"),
                                                                      "autoSizeColumnWidth": lit("true")}}],
                                    "subTotals": [{"properties": {"rowSubtotals": lit("false")}}]},
                        "visualContainerObjects": title("Model check: national votes and units (36 states + FCT) at 25% or more "
                                                        "(expected 29 / 21 / 16 / 1 of 37)")}}
    visuals = [card, check,
               shape_map(stable_id(pid, "map_states"), 20, 240, 600, 470, "nga_states.topo.json",
                         "APC share of valid votes - state boundaries"),
               shape_map(stable_id(pid, "map_tiles"), 660, 240, 600, 470, "nga_tiles.topo.json",
                         "APC share of valid votes - equal-size tiles")]
    from pbip_pages import build_pages
    return build_pages(RPT, wjson, extra_hidden=(pid, "Model check (hidden)", visuals))


CHECK_PAGE = "3704ab6dfce14c89823a"

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    build_model()
    order = build_report()
    print(f"  model: {SM.relative_to(ROOT)}  (DataFolder = {DATA_FOLDER})")
    print(f"  report: {len(order)} pages ({len(order) - 1} visible + hidden model check)")
