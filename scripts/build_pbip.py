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
                                    ("is_fct", "int64", "Int64.Type", "none")]),
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
PARAMS = {  # table: (DAX series, default, format, dataType)
    "param_turnout": ("GENERATESERIES ( -50, 50, 1 )", 0, "0", "int64"),
    "param_swing_national": ("GENERATESERIES ( -20, 20, 0.5 )", 0, "0.0", "double"),
    **{f"param_swing_{z}": ("GENERATESERIES ( -20, 20, 0.5 )", 0, "0.0", "double") for z in ZONES},
    "param_rule": ("GENERATESERIES ( 24, 25, 1 )", 24, "0", "int64"),
}
CALC_TABLES = {**{t: (src, "Value", dt, fmt, False) for t, (src, _, fmt, dt) in PARAMS.items()},
               "scenario": ('{ "Scenario measures - see docs/methodology.md" }', "Value", "string", None, True)}
OK = f'VAR c = {SEL} RETURN NOT ISBLANK ( c ) && c <> "OTHERS"'   # a single real candidate is selected
SHARE = "[Scenario share]"
NATIONAL = "REMOVEFILTERS ( dim_state ), REMOVEFILTERS ( dim_zone )"   # all 37 units, whatever the page filters
MEASURES["scenario"] = [
    # inputs
    ("Supporter turnout", "SELECTEDVALUE ( param_turnout[Value], 0 ) / 100", "0%"),
    ("National swing", "SELECTEDVALUE ( param_swing_national[Value], 0 )", "+0.0;-0.0;0.0"),
    ("Zone swing", "SWITCH ( SELECTEDVALUE ( dim_state[zone_code] ), "
                   + ", ".join(f'"{z}", SELECTEDVALUE ( param_swing_{z}[Value], 0 )' for z in ZONES) + " )",
     "+0.0;-0.0;0.0"),
    ("Units needed (rule)", "SELECTEDVALUE ( param_rule[Value], 24 )", "0"),
    ("Candidate is valid", OK, None),
    # per unit (one state in context), steps 1-3 of the note
    # DAX names are case-insensitive: candidate votes = cv, valid votes = tv (never v / V)
    ("Scenario valid votes", "VAR cv = [Candidate votes] VAR tv = [Valid votes] RETURN IF ( [Candidate is valid] && "
                             "HASONEVALUE ( dim_state[state_pcode] ) && NOT ISBLANK ( cv ) && tv > 0, tv + cv * [Supporter turnout] )",
     "#,0"),
    ("Scenario share uncapped", "VAR cv = [Candidate votes] VAR tv = [Valid votes] VAR t = [Supporter turnout] "
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
]
for t, (_, dflt, fmt, _dt) in PARAMS.items():
    MEASURES[t] = [(f"{t} value", f"SELECTEDVALUE ( {t}[Value], {dflt} )", fmt)]


def calc_table_tmdl(name):
    src, col, dt, fmt, hidden = CALC_TABLES[name]
    out = [f"table {name}", f"\tlineageTag: {stable_uuid('table', name)}", ""]
    for mname, expr, mfmt in MEASURES.get(name, []):
        out += [f"\tmeasure '{mname}' = {expr}"] + ([f"\t\tformatString: {mfmt}"] if mfmt else []) + \
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
                                      + [f"ref table {t}" for t in list(TABLES) + list(CALC_TABLES)]) + "\n\n")
    path = DATA_FOLDER.replace('"', '""')
    write(d / "expressions.tmdl",
          f'expression DataFolder = "{path}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n'
          f"\tlineageTag: {stable_uuid('expr', 'DataFolder')}\n\n\tannotation PBI_ResultType = Text\n\n")
    for t, (csv_name, cols) in TABLES.items():
        write(d / "tables" / f"{t}.tmdl", table_tmdl(t, csv_name, cols) + "\n")
    for t in CALC_TABLES:
        write(d / "tables" / f"{t}.tmdl", calc_table_tmdl(t) + "\n")
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
                           "Category": {"projections": [proj("Column", "dim_state", "state_pcode")]},
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
    page_dir = next((RPT / "definition" / "pages").glob("*/page.json")).parent
    pid = page_dir.name
    vis = page_dir / "visuals"
    if vis.exists():
        shutil.rmtree(vis)
    # register the two TopoJSON files as report resources
    rr = RPT / "StaticResources" / "RegisteredResources"
    rr.mkdir(parents=True, exist_ok=True)
    items = []
    for f in ("nga_states.topo.json", "nga_tiles.topo.json"):
        shutil.copyfile(PBIP / "assets" / f, rr / f)
        items.append({"name": f, "path": f, "type": "ShapeMap"})
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
    for i, v in enumerate(visuals):
        v["position"]["tabOrder"] = i
        wjson(vis / v["name"] / "visual.json", v)
    return pid


if __name__ == "__main__":
    build_model()
    pid = build_report()
    print(f"  model: {SM.relative_to(ROOT)}  (DataFolder = {DATA_FOLDER})")
    print(f"  report page {pid}: card + model-check matrix + 2 shape maps")
