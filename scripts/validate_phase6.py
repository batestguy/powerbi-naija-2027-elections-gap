"""Phase 6 QA checks against the live model in Power BI Desktop plus the report files (no clicking).

Covers the brief's Phase 6 list where a script can decide it:
  1. Phase 3 and Phase 4 checks re-run (model = staging, national = INEC, scenario engine = methodology)
  2. National totals vs independent copies (Wikipedia, NigeriaLawyer, ThisDay, Vanguard) within a stated tolerance
  3. Geometry keys after import: the map files embedded in the report = the built files, and their keys = the model's
  4. Overview page = simulator at the simulator's saved (neutral) slider values, per unit and nationally
  5. Refresh from a clean cache (no cache.abf on disk; the open + refresh ran from source CSVs)
  6. Static accessibility: alt text on every visual of the visible pages, unique tab order, slider defaults neutral
  7. Engine time for the heaviest page queries at a non-neutral setting (rendering time not included)
  8. (2026-11-14 redesign) Maps bind to the state NAME (hover shows names), and the TopoJSON name = model name for all 37
  9. (2026-11-14 redesign) Plain-words sentences and votes needed / votes to spare = an independent exact computation
     from the staging CSVs (Python fractions), for every candidate at several slider settings
 10. (2026-11-14 redesign) Photos: embedded files = built files, licence allowed, alt text, last in tab order
 11. (2026-11-14 redesign) Result sentence and settings sentence = the Phase 4 reference (validate_phase4.py functions)
 12. (2026-11-14 redesign) Candidate identity: portrait data URI = built file (<= 30,000 chars), party now = the dated
     sources in data/reference/party_now.csv, party-colour text contrast >= 4.5:1 (recomputed here)
 13. (2026-11-16 coalitions) Coalition names: every "real" row of data/reference/coalition_names.csv has a source
     (publisher, URL, date) and the model's name table = the CSV; the real ticket's date on the pages = the CSV
 14. (2026-11-16 coalitions) Coalition pickers, follow sliders and switch saved at the preset (LP + NNPP, 100%, vs APC
     alone; switch Off) and synced across the coalition pages and the simulator
Writes reports/phase6_validation.json; exits 1 on any gate failure.

Usage (repo root, Desktop open on pbip/NaijaElectionsGap.pbip):  uv run python -I scripts/validate_phase6.py
"""
import csv, hashlib, json, math, statistics, subprocess, sys, tempfile, time
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))   # -I leaves the script folder off the path
from build_stamp import build_stamp, same_build  # noqa: E402
STG, REF, REP = ROOT / "data" / "staging", ROOT / "data" / "reference", ROOT / "reports"
RPT = ROOT / "pbip" / "NaijaElectionsGap.Report"
PS = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "pbi_engine.ps1")]
PARTIES = ["APC", "PDP", "LP", "NNPP"]
NATIONAL_TOLERANCE_VOTES = 20     # stated tolerance per candidate vs each independent copy of the national total
LATENCY_LIMIT_S = 2.0             # engine time per page query, empty cache (median of 3); rendering not measured
checks = []


def check(name, ok, evidence, status=None):
    checks.append({"check": name, "status": status or ("pass" if ok else "fail"), "evidence": evidence})
    print(f"  [{checks[-1]['status'].upper():4}] {name}", flush=True)   # as it lands (a stopped run still shows progress)


def engine(*args):
    r = subprocess.run(PS + list(args), capture_output=True, text=True, encoding="utf-8", timeout=420)
    if r.returncode:
        raise RuntimeError(f"pbi_engine.ps1 {args[:2]} failed:\n{r.stderr or r.stdout}")
    return json.loads(r.stdout.lstrip("﻿"))


def dax(q):
    with tempfile.NamedTemporaryFile("w", suffix=".dax", delete=False, encoding="utf-8") as f:
        f.write(q)
    try:
        rows = engine("-Action", "Query", "-DaxFile", f.name)
    finally:
        Path(f.name).unlink(missing_ok=True)
    return [{k.rsplit("[", 1)[-1].rstrip("]"): v for k, v in r.items()} for r in rows]


def read(name, folder=STG):
    with open(folder / name, encoding="utf-8") as f:
        return list(csv.DictReader(l for l in f if not l.startswith("#")))


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pages():
    out = {}
    for pj in (RPT / "definition" / "pages").glob("*/page.json"):
        meta = json.loads(pj.read_text(encoding="utf-8"))
        vis = [json.loads(v.read_text(encoding="utf-8")) for v in sorted((pj.parent / "visuals").glob("*/visual.json"))]
        out[meta["displayName"]] = {"hidden": meta.get("visibility") == "HiddenInViewMode", "visuals": vis}
    return out


def rerun(script, *extra, timeout=1800):
    r = subprocess.run(["uv", "run", "python", "-I", str(ROOT / "scripts" / script), *extra],
                       capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=timeout)
    return r.returncode, (r.stdout.strip().splitlines() or [""])[-1]


PHASE4_PARTS = ["core", "invalid", "switch_off", "boundary", "simulator", "pages"]


def phase4_on_current_build():
    """The full Phase 4 run takes ~45 min (longer than one subprocess timeout, and heavy on this machine's memory).
    Reuse reports/phase4_validation.json only if it passed, is complete, holds all six parts with check counts that add
    up, and its build stamp (model files, staging + reference tables, check and engine scripts, live model measures;
    scripts/build_stamp.py) equals the current one. Otherwise run the parts one by one and combine (review 2026-11-18)."""
    res = REP / "phase4_validation.json"
    d = json.loads(res.read_text(encoding="utf-8")) if res.exists() else {}
    now = build_stamp()
    parts_ok = isinstance(d.get("parts"), dict) and sorted(d["parts"]) == sorted(PHASE4_PARTS) and         sum(d["parts"].values()) == (d.get("summary") or {}).get("checks")
    if d.get("gate_passed") and d.get("complete") and parts_ok and same_build(d.get("build_stamp"), now):
        return 0, {"how": "existing result has the current build stamp", "result_written": time.ctime(res.stat().st_mtime),
                   "build_stamp": now, "parts": d["parts"], "summary": d.get("summary")}
    parts = {}
    for part in PHASE4_PARTS:
        parts[part] = rerun("validate_phase4.py", "--part", part, timeout=3600)
        print(f"    ... validate_phase4.py --part {part}: exit {parts[part][0]}", flush=True)
    code, last = rerun("validate_phase4.py", "--combine")
    return (code if all(c == 0 for c, _ in parts.values()) else 1), {"how": "re-run in parts", "parts": parts, "combine": last}


# ---- independent exact reference for the plain-words measures (fractions; no floating point) ----
SETTINGS = {  # name: (turnout %, national, {zone: swing}, rule N)
    "neutral, N=24": (0, 0, {}, 24),
    "neutral, N=25": (0, 0, {}, 25),
    "turnout +10, national +4, SE -6, NW +3, N=25": (10, 4, {"SE": -6, "NW": 3}, 25),
    "turnout -20, national -3.5, SS +7.5, N=24": (-20, Fraction(-7, 2), {"SS": Fraction(15, 2)}, 24),
}
ZONES = ["NC", "NE", "NW", "SE", "SS", "SW"]


def reference(party, t_pct, S, Z, n):
    st = {r["state_pcode"]: r for r in read("dim_state.csv")}
    votes = {(r["state_pcode"], r["party"]): int(r["votes"]) for r in read("fact_result_2023.csv")}
    valid = {r["state_pcode"]: int(r["total_valid"]) for r in read("fact_turnout_2023.csv")}
    t = Fraction(t_pct) / 100
    per = {}
    for s, V in valid.items():
        v = votes[(s, party)]
        V1 = V + v * t
        p1 = v * (1 + t) / V1
        p2 = min(Fraction(1), max(Fraction(0), p1 + (Fraction(S) + Fraction(Z.get(st[s]["zone_code"], 0))) / 100))
        v2 = p2 * V1
        per[s] = {"p2": p2, "need": math.ceil(max(Fraction(0), V1 / 4 - v2)), "spare": math.floor(max(Fraction(0), v2 - V1 / 4))}
    k = sorted(per, key=lambda s: (-per[s]["p2"], s))[n - 1]
    gap = (Fraction(1, 4) - per[k]["p2"]) * 100
    cand = {r["party"]: r["candidate"] for r in read("dim_party.csv")}[party]
    g1 = (Decimal(abs(gap).numerator) / Decimal(abs(gap).denominator)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if gap <= 0:
        sent = (f"{st[k]['state_name']} is the deciding state. {cand} is {g1} points above a quarter of the vote there: "
                f"about {per[k]['spare']:,} votes could switch to other candidates before the state is lost.")
    else:
        sent = (f"{st[k]['state_name']} is the deciding state. {cand} is {g1} points short of a quarter of the vote there: "
                f"about {per[k]['need']:,} more votes would need to switch to them from other candidates.")
    return per, sent


def closest_reference(party):
    st = {r["state_pcode"]: r["state_name"] for r in read("dim_state.csv")}
    votes = {(r["state_pcode"], r["party"]): int(r["votes"]) for r in read("fact_result_2023.csv")}
    valid = {r["state_pcode"]: int(r["total_valid"]) for r in read("fact_turnout_2023.csv")}
    cand = {r["party"]: r["candidate"] for r in read("dim_party.csv")}[party]
    d = {s: 4 * votes[(s, party)] - V for s, V in valid.items()}
    won = sorted((x, s) for s, x in d.items() if x >= 0)
    miss = sorted((-x, s) for s, x in d.items() if x < 0)
    a = (f"{st[won[0][1]]}, the narrowest state won, was about {math.floor(Fraction(won[0][0], 4)):,} votes above a "
         f"quarter of the vote." if won else "No state reached a quarter of the vote.")
    b = (f" {st[miss[0][1]]}, the narrowest miss, needed about {math.ceil(Fraction(miss[0][0], 4)):,} more votes "
         f"switching to {cand} from other candidates." if miss else " Every state reached a quarter of the vote.")
    return f"{cand} in 2023: {a}{b}"


def sentence_check():
    bad, seen = [], {}
    for name, (tp, S, Z, n) in SETTINGS.items():
        fl = [f"TREATAS({{{tp}}}, param_turnout[Value])", f"TREATAS({{{float(S)}}}, param_swing_national[Value])",
              f"TREATAS({{{n}}}, param_rule[Value])"]
        fl += [f"TREATAS({{{float(Z.get(z, 0))}}}, param_swing_{z}[Value])" for z in ZONES]
        for party in PARTIES:
            per, sent = reference(party, tp, S, Z, n)
            f = ", ".join(fl + [f'TREATAS({{"{party}"}}, dim_party[party])'])
            got = dax(f'EVALUATE CALCULATETABLE(ROW("s", [Deciding state sentence]), {f})')[0]["s"]
            rows = dax(f'EVALUATE CALCULATETABLE(SUMMARIZECOLUMNS(dim_state[state_pcode], "need", [Votes needed], '
                       f'"spare", [Votes to spare]), {f})')
            seen[f"{name} / {party}"] = got
            if got != sent:
                bad.append({"setting": name, "party": party, "model": got, "reference": sent})
            for r in rows:
                ref = per[r["state_pcode"]]
                if r["need"] != ref["need"] or r["spare"] != ref["spare"]:
                    bad.append({"setting": name, "party": party, "state": r["state_pcode"], "model": [r["need"], r["spare"]],
                                "reference": [ref["need"], ref["spare"]]})
            if len(rows) != 37:
                bad.append({"setting": name, "party": party, "states_returned": len(rows)})
    for party in PARTIES:
        got = dax(f'EVALUATE CALCULATETABLE(ROW("s", [Closest calls sentence]), TREATAS({{"{party}"}}, dim_party[party]))')[0]["s"]
        ref = closest_reference(party)
        seen[f"closest calls / {party}"] = got
        if got != ref:
            bad.append({"closest_calls": party, "model": got, "reference": ref})
    return not bad, {"mismatches": bad[:20], "settings": list(SETTINGS), "sentences_seen": seen,
                     "per_state_cells_compared": 2 * 37 * len(PARTIES) * len(SETTINGS)}


def result_check():
    sys.path.insert(0, str(ROOT / "scripts"))
    import validate_phase4 as v4    # its reference functions read only the staging CSVs
    names = {r["party"]: r["candidate"] for r in read("dim_party.csv")}
    zname = {"NC": "North Central and Abuja", "NE": "North East", "NW": "North West", "SE": "South East",
             "SS": "South South", "SW": "South West"}
    bad, seen = [], {}
    for name, (tp, S, Z, n) in SETTINGS.items():
        st = v4.setting(t=float(tp), S=float(S), **{z: float(x) for z, x in Z.items()})
        fl = [f"TREATAS({{{tp}}}, param_turnout[Value])", f"TREATAS({{{float(S)}}}, param_swing_national[Value])",
              f"TREATAS({{{n}}}, param_rule[Value])"]
        fl += [f"TREATAS({{{float(Z.get(z, 0))}}}, param_swing_{z}[Value])" for z in ZONES]
        parts = ([f"{float(S):+.1f} points everywhere"] if S else []) + \
                ([", ".join(f"{float(Z[z]):+.1f} in the {zname[z]}" for z in ZONES if Z.get(z))] if any(Z.values()) else []) + \
                ([f"{tp:+d}% turnout among the candidate's 2023 voters"] if tp else [])
        settings_ref = ("; ".join(parts) if parts else "No changes: this is the 2023 result") + f". {n} states needed to win."
        for party in PARTIES:
            c, rv = v4.counts(party, st, n), v4.rivals(party, st, n)
            nm, k, lead = names[party], c["sec"], rv["lead"]
            rn = names[lead]
            if rv["most"] == "Yes" and c["clears"] == "Yes":
                ref = f"{nm} wins outright: the most votes nationwide and a quarter of the vote in {k} states ({n} needed)."
            elif rv["most"] == "Yes":
                ref = (f"No outright winner: {nm} has the most votes but a quarter of the vote in only {k} states "
                       f"({n} needed). This would go to a run-off.")
            elif rv["most"] == "Tied":
                ref = "Tie on votes: no outright winner."
            elif rv["lead_25"] >= n:
                ref = f"{nm} loses: {rn} ({lead}) has the most votes and a quarter of the vote in enough states."
            else:
                ref = (f"No outright winner: {rn} ({lead}) has the most votes but not a quarter of the vote in enough "
                       f"states. This would go to a run-off.")
            f = ", ".join(fl + [f'TREATAS({{"{party}"}}, dim_party[party])'])
            got = dax(f'EVALUATE CALCULATETABLE(ROW("r", [Result sentence], "s", [Assumptions in force]), {f})')[0]
            seen[f"{name} / {party}"] = got
            if got["r"] != ref:
                bad.append({"setting": name, "party": party, "model": got["r"], "reference": ref})
            if got["s"] != settings_ref:
                bad.append({"setting": name, "party": party, "model": got["s"], "reference": settings_ref})
    return not bad, {"mismatches": bad[:20], "seen": seen}


def expected_identity(party, r):
    """Identity text rebuilt from party_now.csv (publisher and full date; 2026-11-16: role and dated short note),
    independent of the generator."""
    def day(x):
        y, m, d = x.split("-")
        return f"{int(d)} {'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[int(m) - 1]} {y}"
    role = f", {r['role']}" if r.get("role") else ""
    note = (f". {r['note_short']} ({r['note_source_publisher'].split(' (')[0]}, {day(r['note_date'])})"
            if r.get("note_short") else "")
    return f"2023: {party}. Now: {r['party_now']}{role} ({r['source_publisher'].split(' (')[0]}, {day(r['as_of'])}){note}"


def identity_check():
    man = {c["party"]: c for c in json.loads((ROOT / "pbip" / "assets" / "photos" / "candidates_manifest.json")
                                              .read_text(encoding="utf-8"))["candidates"]}
    now = {r["party_2023"]: r for r in read("party_now.csv", REF)}
    colours = {r["party"]: r["colour_hex"] for r in read("party_display.csv", REF)}
    logos = {l["party"]: l["data_uri"] for l in json.loads((ROOT / "pbip" / "assets" / "photos" / "logos_manifest.json")
                                                             .read_text(encoding="utf-8"))["logos"]}

    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    bad, ev = [], {}
    for party in PARTIES:
        g = dax(f'EVALUATE CALCULATETABLE(ROW("photo", [Candidate photo], "badge", [Party badge], "id", [Party identity], '
                f'"bg", [Party accent colour], "fg", [Party accent text colour], "logo", [Party logo], "logonow", [Party now logo]), TREATAS({{"{party}"}}, dim_party[party]))')[0]
        hi, lo = sorted((lum(g["bg"]), lum(g["fg"])), reverse=True)
        ratio = round((hi + 0.05) / (lo + 0.05), 2)
        r = now[party]
        ok = (g["photo"] == man[party]["data_uri"] and len(g["photo"]) <= 30_000
              and hashlib.sha256((ROOT / man[party]["output"]).read_bytes()).hexdigest() == man[party]["sha256"]
              and g["badge"] == party and g["bg"] == colours[party] and ratio >= 4.5
              and g["id"] == expected_identity(party, r)
              and g["logo"] == logos[party] and g["logonow"] == logos[r["party_now"]]
              and len(g["logo"]) <= 30_000 and len(g["logonow"]) <= 30_000
              and man[party]["licence"].startswith(("CC0", "CC BY", "Public domain")))
        ev[party] = {"photo_chars": len(g["photo"] or ""), "logo_chars": len(g["logo"] or ""), "badge": g["badge"], "identity": g["id"], "bg": g["bg"],
                     "fg": g["fg"], "contrast": ratio, "portrait_licence": man[party]["licence"],
                     "party_now_source": r["source_url"], "as_of": r["as_of"]}
        if not ok:
            bad.append(party)
    return not bad, {"failed": bad, "parties": ev}


NO_PHOTO = {"Merge two parties", "Head to head"}
COAL_ON = 'coal_switch[Value] = "On"'
COAL_2V2 = ('coal_a_lead[party] = "PDP", coal_a_partner[party] = "LP", coal_b_lead[party] = "APC", '
            'coal_b_partner[party] = "NNPP", param_follow_a[Value] = 35, param_follow_b[Value] = 70')


def coalition_names_check(pg):
    rows = read("coalition_names.csv", REF)
    model = {(r["l"], r["p"]): (r["n"], r["st"]) for r in dax('EVALUATE SELECTCOLUMNS(coalition_names, "l", '
             'coalition_names[lead], "p", coalition_names[partner], "n", coalition_names[display_name], "st", '
             'coalition_names[status])')}
    csvm = {(r["lead"], r["partner"]): (r["display_name"], r["status"]) for r in rows}
    real = [r for r in rows if r["status"] == "real"]
    no_source = [r["display_name"] for r in real if not (r["source_url"].startswith("https://") and r["as_of"]
                                                         and r["source_publisher"])]
    pairs_ok = len(rows) == 12 and set(csvm) == {(a, b) for a in PARTIES for b in PARTIES if a != b}
    bad_status = [r["display_name"] for r in rows if r["status"] not in ("real", "hypothetical")
                  or (r["status"] == "hypothetical" and not r["display_name"].endswith("(what-if)"))]
    text = " ".join(json.dumps(v, ensure_ascii=False) for p in pg.values() for v in p["visuals"])

    def day(x):
        y, m, d = x.split("-")
        return f"{int(d)} {'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[int(m) - 1]} {y}"
    page_dates = {r["display_name"]: (day(r["as_of"]) in text and r["as_of"] in text) for r in real}
    ok = model == csvm and not no_source and pairs_ok and not bad_status and all(page_dates.values()) and len(real) >= 1
    return ok, {"real_rows": [{k: r[k] for k in ("lead", "partner", "display_name", "source_publisher", "source_url",
                                                  "as_of")} for r in real],
                "real_without_source": no_source, "model_equals_csv": model == csvm, "all_12_ordered_pairs": pairs_ok,
                "bad_status_or_name": bad_status, "real_date_in_page_text": page_dates}


def coalition_preset_check(pg, follow):
    """Saved slicer states: pickers at the preset, follow 100, switch Off; same sync group per field on every page."""
    want = {"coal_a_lead": "'Peter Obi (LP)'", "coal_a_partner": "'Rabiu Kwankwaso (NNPP)'",
            "coal_b_lead": "'Bola Tinubu (APC)'", "coal_b_partner": "'Nobody: one party alone'", "coal_switch": "'Off'",
            "param_follow_a": "100L", "param_follow_b": "100L"}
    found, bad = {}, []
    for name in ("Merge two parties", "Head to head", "What-if simulator"):
        for v in pg[name]["visuals"]:
            q = v["visual"]
            if q.get("visualType") != "slicer":
                continue
            tbl = q["query"]["queryState"]["Values"]["projections"][0]["field"]["Column"]["Expression"]["SourceRef"]["Entity"]
            if tbl not in want:
                continue
            cond = q["objects"]["general"][0]["properties"]["filter"]["filter"]["Where"][0]["Condition"]
            val = (cond["In"]["Values"][0][0]["Literal"]["Value"] if "In" in cond
                   else cond["Comparison"]["Right"]["Literal"]["Value"])
            grp = q.get("syncGroup", {}).get("groupName")
            found.setdefault(tbl, []).append({"page": name, "value": val, "sync": grp, "hidden": v.get("isHidden", False)})
            if val != want[tbl] or grp != tbl:
                bad.append({"page": name, "table": tbl, "value": val, "sync": grp})
    expect_pages = {"coal_a_lead": 3, "coal_a_partner": 3, "coal_b_lead": 2, "coal_b_partner": 2, "coal_switch": 1,
                    "param_follow_a": 3, "param_follow_b": 2}
    counts = {t: len(found.get(t, [])) for t in want}
    sim_visible = [x for t in want for x in found.get(t, []) if x["page"] == "What-if simulator" and not x["hidden"]
                   and t != "coal_switch"]
    ok = not bad and counts == expect_pages and not sim_visible and follow == {"param_follow_a": "100L",
                                                                              "param_follow_b": "100L"}
    return ok, {"found": found, "mismatches": bad, "counts": counts, "expected_counts": expect_pages,
                "simulator_follow_saved": follow, "pickers_visible_on_simulator": sim_visible}


def page_numbers_check():
    """Fixed 2023 numbers written in page text, recomputed from staging and found in the generated report files."""
    votes = {(r["state_pcode"], r["party"]): int(r["votes"]) for r in read("fact_result_2023.csv")}
    valid = {r["state_pcode"]: int(r["total_valid"]) for r in read("fact_turnout_2023.csv")}
    names = {r["state_pcode"]: r["state_name"] for r in read("dim_state.csv")}
    inec = next(r for r in read("national_totals_reported.csv") if r["source"] == "inec_declaration")
    rec = next(r for r in csv.DictReader(open(ROOT / "reports" / "result_reconciliation.csv", encoding="utf-8"))
               if r["state_pcode"] == "NG020" and r["party"] == "APC")
    others_gap = sum(v for (s, p), v in votes.items() if p == "OTHERS") - int(inec["OTHERS"])
    kano_used, kano_alt = votes[("NG020", "APC")], int(rec["wikipedia"])
    gap = kano_alt - kano_used
    # who has a quarter in Kano, under the used figure and the alternative (valid total unchanged, or raised by the gap)
    def quarter(apc, total):
        return {p: 4 * (apc if p == "APC" else votes[("NG020", p)]) >= total for p in PARTIES}
    base = quarter(kano_used, valid["NG020"])
    kano_same = base == quarter(kano_alt, valid["NG020"]) == quarter(kano_alt, valid["NG020"] + gap)
    tin_states = sum(4 * votes[(s, "APC")] >= valid[s] for s in valid)
    spare = {s: votes[(s, "APC")] - valid[s] / 4 for s in valid if 4 * votes[(s, "APC")] >= valid[s]}
    narrow = min(spare, key=spare.get)
    narrow_votes = int(spare[narrow])            # rounded down, as the "Votes to spare" measure
    text = " ".join(json.dumps(v) for p in pages().values() for v in p["visuals"])
    want = {"others gap": f"{others_gap:,}", "Kano used": f"{kano_used:,}", "Kano alternative": f"{kano_alt:,}",
            "Tinubu states": f"{tin_states} states in 2023 rest on {narrow_votes} votes in {names[narrow]}"}
    found = {k: s in text for k, s in want.items()}
    ok = all(found.values()) and kano_same
    return ok, {"expected_text": want, "found_in_report": found, "kano_quarter_same_under_either_figure": kano_same,
                "kano_quarter": base, "narrowest_tinubu_state": names[narrow]}


def main():
    # 5 first: the clean-cache claim is about the state of disk at the time of this run
    caches = [str(p.relative_to(ROOT)) for p in (ROOT / "pbip").rglob("cache.abf")]
    check("refresh from a clean cache: no saved data cache on disk, model refreshed from the source CSVs",
          not caches and engine("-Action", "Refresh")["status"] == "ok", {"cache_files": caches})

    # 1. earlier gates still pass on this build
    code, last = rerun("validate_phase3.py", "--no-refresh")
    check("validate_phase3.py passes on the current build", code == 0, {"exit_code": code, "summary": last})
    code, ev = phase4_on_current_build()
    check("validate_phase4.py passes on the current build", code == 0, ev)

    # 2. national totals: model vs every independent copy
    model = {r["party"]: r["votes"] for r in dax('EVALUATE SUMMARIZECOLUMNS(dim_party[party], "votes", [Candidate votes])')}
    copies = {r["source"]: r for r in read("national_totals_reported.csv")}
    diffs = {src: {p: model[p] - int(r[p]) for p in PARTIES} for src, r in copies.items()}
    worst = max(abs(d) for row in diffs.values() for d in row.values())
    check(f"national candidate totals = each independent copy within {NATIONAL_TOLERANCE_VOTES} votes",
          worst <= NATIONAL_TOLERANCE_VOTES, {"model": model, "model_minus_copy": diffs, "worst_abs_diff": worst})

    # 3. geometry after import
    man = json.loads((ROOT / "pbip" / "assets" / "geometry_manifest.json").read_text(encoding="utf-8"))
    keys = {r["state_pcode"]: r["state_name"] for r in dax("EVALUATE SELECTCOLUMNS(dim_state, \"state_pcode\", dim_state[state_pcode], \"state_name\", dim_state[state_name])")}
    geo = {}
    for o in man["outputs"]:
        name = Path(o["file"]).name
        emb = RPT / "StaticResources" / "RegisteredResources" / name
        topo = json.loads(emb.read_text(encoding="utf-8"))
        g = [x["properties"] for obj in topo["objects"].values() for x in obj["geometries"]]
        tk = {x["state_pcode"] for x in g}
        tn = {x["state_name"] for x in g}
        geo[name] = {"embedded_sha_equals_manifest": sha(emb) == o["sha256"], "features": len(g),
                     "map_keys_not_in_model": sorted(tk - set(keys)), "model_keys_not_in_map": sorted(set(keys) - tk),
                     # the Shape Maps bind to the name (check 8), so names must match exactly too
                     "map_names_not_in_model": sorted(tn - set(keys.values())),
                     "model_names_not_in_map": sorted(set(keys.values()) - tn),
                     "pcode_name_pairs_differ": sorted(x["state_pcode"] for x in g if keys.get(x["state_pcode"]) != x["state_name"])}
    check("embedded map files = built files, and every map key and name matches the model (both maps, 0 unmatched)",
          all(v["embedded_sha_equals_manifest"] and v["features"] == 37 and not v["map_keys_not_in_model"]
              and not v["model_keys_not_in_map"] and not v["map_names_not_in_model"] and not v["model_names_not_in_map"]
              and not v["pcode_name_pairs_differ"] for v in geo.values()) and len(keys) == 37, geo)

    # 6a. slider defaults saved in the report are neutral (0, rule 24)
    pg = pages()
    saved = {}
    for v in pg["What-if simulator"]["visuals"]:
        q = v.get("visual", {})
        if q.get("visualType") != "slicer":
            continue
        try:
            cond = q["objects"]["general"][0]["properties"]["filter"]["filter"]["Where"][0]["Condition"]
            tbl = q["query"]["queryState"]["Values"]["projections"][0]["field"]["Column"]["Expression"]["SourceRef"]["Entity"]
            saved[tbl] = cond["Comparison"]["Right"]["Literal"]["Value"]
        except (KeyError, IndexError, TypeError):
            continue
    follow = {t: saved.pop(t) for t in [t for t in saved if t.startswith("param_follow_")]}   # coalition (hidden, synced)
    neutral = all((val in ("24L", "24D") if t == "param_rule" else val in ("0L", "0D")) for t, val in saved.items())
    check("simulator sliders saved at neutral values (all swings 0, turnout 0, rule 24)", neutral and len(saved) == 9, saved)

    # 4. overview figures = simulator figures at those saved values
    flt = ", ".join(f"{t}[Value] = {val.rstrip('LD')}" for t, val in saved.items())
    bad, nat = [], {}
    for p in PARTIES:
        rows = dax(f'EVALUATE CALCULATETABLE(SUMMARIZECOLUMNS(dim_state[state_pcode], "b", [Candidate share], '
                   f'"s", [Scenario share], "bl", [Baseline label], "sl", [Scenario label]), dim_party[party] = "{p}", {flt})')
        bad += [{"party": p, **r} for r in rows if r["b"] is None or abs(r["b"] - r["s"]) > 1e-12 or r["bl"] != r["sl"]]
        n = dax(f'EVALUATE CALCULATETABLE(ROW("share", [Candidate share], "sshare", [Scenario national share], '
                f'"t25", [States at 25% or more], "sec", [Units secured (national)]), dim_party[party] = "{p}", {flt})')[0]
        nat[p] = n
        if abs(n["share"] - n["sshare"]) > 1e-12 or n["t25"] != n["sec"]:
            bad.append({"party": p, "national": n})
        if len(rows) != 37:
            bad.append({"party": p, "units_returned": len(rows)})
    check("overview = simulator at saved slider values: 37 unit shares and labels, national share, units at 25%",
          not bad, {"national": nat, "mismatches": bad[:10]})

    # 6b. static accessibility: alt text + unique tab order on visible pages
    a11y = {}
    for name, p in pg.items():
        if p["hidden"]:
            continue
        missing, orders = [], []
        for v in p["visuals"]:
            orders.append(v.get("position", {}).get("tabOrder"))
            alt = None
            for blk in (v.get("visual", {}).get("visualContainerObjects", {}), v.get("visual", {}).get("objects", {})):
                for g in blk.get("general", []):
                    alt = alt or g.get("properties", {}).get("altText")
            if not alt:
                missing.append(v["name"])
        a11y[name] = {"visuals": len(p["visuals"]), "missing_alt_text": missing,
                      "tab_order_unique": len(set(orders)) == len(orders) and None not in orders}
    check("every visual on visible pages has alt text and a unique tab position",
          all(not v["missing_alt_text"] and v["tab_order_unique"] for v in a11y.values()), a11y)

    # 8. maps: location bound to the state name, so the hover shows names (not P-codes); P-code nowhere in a map's fields
    maps = {}
    for name, p in pg.items():
        for v in p["visuals"]:
            if v["visual"]["visualType"] != "shapeMap":
                continue
            qs = v["visual"]["query"]["queryState"]
            cat = [x["field"]["Column"]["Property"] for x in qs["Category"]["projections"]]
            fields = [x["queryRef"] for role in qs.values() for x in role["projections"]]
            maps[f"{name} / {v['name']}"] = {"location": cat, "fields": fields}
    check("every map (incl. the hidden check page) is located by state name; no P-code in any map field (hover shows "
          "names; rendering of the hover itself not checked)",
          len(maps) == 3 and all(m["location"] == ["state_name"] and not any("pcode" in f for f in m["fields"])
                                 for m in maps.values()), maps)

    # 8b. state codes (ISO 3166-2:NG, user request 2026-11-14): 37 unique two-letter codes, all matched, = reference file
    iso = {r["state_pcode"]: r for r in read("state_codes_iso3166.csv", REF)}
    mcodes = {r["p"]: r["c"] for r in dax('EVALUATE SELECTCOLUMNS(dim_state, "p", dim_state[state_pcode], "c", dim_state[state_code])')}
    tiles = {(r["state_pcode"]) for r in read("tile_grid_layout.csv", REF)}
    check("state codes: 37 unique two-letter ISO 3166-2:NG codes in the model, each = the sourced reference file; "
          "every state has a tile position",
          len(mcodes) == 37 and len(set(mcodes.values())) == 37 and all(len(c or "") == 2 for c in mcodes.values())
          and all(iso[p]["state_code"] == c and iso[p]["iso_3166_2"] == "NG-" + c for p, c in mcodes.items())
          and tiles == set(mcodes),
          {"codes": mcodes, "reference": "data/reference/state_codes_iso3166.csv"})

    # 9. plain-words sentences and votes to switch = independent exact computation (docs/methodology.md)
    check("sentences and votes needed / to spare = independent exact computation from staging", *sentence_check())

    # 11. result + settings sentences
    check("result sentence and settings sentence = Phase 4 reference for every candidate at several settings",
          *result_check())

    # 12. identity
    check("candidate identity: portrait = built file, party now = dated source file, party-colour text contrast >= 4.5:1",
          *identity_check())

    # 13. fixed numbers in page text
    check("fixed 2023 numbers in page text (4,858; Kano figures; 29 states / Adamawa margin) = staging, and the Kano "
          "dispute changes no candidate's quarter there", *page_numbers_check())

    # 10. photos
    pman = json.loads((ROOT / "pbip" / "assets" / "photos" / "photos_manifest.json").read_text(encoding="utf-8"))
    rr = RPT / "StaticResources" / "RegisteredResources"
    ph = {}
    for x in pman["photos"]:
        f = Path(x["output"]).name
        emb = rr / f
        ph[f] = {"embedded_sha_equals_manifest": emb.exists() and sha(emb) == x["sha256"], "bytes": x["bytes"],
                 "licence": x["licence"], "licence_ok": x["licence"].startswith(("CC0", "CC BY", "Public domain"))}
    tab = {}
    for name, p in pg.items():
        if p["hidden"]:
            continue
        vis = sorted(p["visuals"], key=lambda v: v["position"]["tabOrder"])
        alt_of = lambda v: v["visual"]["visualContainerObjects"]["general"][0]["properties"]["altText"]["expr"]["Literal"]["Value"]
        # decorative side-panel photos only = images showing an embedded photo_*.jpg (the candidate portrait, the party
        # logos and the "Where is each state?" locator are image visuals too, but informative)
        def item(v):
            try:
                return v["visual"]["objects"]["image"][0]["properties"]["sourceFile"]["image"]["url"]["expr"][
                    "ResourcePackageItem"]["ItemName"]
            except (KeyError, IndexError, TypeError):
                return ""
        imgs = [i for i, v in enumerate(vis) if v["visual"]["visualType"] == "image" and item(v).startswith("photo_")]
        alts = [alt_of(vis[i]) for i in imgs]
        # photo + its credit caption are the last two visuals in tab order
        tab[name] = {"photos": len(imgs), "photo_last_but_caption": bool(imgs) and imgs[-1] == len(vis) - 2,
                     "alt_starts_decorative": all(a.startswith("'Decorative photo:") for a in alts)}
    check("photos: embedded = built (sha256), licence CC0/CC BY/CC BY-SA/PD, <= 250 KB each and <= 2 MB total; one "
          "per visible page except the two coalition pages (none, by design: no room beside their pickers), decorative "
          "alt text, last in tab order (before its caption)",
          all(v["embedded_sha_equals_manifest"] and v["licence_ok"] and v["bytes"] <= 250_000 for v in ph.values())
          and pman["total_bytes"] <= 2_000_000 and len(tab) == 9
          and all((v["photos"] == 0) if name in NO_PHOTO else
                  (v["photos"] == 1 and v["photo_last_but_caption"] and v["alt_starts_decorative"]) for name, v in tab.items()),
          {"files": ph, "total_bytes": pman["total_bytes"], "pages": tab,
           "pages_without_photo_by_design": sorted(NO_PHOTO)})

    # 13-14. coalitions
    check("coalition names: every real row has publisher, URL and date; model name table = CSV; real ticket's date on "
          "the pages = CSV", *coalition_names_check(pg))
    check("coalition pickers, follow sliders and switch saved at the preset (Obi (LP) + Kwankwaso (NNPP), 100%, vs "
          "Tinubu (APC) alone; switch Off), in matching sync groups on the coalition pages and the simulator",
          *coalition_preset_check(pg, follow))

    # 7. engine time for the heaviest queries at a non-neutral setting: timed inside one engine connection (no PowerShell
    # start-up), cache cleared before each of 3 rounds; gate on the median cold time (review 2026-11-18, item 3)
    busy = ("param_swing_national[Value] = 4, param_swing_SE[Value] = -6, param_swing_NW[Value] = 3, "
            "param_turnout[Value] = 10, param_rule[Value] = 25, dim_party[party] = \"LP\"")
    queries = {
        "Path to 24 table": f'EVALUATE CALCULATETABLE(SUMMARIZECOLUMNS(dim_state[state_name], "r", [Unit rank], "s", [Scenario share], '
                            f'"l", [Scenario label], "v", [Votes needed], "c", [Path column colour]), {busy})',
        "Spread map": f'EVALUATE CALCULATETABLE(SUMMARIZECOLUMNS(dim_state[state_pcode], "s", [Scenario share], '
                      f'"d", [Points from 25%]), {busy})',
        "Head to head table + cards": f'EVALUATE CALCULATETABLE(ADDCOLUMNS(VALUES(dim_state[state_name]), "a", '
                           f'[Side A share (head to head)], "b", [Side B share (head to head)], "w", [Who leads (head to head)], '
                           f'"a25", [Side A at 25% (head to head)], "b25", [Side B at 25% (head to head)], "s", '
                           f'[Head to head sentence], "la", [States led by Side A], "c", [Head to head leader colour]), {COAL_2V2})',
    }
    # Simulator page: one query per VISUAL, with exactly the measures that visual shows (read from the report files
    # 2026-11-18), as Desktop sends them (user decision 2026-11-18, decision log). Until then the check timed ten
    # measures as ONE query, two of which (Verdict, Tipping-point gap) are not on the page (2.0-2.8 s, switch On).
    sim_visuals = {
        "tile map": 'SUMMARIZECOLUMNS(dim_state[tile_row], dim_state[tile_col], "c", [Tile code], "f", [Tile fill], '
                    '"t", [Tile text colour])',
        "headline card": 'ROW("m", [Has most votes], "rv", [Leading rival], "ns", [Scenario national share], '
                         '"a", [Party accent colour])',
        "counts card": 'ROW("sec", [Units secured (national)], "need", [Units still needed], "cap", [Units at a cap], '
                       '"a", [Party accent colour])',
        "result sentence": 'ROW("r", [Result sentence], "a", [Party accent colour])',
        "deciding state sentence": 'ROW("d", [Deciding state sentence], "a", [Party accent colour])',
        "settings sentence": 'ROW("s", [Assumptions in force], "a", [Party accent colour])',
        "coalition sentence": 'ROW("s", [Simulator coalition sentence])',
        "header line": 'ROW("s", [Simulator header line])',
    }
    for k, v in sim_visuals.items():
        queries[f"Simulator {k}"] = f"EVALUATE CALCULATETABLE({v}, {busy})"
        queries[f"Simulator {k} (coalition On, 2 v 2)"] = f"EVALUATE CALCULATETABLE({v}, {busy}, {COAL_ON}, {COAL_2V2})"

    def timed(q):
        with tempfile.NamedTemporaryFile("w", suffix=".dax", delete=False, encoding="utf-8") as f:
            f.write(q)
        try:
            return engine("-Action", "Time", "-Repeat", "3", "-DaxFile", f.name)
        finally:
            Path(f.name).unlink(missing_ok=True)
    raw = {k: timed(q) for k, q in queries.items()}
    cold = {k: round(statistics.median(v["cold_s"]), 3) for k, v in raw.items()}
    warm = {k: round(statistics.median(v["warm_s"]), 3) for k, v in raw.items()}
    check(f"engine time per heavy page query (one query per visual, as Desktop sends them) under "
          f"{LATENCY_LIMIT_S} s with an empty cache (non-neutral sliders; rendering not included)",
          all(v < LATENCY_LIMIT_S for v in cold.values()),
          {"median_cold_s": cold, "median_warm_s": warm, "runs": raw, "slowest_cold": max(cold, key=cold.get),
           "how": "pbi_engine.ps1 -Action Time: cache cleared, cold run, warm run; x3; inside one connection"})

    failed = [c["check"] for c in checks if c["status"] == "fail"]
    out = {"built_by": "scripts/validate_phase6.py", "gate_passed": not failed,
           "summary": {"checks": len(checks), "pass": sum(c["status"] == "pass" for c in checks), "fail": len(failed)},
           "not_scriptable": ["tooltips render as designed (needs hover)", "keyboard-only path and screen reader in Desktop",
                              "release .pbix on a clean Windows profile (Phase 7 builds the .pbix)",
                              "non-specialist completes the core task unaided"],
           "failed": failed, "checks": checks}
    (REP / "phase6_validation.json").write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    print(f"\n  gate {'PASSED' if not failed else 'FAILED'}: {out['summary']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
