"""Report pages (PBIR). Imported by scripts/build_pbip.py, which owns the model and writes these pages.

Design rules (docs/PLAN.md Phase 5, user review 2026-11-14): plain words on every page except "Technical notes", which
carries the terms and formulas; 25% is a fixed, bold wine-coloured reference line; colours are colour-blind safe
(Okabe-Ito blue / vermillion / grey, Tol wine for the 25% line) and never the only signal (a key of coloured lines with
words sits next to every coloured chart or map, and tables carry the same information); every page states its
assumptions on the page; every visual has alt text and a tab order; slider slicers are single-value. Each visible page
has one decorative election photo in a tall side panel (left or right, whichever fits the layout), credited under the
photo and on the Data sources page, last in tab order, never behind a chart or text.
"""
import hashlib
import json
import os
from pathlib import Path

VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.9.0/schema.json"
PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
# contrast on white: blue 5.19, vermillion 3.87, grey 4.54, wine 9.6, ink 16.6, muted 7.7 (all >= 3:1; text >= 4.5:1)
BLUE, ORANGE, GREY, WINE, INK, MUTED = "#0072B2", "#D55E00", "#767676", "#882255", "#1F1F1F", "#505050"
W, H = 1280, 720
PHOTOS = {p["key"]: p for p in json.loads((Path(__file__).resolve().parent.parent / "pbip" / "assets" / "photos" /
                                           "photos_manifest.json").read_text(encoding="utf-8"))["photos"]}
_ASSETS = Path(__file__).resolve().parent.parent
CANDS = {c["party"]: c for c in json.loads((_ASSETS / "pbip" / "assets" / "photos" / "candidates_manifest.json")
                                           .read_text(encoding="utf-8"))["candidates"]}
with open(_ASSETS / "data" / "reference" / "party_now.csv", encoding="utf-8") as _f:
    import csv as _csv
    PARTY_NOW = list(_csv.DictReader(l for l in _f if not l.startswith("#")))
for _r in PARTY_NOW:
    CANDS[_r["party_2023"]]["candidate"] = _r["candidate"]
with open(_ASSETS / "data" / "reference" / "coalition_names.csv", encoding="utf-8") as _f:
    COAL_NAMES = list(_csv.DictReader(l for l in _f if not l.startswith("#")))
with open(_ASSETS / "data" / "staging" / "dim_state.csv", encoding="utf-8") as _f:
    CODES = sorted((r["state_code"], r["state_name"]) for r in _csv.DictReader(_f))
CODE_LIST = " \u00b7 ".join(f"{c} {n}" for c, n in CODES)
LOGO_LIST = json.loads((_ASSETS / "pbip" / "assets" / "photos" / "logos_manifest.json").read_text(encoding="utf-8"))["logos"]
PW, PH, PY = 190, 560, 86          # photo panel (report px); build_photos.py crops to the same shape
LEFT_X, RIGHT_X = 20, W - 20 - PW  # photo panel on the left or the right
BAR = "███"         # a short thick bar (three full blocks), coloured, in the colour keys


def sid(*parts, n=20):
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:n]


TILE_TIP = sid("page", "tiletip")   # hidden tooltip page shown when hovering a tile map square

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
    """paras: list of (text, size_pt, bold, colour). text may also be a list of runs [(text, colour, bold), ...]."""
    def style(sz, b, c):
        return {"fontFamily": "Segoe UI Semibold" if b else "Segoe UI", "fontSize": f"{sz}pt", "color": c}

    def runs(t, sz, b, c):
        if isinstance(t, list):
            return [{"value": rt, "textStyle": style(sz, rb, rc)} for rt, rc, rb in t]
        # "Lead. :: body" renders the lead in bold and the body in regular weight
        if " :: " in t:
            lead, body = t.split(" :: ", 1)
            return [{"value": lead + " ", "textStyle": style(sz, True, c)}, {"value": body, "textStyle": style(sz, False, c)}]
        return [{"value": t, "textStyle": style(sz, b, c)}]
    paragraphs = [{"textRuns": runs(t, sz, b, c), "horizontalTextAlignment": "left"} for t, sz, b, c in paras]
    v = {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": paragraphs}}]},
         "visualContainerObjects": {"background": [{"properties": {"show": lit("false")}}],
                                    "border": [{"properties": {"show": lit("false")}}],
                                    "padding": [{"properties": {k: lit("0D") for k in ("top", "bottom", "left", "right")}}],
                                    **({"general": [{"properties": {"altText": s(alt)}}]} if alt else {})}}
    return container(name, x, y, w, h, v)


def key_runs(items, sep="     "):
    """Colour key as text runs: a short thick coloured line, then its meaning in words (colour is never alone)."""
    out = []
    for i, (colour, meaning, *glyph) in enumerate(items):
        out += [(("" if i == 0 else sep) + (glyph[0] if glyph else BAR) + " ", colour, True), (meaning, INK, False)]
    return out


def key_box(name, x, y, w, h, items, alt, title="Colour key", stacked=False, size=9):
    """A key built from coloured lines + words. stacked: one item per line; otherwise one wrapped line."""
    if stacked:
        paras = [(title, size, True, INK)] + [(key_runs([it]), size, False, INK) for it in items]
    else:   # title inline, so the key takes at most two lines
        paras = [([(title + ":   ", INK, True)] + key_runs(items), size, False, INK)]
    return textbox(name, x, y, w, h, paras, alt=alt)


STATUS_KEY = [(BLUE, "a quarter of the vote or more (state won: \"Secured\")"),
              (ORANGE, "20% to just under a quarter (\"Within reach\")"),
              (GREY, "under 20% (\"Out of reach\")"),
              (WINE, "the 25% line: a quarter of the vote")]
STATUS_ALT = ("Colour key: blue line = a quarter of the vote or more, state won; vermillion = 20% to just under a quarter, "
              "within reach; grey = under 20%, out of reach; wine-coloured line = a quarter of the vote (25%).")
MAP_KEY = [(BLUE, "blue: above a quarter (the deeper, the safer)"),
           (GREY, "white or pale: close to a quarter", "□□□"),   # outlined squares = a pale fill
           (ORANGE, "vermillion: below a quarter (the deeper, the further away)")]
MAP_ALT = ("Map colour key: blue = above a quarter of the vote, deeper blue is safer; white or pale = close to a quarter; "
           "vermillion = below a quarter, deeper is further away. The scale is fixed at 25 points either side.")


def cards(name, x, y, w, h, measures, title, alt, value_pt=None, label_pt=None, accent=True, border=None):
    """measures: list of (table, measure, display name). Labels and values wrap instead of being cut off.
    accent: a 2 px border in the selected candidate's party colour (decoration only; never encodes data)."""
    vp = {"labelDisplayUnits": lit("1D"), "textWrap": lit("true")}
    if value_pt:
        vp["fontSize"] = lit(f"{value_pt}D")
    lp = {"textWrap": lit("true")}
    if label_pt:
        lp["fontSize"] = lit(f"{label_pt}D")
    v = {"visualType": "cardVisual",
         "query": {"queryState": {"Data": {"projections": [proj("Measure", t, m, d) for t, m, d in measures]}}},
         "objects": {"value": [{"properties": vp, "selector": {"id": "default"}}],
                     "label": [{"properties": lp, "selector": {"id": "default"}}]},
         "visualContainerObjects": vco(title, alt)}
    if accent:
        v["visualContainerObjects"]["border"] = [{"properties": {
            "show": lit("true"), "color": {"solid": {"color": {"expr": meas("scenario", "Party accent colour")}}},
            "width": lit("2D")}}]
    elif border:
        v["visualContainerObjects"]["border"] = [{"properties": {
            "show": lit("true"), "color": {"solid": {"color": lit(f"'{border}'")}}, "width": lit("2D")}}]
    return container(name, x, y, w, h, v)


def party_card(name, x, y, w, h, measure, alt, value_pt):
    """Card filled with the selected candidate's party colour; text white or ink, whichever passes 4.5:1 (measure)."""
    c = classic_card(name, x, y, w, h, measure, None, alt, value_pt, colour="Party accent text colour", accent=False)
    c["visual"]["visualContainerObjects"]["background"] = [{"properties": {
        "show": lit("true"), "color": {"solid": {"color": {"expr": meas("scenario", "Party accent colour")}}},
        "transparency": lit("0D")}}]
    c["visual"]["visualContainerObjects"]["padding"] = [{"properties": {k: lit("4D") for k in ("top", "bottom", "left", "right")}}]
    return c


def candidate_photo(name, x, y, w, h, measure="Candidate photo", alt=None):
    """An image visual whose URL is a measure (base64 data URI, works offline): the selected candidate's portrait, or
    a party logo."""
    v = {"visualType": "image",
         "objects": {"image": [{"properties": {"sourceType": s("imageUrl"),
                                               "sourceUrl": {"expr": meas("scenario", measure)}}}],
                     "imageScaling": [{"properties": {"imageScalingType": s("Fit")}}]},
         "visualContainerObjects": {"title": [{"properties": {"show": lit("false")}}],
                                    "background": [{"properties": {"show": lit("false")}}],
                                    "border": [{"properties": {"show": lit("false")}}],
                                    "padding": [{"properties": {k: lit("0D") for k in ("top", "bottom", "left", "right")}}],
                                    "general": [{"properties": {"altText": s(alt or
                                        "Photo of the selected candidate (free-licence portrait; credit on the Data "
                                        "sources page).")}}]}}
    return container(name, x, y, w, h, v)


def classic_card(name, x, y, w, h, measure, title, alt, value_pt, colour=None, accent=True, bold=True, border=None):
    """Classic card: its value wraps onto several lines in a small box (the new card truncated long text to one line).
    title: shown as the visual title (None hides it); colour: a measure name returning the text colour."""
    lab = {"fontSize": lit(f"{value_pt}D"), "fontFamily": s("Segoe UI Semibold" if bold else "Segoe UI")}
    lab["color"] = {"solid": {"color": ({"expr": meas("scenario", colour)} if colour else lit(f"'{INK}'"))}}
    v = {"visualType": "card",
         "query": {"queryState": {"Values": {"projections": [proj("Measure", "scenario", measure)]}}},
         "objects": {"labels": [{"properties": lab}], "categoryLabels": [{"properties": {"show": lit("false")}}],
                     "wordWrap": [{"properties": {"show": lit("true")}}]},
         "visualContainerObjects": vco(title, alt)}
    if title is not None:
        v["visualContainerObjects"]["title"][0]["properties"].update({"fontSize": lit("9D"), "fontColor": {"solid": {"color": lit(f"'{MUTED}'")}}})
    if accent:
        v["visualContainerObjects"]["border"] = [{"properties": {
            "show": lit("true"), "color": {"solid": {"color": {"expr": meas("scenario", "Party accent colour")}}},
            "width": lit("2D")}}]
    elif border:
        v["visualContainerObjects"]["border"] = [{"properties": {
            "show": lit("true"), "color": {"solid": {"color": lit(f"'{border}'")}}, "width": lit("2D")}}]
    return container(name, x, y, w, h, v)


def sentence(name, x, y, w, h, measure, label, alt, value_pt=11, accent=True, border=None):
    """One long text measure shown as a wrapped sentence under a small title."""
    return classic_card(name, x, y, w, h, measure, label, alt, value_pt, accent=accent, border=border)


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


def param_slicer(name, x, y, w, h, table, label, default, integer, sync=None, hidden=False):
    """Single-value slider bound to a What-If table, pre-set to its neutral value. Its plain-words label is a textbox
    above it (slicer headers cannot wrap), so the slicer header is hidden."""
    val = f"{default}L" if integer else f"{default}D"
    v = {"visualType": "slicer",
         "query": {"queryState": {"Values": {"projections": [proj("Column", table, "Value")]}}},
         "objects": {"data": [{"properties": {"mode": s("Single"), "numericStart": lit(f"{default}D")}}],
                     "slider": [{"properties": {"show": lit("true")}}],
                     "header": [{"properties": {"show": lit("false"), "text": s(label)}}],
                     "general": [{"properties": {"filter": {"filter": {
                         "Version": 2, "From": [{"Name": "p", "Entity": table, "Type": 0}],
                         "Where": [{"Condition": {"Comparison": {"ComparisonKind": 0,
                                                                  "Left": {"Column": {"Expression": {"SourceRef": {"Source": "p"}}, "Property": "Value"}},
                                                                  "Right": {"Literal": {"Value": val}}}}}]}}}}]},
         "visualContainerObjects": vco(None, f"Slider: {label}. Starts at {default}.")}
    if sync:
        v["syncGroup"] = {"groupName": sync, "fieldChanges": True, "filterChanges": True}
    c = container(name, x, y, w, h, v)
    if hidden:   # synced but not shown (the engine on this page uses the value picked on a coalition page)
        c["isHidden"] = True
    return c


def choice_slicer(name, x, y, w, h, table, header, preset, sync, alt, column="choice", hidden=False, show_header=True):
    """Single-select dropdown on a disconnected coalition table, pre-set, synced across pages by `sync`."""
    v = {"visualType": "slicer",
         "syncGroup": {"groupName": sync, "fieldChanges": True, "filterChanges": True},
         "query": {"queryState": {"Values": {"projections": [proj("Column", table, column)]}}},
         "objects": {"data": [{"properties": {"mode": s("Dropdown")}}],
                     "selection": [{"properties": {"strictSingleSelect": lit("true"), "selectAllCheckboxEnabled": lit("false")}}],
                     "header": [{"properties": {"show": lit("true" if show_header else "false"), "text": s(header)}}],
                     "general": [{"properties": {"filter": {"filter": {
                         "Version": 2, "From": [{"Name": "d", "Entity": table, "Type": 0}],
                         "Where": [{"Condition": {"In": {
                             "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "d"}}, "Property": column}}],
                             "Values": [[{"Literal": {"Value": "'" + preset.replace("'", "''") + "'"}}]]}}}]}}}}]},
         "visualContainerObjects": vco(None, alt)}
    c = container(name, x, y, w, h, v)
    if hidden:
        c["isHidden"] = True
    return c


def bar_chart(name, x, y, w, h, value, colour, title, alt, tooltips=(), axis_pt=8):
    """37 states ranked by share (desc), bars coloured by a measure returning a hex colour, fixed bold 25% line."""
    v = {"visualType": "clusteredColumnChart",   # upright columns: all 37 states fit across the width, no scrolling
         "query": {"queryState": {
             "Category": {"projections": [proj("Column", "dim_state", "state_name", "State")]},
             "Y": {"projections": [proj("Measure", value[0], value[1], value[2])]},
             **({"Tooltips": {"projections": [proj("Measure", t, m, d) for t, m, d in tooltips]}} if tooltips else {})},
             "sortDefinition": {"sort": [{"field": meas(value[0], value[1]), "direction": "Descending"}], "isDefaultSort": True}},
         "objects": {
             "dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": meas(colour[0], colour[1])}}}},
                            "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
             # 37 labels would overlap: exact shares are in the tooltip and in the tables on the page
             "labels": [{"properties": {"show": lit("false")}}],
             "categoryAxis": [{"properties": {"fontSize": lit(f"{axis_pt}D"), "showAxisTitle": lit("false"),
                                              "preferredCategoryWidth": lit("8D"), "innerPadding": lit("15L")}}],
             "valueAxis": [{"properties": {"start": lit("0D"), "showAxisTitle": lit("false")}}],
             "y1AxisReferenceLine": [{"properties": {"show": lit("true"), "value": lit("0.25D"), "style": s("solid"),
                                                     "lineColor": {"solid": {"color": lit(f"'{WINE}'")}},
                                                     "width": lit("3D"), "transparency": lit("0D"),
                                                     "displayName": s("A quarter of the vote (25%)"),
                                                     "dataLabelShow": lit("true"), "dataLabelText": s("Name"),
                                                     "dataLabelColor": {"solid": {"color": lit(f"'{WINE}'")}},
                                                     "dataLabelHorizontalPosition": s("right"),
                                                     "dataLabelVerticalPosition": s("above")},
                                      "selector": {"id": "1"}}]},
         "visualContainerObjects": vco(title, alt, {"visualTooltip": [{"properties": {"show": lit("true")}}]})}
    return container(name, x, y, w, h, v)


def matrix(name, x, y, w, h, rows, values, title, alt, sort=None, row_wrap=False, font_pt=None):
    q = {"queryState": {"Rows": {"projections": [proj("Column", t, c, d) for t, c, d in rows]},
                        "Values": {"projections": [proj("Measure", t, m, d) for t, m, d in values]}}}
    if sort:
        q["sortDefinition"] = {"sort": [{"field": meas(*sort), "direction": "Descending"}], "isDefaultSort": True}
    v = {"visualType": "pivotTable", "query": q,
         "objects": {"columnHeaders": [{"properties": {"columnAdjustment": s("growToFit"), "autoSizeColumnWidth": lit("true"),
                                                       "wordWrap": lit("true")}}],
                     "subTotals": [{"properties": {"rowSubtotals": lit("false")}}]},
         "visualContainerObjects": vco(title, alt)}
    if row_wrap:   # long state names wrap onto two lines instead of widening the State column
        v["objects"]["rowHeaders"] = [{"properties": {"wordWrap": lit("true")}}]
    if font_pt:    # one size smaller where a table must share the page width with a 37-column chart
        f = {"fontSize": lit(f"{font_pt}D")}
        for k in ("columnHeaders", "rowHeaders", "values"):
            v["objects"].setdefault(k, [{"properties": {}}])[0]["properties"].update(f)
    return container(name, x, y, w, h, v)


def shape_map(name, x, y, w, h, resource, value, title, alt):
    """Coloured by points above/below 25%: vermillion (below) - near-white at exactly 25% - blue (above), fixed at -25/0/+25.
    Bound to the state NAME (TopoJSON property state_name = dim_state[state_name], all 37 checked by validate_phase6),
    so the hover shows the state's name rather than its code."""
    v = {"visualType": "shapeMap",
         "query": {"queryState": {
             "Category": {"projections": [proj("Column", "dim_state", "state_name", "State")]},
             "Value": {"projections": [proj("Measure", value[0], value[1], value[2])]},
             "Tooltips": {"projections": [proj("Measure", "scenario", "Scenario share", "Share of the vote"),
                                          proj("Measure", "scenario", "Scenario label", "Status")]}}},
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


def tile_chart(name, x, y, w, h, title, alt, label_pt=10, marker=40):
    """Equal-size tile map drawn as a scatter chart (one square per state at its fixed grid position) so every tile
    can carry its ISO code. Same fixed colour scale as the Shape Maps. Codes sit in a white label box, so they read
    at >= 4.5:1 on every fill. Hover: code, full state name, share and status."""
    grad = {"FillRule": {"Input": meas("scenario", "Points from 25%"), "FillRule": {"linearGradient3": {
        "min": {"color": {"Literal": {"Value": f"'{ORANGE}'"}}, "value": {"Literal": {"Value": "-25D"}}},
        "mid": {"color": {"Literal": {"Value": "'#F2F2F2'"}}, "value": {"Literal": {"Value": "0D"}}},
        "max": {"color": {"Literal": {"Value": f"'{BLUE}'"}}, "value": {"Literal": {"Value": "25D"}}},
        "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'noColor'"}}}}}}}
    v = {"visualType": "scatterChart",
         "query": {"queryState": {
             "Category": {"projections": [proj("Column", "dim_state", "state_code", "Code")]},
             "X": {"projections": [proj("Measure", "scenario", "Grid column", "Grid column")]},
             "Y": {"projections": [proj("Measure", "scenario", "Grid row", "Grid row")]},
             "Tooltips": {"projections": [proj("Measure", "scenario", "State name", "State"),
                                          proj("Measure", "scenario", "Scenario share", "Share of the vote"),
                                          proj("Measure", "scenario", "Scenario label", "Status")]}}},
         "objects": {
             "dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": grad}}}},
                            "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
             "bubbles": [{"properties": {"markerShape": s("square"), **({"bubbleSize": lit(f"{marker}L")} if marker else {})}}],
             "markers": [{"properties": {"borderShow": lit("true"), "borderColor": {"solid": {"color": lit("'#FFFFFF'")}},
                                         "borderWidth": lit("1D"), "transparency": lit("0D")}}],
             "categoryLabels": [{"properties": {"show": lit("true"), "fontSize": lit(f"{label_pt}D"), "bold": lit("true"),
                                                "color": {"solid": {"color": lit(f"'{INK}'")}},
                                                # default label background is white; setting backgroundColor
                                                # trips the PBIR validator (nested-colour rule), so it is left default
                                                "enableBackground": lit("true"), "backgroundTransparency": lit("0D")}}],
             "categoryAxis": [{"properties": {"show": lit("false"), "showAxisTitle": lit("false"), "start": lit("-0.6D"),
                                              "end": lit("6.6D"), "gridlineShow": lit("false")}}],
             "valueAxis": [{"properties": {"show": lit("false"), "showAxisTitle": lit("false"), "start": lit("2.9D"),
                                           "end": lit("10.5D"), "gridlineShow": lit("false")}}],
             "legend": [{"properties": {"show": lit("false")}}]},
         "visualContainerObjects": vco(title, alt, {"visualTooltip": [{"properties": {"show": lit("true")}}]})}
    return container(name, x, y, w, h, v)


def tile_matrix(name, x, y, w, h, title, alt, value_pt=10, pad=1, code="Tile code", fill="Tile fill",
                text="Tile text colour", tip=None):
    """Equal-size tile map as a matrix: one cell per grid position, the state's code inside, the cell coloured on the
    maps' fixed scale and the code in black or white, whichever contrasts more (measures Tile fill / Tile text colour).
    The grid's row and column numbers are layout only and are drawn in the background colour."""
    wild = {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}
    hide = {"fontColor": {"solid": {"color": lit("'#FFFFFF'")}}, "backColor": {"solid": {"color": lit("'#FFFFFF'")}},
            "fontSize": lit("6D")}
    v = {"visualType": "pivotTable",
         "query": {"queryState": {"Rows": {"projections": [proj("Column", "dim_state", "tile_row", "Row")]},
                                  "Columns": {"projections": [proj("Column", "dim_state", "tile_col", "Column")]},
                                  "Values": {"projections": [proj("Measure", "scenario", code, "Code")]}}},
         "objects": {
             "values": [{"properties": {"backColor": {"solid": {"color": {"expr": meas("scenario", fill)}}},
                                        "fontColor": {"solid": {"color": {"expr": meas("scenario", text)}}}},
                         "selector": {**wild, "metadata": f"scenario.{code}"}},
                        {"properties": {"fontSize": lit(f"{value_pt}D"), "bold": lit("true")}}],
             "columnHeaders": [{"properties": {**hide, "autoSizeColumnWidth": lit("false")}}],
             "rowHeaders": [{"properties": hide}],
             "subTotals": [{"properties": {"rowSubtotals": lit("false"), "columnSubtotals": lit("false")}}],
             "grid": [{"properties": {"gridVertical": lit("true"), "gridVerticalColor": {"solid": {"color": lit("'#FFFFFF'")}},
                                      "gridVerticalWeight": lit("3D"), "gridHorizontal": lit("true"),
                                      "gridHorizontalColor": {"solid": {"color": lit("'#FFFFFF'")}},
                                      "gridHorizontalWeight": lit("3D"), "rowPadding": lit(f"{pad}D"),
                                      "outlineColor": {"solid": {"color": lit("'#FFFFFF'")}}}}]},
         "visualContainerObjects": {**vco(title, alt), "visualTooltip": [{"properties": {
             "show": lit("true"), "type": s("Canvas"), "section": s(tip or TILE_TIP)}}]}}
    return container(name, x, y, w, h, v)


def locator(name, x, y, w, h):
    """Static 'Where is each state?' map (scripts/build_photos.py): grey states with their ISO codes."""
    f = "locator_states.png"
    img = {"visualType": "image",
           "objects": {"image": [{"properties": {"sourceType": s("image"),
                                                 "sourceFile": {"image": {"name": s(f), "url": {"expr": {"ResourcePackageItem": {
                                                     "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": f}}},
                                                     "scaling": s("Fit")}}}}],
                       "imageScaling": [{"properties": {"imageScalingType": s("Fit")}}]},
           "visualContainerObjects": {"title": [{"properties": {"show": lit("true"), "text": s("Where is each state?")}}],
                                      "background": [{"properties": {"show": lit("false")}}],
                                      "border": [{"properties": {"show": lit("false")}}],
                                      "padding": [{"properties": {k: lit("2D") for k in ("top", "bottom", "left", "right")}}],
                                      "general": [{"properties": {"altText": s(
                                          "Where is each state: a grey map of Nigeria with each state's two-letter code "
                                          "(the same codes as the coloured squares). The full list of codes is beside it.")}}]}}
    return container(name, x, y, w, h, img)


def photo(pid, key, x):
    """Decorative photo in a tall side panel + its credit caption. Returned last so it is last in tab order."""
    ph = PHOTOS[key]
    f = ph["output"].rsplit("/", 1)[-1]
    credit = f"Photo: {ph['author']} / Wikimedia Commons, {ph['licence']} (cropped)"
    img = {"visualType": "image",
           "objects": {"image": [{"properties": {"sourceType": s("image"),
                                                 "sourceFile": {"image": {"name": s(f), "url": {"expr": {"ResourcePackageItem": {
                                                     "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": f}}},
                                                     "scaling": s("Fit")}}}}],
                       "imageScaling": [{"properties": {"imageScalingType": s("Fit")}}]},
           "visualContainerObjects": {"title": [{"properties": {"show": lit("false")}}],
                                      "background": [{"properties": {"show": lit("false")}}],
                                      "border": [{"properties": {"show": lit("false")}}],
                                      "padding": [{"properties": {k: lit("0D") for k in ("top", "bottom", "left", "right")}}],
                                      "general": [{"properties": {"altText": s(
                                          f"Decorative photo: {ph['subject']} ({credit}; full credit on the Data sources page)")}}]}}
    return [container(sid(pid, "photo"), x, PY, PW, PH, img),
            textbox(sid(pid, "photo_credit"), x, PY + PH + 4, PW, 40, [(credit, 8, False, MUTED)],
                    alt=f"Photo credit: {credit}")]


# ---------------- pages ----------------

NO_LOGOS = os.environ.get("PBIP_NO_LOGOS") == "1"   # fall back to abbreviation badges (e.g. after a takedown request)


def header(pid, title, subtitle, w=600):
    """Title + subtitle, then the selected candidate's identity: portrait, 2023 party logo, a party-coloured box with
    2023 party and party now (dated source), the party-now logo, and the candidate selector."""
    if NO_LOGOS:
        logo23 = party_card(sid(pid, "badge"), 704, 10, 60, 66, "Party badge",
                            "The selected candidate's 2023 party, as an abbreviation on the party's colour.", 12)
        lognow = party_card(sid(pid, "badge_now"), 936, 10, 58, 66, "Party now badge",
                            "The selected candidate's party now, as an abbreviation.", 12)
    else:
        logo23 = candidate_photo(sid(pid, "badge"), 704, 10, 60, 66, "Party logo",
                                 "Logo of the selected candidate's 2023 party (trademark, shown for identification only).")
        lognow = candidate_photo(sid(pid, "badge_now"), 936, 10, 58, 66, "Party now logo",
                                 "Logo of the selected candidate's party now (trademark, shown for identification only).")
    return [textbox(sid(pid, "title"), 20, 8, w, 34, [(title, 18, True, INK)], alt=title),
            textbox(sid(pid, "subtitle"), 20, 44, w, 40, [(subtitle, 10, False, MUTED)], alt=subtitle),
            candidate_slicer(sid(pid, "candidate"), 1000, 4, 260, 76),
            candidate_photo(sid(pid, "cand_photo"), 628, 6, 72, 74),
            logo23,
            party_card(sid(pid, "party_now"), 770, 6, 162, 74, "Party identity",
                       "The selected candidate's 2023 party and party now, with the publisher and date of the news "
                       "report used.", 9),
            lognow]


SRC = ("2023 result per state, from five copies of INEC's declaration (not INEC's own state sheets). Abuja (the "
       "Federal Capital Territory) counts as a state here, so there are 37.")
RULE_NOTE = ("States needed to win (24 or 25): the constitution says a quarter of the vote in two-thirds of the states. "
             "Courts have not said whether that means 24 or 25 once Abuja counts as a state; 24 is used unless you choose 25.")


def page_overview(pid):
    cx, cw = 20, RIGHT_X - 10 - 20   # photo on the right
    v = header(pid, "Candidate overview: 2023", SRC)
    v.append(cards(sid(pid, "kpis"), cx, 86, cw, 96,
                   [("fact_result_2023", "Candidate votes", "Votes, 2023"), ("fact_result_2023", "Candidate share", "Share of the vote"),
                    ("scenario", "Candidate national rank", "Place nationally"),
                    ("fact_result_2023", "States at 25% or more", "States won (of 37)"),
                    ("fact_result_2023", "States with a computable share", "States with results")],
                   None, "Headline figures for the selected candidate in 2023: votes, share of the vote, place nationally, "
                         "states with a quarter of the vote or more out of 37, and states with results."))
    v.append(bar_chart(sid(pid, "bars"), cx, 186, cw, 212, ("fact_result_2023", "Candidate share", "Share of the vote"),
                       ("scenario", "Baseline label colour"),
                       "Share of the vote in each state, 2023 (highest first)",
                       "Column chart of the selected candidate's 2023 share of the vote in all 37 states, highest first, with a "
                       "fixed wine-coloured line at a quarter of the vote. Blue columns are at a quarter or more, vermillion "
                       "20% to just under a quarter, grey under 20%.",
                       tooltips=[("scenario", "Baseline label", "Status"), ("fact_result_2023", "Candidate votes", "Votes")]))
    v.append(key_box(sid(pid, "key"), cx + 8, 402, cw - 8, 48, STATUS_KEY, STATUS_ALT))
    v.append(matrix(sid(pid, "zones"), cx, 454, 470, 258, [("dim_zone", "zone", "Zone")],
                    [("fact_result_2023", "Candidate share", "Share of the vote"),
                     ("fact_result_2023", "States at 25% or more", "States won"),
                     ("fact_result_2023", "States with a computable share", "States")],
                    "By zone of the country", "Table of the selected candidate's 2023 share of the vote and states won "
                                              "(a quarter of the vote or more) in each of the six zones."))
    nx, nw = cx + 480, cw - 480
    v.append(sentence(sid(pid, "close"), nx, 454, nw, 140, "Closest calls sentence", "Closest calls in 2023",
                      "The selected candidate's narrowest state won and narrowest miss in 2023, in votes.", value_pt=10))
    v.append(textbox(sid(pid, "notes"), nx + 8, 604, nw - 8, 108, [
        ("How sure are these margins? :: The vote counts include 4,858 votes that nobody can place in a state (in the "
         "minor candidates' column). A margin smaller than that could change with better data.", 9, False, INK),
        ("Kano: :: one figure is disputed, Bola Tinubu's votes there (we use 506,412; three of four copies print "
         "517,341). Either figure gives the same answer for every candidate: who has a quarter in Kano does not change. "
         "Formulas and terms: see the Technical notes page.", 9, False, INK)],
        alt="Notes: how sure the margins are, the Kano figure, and where the formulas are."))
    v += photo(pid, "overview", RIGHT_X)
    return "Candidate overview", v


def page_path(pid):
    cx = LEFT_X + PW + 20            # photo on the left
    cw = W - 20 - cx
    v = header(pid, "Path to 24: the states that count",
               "2023 result. To try a different 2027, use the What-if simulator page. Abuja (the Federal Capital "
               "Territory) counts as a state here, so there are 37.")
    v.append(cards(sid(pid, "kpis"), cx, 86, cw, 80,
                   [("scenario", "Units secured (national)", "States won (of 37)"),
                    ("scenario", "Units needed (rule)", "States needed to win"),
                    ("scenario", "Units still needed", "More states needed"),
                    ("scenario", "Clears the rule", "Meets the 25% rule?"),
                    ("scenario", "Tipping-point unit", "The deciding state")],
                   None, "Counts for the rule: states won out of 37, states needed to win, more states needed, whether "
                         "the rule is met, and the deciding state.", label_pt=10))
    v.append(sentence(sid(pid, "decide"), cx, 170, cw, 96, "Deciding state sentence", "The deciding state, in votes",
                      "Sentence: the deciding state, how far the candidate is above or below a quarter of the vote there, "
                      "in points and in votes.", value_pt=10))
    v.append(bar_chart(sid(pid, "bars"), cx, 270, cw, 196, ("scenario", "Scenario share", "Share of the vote"),
                       ("scenario", "Path column colour"),
                       "All 37 states ranked by share of the vote (the black column is the deciding state)",
                       "Column chart of all 37 states ranked by the selected candidate's share of the vote, with a fixed "
                       "wine-coloured line at a quarter; colour shows won, within reach or out of reach; the deciding state "
                       "is black. Hover for extra votes needed.",
                       tooltips=[("scenario", "Unit rank", "Rank"), ("scenario", "Scenario label", "Status"),
                                 ("scenario", "Points needed", "Points short of a quarter"),
                                 ("scenario", "Votes needed", "Extra votes needed to reach a quarter")]))
    v.append(key_box(sid(pid, "key"), cx + 8, 468, cw - 8, 44, STATUS_KEY + [(INK, "the deciding state")],
                     STATUS_ALT + " Black column = the deciding state."))
    v.append(matrix(sid(pid, "table"), cx, 514, 800, 198, [("dim_state", "state_name", "State")],
                    [("scenario", "Unit rank", "Rank"), ("scenario", "Scenario label", "Status"),
                     ("scenario", "Scenario share", "Share"),
                     ("scenario", "Points needed", "Points short"),
                     ("scenario", "Votes needed", "Extra votes needed to reach a quarter")],
                    "Every state: status and distance to a quarter of the vote",
                    "Table of all 37 states with rank, status, share of the vote, points short of a quarter and extra "
                    "votes needed to reach a quarter.", sort=("scenario", "Scenario share")))
    v.append(textbox(sid(pid, "notes"), cx + 812, 518, cw - 812, 194, [
        ("24 or 25? :: The constitution says two-thirds of the states; courts have not said whether that is 24 or 25 "
         "once Abuja counts.", 9, False, INK),
        ("The deciding state: :: the 24th (or 25th) strongest state.", 9, False, INK),
        ("Extra votes needed: :: votes switching from other candidates, state total unchanged. See Technical notes.",
         9, False, INK)],
        alt="Notes: states needed (24 or 25), the deciding state, and extra votes needed, in plain words."))
    v += photo(pid, "path", LEFT_X)
    return "Path to 24", v


def page_map(pid):
    cx, cw = 20, RIGHT_X - 10 - 20   # photo on the right
    v = header(pid, "Spread map: strong and fragile states",
               "2023 result. Colour = points above or below a quarter of the vote. Abuja (the Federal Capital "
               "Territory) counts as a state here, so there are 37.")
    v.append(shape_map(sid(pid, "geo"), cx, 86, 300, 390, "nga_states.topo.json",
                       ("scenario", "Points from 25%", "Points above (+) or below (-) a quarter"), "State boundaries",
                       "Map of Nigeria's 37 states coloured by the selected candidate's share against a quarter of the "
                       "vote: blue above, vermillion below, near-white close to a quarter. Hover a state for its name, "
                       "share and status."))
    v.append(tile_matrix(sid(pid, "tiles"), cx + 306, 86, 340, 390, "Equal-size squares, with state codes",
                         "Tile grid with one equal square per state and its two-letter code inside, same colours as the "
                         "state map, so small states are as visible as large ones. Codes and names are listed below.",
                         value_pt=12, pad=9))
    v.append(matrix(sid(pid, "list"), cx + 652, 86, cw - 652, 390, [("dim_state", "state_name", "State")],
                    [("scenario", "Scenario label", "Status"),
                     ("scenario", "Points from 25%", "Points vs 25%")],
                    "Every state in words", "Table of all 37 states with their status and points above or below a quarter "
                    "of the vote, the same information as the map colours.", sort=("scenario", "Points from 25%")))
    v.append(locator(sid(pid, "locator"), cx, 480, 300, 232))
    v.append(key_box(sid(pid, "key"), cx + 310, 482, 380, 80, MAP_KEY, MAP_ALT, title="Colour key (fixed scale)", stacked=True))
    v.append(cards(sid(pid, "counts"), cx + 700, 480, cw - 700, 82,
                   [("scenario", "Units secured", "Won"),
                    ("scenario", "Units within reach", "Within reach"),
                    ("scenario", "Units out of reach", "Out of reach")],
                   None, "Counts of states won, within reach and out of reach for the selected candidate.", label_pt=9))
    v.append(textbox(sid(pid, "notes"), cx + 310, 568, cw - 310, 144, [
        ("Reading the map. :: Deepest blue = 25 or more points above a quarter; deepest vermillion = 25 or more below. "
         "Hover a state on the boundary map for its name, share and status. The rule counts states, not land, so the "
         "equal-size squares show small states as clearly as big ones. The grey map's codes match the squares.", 9, False, INK),
        ("State codes: :: " + CODE_LIST, 9, False, INK)],
        alt="Notes: how to read the map colours, and the list of two-letter state codes with their names."))
    v += photo(pid, "map", RIGHT_X)
    return "Spread map", v


def page_sim(pid):
    v = header(pid, "What-if simulator: try 2027",
               "How to play: :: 1. Pick a candidate (top right). 2. Move a slider, or type a number in its box. "
               "3. Watch who wins and how many states change. A what-if tool, not a forecast.")
    v[1] = textbox(sid(pid, "subtitle"), 20, 44, 600, 40,
                   [("How to play: :: 1. Pick a candidate (top right). 2. Move a slider, or type a number in its box. "
                     "3. Watch who wins and how many states change. A what-if tool, not a forecast.", 10, False, INK)],
                   alt="How to play: pick a candidate, move a slider, watch who wins and how many states change.")
    # sliders: 2 columns x 5 rows to the right of the photo; each = a wrapped plain-words label + a header-less slider.
    # PBIP_SLIDER_PROBE=1 builds a test variant with non-neutral defaults (national +5, SE -3) to prove propagation.
    probe = os.environ.get("PBIP_SLIDER_PROBE") == "1"
    defaults = {"param_swing_national": 5 if probe else 0, "param_swing_SE": -3 if probe else 0}
    # each slider = an everyday question + a short hint (user request 2026-11-14)
    zq = "What if things change only in the {}?"
    sliders = [("turnout", "param_turnout", ("What if more (or fewer) of their 2023 voters turn out?", "%"), True),
               ("national", "param_swing_national", ("What if they gain or lose support everywhere?", "points"), False),
               ("zone_NC", "param_swing_NC", (zq.format("North Central and Abuja"), "points"), False),
               ("zone_NE", "param_swing_NE", (zq.format("North East"), "points"), False),
               ("zone_NW", "param_swing_NW", (zq.format("North West"), "points"), False),
               ("zone_SE", "param_swing_SE", (zq.format("South East"), "points"), False),
               ("zone_SS", "param_swing_SS", (zq.format("South South"), "points"), False),
               ("zone_SW", "param_swing_SW", (zq.format("South West"), "points"), False),
               ("rule", "param_rule", ("How many states must they win?", "24 or 25"), True)]
    sx = LEFT_X + PW + 12
    for i, (key, table, (question, hint), integer) in enumerate(sliders):
        x, y = sx + (i % 2) * 206, 86 + (i // 2) * 125
        label = f"{question} ({hint})"
        v.append(textbox(sid(pid, key, "label"), x + 4, y, 196, 40,
                         [([(question, INK, True), (f" ({hint})", MUTED, False)], 9, False, INK)],
                         alt=f"Slider label: {label}"))
        v.append(param_slicer(sid(pid, key), x, y + 40, 200, 82, table, label,
                              24 if table == "param_rule" else defaults.get(table, 0), integer))
    # Coalition switch (user decision 2026-11-16) where the 24-or-25 note was (that note stays on Path to 24, How to
    # read this and Technical notes). Default Off = today's engine; PBIP_COALITION_ON=1 builds a test variant set to On.
    cx0, cy0 = sx + 206, 86 + 4 * 125
    v.append(textbox(sid(pid, "coal_label"), cx0 + 4, cy0, 196, 18,
                     [([("Use the coalition?", INK, True), (" (Off or On)", MUTED, False)], 9, False, INK)],
                     alt="Switch label: use the coalition? Off or On."))
    v.append(choice_slicer(sid(pid, "coal_switch"), cx0, cy0 + 18, 200, 48, "coal_switch", "Use the coalition (Off or On)",
                           "On" if COALITION_ON else "Off", "coal_switch",
                           "Switch: use the coalition picked on the Head to head page instead of the candidate. Off by "
                           "default.", column="Value", show_header=False))
    v.append(sentence(sid(pid, "coal_inuse"), cx0, cy0 + 68, 200, 58, "Simulator coalition sentence", None,
                      "Sentence: whether the simulator uses the coalition, which coalition and follow rates, and against "
                      "whom.", value_pt=8, accent=False, border=MUTED))
    rx = sx + 412 + 10
    rw = W - 20 - rx
    # open question 22 (user decision 2026-11-19): a line under the header, empty unless the coalition switch is On;
    # the results column moves down and its gaps shrink to 2 px (screenshots 2026-11-20: a shorter Result box cut it to one line,
    # 52 px card rows clipped, a 22 px line showed no text); the room comes from the tile grid's empty bottom. No
    # background, so the empty line shows nothing with the switch Off.
    hl = sentence(sid(pid, "coal_header"), 628, 78, W - 20 - 628, 30, "Simulator header line", None,
                  "Line under the header: with the coalition switch On, says which coalition the results are for. "
                  "Empty when the switch is Off.", value_pt=9, accent=False)
    hl["visual"]["visualContainerObjects"]["background"] = [{"properties": {"show": lit("false")}}]
    v.append(hl)
    v.append(sentence(sid(pid, "verdict"), rx, 110, rw, 92, "Result sentence", "Result",
                      "Result of your what-if as a sentence: who wins outright, or whether it goes to a run-off.",
                      value_pt=10))
    v.append(cards(sid(pid, "who"), rx, 204, rw, 56,
                   [("scenario", "Has most votes", "Most votes nationwide?"), ("scenario", "Leading rival", "Closest rival (party)"),
                    ("scenario", "Scenario national share", "Share of the vote nationwide")],
                   None, "Whether the candidate has the most votes nationwide, the closest rival's party and the candidate's "
                         "share of the vote nationwide.", value_pt=13, label_pt=9))
    v.append(cards(sid(pid, "counts"), rx, 262, rw, 56,
                   [("scenario", "Units secured (national)", "States won (of 37)"), ("scenario", "Units still needed", "More states needed"),
                    ("scenario", "Units at a cap", "States that hit 0% or 100%")],
                   None, "Your what-if: states won out of 37, more states needed, and states where a slider pushed the "
                         "share to 0% or 100%.", value_pt=13, label_pt=9))
    v.append(sentence(sid(pid, "decide"), rx, 320, rw, 90, "Deciding state sentence", "The deciding state, in votes",
                      "Sentence: the deciding state under your what-if, how far the candidate is above or below a quarter "
                      "of the vote there, in points and in votes.", value_pt=9))
    v.append(sentence(sid(pid, "inforce"), rx, 412, rw, 60, "Assumptions in force", "Your what-if, in words",
                      "Sentence listing every slider that is not at 0, and the number of states needed.", value_pt=10))
    mw = 300
    v.append(tile_matrix(sid(pid, "tiles"), rx, 474, mw, 238, "Each state under your what-if",
                         "Tile grid, one square per state with its two-letter code inside, recoloured by your what-if: "
                         "blue above a quarter of the vote, vermillion below. The codes and full state names are listed on "
                         "the Spread map and Technical notes pages."))
    kx, kw = rx + mw + 6, rw - mw - 6
    v.append(textbox(sid(pid, "key"), kx + 8, 478, kw - 8, 234, [
        ("Colour key (codes: see Spread map)", 9, True, INK)] + [(key_runs([it]), 9, False, INK) for it in MAP_KEY] + [
        ("Try these: :: \"everywhere\" +3 (a small gain); North West \u221210 (a big loss in one region); turnout "
         "\u221220 (supporters stay at home). Set everything back to 0 to see 2023 again.", 9, False, INK),
        ("Good to know: :: a zone change adds to the change everywhere. More on Technical notes.", 9, False, INK)],
        alt="Map colour key, example what-ifs to try, and the assumptions behind the simulator."))
    # the coalition's pickers and follow sliders, synced from the coalition pages but not shown here
    v += side_controls(pid, "A", cx0, cy0, hidden=True) + side_controls(pid, "B", cx0, cy0, hidden=True)
    v += photo(pid, "simulator", LEFT_X)
    return "What-if simulator", v


# ---------------- coalition pages (user decisions 2026-11-16; docs/methodology.md "Coalitions") ----------------
COALITION_ON = os.environ.get("PBIP_COALITION_ON") == "1"   # test variant: simulator switch preset On
NOBODY = "Nobody: one party alone"


def choice(party):
    return f"{CANDS[party]['candidate']} ({party})"


# preset (user decision 2026-11-16): Side A = Peter Obi (LP) lead + Rabiu Kwankwaso (NNPP) partner, 100% follow;
# Side B = Bola Tinubu (APC) alone
PRESET = {"A": (choice("LP"), choice("NNPP")), "B": (choice("APC"), NOBODY)}
SIDE_COLOUR = {"A": BLUE, "B": ORANGE}


def side_controls(pid, side, x0, y0, hidden=False, heading=None):
    """Lead and partner pickers (with portraits) and the follow slider for one side, synced across the coalition pages
    and the simulator. hidden: only the three slicers, not shown (the simulator)."""
    lo = side.lower()
    lead, partner = PRESET[side]
    tl, tp, tf = f"coal_{lo}_lead", f"coal_{lo}_partner", f"param_follow_{lo}"
    pl = "Partner (or Nobody)" if side == "B" else "Partner party"
    q = "Partner voters who follow (%)"
    sl = [choice_slicer(sid(pid, side, "lead"), x0 + 60, y0 + 22, 150, 76, tl, "Lead party", lead, tl,
                        f"Side {side} lead party picker: the party at the top of the ticket. Starts at {lead}.",
                        hidden=hidden),
          choice_slicer(sid(pid, side, "partner"), x0 + 276, y0 + 22, 150, 76, tp, pl, partner, tp,
                        f"Side {side} partner picker" + (", or Nobody for one party alone" if side == "B" else "")
                        + f". Starts at {partner}.", hidden=hidden),
          param_slicer(sid(pid, side, "follow"), x0 + 430, y0 + 52, 180, 56, tf,
                       f"Side {side}: how many of the partner's 2023 voters follow (%)", 100, True, sync=tf,
                       hidden=hidden)]
    if hidden:
        for c in sl:
            c["position"].update({"x": x0, "y": y0, "width": 150, "height": 76})
        return sl
    head = heading or (f"Side {side}" + (": the coalition (blue)" if side == "A" else ": one party or another coalition (vermillion)"))
    return [textbox(sid(pid, side, "head"), x0, y0, 610, 20, [([(BAR + " ", SIDE_COLOUR[side], True), (head, INK, True)], 10,
                                                              False, INK)], alt=head),
            candidate_photo(sid(pid, side, "lead_photo"), x0, y0 + 24, 56, 66, f"Side {side} lead photo",
                            f"Photo of Side {side}'s lead candidate (free-licence portrait; credit on the Data sources page)."),
            sl[0],
            candidate_photo(sid(pid, side, "partner_photo"), x0 + 216, y0 + 24, 56, 66, f"Side {side} partner photo",
                            f"Photo of Side {side}'s partner (free-licence portrait; credit on the Data sources page)."),
            sl[1],
            textbox(sid(pid, side, "follow_label"), x0 + 434, y0 + 20, 176, 32,
                    [([(q, INK, True), (" (an assumption)", MUTED, False)], 9, False, INK)], alt=f"Slider label: {q}"),
            sl[2]]


COAL_ASSUME = [
    ("What this page assumes. :: How many of the partner's voters follow is an assumption, not a measurement: no "
     "published figure exists. The 2011 to 2015 APC merger only loosely suggests that most partner voters followed.",
     9, False, INK),
    ("Partner voters who do not follow stay home: :: none go to another party, so the state's total shrinks.", 9, False, INK),
    ("2023 votes recombined, :: not a 2027 forecast. Every other party keeps its 2023 votes. No swing, no turnout change "
     "(the What-if simulator adds those when its coalition switch is On).", 9, False, INK),
    ("Names: :: \"NDC (Obi + Kwankwaso)\" is a real joint ticket (NDC, 31 May 2026). Every other pairing is "
     "hypothetical and named \"X + Y (what-if)\".", 9, False, INK),
]


def page_merge(pid):
    v = [textbox(sid(pid, "title"), 20, 8, 620, 34, [("Merge two parties: 2023 votes added together", 18, True, INK)],
                 alt="Merge two parties: 2023 votes added together"),
         textbox(sid(pid, "subtitle"), 20, 44, 620, 40, [
             ("Pick a lead party and a partner. The coalition gets the lead's 2023 votes plus the partner's voters who "
              "follow; the rest stay home. Abuja counts as a state, so there are 37.", 10, False, MUTED)],
             alt="Subtitle: how the coalition's votes are made.")]
    v += side_controls(pid, "A", 650, 4, heading="The coalition (Side A)")
    v.append(sentence(sid(pid, "msg"), 20, 116, 620, 74, "Side A message", "The coalition",
                      "Who is in the coalition, whether it is a real ticket, and how many partner voters follow; or what to "
                      "change if the choice is not complete.", value_pt=10, accent=False, border=BLUE))
    v.append(cards(sid(pid, "kpis"), 650, 116, 610, 74,
                   [("scenario", "Side A states at 25% (merge)", "Coalition: states won (of 37)"),
                    ("scenario", "Side A lead states at 25%", "Lead alone, 2023: states won"),
                    ("scenario", "Side A national votes", "Coalition votes"),
                    ("scenario", "Side A national share (merge)", "Coalition share of the vote")],
                   None, "Headline figures: states where the coalition has a quarter of the vote or more (of 37), the same "
                         "count for the lead party alone in 2023, the coalition's votes and its share nationwide.",
                   value_pt=14, label_pt=9, accent=False, border=BLUE))
    v.append(bar_chart(sid(pid, "bars"), 20, 196, 820, 262, ("scenario", "Side A share (merge)", "Coalition share"),
                       ("scenario", "Side A status colour (merge)"),
                       "The coalition's share of the vote in each state (highest first)",
                       "Column chart of the coalition's share of the vote in all 37 states, highest first, with a fixed "
                       "wine-coloured line at a quarter of the vote. Blue columns are at a quarter or more, vermillion 20% "
                       "to just under a quarter, grey under 20%.",
                       tooltips=[("scenario", "Side A status (merge)", "Status"),
                                 ("scenario", "Side A lead share", "Lead alone, 2023"),
                                 ("scenario", "Side A votes", "Coalition votes")]))
    v.append(key_box(sid(pid, "key"), 28, 460, 812, 44, STATUS_KEY, STATUS_ALT))
    v.append(textbox(sid(pid, "assume"), 28, 510, 812, 202, COAL_ASSUME,
                     alt="What this page assumes: follow rate is an assumption; non-followers stay home; 2023 votes "
                         "recombined, not a forecast; which names are real."))
    v.append(matrix(sid(pid, "table"), 850, 196, 410, 516, [("dim_state", "state_name", "State")],
                    [("scenario", "Side A lead share", "Lead"), ("scenario", "Side A share (merge)", "Coalition"),
                     ("scenario", "Side A change (points)", "Change"),
                     ("scenario", "Side A status (merge)", "Status")],
                    "Every state: the lead alone and the coalition (change in points)",
                    "Table of all 37 states: the lead party's 2023 share alone, the coalition's share, the change in "
                    "points and the coalition's status.", sort=("scenario", "Side A share (merge)"), row_wrap=True, font_pt=9))
    return "Merge two parties", v


H2H_KEY = [(BLUE, "Side A leads"), (ORANGE, "Side B leads"), (GREY, "another party leads, or a tie")]
H2H_TIP = sid("page", "h2htip")


def page_h2h(pid):
    v = [textbox(sid(pid, "title"), 20, 8, 1240, 34, [("Head to head: two sides, 2023 votes recombined", 18, True, INK)],
                 alt="Head to head: two sides, 2023 votes recombined"),
         textbox(sid(pid, "subtitle"), 20, 44, 1240, 36, [
             ("Side A is a coalition of two parties; Side B is one party or another coalition. Each party can be used once. "
              "No swing or turnout change. Abuja counts as a state, so there are 37. 24 states needed.", 10, False, MUTED)],
             alt="Subtitle: what the two sides are.")]
    v += side_controls(pid, "A", 20, 84) + side_controls(pid, "B", 650, 84)
    v.append(sentence(sid(pid, "msg_a"), 20, 196, 610, 50, "Side A message", None,
                      "Side A in words, or what to change if the choice is not complete.", value_pt=9, accent=False,
                      border=BLUE))
    v.append(sentence(sid(pid, "msg_b"), 650, 196, 610, 50, "Side B message", None,
                      "Side B in words, or what to change if the choice is not complete.", value_pt=9, accent=False,
                      border=ORANGE))
    v.append(cards(sid(pid, "nat_a"), 20, 250, 610, 66,
                   [("scenario", "Side A national votes (head to head)", "Side A votes"),
                    ("scenario", "Side A national share (head to head)", "Side A share"),
                    ("scenario", "Side A states at 25% (head to head)", "Side A: states at 25%+"),
                    ("scenario", "States led by Side A", "States Side A leads")],
                   None, "Side A nationwide: votes, share of the vote, states with a quarter of the vote or more, states "
                         "where Side A has the most votes.", value_pt=13, label_pt=9, accent=False, border=BLUE))
    v.append(cards(sid(pid, "nat_b"), 650, 250, 610, 66,
                   [("scenario", "Side B national votes", "Side B votes"),
                    ("scenario", "Side B national share (head to head)", "Side B share"),
                    ("scenario", "Side B states at 25% (head to head)", "Side B: states at 25%+"),
                    ("scenario", "States led by Side B", "States Side B leads")],
                   None, "Side B nationwide: votes, share of the vote, states with a quarter of the vote or more, states "
                         "where Side B has the most votes.", value_pt=13, label_pt=9, accent=False, border=ORANGE))
    v.append(sentence(sid(pid, "verdict"), 20, 320, 1240, 66, "Head to head sentence", "Result (Side A's view; 24 states "
                      "needed)", "Result as a sentence: whether Side A wins outright, loses, or it goes to a run-off.",
                      value_pt=10, accent=False, border=MUTED))
    v.append(tile_matrix(sid(pid, "tiles"), 20, 390, 330, 258, "Who leads each state",
                         "Tile grid, one square per state with its two-letter code inside: blue where Side A has the most "
                         "votes, vermillion where Side B does, grey where another party leads or it is a tie. The table "
                         "beside it gives the same in words.", value_pt=10, pad=3, code="Head to head tile code",
                         fill="Head to head leader colour", text="Head to head leader text colour", tip=H2H_TIP))
    v.append(key_box(sid(pid, "key"), 28, 652, 322, 60, H2H_KEY,
                     "Colour key: blue = Side A leads; vermillion = Side B leads; grey = another party leads, or a tie.",
                     stacked=True))
    v.append(matrix(sid(pid, "table"), 360, 390, 620, 322, [("dim_state", "state_name", "State")],
                    [("scenario", "Side A share (head to head)", "Side A share"),
                     ("scenario", "Side B share (head to head)", "Side B share"),
                     ("scenario", "Who leads (head to head)", "Who leads"),
                     ("scenario", "Side A at 25% (head to head)", "Side A a quarter?"),
                     ("scenario", "Side B at 25% (head to head)", "Side B a quarter?")],
                    "Every state: both sides",
                    "Table of all 37 states: each side's share of the vote, who leads, and whether each side has a quarter "
                    "of the vote.", sort=("scenario", "Side A share (head to head)")))
    v.append(textbox(sid(pid, "notes"), 990, 390, 270, 322, [
        ("Assumptions. :: How many partner voters follow is an assumption; no published figure exists. Those who do not "
         "follow stay home.", 9, False, INK),
        ("Recombined 2023 votes, :: not a 2027 forecast. Parties on neither side keep their 2023 votes; the 14 minor "
         "candidates are never counted as a leader.", 9, False, INK),
        ("Real or what-if: :: only \"NDC (Obi + Kwankwaso)\" is a real joint ticket. Try it under 2027 what-ifs: "
         "What-if simulator, switch \"Use the coalition\" On.", 9, False, INK)],
        alt="Notes: the assumptions behind this page and how to use the coalition in the simulator."))
    return "Head to head", v


def page_h2htip(pid):
    """Hover card for the head-to-head tile map: the state's name, both sides' shares and who leads."""
    return "Head to head state (tooltip)", [
        classic_card(sid(pid, "name"), 8, 6, TIP_W - 16, 44, "State name", None, "Name of the state under the pointer.", 14,
                     accent=False),
        classic_card(sid(pid, "a"), 8, 52, 96, 90, "Side A share (head to head)", "Side A", "Side A's share in this state.",
                     12, accent=False),
        classic_card(sid(pid, "b"), 108, 52, 96, 90, "Side B share (head to head)", "Side B", "Side B's share in this state.",
                     12, accent=False),
        classic_card(sid(pid, "lead"), 208, 52, TIP_W - 216, 90, "Who leads (head to head)", "Who leads",
                     "Who has the most votes in this state.", 10, accent=False)]


HOW = [
    ("How to read this report", 18, True, INK),
    ("The rule. :: To win outright, a presidential candidate needs the most votes nationwide and at least a quarter (25%) "
     "of the votes in at least two-thirds of the states. Abuja (the Federal Capital Territory) counts as a state here, so "
     "there are 37. We use 24 states as the default; 25 is offered as a stricter reading. This is our reading of section "
     "134 of the Constitution, checked against an unofficial copy.", 10, False, INK),
    ("What the numbers are. :: The 2023 result in each state, put together from five copies of INEC's declaration, because "
     "INEC's own state sheet is not public. PDP and NNPP state totals add up to INEC's national declaration with no "
     "adjustment; for APC and Labour they match because three disputed figures were chosen to make them match. The minor "
     "candidates' column is 4,858 votes too high nationally, and nobody can yet say where.", 10, False, INK),
    ("What the simulator assumes. :: A change in vote share adds the same number of points in every state of a zone. "
     "Turnout changes only the candidate's own 2023 voters. Other candidates gain or lose in proportion to their 2023 "
     "votes. No new candidates or boundary changes, and no merged parties unless you switch the coalition On. It is a "
     "what-if tool, not a forecast: it says nothing about how likely any what-if is.", 10, False, INK),
    ("Merging parties. :: Two pages add 2023 votes together. \"Merge two parties\" joins a lead party and a partner; "
     "\"Head to head\" sets that coalition against one party or another coalition. You choose how many of the partner's "
     "voters follow (an assumption: no published figure exists); those who do not follow stay home. These are 2023 votes "
     "recombined, not a forecast. On the What-if simulator, \"Use the coalition\" (Off by default) applies every slider "
     "to the coalition instead of the candidate. Only \"NDC (Obi + Kwankwaso)\" is a real ticket.", 10, False, INK),
    ("Words used. :: \"Won\" (or \"Secured\") = a quarter of the vote or more in a state; \"Within reach\" = 20% to just "
     "under a quarter; \"Out of reach\" = under 20%. \"The deciding state\" = the weakest state the candidate needs to "
     "reach 24 (or 25). Exact definitions and formulas are on the Technical notes page.", 10, False, INK),
    ("What it does not claim. :: It is not an electoral authority and not INEC's figures. It has no local-government "
     "detail. Small changes near a quarter of the vote are within the data's uncertainty: for example, Bola Tinubu's 29 "
     "states in 2023 rest on 96 votes in Adamawa.", 10, False, INK),
]


def page_how(pid):
    paras = []
    for i, (txt, sz, b, c) in enumerate(HOW):
        paras.append((txt, sz if i == 0 else 12, b, c))
        paras.append((" ", 8, False, c))
    v = [textbox(sid(pid, "body"), 40, 24, RIGHT_X - 30 - 40, 680, paras, alt="How to read this")]
    v += photo(pid, "howto", RIGHT_X)
    return "How to read this", v


# Technical notes (user decision 2026-11-14): plain section titles; each formula on its own line, written in words with
# Unicode symbols (no code-style names, no underscores), with what it means underneath. Every formula is the same
# mathematics as docs/methodology.md (shares in %, changes in points, so "+ points" = "+ S / 100" on fractions).
# Items: ("f", formula line) in semibold; ("t", explanation) in regular weight.
TECH = [
    [("How we count a state as won", [
        ("f", "Share = candidate’s votes ÷ valid votes"),
        ("t", "Worked out for each of the 37: the 36 states and Abuja (the method note calls each one a “unit”)."),
        ("f", "Won (“Secured”): share ≥ 25%"),
        ("f", "Within reach: 20% ≤ share < 25%"),
        ("f", "Out of reach: share < 20%"),
        ("t", "The 2023 pages test whole numbers: 4 × candidate’s votes ≥ valid votes.")]),
     ("How many states are needed", [
        ("f", "States needed (N) = 24 or 25"),
        ("t", "24 = two-thirds of the 36 states (Abuja counts as one of the 37); 25 = two-thirds of 37, rounded up. "
              "Default 24."),
        ("f", "Meets the rule: states won ≥ N"),
        ("f", "More states needed = N − states won"),
        ("t", "never below 0. These always use all 37, whatever else is selected.")]),
     ("Where the numbers could be off", [
        ("t", "Same change across a zone; rivals move together; 24 or 25 is our reading; 2023 data gaps (4,858 votes "
              "not placed in any state; Kano APC chosen from disputed copies).")]),
     ("Who wins: the result", [
        ("t", "Our reading of section 134:"),
        ("f", "Most votes + meets the rule → Outright win"),
        ("f", "Most votes, rule not met → Run-off"),
        ("f", "Tied on votes → No outright winner"),
        ("f", "Rival has most votes and a quarter in N states → Loses"),
        ("f", "Rival has most votes, but not that → Run-off")])],
    [("How the what-if sliders change the numbers", [
        ("t", "t = turnout slider ÷ 100 (−50% to +50%). Nationwide change and zone change are in points "
              "(−20 to +20 each) and add up."),
        ("t", "Step 1: turnout of the candidate’s 2023 voters"),
        ("f", "Votes after turnout = 2023 votes × (1 + t)"),
        ("f", "Valid votes after turnout ="),
        ("f", "2023 valid votes + 2023 votes × t"),
        ("f", "Share after turnout ="),
        ("f", "votes after turnout ÷ valid votes after turnout"),
        ("t", "Step 2: change in vote share"),
        ("f", "New share = share after turnout"),
        ("f", "+ nationwide change + zone change"),
        ("t", "shares in %, changes in points; then kept between 0% and 100%. Valid votes do not change."),
        ("t", "Step 3: votes (turnout first, then the change in share)"),
        ("f", "New votes = new share × valid votes after turnout"),
        ("t", "States that hit 0% or 100%:"),
        ("f", "share after turnout + changes ≤ 0% or ≥ 100%")]),
     ("How the other candidates move", [
        ("f", "Rival’s new votes = rival’s 2023 votes"),
        ("f", "× (100% − new share) ÷ (100% − share after turnout)"),
        ("t", "0 if the share after turnout is 100%. The state’s total stays the same."),
        ("t", "Closest rival = the other main candidate (APC, PDP, LP, NNPP) with the most votes nationwide.")]),
     ("Merging two parties", [
        ("t", "f = share of the partner’s 2023 voters who follow (0% to 100%)."),
        ("f", "Coalition votes = lead’s votes + f × partner’s votes"),
        ("f", "Valid votes = 2023 valid votes − (1 − f) × partner’s votes"),
        ("t", "Those who do not follow stay home. Side B with a partner: the same for its partner. Tested in whole "
              "numbers: 4 × coalition votes ≥ valid votes."),
        ("t", "Switch On: the simulator uses coalition votes and these valid votes in Step 1; Side B moves as one rival.")])],
    [("How we pick the deciding state", [
        ("t", "Rank all 37 by new share, highest first (ties: by state code, A to Z)."),
        ("f", "Deciding state = the state in position N"),
        ("f", "Gap = 25% − new share (in points)"),
        ("t", "A negative gap means the state is above a quarter.")]),
     ("Votes needed to reach a quarter", [
        ("f", "Points short = 25% − new share"),
        ("t", "never below 0."),
        ("f", "Extra votes needed ="),
        ("f", "25% × valid votes after turnout − new votes"),
        ("t", "rounded up, never below 0: votes switching to the candidate from others, with the state’s "
              "total unchanged."),
        ("f", "Votes to spare ="),
        ("f", "new votes − 25% × valid votes after turnout"),
        ("t", "rounded down, never below 0: votes that could switch away while the candidate keeps a quarter.")]),
     ("State codes", [
        ("t", "Two-letter codes on the maps are the official ISO 3166-2:NG codes without \u201cNG-\u201d. " + CODE_LIST)])],
]


def page_technical(pid):
    cx = LEFT_X + PW + 20            # photo on the left
    v = [textbox(sid(pid, "title"), cx, 8, W - 20 - cx, 34, [("Technical notes: terms and formulas", 18, True, INK)],
                 alt="Technical notes: terms and formulas"),
         textbox(sid(pid, "subtitle"), cx, 44, W - 20 - cx, 40, [
             ("The exact method behind every number, one formula per line, then what it means. Same mathematics as "
              "docs/methodology.md in the project repository.", 10, False, MUTED)],
             alt="Technical notes subtitle")]
    gap = 14
    colw = (W - 20 - cx - 2 * gap) // 3
    for ci, column in enumerate(TECH):
        x = cx + ci * (colw + gap)
        paras = []
        for title, body in column:
            paras.append((title, 11, True, WINE))
            paras += [(txt, 9, kind == "f", INK) for kind, txt in body]
            paras.append((" ", 6, False, INK))
        v.append(textbox(sid(pid, "col", str(ci)), x, 90, colw, 622, paras,
                         alt="Technical notes, column " + str(ci + 1) + ": " + "; ".join(t for t, _ in column) + "."))
    v += photo(pid, "technical", LEFT_X)
    return "Technical notes", v


SOURCES = [
    ("State results (2023): :: five copies of INEC's declaration, compared figure by figure - Wikipedia '2023 Nigerian "
     "presidential election' By-state table (revision 1381904162, CC BY-SA 4.0); AGADA-BI state table (no licence stated; "
     "one of five copies, and with Wikipedia the only per-state source for the minor candidates' column; its value is used "
     "for Kano APC); thenigerialawyer.com and ThisDay (identical copies; news pages, licence not stated); Vanguard (news "
     "page, licence and terms not checked; fetched once with a browser identity after the site refused our scripted "
     "request). Vote counts are used as facts with credit. Accessed 13-14 Nov 2026. Limitation: not INEC's own state "
     "sheets; 3 figures decided by hand (Kano APC, two Labour ties)."),
    ("National totals: :: INEC, Report of the 2023 General Election, Annexure 2 (national Declaration of Results), via a "
     "copy hosted on thenigerialawyer.com (not found on INEC's site); public report, licence not stated. Accessed 14 Nov 2026."),
    ("Registered voters: :: the 37 Wikipedia state pages (CC BY-SA 4.0). Limitation: they sum to 120,281 fewer than "
     "INEC's 93,469,008."),
    ("Zones: :: Wikipedia 'Geopolitical zones of Nigeria' (CC BY-SA 4.0). State boundaries: HDX COD-AB Nigeria (CC BY-IGO), "
     "simplified. Equal-size square layout: our own."),
]


def page_sources(pid):
    cw = RIGHT_X - 30 - 40           # photo on the right
    paras = [("Data sources", 18, True, INK),
             ("Full method, code and registers: github.com/batestguy/powerbi-naija-2027-elections-gap (method: "
              "docs/methodology.md). What the report does not claim: How to read this and Technical notes.", 9, False, MUTED),
             (" ", 6, False, INK)]
    for t in SOURCES:
        paras += [(t, 9, False, INK), (" ", 4, False, INK)]
    paras.append(("Sources, access dates, licences and transforms are listed in registers/sources.md and in the data "
                  "manifests (data/raw/*/manifest.json, data/staging/manifest.json) in the project repository.", 9, False, MUTED))
    v = [textbox(sid(pid, "body"), 40, 20, cw, 280, paras, alt="Data sources")]
    credits = [("Photo credits (Wikimedia Commons, accessed 14 Nov 2026; cropped and resized, shared under the same "
                "licence: CC BY-SA 4.0 = creativecommons.org/licenses/by-sa/4.0, CC BY 4.0 = "
                "creativecommons.org/licenses/by/4.0)", 9, True, INK)]
    for ph in PHOTOS.values():
        credits.append((f"{ph['page']}: :: {ph['author']}, {ph['licence']}, {ph['file_page'].replace('https://', '')}", 9, False, INK))
    for c in CANDS.values():
        credits.append((f"Portrait, {c['candidate']}: :: {c['author']}, {c['licence']}, {c['file_page'].replace('https://', '')}", 9, False, INK))
    credits.append(("Party logos are trademarks of their respective parties, shown for identification only; no "
                    "endorsement implied. :: Licence as stated on each file page: " + " ; ".join(
                        f"{l['party']} {l['file_page'].replace('https://', '')} ({l['licence_as_stated'].lower()})"
                        for l in LOGO_LIST), 9, False, INK))
    credits.append(("Party now (news reports checked 14 Nov 2026, re-checked 20 Nov 2026; not an official INEC list, and it can change before 2027)", 10, True, INK))
    for r in PARTY_NOW:
        extra = (f" Role: {r['role']}." if r.get("role") else "") + (
            f" {r['note']} ({r['note_source_publisher']}, {r['note_date']}, {r['note_source_url'].replace('https://', '')})."
            if r.get("note") else "")
        credits.append((f"{r['candidate']}: :: {r['party_now']} as of {r['as_of']}, {r['source_publisher']}, "
                        f"{r['source_url'].replace('https://', '')}.{extra}", 9, False, INK))
    real = [r for r in COAL_NAMES if r["status"] == "real"]
    credits.append(("Coalition names: :: " + "; ".join(
        f"\"{r['display_name']}\" is a real joint ticket ({r['source_publisher']}, {r['as_of']}, "
        f"{r['source_url'].replace('https://', '')})" for r in real)
        + ". Every other pairing is hypothetical, named \"X + Y (what-if)\" (data/reference/coalition_names.csv).",
        9, False, INK))
    v.append(textbox(sid(pid, "credits"), 40, 302, cw, 410, credits,
                     alt="Credits: each page photo and candidate portrait with photographer, licence and file page; the "
                         "news reports used for each candidate's party now."))
    v += photo(pid, "sources", RIGHT_X)
    return "Data sources", v


TIP_W, TIP_H = 320, 150


def page_tiletip(pid):
    """Hover card for the tile maps (a matrix has no tooltip fields): the state's full name, its share and status
    under the current settings. Hidden tooltip page; the hovered tile's row and column filter it to one state."""
    v = [classic_card(sid(pid, "name"), 8, 6, TIP_W - 16, 44, "State name", None, "Name of the state under the pointer.", 14,
                      accent=False),
         classic_card(sid(pid, "share"), 8, 52, 150, 90, "Scenario share", "Share of the vote",
                      "The candidate's share of the vote in this state under the current settings.", 14, accent=False),
         classic_card(sid(pid, "label"), 162, 52, TIP_W - 170, 90, "Scenario label", "Status",
                      "Whether the state is won, within reach or out of reach under the current settings.", 12,
                      accent=False)]
    return "State on hover (tooltip)", v


PAGES = [("overview", page_overview), ("path", page_path), ("map", page_map), ("simulator", page_sim),
         ("merge", page_merge), ("h2h", page_h2h),
         ("howto", page_how), ("technical", page_technical), ("sources", page_sources)]
NON_DATA = ("slicer", "textbox", "image")   # the candidate photo is an image too   # never cross-filter sources; textboxes and images are never targets


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
    display, visuals = page_tiletip(TILE_TIP)
    write_page(pages_dir, TILE_TIP, display, visuals, write_json, hidden=True, tooltip=True)
    order.append(TILE_TIP)
    display, visuals = page_h2htip(H2H_TIP)
    write_page(pages_dir, H2H_TIP, display, visuals, write_json, hidden=True, tooltip=True)
    order.append(H2H_TIP)
    if extra_hidden:
        pid, display, visuals = extra_hidden
        write_page(pages_dir, pid, display, visuals, write_json, hidden=True)
        order.append(pid)
    write_json(pages_dir / "pages.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": order, "activePageName": order[0]})
    return order


def write_page(pages_dir, pid, display, visuals, write_json, hidden=False, tooltip=False):
    import shutil
    d = pages_dir / pid
    if (d / "visuals").exists():
        shutil.rmtree(d / "visuals")
    page = {"$schema": PAGE, "name": pid, "displayName": display, "displayOption": "FitToPage", "height": H, "width": W}
    # Clicking a chart, table or map must not silently change other visuals (e.g. headline cards showing one zone):
    # only slicers filter. Every data visual -> every other data visual = NoFilter.
    sources = [v["name"] for v in visuals if v["visual"]["visualType"] not in NON_DATA]
    page["visualInteractions"] = [{"source": a, "target": c["name"], "type": "NoFilter"}
                                  for a in sources for c in visuals
                                  if c["name"] != a and c["visual"]["visualType"] not in ("textbox", "image")]
    if hidden:
        page["visibility"] = "HiddenInViewMode"
    if tooltip:
        page.update({"displayOption": "ActualSize", "width": TIP_W, "height": TIP_H,
                     "pageBinding": {"name": "Pod", "type": "Tooltip", "parameters": []}})
    write_json(d / "page.json", page)
    for i, v in enumerate(visuals):
        v["position"]["tabOrder"] = i
        v["position"]["z"] = i
        write_json(d / "visuals" / v["name"] / "visual.json", v)
