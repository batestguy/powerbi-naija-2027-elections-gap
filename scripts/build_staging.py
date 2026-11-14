"""Phase 2 staging. Parses the raw snapshots into tidy CSVs in data/staging/.

Rules: no value is filled, guessed or interpolated. A number that does not parse cleanly stops
the script. Every state name is resolved through data/reference/crosswalk_state_names.csv by
exact string match; names not in it are written to reports/unmatched_keys.csv (and fail validation).

Inputs: the latest dated folder of each source under data/raw/ (or --date YYYY-MM-DD).
Usage (repo root):  .venv/Scripts/python.exe -I scripts/build_staging.py [--date 2026-11-13]

State results are RECONCILED, not taken from one source: Wikipedia's By-state table does not sum to INEC's
national declaration. Five copies of the INEC state declaration (Wikipedia, AGADA, thenigerialawyer.com,
ThisDay, Vanguard) are compared cell by cell; ThisDay and thenigerialawyer.com share every error, so they
vote as one copy. Unanimous or clear-majority values are used; ties and overrides come only from
data/reference/result_cell_decisions.csv. Every non-unanimous cell is written to
reports/result_reconciliation.csv. Without --date, each source's latest snapshot is used.
"""
import csv, html, json, re, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, STG, REF = ROOT / "data" / "raw", ROOT / "data" / "staging", ROOT / "data" / "reference"
REPORTS = ROOT / "reports"
PARTIES = [("APC", "Bola Tinubu"), ("PDP", "Atiku Abubakar"), ("LP", "Peter Obi"), ("NNPP", "Rabiu Kwankwaso")]
ZONE_CODES = {"North Central": "NC", "North East": "NE", "North West": "NW",
              "South East": "SE", "South South": "SS", "South West": "SW"}


def snap(source):
    """Dated snapshot folder for a source (--date, else the latest)."""
    if "--date" in sys.argv:
        d = RAW / source / sys.argv[sys.argv.index("--date") + 1]
    else:
        ds = sorted(p for p in (RAW / source).glob("????-??-??") if p.is_dir())
        if not ds:
            raise FileNotFoundError(f"no snapshot for {source}; run scripts/pull_sources.py")
        d = ds[-1]
    return d, json.loads((d / "manifest.json").read_text(encoding="utf-8"))


def to_int(s, where):
    """Strict integer parse: digits with optional thousands commas. Anything else stops the build."""
    t = s.replace("'''", "").strip()
    if not re.fullmatch(r"\d{1,3}(,\d{3})*|\d+", t):
        raise ValueError(f"unparseable number {s!r} at {where}")
    return int(t.replace(",", ""))


def to_pct(s, where):
    t = s.replace("'''", "").strip()
    if not re.fullmatch(r"\d+(\.\d+)?%", t):
        raise ValueError(f"unparseable percentage {s!r} at {where}")
    return float(t[:-1])


def strip_refs(t):
    """Drop <ref>...</ref> footnotes and <!-- comments --> (markup, not data)."""
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r"<ref[^>/]*/>", "", t)
    return re.sub(r"<ref[^>]*>.*?</ref>", "", t, flags=re.S)


class Crosswalk:
    def __init__(self):
        lines = (REF / "crosswalk_state_names.csv").read_text(encoding="utf-8").splitlines()
        rows = list(csv.DictReader(l for l in lines if not l.startswith("#")))
        self.map = {r["name_variant"]: r["state_pcode"] for r in rows}
        if len(self.map) != len(rows):
            raise ValueError("duplicate name_variant in crosswalk")
        self.rows, self.seen, self.unmatched = rows, {}, []

    def __call__(self, name, source, context=""):
        self.seen.setdefault(name, set()).add(source)
        p = self.map.get(name)
        if p is None:
            self.unmatched.append({"source": source, "name": name, "context": context})
        return p


# ---------- parsers ----------

def parse_wiki_by_state(xw):
    d, man = snap("wikipedia_main")
    parse = json.loads((d / "by_state.json").read_text(encoding="utf-8"))["parse"]
    revid, wt = parse["revid"], strip_refs(parse["wikitext"])
    lines = wt.split("\n")
    states, total = [], None
    for i, ln in enumerate(lines):
        m = re.match(r'\| style="text-align:left;" \| \[\[(2023 Nigerian presidential election in [^|\]]+)\|(.*?)\]\]\s*$', ln)
        if m or ln.strip() == "! Total":
            cells = lines[i + 1:i + 8]
            sep = "!" if not m else "|"
            if not all(c.startswith(sep) for c in cells):
                raise ValueError(f"unexpected row layout after line {i}: {cells}")
            c = [x.strip() for x in cells]
            c = [x[1:].strip() for x in c]
            rec = {}
            for k, (party, _) in enumerate(PARTIES):
                v, p, t = [x.strip() for x in c[k].split("||")]
                rec[party] = to_int(v, f"wiki {party} line {i}")
                rec[party + "_pct"] = to_pct(p, f"wiki {party}% line {i}")
                rec[party + "_T"] = to_int(t, f"wiki {party} T line {i}")
            v, p = [x.strip() for x in c[4].split("||")]
            rec["OTHERS"], rec["OTHERS_pct"] = to_int(v, f"wiki others line {i}"), to_pct(p, f"wiki others% line {i}")
            rec["total_valid"] = to_int(c[5], f"wiki valid line {i}")
            rec["turnout_pct"] = to_pct(c[6], f"wiki turnout line {i}")
            if m:
                label = re.sub(r"\{\{abbr\|([^|}]+)\|[^}]*\}\}", r"\1", m.group(2)).strip()
                rec.update(page_title=m.group(1), wiki_name=label,
                           state_pcode=xw(label, "wikipedia_main", "By state label"))
                xw(m.group(1).replace("2023 Nigerian presidential election in ", ""), "wikipedia_main", "By state link")
                states.append(rec)
            else:
                total = rec
    if len(states) != 37 or total is None:
        raise ValueError(f"expected 37 state rows + Total in By state table, parsed {len(states)}")
    return states, total, revid, man


def parse_wiki_states(xw, by_title):
    d, man = snap("wikipedia_states")
    out = {}
    for f in man["files"]:
        parse = json.loads((d / f["file"]).read_text(encoding="utf-8"))["parse"]
        wt = parse["wikitext"]
        title = f["title"]
        pcode = xw(title.replace("2023 Nigerian presidential election in ", ""), "wikipedia_states", "page title")
        if by_title.get(title) != pcode:
            raise ValueError(f"state page {title} does not map to its By-state row")
        reg = re.search(r"^\|\s*registered\s*=\s*([^\n<]*)", wt, re.M)
        tur = re.search(r"^\|\s*turnout\s*=\s*([^\n<]*)", wt, re.M)
        rec = {"registered": to_int(reg.group(1), f"{title} registered") if reg and reg.group(1).strip() else None,
               "infobox_turnout_pct": to_pct(tur.group(1), f"{title} turnout") if tur and tur.group(1).strip() else None,
               "revid": parse["revid"]}
        for key, box in [("ebox_total_valid", "total"), ("rejected", "invalid"), ("total_cast", "turnout")]:
            m = re.search(r"\{\{\s*Election box " + box + r"[^}]*?\|\s*votes\s*=\s*([^\n|}]*)", wt, re.I)
            rec[key] = to_int(m.group(1), f"{title} ebox {box}") if m and m.group(1).strip() else None
        out[pcode] = rec
    return out, man


def parse_zones(xw):
    d, man = snap("zones")
    parse = json.loads((d / "zones.json").read_text(encoding="utf-8"))["parse"]
    wt = parse["wikitext"]
    sec = wt[wt.index("==List of geopolitical zones=="):]
    sec = sec[:sec.index("{{div col end")]
    zone_of, zone = {}, None
    for ln in sec.split("\n"):
        if ln.startswith("* "):
            links = re.findall(r"\[\[([^|\]]+)(?:\|([^\]]+))?\]\]", ln)
            zone = (links[0][1] or links[0][0]).strip()
            if zone not in ZONE_CODES:
                raise ValueError(f"unknown zone heading {zone!r}")
        elif ln.startswith("** ") and zone:
            for target, label in re.findall(r"\[\[([^|\]]+)(?:\|([^\]]+))?\]\]", ln):
                p = xw((label or target).strip(), "zones", zone)
                if p in zone_of:
                    raise ValueError(f"{p} listed in two zones")
                zone_of[p] = zone
    return zone_of, parse["revid"], man


def parse_hdx():
    d, man = snap("hdx_cod_ab")
    zf = next(f["file"] for f in man["files"] if f["file"].endswith(".zip"))
    fc = json.loads(zipfile.ZipFile(d / zf).read("nga_admin1.geojson"))
    return [(f["properties"]["adm1_pcode"], f["properties"]["adm1_name"]) for f in fc["features"]], man


def parse_nigerialawyer(xw):
    d, man = snap("nigerialawyer")
    h = (d / "results.html").read_text(encoding="utf-8")
    tables = re.findall(r"<table.*?</table>", h, re.S)
    if len(tables) != 1:
        raise ValueError(f"expected 1 table on nigerialawyer page, found {len(tables)}")
    rows = [[html.unescape(re.sub(r"<.*?>", "", c)).replace("\xa0", " ").strip()
             for c in re.findall(r"<t[dh].*?</t[dh]>", r, re.S)] for r in re.findall(r"<tr.*?</tr>", tables[0], re.S)]
    hdr = rows[1]
    cols = {p: next(j for j, h_ in enumerate(hdr) if f"({p})" in h_) for p, _ in PARTIES}
    out, total, fixes = {}, None, []
    for r in rows[2:]:
        rec = {}
        for p, j in cols.items():
            raw = r[j]
            clean = re.sub(r"(?<=\d),\s+(?=\d{3}\b)", ",", raw)  # "198, 567" -> "198,567"
            if clean != raw:
                fixes.append({"row": r[0], "party": p, "raw": raw, "parsed_as": clean})
            rec[p] = to_int(clean, f"nigerialawyer {r[0]} {p}")
        if r[0] == "TOTAL":
            total = rec
        else:
            out[xw(r[0], "nigerialawyer", "results table")] = rec
    return out, total, fixes, man


def parse_agada(xw):
    import openpyxl
    d, man = snap("agada")
    ws = openpyxl.load_workbook(d / "agada_results.xlsx", read_only=True, data_only=True)["Results"]
    it = ws.iter_rows(values_only=True)
    hdr = list(next(it))
    out = {}
    for r in it:
        if r[0] is None:
            continue
        row = dict(zip(hdr, r))
        rec = {p: int(row[p]) for p, _ in PARTIES}
        rec["OTHERS"], rec["total_valid"] = int(row["Others"]), int(row["Total Valid Votes"])
        out[xw(str(row["State"]), "agada", "Results sheet")] = rec
    return out, man


NEWS_HEADER_SKIP = {"STATES", "State", "2023 PRESIDENTIAL ELECTION RESULTS (as announced by INEC)"}
NEWS_TOTAL_LABELS = {"TOTAL", "AgGregate"}


def clean_news_number(raw, where, fixes):
    """Strict parse with two logged, unambiguous repairs: '198, 567' -> 198,567 and '85.829' -> 85,829.
    Anything else (e.g. '30,8372') is returned as None and logged - never guessed."""
    t = raw.strip()
    c = re.sub(r"(?<=\d),\s+(?=\d{3}\b)", ",", t)
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", c):
        c = c.replace(".", ",")
    if re.fullmatch(r"\d{1,3}(,\d{3})*|\d+", c):
        if c != t:
            fixes.append({"where": where, "raw": raw, "parsed_as": c})
        return int(c.replace(",", ""))
    fixes.append({"where": where, "raw": raw, "parsed_as": None})
    return None


def parse_news_table(xw, source, fname):
    """Four-party state table from a news page. Header row: first row naming all four parties."""
    d, man = snap(source)
    h = (d / fname).read_text(encoding="utf-8")
    tables = re.findall(r"<table.*?</table>", h, re.S)
    if len(tables) != 1:
        raise ValueError(f"expected 1 table on {source} page, found {len(tables)}")
    rows = [[html.unescape(re.sub(r"<.*?>", "", c)).replace("\xa0", " ").strip()
             for c in re.findall(r"<t[dh].*?</t[dh]>", r, re.S)] for r in re.findall(r"<tr.*?</tr>", tables[0], re.S)]
    hi = next(i for i, r in enumerate(rows) if all(any(c == p or f"({p})" in c for c in r) for p, _ in PARTIES))
    cols = {p: next(j for j, c in enumerate(rows[hi]) if c == p or f"({p})" in c) for p, _ in PARTIES}
    out, total, fixes = {}, None, []
    for r in rows[hi + 1:]:
        if not r or r[0] in NEWS_HEADER_SKIP:
            continue
        rec = {p: clean_news_number(r[j], f"{source} {r[0]} {p}", fixes) for p, j in cols.items()}
        if r[0] in NEWS_TOTAL_LABELS:
            total = rec
        else:
            out[xw(r[0], source, "results table")] = rec
    return out, total, fixes, man


COPY_GROUPS = {"wikipedia": ["wikipedia"], "agada": ["agada"],
               "nigerialawyer+thisday": ["nigerialawyer", "thisday"], "vanguard": ["vanguard"]}


def read_decisions():
    lines = (REF / "result_cell_decisions.csv").read_text(encoding="utf-8").splitlines()
    return {(r["state_pcode"], r["party"]): {"chosen": int(r["chosen_votes"]), "reason": r["reason"]}
            for r in csv.DictReader(l for l in lines if not l.startswith("#"))}


def reconcile(copies, keys):
    """copies: {source: {(pcode, party): votes or None}}. Returns chosen values and a log of non-unanimous cells."""
    decisions, chosen, log = read_decisions(), {}, []
    for k in keys:
        vals = {s: copies[s].get(k) for s in copies}
        present = {v for v in vals.values() if v is not None}
        if not present:
            raise ValueError(f"no copy has a value for {k}")
        votes = {}
        for g, members in COPY_GROUPS.items():
            for v in {vals[m] for m in members if vals.get(m) is not None}:
                votes[v] = votes.get(v, 0) + 1
        top = max(votes.values())
        leaders = [v for v, n in votes.items() if n == top]
        if k in decisions:
            v, rule, reason = decisions[k]["chosen"], "decision", decisions[k]["reason"]
            if v not in present:
                raise ValueError(f"decision for {k} ({v}) is not printed by any copy {vals}")
            if len(present) == 1:
                raise ValueError(f"decision for {k} on a unanimous cell")
        elif len(present) == 1:
            v, rule, reason = next(iter(present)), "unanimous", ""
        elif len(leaders) == 1:
            v, rule, reason = leaders[0], "majority", ""
        else:
            raise ValueError(f"tie at {k}: {votes}; add a row to data/reference/result_cell_decisions.csv")
        chosen[k] = v
        if rule != "unanimous" or any(x is None for x in vals.values()):
            log.append({"state_pcode": k[0], "party": k[1], **vals, "chosen": v, "rule": rule,
                        "copies_for_chosen": votes[v], "copies_total": len(COPY_GROUPS), "reason": reason})
    unused = set(decisions) - set(keys)
    if unused:
        raise ValueError(f"decisions for unknown cells: {unused}")
    return chosen, log


def read_inec_national():
    lines = (REF / "inec_national_declaration_2023.csv").read_text(encoding="utf-8").splitlines()
    rows = list(csv.DictReader(l for l in lines if not l.startswith("#")))
    cand = {r["party"]: int(r["value"]) for r in rows if r["measure"] == "candidate_votes"}
    other = {r["measure"]: int(r["value"]) for r in rows if r["measure"] != "candidate_votes"}
    return cand, other


def parse_mundx(xw):
    try:
        d, man = snap("mundx")
    except FileNotFoundError:
        return None, None
    recs = json.loads((d / "lgas.json").read_text(encoding="utf-8"))
    roll = {}
    for r in recs:
        p = xw(r["state_name"], "mundx", "lgas.json state_name")
        a = roll.setdefault(p, {"lga_count": 0, "apc": 0, "pdp": 0, "lp": 0, "nnpp": 0, "four_party": 0,
                                "polling_units_included": 0, "inventory": 0, "unresolved": 0})
        a["lga_count"] += 1
        for k in list(a)[1:]:
            if r[k] is None:
                raise ValueError(f"null {k} in Mundx {r['state_name']}/{r['lga_name']}")
            a[k] += int(r[k])
    return roll, man


# ---------- writers ----------

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})
    print(f"  {path.relative_to(ROOT)}: {len(rows)} rows")


def main():
    xw = Crosswalk()
    hdx, hdx_man = parse_hdx()
    for p, n in hdx:
        if xw(n, "hdx_cod_ab", "adm1_name") != p:
            raise ValueError(f"crosswalk maps HDX name {n!r} to a different P-code than {p}")
    hdx_name = dict(hdx)
    states, total, revid, wm_man = parse_wiki_by_state(xw)
    by_title = {s["page_title"]: s["state_pcode"] for s in states}
    st_pages, ws_man = parse_wiki_states(xw, by_title)
    zone_of, zones_revid, z_man = parse_zones(xw)
    nl, nl_total, nl_fixes, nl_man = parse_nigerialawyer(xw)
    ag, ag_man = parse_agada(xw)
    td, td_total, td_fixes, td_man = parse_news_table(xw, "thisday", "page.html")
    vg, vg_total, vg_fixes, vg_man = parse_news_table(xw, "vanguard", "page.html")
    inec_cand, inec_other = read_inec_national()
    mx, mx_man = parse_mundx(xw)

    src_main = f"Wikipedia '2023 Nigerian presidential election' By state, revid {revid}"
    wik = {s["state_pcode"]: s for s in states}
    keys = [(p, party) for p in sorted(wik) for party, _ in PARTIES]
    copies = {"wikipedia": {k: wik[k[0]][k[1]] for k in keys},
              "agada": {k: ag.get(k[0], {}).get(k[1]) for k in keys},
              "nigerialawyer": {k: nl.get(k[0], {}).get(k[1]) for k in keys},
              "thisday": {k: td.get(k[0], {}).get(k[1]) for k in keys},
              "vanguard": {k: vg.get(k[0], {}).get(k[1]) for k in keys}}
    chosen, recon_log = reconcile(copies, keys)
    others_mismatch = [p for p in wik if ag.get(p, {}).get("OTHERS") not in (None, wik[p]["OTHERS"])]
    if others_mismatch:
        raise ValueError(f"OTHERS differs between Wikipedia and AGADA in {others_mismatch}; no rule to settle it")
    total_valid = {p: sum(chosen[(p, party)] for party, _ in PARTIES) + wik[p]["OTHERS"] for p in wik}
    src_recon = ("Reconciled from five copies of the INEC state declaration (Wikipedia revid "
                 f"{revid}, AGADA-BI, thenigerialawyer.com, ThisDay, Vanguard); see reports/result_reconciliation.csv")
    dim_state = [{"state_pcode": p, "state_name": n,
                  "wiki_name": next((s["wiki_name"] for s in states if s["state_pcode"] == p), None),
                  "zone": zone_of.get(p), "zone_code": ZONE_CODES.get(zone_of.get(p)),
                  "is_fct": int(p == "NG015")} for p, n in sorted(hdx)]
    write_csv(STG / "dim_state.csv", dim_state, ["state_pcode", "state_name", "wiki_name", "zone", "zone_code", "is_fct"])

    dim_zone = [{"zone_code": c, "zone": z, "state_count": sum(1 for v in zone_of.values() if v == z),
                 "source": f"Wikipedia 'Geopolitical zones of Nigeria', revid {zones_revid}"} for z, c in ZONE_CODES.items()]
    write_csv(STG / "dim_zone.csv", dim_zone, ["zone_code", "zone", "state_count", "source"])

    fact = []
    for s in sorted(states, key=lambda s: s["state_pcode"] or ""):
        for party, cand in PARTIES + [("OTHERS", "Other candidates (14)")]:
            k = (s["state_pcode"], party)
            if party == "OTHERS":
                rule = "wikipedia=agada"
            else:
                rule = next((r["rule"] for r in recon_log if (r["state_pcode"], r["party"]) == k), "unanimous")
            fact.append({"state_pcode": s["state_pcode"], "party": party, "candidate": cand,
                         "votes": chosen.get(k, s[party]), "votes_rule": rule,
                         "votes_wikipedia": s[party], "pct_reported_wikipedia": s[party + "_pct"],
                         "threshold_flag_reported_wikipedia": s.get(party + "_T"),
                         "source": (src_main + " (= AGADA-BI)" if party == "OTHERS" else
                                    src_recon + ("; HAND DECISION chosen for consistency with INEC's national total, "
                                                 "not confirmed as the as-announced state figure - see "
                                                 "data/reference/result_cell_decisions.csv" if rule == "decision" else "")),
                         "source_revid": revid})
    write_csv(STG / "fact_result_2023.csv", fact, ["state_pcode", "party", "candidate", "votes", "votes_rule",
                                                    "votes_wikipedia", "pct_reported_wikipedia",
                                                    "threshold_flag_reported_wikipedia", "source", "source_revid"])
    write_csv(REPORTS / "result_reconciliation.csv", recon_log,
              ["state_pcode", "party", "wikipedia", "agada", "nigerialawyer", "thisday", "vanguard", "chosen", "rule",
               "copies_for_chosen", "copies_total", "reason"])

    turnout = []
    for s in sorted(states, key=lambda s: s["state_pcode"] or ""):
        pg = st_pages.get(s["state_pcode"], {})
        reg = pg.get("registered")
        turnout.append({
            "state_pcode": s["state_pcode"], "registered": reg, "accredited": None,
            "total_valid": total_valid[s["state_pcode"]], "total_valid_wikipedia": s["total_valid"],
            "total_valid_agada": ag.get(s["state_pcode"], {}).get("total_valid"),
            "rejected": pg.get("rejected"), "total_cast": pg.get("total_cast"),
            "turnout_pct_reported": s["turnout_pct"], "infobox_turnout_pct": pg.get("infobox_turnout_pct"),
            "total_cast_implied_from_turnout": round(reg * s["turnout_pct"] / 100) if reg is not None else None,
            "source_results": src_main,
            "source_registered": f"Wikipedia '{s['page_title']}' infobox, revid {pg.get('revid')}" if reg is not None else None,
            "source_rejected_total_cast": (f"Wikipedia '{s['page_title']}' Election box, revid {pg.get('revid')}"
                                           if pg.get("rejected") is not None or pg.get("total_cast") is not None else None),
            "ebox_total_valid": pg.get("ebox_total_valid"),
        })
    write_csv(STG / "fact_turnout_2023.csv", turnout,
              ["state_pcode", "registered", "accredited", "total_valid", "total_valid_wikipedia", "total_valid_agada", "rejected", "total_cast", "turnout_pct_reported",
               "infobox_turnout_pct", "total_cast_implied_from_turnout", "ebox_total_valid",
               "source_results", "source_registered", "source_rejected_total_cast"])

    national = [{"source": "wikipedia_main_total_row", **{k: total[k] for k in ["APC", "PDP", "LP", "NNPP", "OTHERS", "total_valid"]},
                 "T_APC": total["APC_T"], "T_PDP": total["PDP_T"], "T_LP": total["LP_T"], "T_NNPP": total["NNPP_T"],
                 "turnout_pct": total["turnout_pct"]},
                {"source": "nigerialawyer_total_row", **nl_total},
                {"source": "thisday_total_row", **td_total},
                {"source": "vanguard_total_row", **vg_total},
                {"source": "inec_declaration", **{p: inec_cand[p] for p in ["APC", "PDP", "LP", "NNPP"]},
                 "OTHERS": sum(v for p, v in inec_cand.items() if p not in ("APC", "PDP", "LP", "NNPP")),
                 "total_valid": inec_other["valid_votes"]}]
    write_csv(STG / "national_totals_reported.csv", national,
              ["source", "APC", "PDP", "LP", "NNPP", "OTHERS", "total_valid", "T_APC", "T_PDP", "T_LP", "T_NNPP", "turnout_pct"])

    cross = []
    for p in sorted(hdx_name):
        for party, _ in PARTIES + [("OTHERS", None), ("total_valid", None)]:
            cross.append({"state_pcode": p, "measure": party,
                          "nigerialawyer": nl.get(p, {}).get(party), "agada": ag.get(p, {}).get(party),
                          "thisday": td.get(p, {}).get(party), "vanguard": vg.get(p, {}).get(party)})
    write_csv(STG / "crosscheck_sources.csv", cross, ["state_pcode", "measure", "nigerialawyer", "agada", "thisday", "vanguard"])

    xrows = [{"name_variant": r["name_variant"], "state_pcode": r["state_pcode"],
              "seen_in": ";".join(sorted(xw.seen.get(r["name_variant"], []))), "note": r["note"]} for r in xw.rows]
    write_csv(STG / "crosswalk_state_names.csv", xrows, ["name_variant", "state_pcode", "seen_in", "note"])

    if mx is not None:
        write_csv(STG / "mundx_state_rollup.csv", [{"state_pcode": p, **v} for p, v in sorted(mx.items())],
                  ["state_pcode", "lga_count", "apc", "pdp", "lp", "nnpp", "four_party",
                   "polling_units_included", "inventory", "unresolved"])

    write_csv(REPORTS / "unmatched_keys.csv", xw.unmatched, ["source", "name", "context"])

    def ref(man):
        return {"snapshot_date": man["snapshot_date"],
                "files": [{k: f.get(k) for k in ("file", "sha256", "revid")} for f in man["files"]]}
    stg_man = {"built_by": "scripts/build_staging.py", "main_revid": revid, "zones_revid": zones_revid,
               "nigerialawyer_number_format_fixes": nl_fixes,
               "news_number_format_fixes": td_fixes + vg_fixes,
               "inputs": {"wikipedia_main": ref(wm_man), "wikipedia_states": ref(ws_man), "zones": ref(z_man),
                          "hdx_cod_ab": ref(hdx_man), "nigerialawyer": ref(nl_man), "agada": ref(ag_man), "thisday": ref(td_man), "vanguard": ref(vg_man),
                          **({"mundx": ref(mx_man)} if mx_man else {})}}
    (STG / "manifest.json").write_text(json.dumps(stg_man, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"  unmatched names: {len(xw.unmatched)}; nigerialawyer number-format fixes: {len(nl_fixes)}")


if __name__ == "__main__":
    main()
