"""Phase 4 scenario-engine checks against the live model in Power BI Desktop.

Contains a separate re-implementation of docs/methodology.md (same author, so it mainly guards against DAX slips;
the blind reproduction by the Phase 4 reviewer is the independence evidence - registers/qa-log.md) (functions `scenario_share`, `counts`, `tipping`)
that reads only the staging CSVs, and compares it with the model's measures for a grid of slider settings,
including every slider at its minimum and maximum. Writes reports/phase4_validation.json; exits 1 on a failure.

Requires Desktop open on pbip/NaijaElectionsGap.pbip with data refreshed (scripts/pbi_reopen.ps1).
Usage (repo root):  uv run python -I scripts/validate_phase4.py
"""
import csv, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STG, REP = ROOT / "data" / "staging", ROOT / "reports"
PS = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "pbi_engine.ps1")]
PARTIES = ["APC", "PDP", "LP", "NNPP"]
ZONES = ["NC", "NE", "NW", "SE", "SS", "SW"]
TOL = 1e-12
checks = []


def check(name, ok, evidence):
    checks.append({"check": name, "status": "pass" if ok else "fail", "evidence": evidence})


def dax(q):
    r = subprocess.run(PS + ["-Action", "Query", "-Dax", q], capture_output=True, text=True, encoding="utf-8", timeout=420)
    if r.returncode:
        raise RuntimeError(r.stderr or r.stdout)
    return [{k.rsplit("[", 1)[-1].rstrip("]"): v for k, v in row.items()} for row in json.loads(r.stdout.lstrip("﻿"))]


def read(name):
    with open(STG / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------- reference implementation of docs/methodology.md ----------------
STATES = read("dim_state.csv")
ZONE = {s["state_pcode"]: s["zone_code"] for s in STATES}
VOTES = {(r["state_pcode"], r["party"]): int(r["votes"]) for r in read("fact_result_2023.csv")}
VALID = {r["state_pcode"]: int(r["total_valid"]) for r in read("fact_turnout_2023.csv")}


def scenario_share(s, party, st):
    v, V, t = VOTES[(s, party)], VALID[s], st["t"] / 100
    u = v * (1 + t) / (V + v * t) + (st["S"] + st["Z"][ZONE[s]]) / 100     # steps 1-2
    return min(1, max(0, u)), u


def counts(party, st, n):
    p = {s: scenario_share(s, party, st) for s in VALID}
    sec = sum(x >= 0.25 for x, _ in p.values())
    return {"sec": sec, "wr": sum(0.20 <= x < 0.25 for x, _ in p.values()), "out": sum(x < 0.20 for x, _ in p.values()),
            "cap": sum(u <= 0 or u >= 1 for _, u in p.values()), "with": len(p), "need": max(0, n - sec),
            "clears": "Yes" if sec >= n else "No", "tip": tipping(p, n)}


def tipping(p, n):
    ranked = sorted(p, key=lambda s: (-p[s][0], s))   # share desc, P-code asc
    return ranked[n - 1]


# ---------------- model side ----------------
def filters(st, party=None):
    f = [f"TREATAS({{{st['t']}}}, param_turnout[Value])", f"TREATAS({{{st['S']}}}, param_swing_national[Value])"]
    f += [f"TREATAS({{{st['Z'][z]}}}, param_swing_{z}[Value])" for z in ZONES]
    if party:
        f.append(f'TREATAS({{"{party}"}}, dim_party[party])')
    return ", ".join(f)


def setting(t: float = 0, S: float = 0, **z):
    return {"t": t, "S": S, "Z": {k: z.get(k, 0) for k in ZONES}}


GRID = {
    "neutral": setting(),
    "national +5": setting(S=5),
    "national -5, SE +10": setting(S=-5, SE=10),
    "supporters +20%, national +2": setting(t=20, S=2),
    "every slider at minimum": setting(t=-50, S=-20, **{z: -20 for z in ZONES}),
    "every slider at maximum": setting(t=50, S=20, **{z: 20 for z in ZONES}),
    "mixed": setting(t=-10, S=1.5, NC=3, NE=-2, NW=-4.5, SE=12, SS=6, SW=-1),
    "odd: supporters -37%, national +7.5, mixed zones": setting(t=-37, S=7.5, NC=3, NE=-2.5, SE=1, SS=-4.5, SW=6),
    "odd: supporters +13%, national -3.5": setting(t=13, S=-3.5, NW=0.5, SE=-6.5),
    # each slider alone at its minimum and maximum (the note: "every slider at its minimum and at its maximum")
    "supporter turnout alone at -50": setting(t=-50),
    "supporter turnout alone at +50": setting(t=50),
    "national swing alone at -20": setting(S=-20),
    "national swing alone at +20": setting(S=20),
    **{f"zone {z} alone at {v:+d}": setting(**{z: v}) for z in ZONES for v in (-20, 20)},
}


def main():
    for label, st in GRID.items():
        # per unit x candidate
        rows = dax(f'EVALUATE CALCULATETABLE(SUMMARIZECOLUMNS(dim_state[state_pcode], dim_party[party], '
                   f'"p", [Scenario share], "u", [Scenario share uncapped]), {filters(st)})')
        got = {(r["state_pcode"], r["party"]): r for r in rows if r["party"] in PARTIES}
        bad = []
        for s in VALID:
            for party in PARTIES:
                ref_p, ref_u = scenario_share(s, party, st)
                g = got.get((s, party))
                if g is None or g["p"] is None or abs(g["p"] - ref_p) > TOL or abs(g["u"] - ref_u) > TOL:
                    bad.append({"unit": s, "party": party, "model": g, "reference": [ref_p, ref_u]})
        in_range = all(g["p"] is not None and 0 <= g["p"] <= 1 for g in got.values())
        check(f"[{label}] 148 unit shares = reference implementation, all within 0-1",
              len(got) == 148 and not bad and in_range, {"cells": len(got), "mismatches": bad[:5]})
        # national counts for both rule readings
        rows = dax(f'EVALUATE CALCULATETABLE(SUMMARIZECOLUMNS(dim_party[party], param_rule[Value], '
                   f'"sec", [Units secured], "wr", [Units within reach], "out", [Units out of reach], '
                   f'"cap", [Units at a cap], "with", [Units with a scenario], "need", [Units still needed], '
                   f'"clears", [Clears the rule], "tip", [Tipping-point P-code]), {filters(st)})')
        diffs = []
        for r in rows:
            if r["party"] not in PARTIES:
                continue
            ref = counts(r["party"], st, int(r["Value"]))
            model = {k: r[k] for k in ref}
            if model != ref:
                diffs.append({"party": r["party"], "N": r["Value"], "model": model, "reference": ref})
        check(f"[{label}] counts, labels, cap count, rule and tipping point = reference (N = 24 and 25)",
              len([r for r in rows if r["party"] in PARTIES]) == 8 and not diffs,
              {"rows": len(rows), "differences": diffs,
               "sample_APC_N24": counts("APC", st, 24)})

    # neutral settings reproduce the 2023 baseline exactly
    n = dax('EVALUATE SUMMARIZECOLUMNS(dim_party[party], "sec", [Units secured], "base", [States at 25% or more])')
    nb = {r["party"]: (r["sec"], r["base"]) for r in n if r["party"] in PARTIES}
    check("neutral sliders: units secured = baseline 25% count = 29 / 21 / 16 / 1",
          nb == {"APC": (29, 29), "PDP": (21, 21), "LP": (16, 16), "NNPP": (1, 1)}, nb)
    exact = dax('EVALUATE ROW("max_abs_diff", MAXX(CROSSJOIN(VALUES(dim_state[state_pcode]), '
                'FILTER(VALUES(dim_party[party]), dim_party[party] <> "OTHERS")), ABS([Scenario share] - [Candidate share])))')[0]
    check("neutral sliders: every unit's scenario share = baseline share exactly", exact["max_abs_diff"] == 0, exact)

    # more national swing never lowers units secured
    m = dax('EVALUATE SUMMARIZECOLUMNS(dim_party[party], param_swing_national[Value], "sec", [Units secured])')
    series = {p: [r["sec"] for r in sorted((r for r in m if r["party"] == p), key=lambda r: r["Value"])] for p in PARTIES}
    mono = {p: all(a <= b for a, b in zip(v, v[1:])) and len(v) == 81 for p, v in series.items()}
    check("units secured never falls as national swing rises (-20 to +20, 81 steps)", all(mono.values()),
          {p: {"monotonic": mono[p], "at -20": v[0], "at 0": v[40], "at +20": v[-1]} for p, v in series.items()})

    # Exact-boundary search (pure Python, exact fractions): can any reachable slider combination put a unit EXACTLY on
    # 25% or 20%? If not, decimal comparison in the model can never misclassify a unit at the boundary.
    from fractions import Fraction
    hits = []
    for (s, party), v in VOTES.items():
        if party == "OTHERS":
            continue
        V = VALID[s]
        for k in range(-50, 51):                       # supporter turnout, percent
            p1 = Fraction(v * (100 + k), 100 * V + v * k)
            for m in range(-80, 81):                   # total swing in half-points: -40 .. +40 points
                p2 = p1 + Fraction(m, 200)
                if p2 in (Fraction(1, 4), Fraction(1, 5)):
                    hits.append({"unit": s, "party": party, "turnout": k, "swing_points": m / 2, "share": str(p2)})
    check("exact-boundary search: no reachable slider combination puts a unit exactly on 25% or 20%", not hits,
          {"combinations": 37 * 4 * 101 * 161, "exact_hits": hits[:10]})

    # A zone filter on the page: national measures stay national; unit counts follow the filter
    st = setting(S=7.5)
    zf = []
    for party in PARTIES:
        ref = counts(party, st, 24)
        for z in ("NW", "SE"):
            r = dax(f'EVALUATE CALCULATETABLE(ROW("sec_zone", [Units secured], "sec_nat", [Units secured (national)], '
                    f'"need", [Units still needed], "clears", [Clears the rule], "tip", [Tipping-point P-code]), '
                    f'{filters(st, party)}, TREATAS({{24}}, param_rule[Value]), TREATAS({{"{z}"}}, dim_zone[zone_code]))')[0]
            zone_ref = sum(scenario_share(s, party, st)[0] >= 0.25 for s in VALID if ZONE[s] == z)
            ok = (r["sec_nat"], r["need"], r["clears"], r["tip"]) == (ref["sec"], ref["need"], ref["clears"], ref["tip"]) \
                and r["sec_zone"] == zone_ref
            if not ok:
                zf.append({"party": party, "zone": z, "model": r, "national_ref": ref, "zone_ref": zone_ref})
    check("zone filter on the page: rule, units still needed and tipping point stay national; zone count follows the filter",
          not zf, {"setting": "national +7.5, N=24, zones NW and SE", "differences": zf})

    # OTHERS and no selection give blanks, never numbers
    b = dax('EVALUATE ROW("none", [Units secured], "others", CALCULATE([Units secured], dim_party[party] = "OTHERS"),'
            ' "others_share", CALCULATE([Scenario share], dim_party[party] = "OTHERS", dim_state[state_pcode] = "NG001"))')[0]
    check("no candidate / OTHERS -> blank scenario", all(v is None for v in b.values()), b)

    failed = [c["check"] for c in checks if c["status"] == "fail"]
    out = {"built_by": "scripts/validate_phase4.py", "method": "docs/methodology.md", "gate_passed": not failed,
           "summary": {"checks": len(checks), "pass": len(checks) - len(failed), "fail": len(failed)},
           "grid": GRID, "failed": failed, "checks": checks}
    (REP / "phase4_validation.json").write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    for c in checks:
        print(f"  [{c['status'].upper():4}] {c['check']}")
    print(f"\n  gate {'PASSED' if not failed else 'FAILED'}: {out['summary']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
