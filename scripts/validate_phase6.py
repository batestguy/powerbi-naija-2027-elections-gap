"""Phase 6 QA checks against the live model in Power BI Desktop plus the report files (no clicking).

Covers the brief's Phase 6 list where a script can decide it:
  1. Phase 3 and Phase 4 checks re-run (model = staging, national = INEC, scenario engine = methodology)
  2. National totals vs independent copies (Wikipedia, NigeriaLawyer, ThisDay, Vanguard) within a stated tolerance
  3. Geometry keys after import: the map files embedded in the report = the built files, and their keys = the model's
  4. Overview page = simulator at the simulator's saved (neutral) slider values, per unit and nationally
  5. Refresh from a clean cache (no cache.abf on disk; the open + refresh ran from source CSVs)
  6. Static accessibility: alt text on every visual of the visible pages, unique tab order, slider defaults neutral
  7. Engine time for the heaviest page queries at a non-neutral setting (rendering time not included)
Writes reports/phase6_validation.json; exits 1 on any gate failure.

Usage (repo root, Desktop open on pbip/NaijaElectionsGap.pbip):  uv run python -I scripts/validate_phase6.py
"""
import csv, hashlib, json, statistics, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STG, REF, REP = ROOT / "data" / "staging", ROOT / "data" / "reference", ROOT / "reports"
RPT = ROOT / "pbip" / "NaijaElectionsGap.Report"
PS = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "pbi_engine.ps1")]
PARTIES = ["APC", "PDP", "LP", "NNPP"]
NATIONAL_TOLERANCE_VOTES = 20     # stated tolerance per candidate vs each independent copy of the national total
LATENCY_LIMIT_S = 2.0             # engine time per page query; rendering is extra and not measured here
checks = []


def check(name, ok, evidence, status=None):
    checks.append({"check": name, "status": status or ("pass" if ok else "fail"), "evidence": evidence})


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


def rerun(script, *extra):
    r = subprocess.run(["uv", "run", "python", "-I", str(ROOT / "scripts" / script), *extra],
                       capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=1800)
    return r.returncode, (r.stdout.strip().splitlines() or [""])[-1]


def main():
    # 5 first: the clean-cache claim is about the state of disk at the time of this run
    caches = [str(p.relative_to(ROOT)) for p in (ROOT / "pbip").rglob("cache.abf")]
    check("refresh from a clean cache: no saved data cache on disk, model refreshed from the source CSVs",
          not caches and engine("-Action", "Refresh")["status"] == "ok", {"cache_files": caches})

    # 1. earlier gates still pass on this build
    for script, extra in (("validate_phase3.py", ("--no-refresh",)), ("validate_phase4.py", ())):
        code, last = rerun(script, *extra)
        check(f"{script} passes on the current build", code == 0, {"exit_code": code, "summary": last})

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
        geo[name] = {"embedded_sha_equals_manifest": sha(emb) == o["sha256"], "features": len(g),
                     "map_keys_not_in_model": sorted(tk - set(keys)), "model_keys_not_in_map": sorted(set(keys) - tk)}
    check("embedded map files = built files, and every map key matches a model key (both maps, 0 unmatched)",
          all(v["embedded_sha_equals_manifest"] and v["features"] == 37 and not v["map_keys_not_in_model"]
              and not v["model_keys_not_in_map"] for v in geo.values()) and len(keys) == 37, geo)

    # 6a. slider defaults saved in the report are neutral (0, rule 24)
    pg = pages()
    saved = {}
    for v in pg["Scenario simulator"]["visuals"]:
        q = v.get("visual", {})
        if q.get("visualType") != "slicer":
            continue
        try:
            cond = q["objects"]["general"][0]["properties"]["filter"]["filter"]["Where"][0]["Condition"]
            tbl = q["query"]["queryState"]["Values"]["projections"][0]["field"]["Column"]["Expression"]["SourceRef"]["Entity"]
            saved[tbl] = cond["Comparison"]["Right"]["Literal"]["Value"]
        except (KeyError, IndexError, TypeError):
            continue
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

    # 7. engine time for the heaviest queries at a non-neutral setting (median of 3, minus a trivial-query baseline)
    busy = ("param_swing_national[Value] = 4, param_swing_SE[Value] = -6, param_swing_NW[Value] = 3, "
            "param_turnout[Value] = 10, param_rule[Value] = 25, dim_party[party] = \"LP\"")
    queries = {
        "Path to 24 table": f'EVALUATE CALCULATETABLE(SUMMARIZECOLUMNS(dim_state[state_name], "r", [Unit rank], "s", [Scenario share], '
                            f'"l", [Scenario label], "v", [Votes needed], "c", [Path column colour]), {busy})',
        "Simulator cards": f'EVALUATE CALCULATETABLE(ROW("v", [Verdict], "m", [Has most votes], "rv", [Leading rival], '
                           f'"tu", [Tipping-point unit], "tg", [Tipping-point gap (points)], "sec", [Units secured (national)], '
                           f'"need", [Units still needed], "ns", [Scenario national share], "cap", [Units at a cap]), {busy})',
        "Spread map": f'EVALUATE CALCULATETABLE(SUMMARIZECOLUMNS(dim_state[state_pcode], "s", [Scenario share], '
                      f'"d", [Points from 25%]), {busy})',
    }

    def timed(q):
        t = time.perf_counter(); dax(q); return time.perf_counter() - t
    base = statistics.median(timed('EVALUATE ROW("x", 1)') for _ in range(3))
    lat = {k: round(max(0.0, statistics.median(timed(q) for _ in range(3)) - base), 3) for k, q in queries.items()}
    check(f"engine time per heavy page query under {LATENCY_LIMIT_S} s (non-neutral sliders; rendering not included)",
          all(v < LATENCY_LIMIT_S for v in lat.values()), {"seconds_net_of_call_overhead": lat, "call_overhead_s": round(base, 3)})

    failed = [c["check"] for c in checks if c["status"] == "fail"]
    out = {"built_by": "scripts/validate_phase6.py", "gate_passed": not failed,
           "summary": {"checks": len(checks), "pass": sum(c["status"] == "pass" for c in checks), "fail": len(failed)},
           "not_scriptable": ["tooltips render as designed (needs hover)", "keyboard-only path and screen reader in Desktop",
                              "release .pbix on a clean Windows profile (Phase 7 builds the .pbix)",
                              "non-specialist completes the core task unaided"],
           "failed": failed, "checks": checks}
    (REP / "phase6_validation.json").write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    for c in checks:
        print(f"  [{c['status'].upper():4}] {c['check']}")
    print(f"\n  gate {'PASSED' if not failed else 'FAILED'}: {out['summary']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
