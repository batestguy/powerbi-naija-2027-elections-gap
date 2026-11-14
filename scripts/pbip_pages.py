"""Phase 5 report pages (PBIR). Imported by scripts/build_pbip.py, which owns the model and writes these pages.

Design rules (docs/PLAN.md Phase 5): 25% is a fixed reference line; colours are colour-blind safe (Okabe-Ito blue /
orange / grey) and never the only signal (labels and tables carry the same information); every page states its
assumptions on the page; every visual has alt text and a tab order; slider slicers are single-value.
"""
import hashlib
import os

VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json"
PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
BLUE, ORANGE, GREY, INK, MUTED = "#0072B2", "#D55E00", "#767676", "#1F1F1F", "#505050"  # all >= 3:1 on white
W, H = 1280, 720


def sid(*parts, n=20):
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:n]


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def s(text):
    return lit("'" + text.replace("'", "''") + "'")


def col(table, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": prop}}


def meas(table, prop):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": prop}}


def proj(kind, table, prop, display=None):
    p = {"field": {kind: {"Expression": {"SourceRef": {"Entity": table}}, "Property": prop}},
         "queryRef": f"{table}.{prop}", "nativeQueryRef": prop}
    if display:
        p["displayName"] = display
    return p


def vco(title=None, alt=None, extra=None):
    o = {}
    if title is not None:
        o["title"] = [{"properties": {"show": lit("true"), "text": s(title)}}]
    else:
        o["title"] = [{"properties": {"show": lit("false")}}]
    if alt:
        o["general"] = [{"properties": {"altText": s(alt)}}]
    o["subTitle"] = [{"properties": {"show": lit("false")}}]   # hide Desktop's automatic "X by Y" subtitle
    o["padding"] = [{"properties": {k: lit("8D") for k in ("top", "bottom", "left", "right")}}]
    o.update(extra or {})
    return o


def container(name, x, y, w, h, visual, filter_config=None):
    c = {"$schema": VC, "name": name, "position": {"x": x, "y": y, "z": 0, "height": h, "width": w, "tabOrder": 0},
         "visual": visual}
    if filter_config:
        c["filterConfig"] = filter_config
    return c


# ---------------- visual builders ----------------

def textbox(name, x, y, w, h, paras, alt=None):
    """paras: list of (text, size_pt, bold, colour)."""
    def runs(t, sz, b, c):
        # "Lead. :: body" renders the lead in bold and the body in regular weight
        style = lambda bold: {"fontFamily": "Segoe UI Semibold" if bold else "Segoe UI", "fontSize": f"{sz}pt", "color": c}
        if " :: " in t:
            lead, body = t.split(" :: ", 1)
            return [{"value": lead + " ", "textStyle": style(True)}, {"value": body, "textStyle": style(False)}]
        return [{"value": t, "textStyle": style(b)}]
    paragraphs = [{"textRuns": runs(t, sz, b, c), "horizontalTextAlignment": "left"} for t, sz, b, c in paras]
    v = {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": paragraphs}}]},
         "visualContainerObjects": {"background": [{"properties": {"show": lit("false")}}],
                                    "border": [{"properties": {"show": lit("false")}}],
                                    "padding": [{"properties": {k: lit("0D") for k in ("top", "bottom", "left", "right")}}],
                                    **({"general": [{"properties": {"altText": s(alt)}}]} if alt else {})}}
    return container(name, x, y, w, h, v)


def cards(name, x, y, w, h, measures, title, alt, value_pt=None):
    """measures: list of (table, measure, display name). Labels and values wrap instead of being cut off."""
    vp = {"labelDisplayUnits": lit("1D"), "textWrap": lit("true")}
    if value_pt:
        vp["fontSize"] = lit(f"{value_pt}D")
    v = {"visualType": "cardVisual",
         "query": {"queryState": {"Data": {"projections": [proj("Measure", t, m, d) for t, m, d in measures]}}},
         "objects": {"value": [{"properties": vp, "selector": {"id": "default"}}],
                     "label": [{"properties": {"textWrap": lit("true")}, "selector": {"id": "default"}}]},
         "visualContainerObjects": vco(title, alt)}
    return container(name, x, y, w, h, v)


def candidate_slicer(name, x, y, w, h):
    """Single-select candidate dropdown, synced across pages, OTHERS hidden, APC pre-selected."""
    v = {"visualType": "slicer",
         "syncGroup": {"groupName": "candidate", "fieldChanges": True, "filterChanges": True},
         "query": {"queryState": {"Values": {"projections": [proj("Column", "dim_party", "candidate")]}}},
         "objects": {"data": [{"properties": {"mode": s("Dropdown")}}],
                     "selection": [{"properties": {"strictSingleSelect": lit("true"), "selectAllCheckboxEnabled": lit("false")}}],
                     "header": [{"properties": {"show": lit("true"), "text": s("Candidate")}}],
                     "general": [{"properties": {"filter": {"filter": {
                         "Version": 2, "From": [{"Name": "d", "Entity": "dim_party", "Type": 0}],
                         "Where": [{"Condition": {"In": {
                             "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "candidate"}}],
                             "Values": [[{"Literal": {"Value": "'" + os.environ.get("PBIP_CANDIDATE", "Bola Tinubu") + "'"}}]]}}}]}}}}]},
         "visualContainerObjects": vco(None, "Candidate selector: choose one of the four main 2023 candidates.")}
    fc = {"filters": [{"name": sid(name, "no_others"), "field": col("dim_party", "party"), "type": "Categorical",
                       "filter": {"Version": 2, "From": [{"Name": "d", "Entity": "dim_party", "Type": 0}],
                                  "Where": [{"Condition": {"Not": {"Expression": {"In": {
                                      "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": "party"}}],
                                      "Values": [[{"Literal": {"Value": "'OTHERS'"}}]]}}}}}]}}]}
    return container(name, x, y, w, h, v, fc)


def param_slicer(name, x, y, w, h, table, label, default, integer):
    """Single-value slider bound to a What-If table, pre-set to its neutral value."""
    val = f"{default}L" if integer else f"{default}D"
    v = {"visualType": "slicer",
         "query": {"queryState": {"Values": {"projections": [proj("Column", table, "Value")]}}},
         "objects": {"data": [{"properties": {"mode": s("Single"), "numericStart": lit(f"{default}D")}}],
                     "slider": [{"properties": {"show": lit("true")}}],
                     "header": [{"properties": {"show": lit("true"), "text": s(label)}}],
                     "general": [{"properties": {"filter": {"filter": {
                         "Version": 2, "From": [{"Name": "p", "Entity": table, "Type": 0}],
                         "Where": [{"Condition": {"Comparison": {"ComparisonKind": 0,
                                                                  "Left": {"Column": {"Expression": {"SourceRef": {"Source": "p"}}, "Property": "Value"}},
                                                                  "Right": {"Literal": {"Value": val}}}}}]}}}}]},
         "visualContainerObjects": vco(None, f"Slider: {label}. Neutral value {default}.")}
    return container(name, x, y, w, h, v)


def bar_chart(name, x, y, w, h, value, colour, title, alt, tooltips=()):
    """37 units ranked by share (desc), bars coloured by a measure returning a hex colour, fixed 25% line."""
    v = {"visualType": "clusteredColumnChart",   # upright columns: all 37 units fit across the width, no scrolling
         "query": {"queryState": {
             "Category": {"projections": [proj("Column", "dim_state", "state_name", "Unit")]},
             "Y": {"projections": [proj("Measure", value[0], value[1], value[2])]},
             **({"Tooltips": {"projections": [proj("Measure", t, m, d) for t, m, d in tooltips]}} if tooltips else {})},
             "sortDefinition": {"sort": [{"field": meas(value[0], value[1]), "direction": "Descending"}], "isDefaultSort": True}},
         "objects": {
             "dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": meas(colour[0], colour[1])}}}},
                            "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
             # 37 labels would overlap: exact shares are in the tooltip and in the tables on the page
             "labels": [{"properties": {"show": lit("false")}}],
             "categoryAxis": [{"properties": {"fontSize": lit("8D"), "showAxisTitle": lit("false"),
                                              "preferredCategoryWidth": lit("8D"), "innerPadding": lit("15L")}}],
             "valueAxis": [{"properties": {"start": lit("0D"), "showAxisTitle": lit("false")}}],
             "y1AxisReferenceLine": [{"properties": {"show": lit("true"), "value": lit("0.25D"), "style": s("dashed"),
                                                     "lineColor": {"solid": {"color": lit(f"'{INK}'")}},
                                                     "width": lit("2D"), "displayName": s("25%"),
                                                     "dataLabelShow": lit("true"), "dataLabelText": s("Name"),
                                                     "dataLabelColor": {"solid": {"color": lit(f"'{INK}'")}},
                                                     "dataLabelHorizontalPosition": s("right"),
                                                     "dataLabelVerticalPosition": s("above")},
                                      "selector": {"id": "1"}}]},
         "visualContainerObjects": vco(title, alt, {"visualTooltip": [{"properties": {"show": lit("true")}}]})}
    return container(name, x, y, w, h, v)


def matrix(name, x, y, w, h, rows, values, title, alt, sort=None):
    q = {"queryState": {"Rows": {"projections": [proj("Column", t, c, d) for t, c, d in rows]},
                        "Values": {"projections": [proj("Measure", t, m, d) for t, m, d in values]}}}
    if sort:
        q["sortDefinition"] = {"sort": [{"field": meas(*sort), "direction": "Descending"}], "isDefaultSort": True}
    v = {"visualType": "pivotTable", "query": q,
         "objects": {"columnHeaders": [{"properties": {"columnAdjustment": s("growToFit"), "autoSizeColumnWidth": lit("true")}}],
                     "subTotals": [{"properties": {"rowSubtotals": lit("false")}}]},
         "visualContainerObjects": vco(title, alt)}
    return container(name, x, y, w, h, v)


def shape_map(name, x, y, w, h, resource, value, title, alt):
    """Coloured by points above/below 25%: orange (below) - light grey at exactly 25% - blue (above), fixed at -25/0/+25."""
    v = {"visualType": "shapeMap",
         "query": {"queryState": {
             "Category": {"projections": [proj("Column", "dim_state", "state_pcode")]},
             "Value": {"projections": [proj("Measure", value[0], value[1], value[2])]},
             "Tooltips": {"projections": [proj("Measure", "scenario", "Scenario share", "Share"),
                                          proj("Measure", "scenario", "Scenario label", "Label")]}}},
         "objects": {"shape": [{"properties": {
             "map": {"geoJson": {"type": s("packaged"), "name": s(resource),
                                 "content": {"expr": {"ResourcePackageItem": {"PackageName": "RegisteredResources",
                                                                              "PackageType": 1, "ItemName": resource}}}}},
             "projectionEnum": s("mercator")}}],
             "dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": {"FillRule": {
                 "Input": meas(value[0], value[1]),
                 "FillRule": {"linearGradient3": {
                     "min": {"color": {"Literal": {"Value": f"'{ORANGE}'"}}, "value": {"Literal": {"Value": "-25D"}}},
                     "mid": {"color": {"Literal": {"Value": "'#F2F2F2'"}}, "value": {"Literal": {"Value": "0D"}}},
                     "max": {"color": {"Literal": {"Value": f"'{BLUE}'"}}, "value": {"Literal": {"Value": "25D"}}},
                     "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'noColor'"}}}}}}}}}}},
                 "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]},
         "visualContainerObjects": vco(title, alt, {"visualTooltip": [{"properties": {"show": lit("true")}}]})}
    return container(name, x, y, w, h, v)


# ---------------- pages ----------------

def header(pid, title, subtitle):
    return [textbox(sid(pid, "title"), 20, 8, 940, 34, [(title, 18, True, INK)], alt=title),
            textbox(sid(pid, "subtitle"), 20, 44, 940, 22, [(subtitle, 10, False, MUTED)], alt=subtitle),
            candidate_slicer(sid(pid, "candidate"), 1000, 4, 260, 76)]


SRC = "Baseline: 2023 presidential result per unit, reconciled from five copies of INEC's declaration - not INEC's own state sheets."
KEY = ("Colour key: blue = 25% or more (secured); vermillion (dark orange) = 20% to under 25% (within reach); grey = under 20% "
       "(out of reach). The dashed line marks 25%. Hover a column for its label and share; the Path to 24 page lists "
       "every unit with its label in words.")


def page_overview(pid):
    v = header(pid, "Candidate overview: the 2023 baseline", SRC)
    v.append(cards(sid(pid, "kpis"), 20, 86, 1240, 104,
                   [("fact_result_2023", "Candidate votes", "Votes, 2023"), ("fact_result_2023", "Candidate share", "Share of valid votes"),
                    ("scenario", "Candidate national rank", "National rank"),
                    ("fact_result_2023", "States at 25% or more", "Units at 25% or more (of 37)"),
                    ("fact_result_2023", "States with a computable share", "Units with data")],
                   None, "Headline figures for the selected candidate in 2023: votes, share, national rank, "
                         "units at 25% or more out of 37, and units with data."))
    v.append(bar_chart(sid(pid, "bars"), 20, 194, 1240, 250, ("fact_result_2023", "Candidate share", "Share of valid votes"),
                       ("scenario", "Baseline label colour"),
                       "Share of valid votes in each unit, 2023 (dashed line = 25%)",
                       "Bar chart of the selected candidate's 2023 share in all 37 units, highest first, with a fixed line at 25%. "
                       "Blue bars are at or above 25%, vermillion 20 to 25%, grey below 20%.",
                       tooltips=[("scenario", "Baseline label", "Label"), ("fact_result_2023", "Candidate votes", "Votes")]))
    v.append(matrix(sid(pid, "zones"), 20, 450, 560, 262, [("dim_zone", "zone", "Zone")],
                    [("fact_result_2023", "Candidate share", "Share"), ("fact_result_2023", "States at 25% or more", "Units at 25%+"),
                     ("fact_result_2023", "States with a computable share", "Units")],
                    "By geopolitical zone", "Table of the selected candidate's 2023 share and units at 25% or more in each of the six zones."))
    v.append(textbox(sid(pid, "notes"), 600, 456, 660, 256, [
        (KEY, 9, False, INK),
        ("The rule counts 37 units: the 36 states plus the FCT. Without the FCT, Peter Obi has 15 units, not 16.", 9, False, INK),
        ("Notes on specific candidates. Close calls: Tinubu is 96 votes above 25% in Adamawa and 845.5 below in Edo. Valid votes carry an unexplained "
         "4,858-vote excess in the minor-candidates column, larger than the Adamawa margin, so 29 could be 28 or 30.", 9, False, INK),
        ("Kano (Tinubu): 506,412 used; three of four copies print 517,341. Either way he is above 25% there.", 9, False, INK)],
        alt="Notes: colour key, how the 37 units are counted, close calls and data gaps."))
    return "Candidate overview", v


def page_path(pid):
    v = header(pid, "Path to 24: which units carry the 25% test", "2023 baseline (reconciled from five copies of INEC's declaration). Move the sliders on the Simulator page.")
    v.append(cards(sid(pid, "kpis"), 20, 86, 1240, 104,
                   [("scenario", "Units secured (national)", "Units at 25%+"), ("scenario", "Units needed (rule)", "Units needed"),
                    ("scenario", "Units still needed", "Still needed"), ("scenario", "Clears the rule", "Clears the 25% rule"),
                    ("scenario", "Tipping-point unit", "Tipping-point unit"),
                    ("scenario", "Tipping-point gap (points)", "Tipping point: short of 25% (pts)")],
                   None, "Counts for the 25% rule: units at 25% or more, units needed, still needed, whether the rule is "
                         "cleared, the tipping-point unit and its distance from 25%."))
    v.append(bar_chart(sid(pid, "bars"), 20, 194, 1240, 296, ("scenario", "Scenario share", "Share"),
                       ("scenario", "Path column colour"),
                       "37 units ranked by share (dashed line = 25%; black column = tipping-point unit)",
                       "Bar chart of all 37 units ranked by the selected candidate's share, with a fixed 25% line; colour shows "
                       "secured, within reach or out of reach. Hover for votes needed to reach 25%.",
                       tooltips=[("scenario", "Unit rank", "Rank"), ("scenario", "Scenario label", "Label"),
                                 ("scenario", "Points needed", "Points needed"),
                                 ("scenario", "Votes needed", "Votes needed")]))
    v.append(matrix(sid(pid, "table"), 20, 496, 760, 216, [("dim_state", "state_name", "Unit")],
                    [("scenario", "Unit rank", "Rank"), ("scenario", "Scenario label", "Label"), ("scenario", "Scenario share", "Share"),
                     ("scenario", "Points needed", "Points to 25%"), ("scenario", "Votes needed", "Votes to switch")],
                    "Every unit: label and distance to 25%",
                    "Table of all 37 units with label, share, points needed and votes needed to reach 25%.",
                    sort=("scenario", "Scenario share")))
    v.append(textbox(sid(pid, "notes"), 800, 496, 460, 216, [
        ("Colour key: blue = 25% or more (secured); vermillion (dark orange) = 20% to under 25% (within reach); grey = "
         "under 20% (out of reach); black = the tipping-point unit. The dashed line marks 25%. The table spells out every "
         "unit's label and rank.", 9, False, INK),
        ("Tipping-point unit: rank all 37 units by share; it is the unit in position 24 - the weakest one the candidate needs "
         "(a negative 'short of 25%' means it is already above 25%). "
         "Votes to switch: votes that would have to move to the candidate from others, with the unit's total unchanged.", 9, False, INK)],
        alt="Notes: colour key, tipping-point and votes-to-switch definitions."))
    return "Path to 24", v


def page_map(pid):
    v = header(pid, "Spread map: where the 25% hold is strong or fragile", SRC + " Colour = points above or below 25%.")
    v.append(shape_map(sid(pid, "geo"), 20, 86, 410, 512, "nga_states.topo.json",
                       ("scenario", "Points from 25%", "Points from 25%"), "State boundaries",
                       "Map of Nigeria's 37 units coloured by the selected candidate's share relative to 25%: blue above, "
                       "vermillion below, near-white close to 25%."))
    v.append(shape_map(sid(pid, "tiles"), 438, 86, 410, 512, "nga_tiles.topo.json",
                       ("scenario", "Points from 25%", "Points from 25%"), "Equal-size tiles (every unit the same size)",
                       "Tile map with one equal square per unit, same colours as the state map, so small states are as "
                       "visible as large ones."))
    v.append(matrix(sid(pid, "list"), 856, 86, 404, 512, [("dim_state", "state_name", "Unit")],
                    [("scenario", "Scenario label", "Label"), ("scenario", "Points from 25%", "Points vs 25%")],
                    "Every unit in words", "Table of all 37 units with their label and points above or below 25%, "
                    "the same information as the map colours.", sort=("scenario", "Points from 25%")))
    v.append(cards(sid(pid, "counts"), 20, 606, 600, 106,
                   [("scenario", "Units secured", "Secured (25%+)"), ("scenario", "Units within reach", "Within reach (20-25%)"),
                    ("scenario", "Units out of reach", "Out of reach (<20%)")],
                   None, "Counts of units secured, within reach and out of reach for the selected candidate."))
    v.append(textbox(sid(pid, "notes"), 640, 606, 620, 106, [
        ("Colour scale is fixed: deep vermillion = 25 or more points below 25%; near-white = at 25%; deep blue = 25 or more "
         "points above. Hover a unit for its share and label. Large states are not more important: the rule counts "
         "units, which is why the equal-size tiles are shown.", 9, False, INK)],
        alt="Notes: how to read the map colours."))
    return "Spread map", v


def page_sim(pid):
    v = [textbox(sid(pid, "title"), 20, 8, 940, 34, [("Scenario simulator: what if 2027 differs?", 18, True, INK)],
                 alt="Scenario simulator"),
         textbox(sid(pid, "subtitle"), 20, 44, 940, 22,
                 [("Move the sliders. Every figure on this page updates. A what-if tool, not a forecast.", 10, False, MUTED)],
                 alt="Move the sliders; every figure updates. A what-if tool, not a forecast."),
         candidate_slicer(sid(pid, "candidate"), 1000, 4, 260, 76)]
    # sliders: 2 columns x 5 rows, each tall enough (120) for Desktop to draw the slider bar under the value box.
    # PBIP_SLIDER_PROBE=1 builds a test variant with non-neutral defaults (national +5, SE -3) to prove propagation.
    probe = os.environ.get("PBIP_SLIDER_PROBE") == "1"
    defaults = {"param_swing_national": 5 if probe else 0, "param_swing_SE": -3 if probe else 0}
    sliders = [("turnout", "param_turnout", "Supporter turnout vs others (%)", True),
               ("national", "param_swing_national", "National swing (points)", False),
               ("zone_NC", "param_swing_NC", "North Central + FCT", False), ("zone_NE", "param_swing_NE", "North East", False),
               ("zone_NW", "param_swing_NW", "North West", False), ("zone_SE", "param_swing_SE", "South East", False),
               ("zone_SS", "param_swing_SS", "South South", False), ("zone_SW", "param_swing_SW", "South West", False)]
    for i, (key, table, label, integer) in enumerate(sliders):
        lab = label if i < 2 else f"{label} swing (pts)"
        v.append(param_slicer(sid(pid, key), 20 + (i % 2) * 206, 86 + (i // 2) * 122, 200, 120, table, lab,
                              defaults.get(table, 0), integer))
    v.append(param_slicer(sid(pid, "rule"), 20, 574, 200, 120, "param_rule", "Units needed (24 or 25)", 24, True))
    v.append(textbox(sid(pid, "assume"), 226, 578, 200, 134, [
        ("Assumptions: same swing in every unit of a zone (national + zone), capped 0-100%; supporter turnout = the "
         "candidate's 2023 voters only; rivals move in proportion to their 2023 shares. See 'How to read this'.", 9, False, INK)],
        alt="Assumptions behind the simulator."))
    v.append(cards(sid(pid, "verdict"), 440, 86, 820, 80, [("scenario", "Verdict", "Verdict")],
                   None, "Verdict for the scenario: outright win, run-off or loses.", value_pt=18))
    v.append(cards(sid(pid, "who"), 440, 170, 820, 80,
                   [("scenario", "Has most votes", "Most votes?"), ("scenario", "Leading rival", "Leading rival"),
                    ("scenario", "Tipping-point unit", "Tipping point"), ("scenario", "Tipping-point gap (points)", "Short of 25% (pts)")],
                   None, "Whether the candidate has the most votes nationally, the leading rival, the tipping-point unit and "
                         "its gap to 25% in points (negative = above 25%).", value_pt=16))
    v.append(cards(sid(pid, "counts"), 440, 254, 820, 80,
                   [("scenario", "Units secured (national)", "Secured /37"), ("scenario", "Units still needed", "Still needed"),
                    ("scenario", "Scenario national share", "National share"), ("scenario", "Units at a cap", "Capped units")],
                   None, "Scenario counters: units secured out of 37, units still needed, national share and units held at "
                         "the 0% or 100% cap.", value_pt=16))
    v.append(shape_map(sid(pid, "tiles"), 440, 340, 500, 372, "nga_tiles.topo.json",
                       ("scenario", "Points from 25%", "Points from 25%"), "Each unit under this scenario",
                       "Tile map, one square per unit, recoloured by the scenario: blue above 25%, vermillion below."))
    v.append(cards(sid(pid, "inforce"), 950, 340, 310, 130, [("scenario", "Assumptions in force", "Settings the engine is using")],
                   None, "Text listing every slider setting currently applied.", value_pt=10))
    v.append(textbox(sid(pid, "key"), 950, 478, 310, 234, [
        ("Reading the verdict", 9, True, INK),
        ("'Short of 25%' at the tipping point: negative means above 25%. "
         "Outright win = most votes and 25% in the needed number of units. Run-off = nobody meets both. "
         "'Loses' = a rival meets both. Who would contest a run-off is not modelled.", 9, False, INK),
        ("Map: blue above 25%, vermillion below, near-white at 25%; hover a tile for its share and label. "
         "Units at a cap means a slider pushed a share past 0% or "
         "100% and it was held there.", 9, False, INK)],
        alt="How to read the verdict and the map."))
    return "Scenario simulator", v


HOW = [
    ("How to read this report", 18, True, INK),
    ("The rule. :: To win outright, a presidential candidate needs the most votes nationally and at least 25% of the votes in at "
     "least two-thirds of the states. We count 37 units (36 states plus the FCT) and use 24 as the default; 25 is offered as a "
     "stricter reading. This is our reading of section 134 of the Constitution, checked against an unofficial copy.", 10, False, INK),
    ("What the numbers are. :: 2023 results per unit, reconciled from five secondary copies of INEC's declaration, because INEC's "
     "own state sheet is not public. PDP and NNPP state totals add up to INEC's national declaration with no adjustment; "
     "for APC and Labour they match because three disputed cells were chosen to make them match. The minor-candidates "
     "column is 4,858 votes too high nationally, and nobody can yet say where.", 10, False, INK),
    ("What the simulator assumes. :: Swing adds the same number of points in every unit of a zone. Supporter turnout changes only "
     "the candidate's own 2023 voters. Rivals gain or lose in proportion to their 2023 shares. No new candidates, mergers or "
     "boundary changes. It is a what-if tool, not a forecast: it says nothing about how likely a scenario is.", 10, False, INK),
    ("What it does not claim. :: It is not an electoral authority and not INEC's figures. It has no local-government detail. "
     "Small swings near 25% are within the data's uncertainty: for example, Tinubu's 2023 count of 29 rests on 96 votes "
     "in Adamawa.", 10, False, INK),
    ("Full method: docs/methodology.md. Data profile and gaps: docs/data-profile.md (both in the project repository).", 9, False, MUTED),
]
SOURCES = [
    ("Data sources", 18, True, INK),
    ("State results (2023): :: five copies of INEC's declaration, compared cell by cell - Wikipedia '2023 Nigerian presidential "
     "election' By-state table (revision 1381904162, CC BY-SA 4.0); AGADA-BI state table (no licence stated; one of five "
     "copies, and with Wikipedia the only per-state source for the minor-candidates column; its value is used for Kano APC); "
     "thenigerialawyer.com and ThisDay (identical copies; news pages, licence not stated); Vanguard (news page, licence and "
     "terms not checked; fetched once with a browser identity after the site refused our scripted request). Vote counts are "
     "used as facts with credit. Accessed 13-14 Nov 2026. Limitation: not INEC's own state sheets; 3 cells decided by hand "
     "(Kano APC, two Labour ties).", 10, False, INK),
    ("National totals: :: INEC, Report of the 2023 General Election, Annexure 2 (national Declaration of Results), via a copy "
     "hosted on thenigerialawyer.com (not found on INEC's site); public report, licence not stated. Accessed 14 Nov 2026.",
     10, False, INK),
    ("Registered voters: :: the 37 Wikipedia state pages (CC BY-SA 4.0). Limitation: they sum to 120,281 fewer than INEC's "
     "93,469,008.", 10, False, INK),
    ("Zones: :: Wikipedia 'Geopolitical zones of Nigeria' (CC BY-SA 4.0). State boundaries: HDX COD-AB Nigeria (CC BY-IGO), "
     "simplified. Equal-size tile layout: our own.", 10, False, INK),
    ("Sources, access dates, licences and transforms are listed in registers/sources.md and in the data manifests "
     "(data/raw/*/manifest.json, data/staging/manifest.json) in the project repository.", 9, False, MUTED),
]


def page_text(pid, title, paras):
    spaced = []
    for i, (txt, sz, b, c) in enumerate(paras):
        spaced.append((txt, sz if i == 0 else max(sz, 12) if sz >= 10 else 10, b, c))
        spaced.append((" ", 8, False, c))
    return title, [textbox(sid(pid, "body"), 40, 24, 1200, 680, spaced, alt=title)]


PAGES = [("overview", page_overview), ("path", page_path), ("map", page_map), ("simulator", page_sim),
         ("howto", lambda p: page_text(p, "How to read this", HOW)), ("sources", lambda p: page_text(p, "Data sources", SOURCES))]


def build_pages(report_dir, write_json, extra_hidden=None):
    """Writes all pages; returns the ordered list of page ids. extra_hidden: (pid, displayName, visuals) appended hidden."""
    import shutil
    pages_dir = report_dir / "definition" / "pages"
    keep = {extra_hidden[0]} if extra_hidden else set()
    for d in pages_dir.iterdir():
        if d.is_dir() and d.name not in keep:
            shutil.rmtree(d)
    order = []
    all_pages = [(sid("page", key), fn) for key, fn in PAGES]
    for pid, fn in all_pages:
        display, visuals = fn(pid)
        write_page(pages_dir, pid, display, visuals, write_json)
        order.append(pid)
    if extra_hidden:
        pid, display, visuals = extra_hidden
        write_page(pages_dir, pid, display, visuals, write_json, hidden=True)
        order.append(pid)
    write_json(pages_dir / "pages.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": order, "activePageName": order[0]})
    return order


def write_page(pages_dir, pid, display, visuals, write_json, hidden=False):
    import shutil
    d = pages_dir / pid
    if (d / "visuals").exists():
        shutil.rmtree(d / "visuals")
    page = {"$schema": PAGE, "name": pid, "displayName": display, "displayOption": "FitToPage", "height": H, "width": W}
    # Clicking a chart, table or map must not silently change other visuals (e.g. headline cards showing one zone):
    # only slicers filter. Every data visual -> every other visual = NoFilter.
    sources = [v["name"] for v in visuals if v["visual"]["visualType"] not in ("slicer", "textbox")]
    page["visualInteractions"] = [{"source": a, "target": c["name"], "type": "NoFilter"}
                                  for a in sources for c in visuals if c["name"] != a and c["visual"]["visualType"] != "textbox"]
    if hidden:
        page["visibility"] = "HiddenInViewMode"
    write_json(d / "page.json", page)
    for i, v in enumerate(visuals):
        v["position"]["tabOrder"] = i
        v["position"]["z"] = i
        write_json(d / "visuals" / v["name"] / "visual.json", v)
