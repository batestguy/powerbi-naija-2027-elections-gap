"""Phase 3 model checks, run against the live model inside Power BI Desktop (no clicking).

Refreshes the open model through scripts/pbi_engine.ps1, then runs DAX queries and compares every answer with the
staging CSVs and INEC's national declaration. Writes reports/phase3_validation.json; exits 1 on any gate failure.

Requires: Desktop running with pbip/NaijaElectionsGap.pbip open (see CLAUDE.md Commands).
Usage (repo root):  uv run python -I scripts/validate_phase3.py [--no-refresh]
"""
import csv, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STG, REF, REP = ROOT / "data" / "staging", ROOT / "data" / "reference", ROOT / "reports"
PS = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "pbi_engine.ps1")]
PARTIES = ["APC", "PDP", "LP", "NNPP"]
DECLARED_T25 = {"APC": 29, "PDP": 21, "LP": 16, "NNPP": 1}   # as reported for 2023; the check uses a staging recompute too
TIMEOUT = 420   # seconds per engine call; pbi_engine.ps1 itself times out commands at 300 s
checks = []


def check(name, ok, evidence):
    checks.append({"check": name, "status": "pass" if ok else "fail", "evidence": evidence})


def engine(*args):
    try:
        r = subprocess.run(PS + list(args), capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"pbi_engine.ps1 {args[:2]} did not answer within {TIMEOUT} s "
                           "(Desktop busy or a dialog open?) - stopping rather than hanging")
    if r.returncode:
        raise RuntimeError(f"pbi_engine.ps1 {args[:2]} failed:\n{r.stderr or r.stdout}")
    return json.loads(r.stdout.lstrip("﻿"))


def dax(q):
    rows = engine("-Action", "Query", "-Dax", q)
    # ADOMD column names look like "table[column]" or "[measure]"; keep the part inside the last brackets
    return [{k.rsplit("[", 1)[-1].rstrip("]"): v for k, v in r.items()} for r in rows]


def read(name, folder=STG):
    with open(folder / name, encoding="utf-8") as f:
        return list(csv.DictReader(l for l in f if not l.startswith("#")))


def main():
    if "--no-refresh" not in sys.argv:
        check("model refresh through the local engine", engine("-Action", "Refresh")["status"] == "ok", {})

    # 1. Row counts = staging CSVs (one grain per table)
    tables = ["dim_zone", "dim_party", "dim_state", "fact_result_2023", "fact_turnout_2023"]
    got = dax("EVALUATE ROW(" + ", ".join(f'"{t}", COUNTROWS({t})' for t in tables) + ")")[0]
    want = {t: len(read(f"{t}.csv")) for t in tables}
    check("row counts in the model = staging CSVs", got == want, {"model": got, "staging": want})

    # 2. Relationships: no orphan keys either side
    o = dax('EVALUATE ROW("result_no_state", COUNTROWS(FILTER(fact_result_2023, ISBLANK(RELATED(dim_state[state_name])))),'
            ' "turnout_no_state", COUNTROWS(FILTER(fact_turnout_2023, ISBLANK(RELATED(dim_state[state_name])))),'
            ' "state_no_zone", COUNTROWS(FILTER(dim_state, ISBLANK(RELATED(dim_zone[zone])))))')[0]
    check("no orphan keys (result/turnout -> state, state -> zone)", all(v in (None, 0) for v in o.values()), o)

    # 3. National totals per candidate = INEC declaration; 25% counts = 29/21/16/1
    inec = {r["party"]: int(r["value"]) for r in read("inec_national_declaration_2023.csv", REF) if r["measure"] == "candidate_votes"}
    rows = dax('EVALUATE SUMMARIZECOLUMNS(dim_party[party], "votes", [Candidate votes], "share", [Candidate share],'
               ' "t25", [States at 25% or more], "computable", [States with a computable share])')
    by = {r["party"]: r for r in rows}
    check("candidate votes = INEC national (APC, PDP, LP, NNPP)",
          all(by[p]["votes"] == inec[p] for p in PARTIES), {p: {"model": by[p]["votes"], "inec": inec[p]} for p in PARTIES})
    votes = {(r["state_pcode"], r["party"]): int(r["votes"]) for r in read("fact_result_2023.csv")}
    tv = {r["state_pcode"]: int(r["total_valid"]) for r in read("fact_turnout_2023.csv")}
    expected = {p: sum(4 * votes[(s, p)] >= tv[s] for s in tv) for p in PARTIES}   # recomputed from staging
    t25 = {p: by[p]["t25"] for p in PARTIES}
    check("States at 25% or more = staging recompute = 29 / 21 / 16 / 1 (37 units incl. FCT)",
          t25 == expected == DECLARED_T25, {"model": t25, "staging_recompute": expected, "declared": DECLARED_T25})
    comp = {p: by[p]["computable"] for p in PARTIES}
    check("States with a computable share = 37 for every candidate", all(v == 37 for v in comp.values()), comp)
    check("OTHERS row present, and its 25% count is blank (not a candidate)",
          "OTHERS" in by and by["OTHERS"]["t25"] is None, {"OTHERS": by.get("OTHERS")})
    nofct = dax('EVALUATE CALCULATETABLE(SUMMARIZECOLUMNS(dim_party[party], "t25", [States at 25% or more]),'
                ' dim_state[is_fct] = 0)')
    info = {"national_share_model": {p: by[p]["share"] for p in PARTIES},
            "national_share_inec_totals": {p: inec[p] / sum(inec.values()) for p in PARTIES},
            "t25_excluding_fct": {r["party"]: r["t25"] for r in nofct if r["party"] in PARTIES}}
    checks.append({"check": "info: national shares (model vs INEC totals) and 25% counts without FCT",
                   "status": "info", "evidence": info})

    # 4. Every state x candidate share = staging votes / total_valid (exact to 1e-12)
    cells = dax('EVALUATE SUMMARIZECOLUMNS(dim_state[state_pcode], dim_party[party], "v", [Candidate votes], "s", [Candidate share])')
    bad = [c for c in cells if c["v"] != votes[(c["state_pcode"], c["party"])]
           or abs(c["s"] - votes[(c["state_pcode"], c["party"])] / tv[c["state_pcode"]]) > 1e-12]
    check("all 185 state x candidate votes and shares = staging", len(cells) == 185 and not bad,
          {"cells": len(cells), "mismatches": bad[:10]})

    # 5. Guard: dim_party must stay disconnected (true by design; fails if someone adds a relationship)
    d = dax('EVALUATE ROW("all", [Valid votes], "apc_selected", CALCULATE([Valid votes], dim_party[party] = "APC"),'
            ' "lp_selected", CALCULATE([Valid votes], dim_party[party] = "LP"))')[0]
    check("guard: candidate selection does not filter valid votes (dim_party disconnected)",
          d["all"] == d["apc_selected"] == d["lp_selected"] == sum(tv.values()), {**d, "staging_sum": sum(tv.values())})
    # No selection or two selections must give blanks, never a misleading number
    e = dax('EVALUATE ROW("none_votes", [Candidate votes], "none_t25", [States at 25% or more],'
            ' "two_votes", CALCULATE([Candidate votes], dim_party[party] IN {"APC", "PDP"}),'
            ' "two_t25", CALCULATE([States at 25% or more], dim_party[party] IN {"APC", "PDP"}))')[0]
    check("no candidate or two candidates selected -> blank, not a number", all(v is None for v in e.values()), e)

    # 6. Zone roll-up: states per zone = dim_zone.state_count
    z = dax('EVALUATE SUMMARIZECOLUMNS(dim_zone[zone_code], "n", COUNTROWS(dim_state))')
    zc = {r["zone_code"]: int(r["state_count"]) for r in read("dim_zone.csv")}
    check("zone -> state relationship gives the expected state counts", {r["zone_code"]: r["n"] for r in z} == zc,
          {"model": {r["zone_code"]: r["n"] for r in z}, "dim_zone": zc})

    failed = [c["check"] for c in checks if c["status"] == "fail"]
    out = {"built_by": "scripts/validate_phase3.py", "gate_passed": not failed,
           "summary": {"checks": len(checks), "pass": sum(c["status"] == "pass" for c in checks), "fail": len(failed), "info": sum(c["status"] == "info" for c in checks)},
           "failed": failed, "checks": checks}
    (REP / "phase3_validation.json").write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    for c in checks:
        print(f"  [{c['status'].upper():4}] {c['check']}")
    print(f"\n  gate {'PASSED' if not failed else 'FAILED'}: {out['summary']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
