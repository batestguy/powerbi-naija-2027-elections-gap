"""Phase 4 scenario-engine checks against the live model in Power BI Desktop.

Contains a separate re-implementation of docs/methodology.md (same author, so it mainly guards against DAX slips;
the blind reproduction by the Phase 4 reviewer is the independence evidence - registers/qa-log.md) (functions `scenario_share`, `counts`, `tipping`)
that reads only the staging CSVs, and compares it with the model's measures for a grid of slider settings,
including every slider at its minimum and maximum. Writes reports/phase4_validation.json; exits 1 on a failure.

Coalitions (2026-11-16): a second exact re-implementation (Python fractions / whole numbers) of the methodology's
"Coalitions" section is compared with the coalition measures for every 2 v 1 and 2 v 2 pairing at several follow rates,
the simulator with the coalition switch On, invalid choices, and the switch Off.

Requires Desktop open on pbip/NaijaElectionsGap.pbip with data refreshed (scripts/pbi_reopen.ps1).
Usage (repo root):  uv run python -I scripts/validate_phase4.py                 (all parts -> phase4_validation.json)
                    uv run python -I scripts/validate_phase4.py --part pages    (one part -> reports/phase4_parts/pages.json)
                    uv run python -I scripts/validate_phase4.py --combine       (all part files -> phase4_validation.json)
Parts: core, pages, simulator, invalid, switch_off, boundary. Each result is printed as soon as it is known and the
output file is rewritten after every check, so a run that is stopped (e.g. for low memory) keeps what it finished.
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


OUT = {"path": None, "part": "all"}   # where partial results go (set in main)


def write_out(complete):
    failed = [c["check"] for c in checks if c["status"] == "fail"]
    out = {"built_by": "scripts/validate_phase4.py", "method": "docs/methodology.md", "part": OUT["part"],
           "complete": complete, "gate_passed": complete and not failed,
           "summary": {"checks": len(checks), "pass": len(checks) - len(failed), "fail": len(failed)},
           "grid": GRID, "failed": failed, "checks": checks}
    OUT["path"].parent.mkdir(parents=True, exist_ok=True)
    OUT["path"].write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    return out


def check(name, ok, evidence):
    checks.append({"check": name, "status": "pass" if ok else "fail", "evidence": evidence})
    print(f"  [{checks[-1]['status'].upper():4}] {name}", flush=True)
    if OUT["path"]:
        write_out(False)


def progress(msg):
    print(f"    ... {msg}", flush=True)


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


def rivals(party, st, n):
    """docs/methodology.md 'Rivals and the verdict': other candidates scale by (1 - p2) / (1 - p1) in each unit."""
    nat_c = nat_valid = 0.0
    rv = {r: 0.0 for r in PARTIES if r != party}
    r25 = {r: 0 for r in rv}
    for s in VALID:
        v, V, t = VOTES[(s, party)], VALID[s], st["t"] / 100
        V1 = V + v * t
        p1 = v * (1 + t) / V1
        p2, _ = scenario_share(s, party, st)
        scale = (1 - p2) / (1 - p1) if p1 < 1 else 0
        nat_c += p2 * V1
        nat_valid += V1
        for r in rv:
            rv[r] += VOTES[(s, r)] * scale
            r25[r] += VOTES[(s, r)] * scale >= 0.25 * V1
    lead = sorted(rv, key=lambda r: (-rv[r], r))[0]
    most = "Yes" if nat_c > rv[lead] else ("Tied" if nat_c == rv[lead] else "No")
    clears = sum(scenario_share(s, party, st)[0] >= 0.25 for s in VALID) >= n
    if most == "Yes":
        verdict = "Outright win" if clears else "No outright winner: run-off (most votes, but not 25% in enough states)"
    elif most == "Tied":
        verdict = "Tie on votes: no outright winner"
    else:
        verdict = f"Loses: {lead} wins outright" if r25[lead] >= n else f"No outright winner: run-off ({lead} has most votes)"
    return {"nat": nat_c, "share": nat_c / nat_valid, "lead": lead, "lead_votes": rv[lead], "lead_25": r25[lead],
            "most": most, "verdict": verdict}


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


# ---------------- coalitions: reference implementation of docs/methodology.md "Coalitions" (exact fractions) ----------
# Reads only the staging CSVs and data/reference/coalition_names.csv; compares with the model's coalition measures.
from fractions import Fraction as Fr
import math, tempfile
from decimal import Decimal, ROUND_HALF_UP

REFD = ROOT / "data" / "reference"


def read_ref(name):
    with open(REFD / name, encoding="utf-8") as f:
        return list(csv.DictReader(l for l in f if not l.startswith("#")))


CAND = {r["party"]: r["candidate"] for r in read("dim_party.csv")}
NAMES = {(r["lead"], r["partner"]): r for r in read_ref("coalition_names.csv")}
SNAME = {s["state_pcode"]: s["state_name"] for s in STATES}


def dax_file(q):
    """Long queries go through a file (command-line length limit)."""
    with tempfile.NamedTemporaryFile("w", suffix=".dax", delete=False, encoding="utf-8") as f:
        f.write(q)
    try:
        r = subprocess.run(PS + ["-Action", "Query", "-DaxFile", f.name], capture_output=True, text=True,
                           encoding="utf-8", timeout=600)
    finally:
        Path(f.name).unlink(missing_ok=True)
    if r.returncode:
        raise RuntimeError(r.stderr or r.stdout)
    return [{k.rsplit("[", 1)[-1].rstrip("]"): v for k, v in row.items()} for row in json.loads(r.stdout.lstrip("﻿"))]


def cfg_filters(c):
    """c = (al, ap, fa, bl, bp, fb); bp None = Side B alone. Any element None = no selection (left unfiltered)."""
    al, ap, fa, bl, bp, fb = c
    f = []
    for tbl, val in (("coal_a_lead", al), ("coal_a_partner", ap), ("coal_b_lead", bl)):
        if val is not None:
            f.append(f'TREATAS({{"{val}"}}, {tbl}[party])')
    f.append(f'TREATAS({{"{bp or "NONE"}"}}, coal_b_partner[party])')
    f += [f"TREATAS({{{fa}}}, param_follow_a[Value])", f"TREATAS({{{fb}}}, param_follow_b[Value])"]
    return f


def side_name(lead, partner):
    return NAMES[(lead, partner)]["display_name"] if partner else f"{CAND[lead]} ({lead})"


def coal_per_state(al, ap, fa, bl, bp, fb):
    """Whole numbers x100 per state: C (Side A), WA (valid, merge page), B (Side B), W (valid, head to head)."""
    out = {}
    for s in VALID:
        C = 100 * VOTES[(s, al)] + fa * VOTES[(s, ap)]
        WA = 100 * VALID[s] - (100 - fa) * VOTES[(s, ap)]
        B = 100 * VOTES[(s, bl)] + (fb * VOTES[(s, bp)] if bp else 0)
        W = WA - ((100 - fb) * VOTES[(s, bp)] if bp else 0)
        unused = [x for x in PARTIES if x not in (al, ap, bl, bp)]
        o = max((100 * VOTES[(s, x)] for x in unused), default=-1)
        lead = "A" if C > B and C > o else "B" if B > C and B > o else "O" if o > C and o > B else "T"
        if lead == "O":
            lead_txt = sorted(unused, key=lambda x: (-VOTES[(s, x)], x))[0] + " (on neither side)"
        else:
            lead_txt = {"A": "Side A", "B": "Side B", "T": "Tie"}[lead]
        status = "Secured" if 4 * C >= WA else "Within reach" if 5 * C >= WA else "Out of reach"
        out[s] = {"C": C, "WA": WA, "B": B, "W": W, "lead": lead, "lead_txt": lead_txt, "status": status,
                  "a25": "Yes" if 4 * C >= W else "No", "b25": "Yes" if 4 * B >= W else "No"}
    return out


def verdict_strings(most, a_clears, r_disp, r_clears, nm, rl, k, n):
    if most == "Yes":
        v = "Outright win" if a_clears else "No outright winner: run-off (most votes, but not 25% in enough states)"
        s = (f"{nm} wins outright: the most votes nationwide and a quarter of the vote in {k} states ({n} needed)."
             if a_clears else f"No outright winner: {nm} has the most votes but a quarter of the vote in only {k} states "
                              f"({n} needed). This would go to a run-off.")
    elif most == "Tied":
        v, s = "Tie on votes: no outright winner", "Tie on votes: no outright winner."
    elif r_clears:
        v, s = f"Loses: {r_disp} wins outright", f"{nm} loses: {rl} has the most votes and a quarter of the vote in enough states."
    else:
        v = f"No outright winner: run-off ({r_disp} has most votes)"
        s = (f"No outright winner: {rl} has the most votes but not a quarter of the vote in enough states. This would go "
             f"to a run-off.")
    return v, s


def coal_national(al, ap, fa, bl, bp, fb, n):
    per = coal_per_state(al, ap, fa, bl, bp, fb)
    C = sum(p["C"] for p in per.values())
    WA = sum(p["WA"] for p in per.values())
    W = sum(p["W"] for p in per.values())
    Bn = sum(p["B"] for p in per.values())
    ents = {bl: Bn, **{x: 100 * sum(VOTES[(s, x)] for s in VALID) for x in PARTIES if x not in (al, ap, bl, bp)}}
    r = sorted(ents, key=lambda x: (-ents[x], x))[0]
    rv = ents[r]
    r_st = sum(4 * (per[s]["B"] if r == bl else 100 * VOTES[(s, r)]) >= per[s]["W"] for s in VALID)
    most = "Yes" if C > rv else "Tied" if C == rv else "No"
    a_st = sum(p["a25"] == "Yes" for p in per.values())
    r_disp = f"{r}+{bp}" if (r == bl and bp) else r
    rl = side_name(bl, bp) if r == bl else f"{CAND[r]} ({r})"
    v, s = verdict_strings(most, a_st >= n, r_disp, r_st >= n, side_name(al, ap), rl, a_st, n)
    return {"stM": sum(4 * p["C"] >= p["WA"] for p in per.values()),
            "leadSt": sum(4 * VOTES[(s, al)] >= VALID[s] for s in VALID),
            "natA": Fr(C, 100), "shAM": Fr(C, WA), "shAh": Fr(C, W), "shBh": Fr(Bn, W), "natB": Fr(Bn, 100),
            "stA": a_st, "stB": sum(p["b25"] == "Yes" for p in per.values()),
            "ledA": sum(p["lead"] == "A" for p in per.values()), "ledB": sum(p["lead"] == "B" for p in per.values()),
            "rival": r_disp, "rx100": rv, "rst": r_st, "most": most, "verdict": v, "sent": s,
            "nameA": side_name(al, ap), "nameB": side_name(bl, bp)}


def coal_sim(c, st, n):
    """Simulator with the switch On: steps 1-3 on c and V', rivals as entities (exact fractions)."""
    al, ap, fa, bl, bp, fb = c
    per = coal_per_state(al, ap, fa, bl, bp, fb)
    t = Fr(st["t"]).limit_denominator(1000) / 100
    rows, nat_c, nat_v = {}, Fr(0), Fr(0)
    ents = [bl] + [x for x in PARTIES if x not in (al, ap, bl, bp)]
    rv = {e: Fr(0) for e in ents}
    r25 = {e: 0 for e in ents}
    for s in VALID:
        cv, Vp = Fr(per[s]["C"], 100), Fr(per[s]["W"], 100)
        V1 = Vp + cv * t
        p1 = cv * (1 + t) / V1
        sw = (Fr(st["S"]).limit_denominator(10) + Fr(st["Z"][ZONE[s]]).limit_denominator(10)) / 100
        u = p1 + sw
        p2 = min(Fr(1), max(Fr(0), u))
        scale = (1 - p2) / (1 - p1) if p1 < 1 else Fr(0)
        v2 = p2 * V1
        rows[s] = {"p": p2, "u": u, "V1": V1, "v2": v2, "need": math.ceil(max(Fr(0), V1 / 4 - v2)),
                   "spare": math.floor(max(Fr(0), v2 - V1 / 4))}
        nat_c += v2
        nat_v += V1
        for e in ents:
            ev = (Fr(per[s]["B"], 100) if e == bl else Fr(VOTES[(s, e)])) * scale
            rv[e] += ev
            r25[e] += ev >= V1 / 4
    sec = sum(r["p"] >= Fr(1, 4) for r in rows.values())
    ranked = sorted(rows, key=lambda s: (-rows[s]["p"], s))
    tip = ranked[n - 1]
    lead = sorted(ents, key=lambda e: (-rv[e], e))[0]
    most = "Yes" if nat_c > rv[lead] else "Tied" if nat_c == rv[lead] else "No"
    r_disp = f"{lead}+{bp}" if (lead == bl and bp) else lead
    nm = side_name(al, ap)
    rl = side_name(bl, bp) if lead == bl else f"{CAND[lead]} ({lead})"
    verdict, _ = verdict_strings(most, sec >= n, r_disp, r25[lead] >= n, nm, rl, sec, n)
    # Result sentence (the simulator's own wording) and deciding-state sentence
    if most == "Yes":
        result = (f"{nm} wins outright: the most votes nationwide and a quarter of the vote in {sec} states ({n} needed)."
                  if sec >= n else f"No outright winner: {nm} has the most votes but a quarter of the vote in only {sec} "
                                   f"states ({n} needed). This would go to a run-off.")
    elif most == "Tied":
        result = "Tie on votes: no outright winner."
    elif r25[lead] >= n:
        result = f"{nm} loses: {rl} has the most votes and a quarter of the vote in enough states."
    else:
        result = (f"No outright winner: {rl} has the most votes but not a quarter of the vote in enough states. This would "
                  f"go to a run-off.")
    gap = (Fr(1, 4) - rows[tip]["p"]) * 100
    g1 = (Decimal(abs(gap).numerator) / Decimal(abs(gap).denominator)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    decide = (f"{SNAME[tip]} is the deciding state. {nm} is {g1} points above a quarter of the vote there: about "
              f"{rows[tip]['spare']:,} votes could switch to other candidates before the state is lost." if gap <= 0 else
              f"{SNAME[tip]} is the deciding state. {nm} is {g1} points short of a quarter of the vote there: about "
              f"{rows[tip]['need']:,} more votes would need to switch from other candidates to {nm}.")
    zname = {"NC": "North Central and Abuja", "NE": "North East", "NW": "North West", "SE": "South East",
             "SS": "South South", "SW": "South West"}
    parts = ([f"{st['S']:+.1f} points everywhere"] if st["S"] else []) + \
            ([", ".join(f"{st['Z'][z]:+.1f} in the {zname[z]}" for z in ZONES if st["Z"][z])] if any(st["Z"].values()) else []) + \
            ([f"{int(st['t']):+d}% turnout among the coalition's 2023 voters"] if st["t"] else [])
    inforce = ("; ".join(parts) if parts else "No changes: this is the 2023 result") + f". {n} states needed to win."
    return {"per": rows, "sec": sec, "wr": sum(Fr(1, 5) <= r["p"] < Fr(1, 4) for r in rows.values()),
            "out": sum(r["p"] < Fr(1, 5) for r in rows.values()), "cap": sum(r["u"] <= 0 or r["u"] >= 1 for r in rows.values()),
            "with": 37, "need": max(0, n - sec), "clears": "Yes" if sec >= n else "No", "tip": tip,
            "nat": nat_c, "share": nat_c / nat_v, "lead": r_disp, "lead_votes": rv[lead], "lead_25": r25[lead],
            "most": most, "verdict": verdict, "result": result, "decide": decide, "inforce": inforce}


def close(a, b, rel=1e-9):
    return a is not None and abs(float(a) - float(b)) <= rel * max(1.0, abs(float(b)))


ALL_2V1 = [(al, ap, f, bl, None, 100) for al in PARTIES for ap in PARTIES if ap != al
           for bl in PARTIES if bl not in (al, ap) for f in (0, 35, 100)]
FOLLOW_2V2 = [(100, 100), (0, 35), (35, 0), (55, 100), (5, 95)]
ALL_2V2 = [(al, ap, fa, bl, bp, fb) for al in PARTIES for ap in PARTIES if ap != al
           for bl in PARTIES if bl not in (al, ap) for bp in PARTIES if bp not in (al, ap, bl) for fa, fb in FOLLOW_2V2]
PRESET = ("LP", "NNPP", 100, "APC", None, 100)


def coalition_pages_check():
    configs = [PRESET] + ALL_2V1 + ALL_2V2
    state_bad, nat_bad, f_bad = [], [], []
    for i in range(0, len(configs), 10):   # 10 pairings per state query (40 pushed the engine past 3 GB)
        batch = configs[i:i + 10]
        progress(f"coalition pages: pairings {i}-{i + len(batch) - 1} of {len(configs)}")
        parts = []
        for j, c in enumerate(batch):
            parts.append(f'CALCULATETABLE(ADDCOLUMNS(VALUES(dim_state[state_pcode]), "cfg", {i + j}, '
                         '"A100", [Side A x100], "WA", [Valid x100 (merge)], "W", [Valid x100 (head to head)], '
                         '"B100", [Side B x100], "st", [Side A status (merge)], "lead", [Who leads (head to head)], '
                         '"a25", [Side A at 25% (head to head)], "b25", [Side B at 25% (head to head)], '
                         '"shA", [Side A share (merge)], "shAh", [Side A share (head to head)], '
                         f'"shB", [Side B share (head to head)]), {", ".join(cfg_filters(c))})')
        rows = dax_file("EVALUATE UNION(" + ", ".join(parts) + ")")
        got = {(r["cfg"], r["state_pcode"]): r for r in rows}
        for j, c in enumerate(batch):
            per = coal_per_state(*c)
            for s, ref in per.items():
                g = got.get((i + j, s))
                ok = g is not None and (g["A100"], g["WA"], g["W"], g["B100"]) == (ref["C"], ref["WA"], ref["W"], ref["B"]) \
                    and g["st"] == ref["status"] and g["lead"] == ref["lead_txt"] and g["a25"] == ref["a25"] \
                    and g["b25"] == ref["b25"] and close(g["shA"], Fr(ref["C"], ref["WA"]), 1e-12) \
                    and close(g["shAh"], Fr(ref["C"], ref["W"]), 1e-12) and close(g["shB"], Fr(ref["B"], ref["W"]), 1e-12)
                if not ok:
                    state_bad.append({"config": c, "state": s, "model": g, "reference": {k: str(v) for k, v in ref.items()}})
                # follow-rate end points: at 100% the coalition = lead + partner exactly; at 0 it = lead, V' = V - partner
                al, ap, fa = c[:3]
                if g is not None and fa == 100 and (g["A100"] != 100 * (VOTES[(s, al)] + VOTES[(s, ap)]) or g["WA"] != 100 * VALID[s]):
                    f_bad.append({"config": c, "state": s, "model": g})
                if g is not None and fa == 0 and (g["A100"] != 100 * VOTES[(s, al)] or g["WA"] != 100 * (VALID[s] - VOTES[(s, ap)])):
                    f_bad.append({"config": c, "state": s, "model": g})
        # national, both rule readings
        parts = []
        for j, c in enumerate(batch):
            for n in (24, 25):
                parts.append(f'CALCULATETABLE(ROW("cfg", {i + j}, "N", {n}, "stM", [Side A states at 25% (merge)], '
                             '"leadSt", [Side A lead states at 25%], "natA", [Side A national votes], '
                             '"shAM", [Side A national share (merge)], "shAh", [Side A national share (head to head)], '
                             '"shBh", [Side B national share (head to head)], "natB", [Side B national votes], '
                             '"stA", [Side A states at 25% (head to head)], "stB", [Side B states at 25% (head to head)], '
                             '"ledA", [States led by Side A], "ledB", [States led by Side B], "rival", [Head to head rival], '
                             '"rx100", [Head to head rival x100], "rst", [Head to head rival states at 25%], '
                             '"most", [Head to head most votes], "verdict", [Head to head verdict], '
                             '"sent", [Head to head sentence], "nameA", [Side A name], "nameB", [Side B name]), '
                             f'{", ".join(cfg_filters(c))}, TREATAS({{{n}}}, param_rule[Value]))')
        nat_rows = []
        for k in range(0, len(parts), 4):   # 2 pairings x 2 rules per query (80 at once ran out of engine memory)
            nat_rows += dax_file("EVALUATE UNION(" + ", ".join(parts[k:k + 4]) + ")")
        for r in nat_rows:
            c = batch[r["cfg"] - i]
            ref = coal_national(*c, r["N"])
            diff = {k: [r.get(k), str(v)] for k, v in ref.items()
                    if not (close(r.get(k), v, 1e-12) if isinstance(v, Fr) else r.get(k) == v)}
            if diff:
                nat_bad.append({"config": c, "N": r["N"], "differences": diff})
    n_states = 37 * len(configs)
    check(f"coalition pages, per state: whole-number votes and valid totals, shares, status, who leads and 25% flags = "
          f"exact reference ({len(configs)} pairings x follow rates: preset, every 2 v 1 at 0/35/100%, every 2 v 2 at 5 "
          f"follow-rate pairs; {n_states} state rows)", not state_bad, {"mismatches": state_bad[:5], "count": len(state_bad)})
    check("coalition pages, national: states at 25%+ (coalition, lead alone, both sides), votes, shares, states led, "
          "leading rival, most votes, verdict and sentence = exact reference (N = 24 and 25)", not nat_bad,
          {"mismatches": nat_bad[:5], "count": len(nat_bad), "preset_N24": {k: str(v) for k, v in coal_national(*PRESET, 24).items()}})
    check("follow 100%: coalition = lead + partner exactly and valid total unchanged; follow 0: coalition = lead and "
          "valid total = 2023 valid - partner's votes (every state, every pairing at those rates)", not f_bad,
          {"mismatches": f_bad[:5]})


SIM_CONFIGS = {"preset NDC (Obi + Kwankwaso) 100% vs APC": PRESET,
               "2 v 2: PDP+LP 35% vs APC+NNPP 70%": ("PDP", "LP", 35, "APC", "NNPP", 70),
               "2 v 1: APC+PDP 0% vs NNPP": ("APC", "PDP", 0, "NNPP", None, 100),
               "2 v 1: NNPP+LP 85% vs PDP": ("NNPP", "LP", 85, "PDP", None, 100)}
SIM_SETTINGS = {
    "neutral": setting(),
    "every slider at minimum": setting(t=-50, S=-20, **{z: -20 for z in ZONES}),
    "every slider at maximum": setting(t=50, S=20, **{z: 20 for z in ZONES}),
    "national +5": setting(S=5),
    "supporters +20%, national -2": setting(t=20, S=-2),
    "odd: supporters -37%, national +7.5, mixed zones": setting(t=-37, S=7.5, NC=3, NE=-2.5, SE=1, SS=-4.5, SW=6),
    "odd: supporters +13%, national -3.5, NW +0.5, SE -6.5": setting(t=13, S=-3.5, NW=0.5, SE=-6.5),
    "mixed": setting(t=-10, S=1.5, NC=3, NE=-2, NW=-4.5, SE=12, SS=6, SW=-1),
    "national -20 alone": setting(S=-20),
}


def coalition_simulator_check():
    bad = []
    for label, st in SIM_SETTINGS.items():
        names = list(SIM_CONFIGS)
        on = ['TREATAS({"On"}, coal_switch[Value])', filters(st)]
        parts = [f'CALCULATETABLE(ADDCOLUMNS(VALUES(dim_state[state_pcode]), "cfg", {j}, "p", [Scenario share], '
                 f'"u", [Scenario share uncapped], "need", [Votes needed], "spare", [Votes to spare]), '
                 f'{", ".join(on + cfg_filters(SIM_CONFIGS[k]))})' for j, k in enumerate(names)]
        rows = dax_file("EVALUATE UNION(" + ", ".join(parts) + ")")
        parts = [f'CALCULATETABLE(ROW("cfg", {j}, "N", {n}, "sec", [Units secured], "wr", [Units within reach], '
                 '"out", [Units out of reach], "cap", [Units at a cap], "with", [Units with a scenario], '
                 '"need", [Units still needed], "clears", [Clears the rule], "tip", [Tipping-point P-code], '
                 '"nat", [Scenario national votes], "share", [Scenario national share], "lead", [Leading rival], '
                 '"lead_votes", [Leading rival votes], "lead_25", [Leading rival units at 25%], "most", [Has most votes], '
                 '"verdict", [Verdict], "result", [Result sentence], "decide", [Deciding state sentence], '
                 f'"inforce", [Assumptions in force]), {", ".join(on + cfg_filters(SIM_CONFIGS[k]))}, '
                 f'TREATAS({{{n}}}, param_rule[Value]))' for j, k in enumerate(names) for n in (24, 25)]
        progress(f"simulator, switch On: setting '{label}'")
        nat = []
        for k in range(0, len(parts), 2):   # 2 rows per query (8 at once ran out of engine memory)
            nat += dax_file("EVALUATE UNION(" + ", ".join(parts[k:k + 2]) + ")")
        refs = {}
        for r in nat:
            k = names[r["cfg"]]
            ref = refs[(k, r["N"])] = coal_sim(SIM_CONFIGS[k], st, r["N"])
            diff = {}
            for key in ("sec", "wr", "out", "cap", "with", "need", "clears", "tip", "lead", "lead_25", "most", "verdict",
                        "result", "decide", "inforce"):
                if r[key] != ref[key]:
                    diff[key] = [r[key], ref[key]]
            for key in ("nat", "lead_votes"):
                if not close(r[key], ref[key], 1e-9):
                    diff[key] = [r[key], float(ref[key])]
            if not close(r["share"], ref["share"], 1e-12):
                diff["share"] = [r["share"], float(ref["share"])]
            if diff:
                bad.append({"setting": label, "coalition": k, "N": r["N"], "differences": diff})
        for r in rows:
            k = names[r["cfg"]]
            ref = refs[(k, 24)]["per"][r["state_pcode"]]
            if not (close(r["p"], ref["p"], 1e-12) and close(r["u"], ref["u"], 1e-12) and r["need"] == ref["need"]
                    and r["spare"] == ref["spare"] and 0 <= r["p"] <= 1):
                bad.append({"setting": label, "coalition": k, "state": r["state_pcode"], "model": r,
                            "reference": {x: str(y) for x, y in ref.items()}})
        if len(rows) != 37 * len(names) or len(nat) != 2 * len(names):
            bad.append({"setting": label, "rows": len(rows), "national_rows": len(nat)})
    check(f"simulator with the coalition switch On: per-state shares (capped and uncapped), votes needed / to spare, "
          f"counts, cap count, tipping point, rivals, most votes, verdict, result / deciding-state / settings sentences "
          f"= exact reference ({len(SIM_SETTINGS)} slider settings incl. extremes and odd values x {len(SIM_CONFIGS)} "
          f"coalitions incl. 2 v 2, N = 24 and 25)", not bad,
          {"mismatches": bad[:6], "count": len(bad),
           "preset_neutral_N24": {k: (str(v) if not isinstance(v, dict) else "...")
                                  for k, v in coal_sim(PRESET, setting(), 24).items()}})


def coalition_invalid_check():
    cases = {"Side A lead = partner (LP, LP)": (("LP", "LP", 100, "APC", None, 100), "same party", True),
             "no Side A lead chosen": ((None, "NNPP", 100, "APC", None, 100), "lead party", True),
             "Side B lead already on Side A": (("LP", "NNPP", 100, "NNPP", None, 100), "already on Side A", False),
             "Side B partner already on Side A": (("LP", "NNPP", 100, "APC", "LP", 100), "already on Side A", False),
             "Side B partner = Side B lead": (("LP", "NNPP", 100, "APC", "APC", 100), "same", False),
             "no Side B lead chosen": (("LP", "NNPP", 100, None, None, 100), "main party", False)}
    bad, seen = [], {}
    for name, (c, word, a_bad) in cases.items():
        f = ", ".join(cfg_filters(c))
        r = dax_file(f'EVALUATE CALCULATETABLE(ROW("msgA", [Side A message], "msgB", [Side B message], '
                     '"stM", [Side A states at 25% (merge)], "natA", [Side A national votes], "shA", [Side A national share (merge)], '
                     '"stA", [Side A states at 25% (head to head)], "natB", [Side B national votes], "verdict", [Head to head verdict], '
                     '"sent", [Head to head sentence], "ledA", [States led by Side A], '
                     '"sim_sec", CALCULATE([Units secured (national)], coal_switch[Value] = "On"), '
                     '"sim_verdict", CALCULATE([Verdict], coal_switch[Value] = "On"), '
                     '"sim_result", CALCULATE([Result sentence], coal_switch[Value] = "On"), '
                     '"sim_share", CALCULATE([Scenario share], coal_switch[Value] = "On", dim_state[state_pcode] = "NG001"), '
                     '"sim_rival", CALCULATE([Leading rival], coal_switch[Value] = "On"), '
                     '"sim_msg", CALCULATE([Simulator coalition sentence], coal_switch[Value] = "On")), '
                     f'{f}, TREATAS({{"APC"}}, dim_party[party]))')[0]
        seen[name] = r
        blank_keys = ["stA", "natB", "verdict", "sent", "ledA", "sim_sec", "sim_verdict", "sim_result", "sim_share", "sim_rival"]
        if a_bad:
            blank_keys += ["stM", "natA", "shA"]
        msg = r["msgA"] if a_bad else r["msgB"]
        if any(r[k] is not None for k in blank_keys) or word not in (msg or "") or "not complete" not in (r["sim_msg"] or ""):
            bad.append(name)
    check("invalid coalition choices (lead = partner, a party on both sides, partner = lead, nothing chosen) -> blank "
          "figures on both coalition pages and in the simulator with the switch On, and a message saying what to change",
          not bad, {"failed": bad, "seen": seen})


def coalition_switch_off_check():
    """Switch Off (explicitly, with a coalition picked) = no coalition filter at all, for every candidate."""
    st = setting(t=10, S=4, SE=-6, NW=3)
    meas = ('"sec", [Units secured (national)], "tip", [Tipping-point P-code], "nat", [Scenario national votes], '
            '"lead", [Leading rival], "lead_votes", [Leading rival votes], "lead25", [Leading rival units at 25%], '
            '"verdict", [Verdict], "result", [Result sentence], "decide", [Deciding state sentence], '
            '"inforce", [Assumptions in force], "share", [Scenario national share]')
    base = dax(f'EVALUATE CALCULATETABLE(SUMMARIZECOLUMNS(dim_party[party], {meas}), {filters(st)})')
    off = dax_file(f'EVALUATE CALCULATETABLE(SUMMARIZECOLUMNS(dim_party[party], {meas}), {filters(st)}, '
                   f'TREATAS({{"Off"}}, coal_switch[Value]), {", ".join(cfg_filters(("PDP", "LP", 35, "APC", "NNPP", 70)))})')
    a = {r["party"]: r for r in base if r["party"] in PARTIES}
    b = {r["party"]: r for r in off if r["party"] in PARTIES}
    check("switch Off with a coalition picked = no coalition at all: every engine measure identical for every candidate "
          "(turnout +10, national +4, SE -6, NW +3)", a == b and len(a) == 4, {"no_coalition": a, "switch_off": b})


def coalition_boundary_search():
    """Exact search (whole numbers): can any reachable simulator setting with the switch On put Side A exactly on 25% or
    20% in a state? p1 = C (100 + k) / (100 W + C k) with C, W the x100 whole numbers; a hit needs 200 p1 to be a whole
    number m0 with 50 - m0 or 40 - m0 within the reachable total swing (-80..80 half-points)."""
    import numpy as np
    ks = np.arange(-50, 51, dtype=np.int64)
    hits, combos = [], 0
    for al in PARTIES:
        for ap in PARTIES:
            if ap == al:
                continue
            others = [x for x in PARTIES if x not in (al, ap)]
            for s in VALID:
                for fa in range(0, 101, 5):
                    C = 100 * VOTES[(s, al)] + fa * VOTES[(s, ap)]
                    WA = 100 * VALID[s] - (100 - fa) * VOTES[(s, ap)]
                    Ws = {WA} | {WA - (100 - fb) * VOTES[(s, bp)] for bp in others for fb in range(0, 101, 5)}
                    for W in Ws:
                        combos += len(ks)
                        num = 200 * C * (100 + ks)
                        den = 100 * W + C * ks
                        ok = den > 0
                        idx = np.nonzero(ok & (num % np.where(ok, den, 1) == 0))[0]
                        for i in idx:
                            m0 = int(num[i] // den[i])
                            if any(-80 <= target - m0 <= 80 for target in (50, 40)):
                                hits.append({"lead": al, "partner": ap, "follow": fa, "state": s, "W": int(W),
                                             "turnout": int(ks[i]), "p1_x200": m0})
    # 2026-11-18: exact hits exist (6), so the model compares with a margin of 1E-12 (decision log). Two checks replace
    # "no hits": (1) every reachable share that is NOT exactly on a line is further from it than 100 x the margin;
    # (2) at every exact hit the model shows the exact-line answer (label, order, colour; 0 votes needed at 25%).
    gap = smallest_gap()
    check("margin proof: the smallest non-zero distance between any reachable share (single candidate and every coalition "
          "setting, every turnout and swing step) and the 25% or 20% line is more than 100 x the 1E-12 margin",
          gap["gap"] > 100 * MARGIN, {**gap, "margin": MARGIN, "combinations_turnout_level": combos})
    bad, tested = [], []
    for h in hits:
        al, ap, fa, s, W, k, m0 = h["lead"], h["partner"], h["follow"], h["state"], h["W"], h["turnout"], h["p1_x200"]
        others = [x for x in PARTIES if x not in (al, ap)]
        WA = 100 * VALID[s] - (100 - fa) * VOTES[(s, ap)]
        sideb = [(bp, fb) for bp in others for fb in range(0, 101, 5) if WA - (100 - fb) * VOTES[(s, bp)] == W]
        bp, fb = sideb[0] if sideb else (None, 100)
        bl = next(x for x in others if x != bp)
        for target in (50, 40):
            sw = target - m0   # half-points of total swing; put it all on the national slider when it fits
            if not -40 <= sw <= 40:
                continue
            want = ("Secured", 1, "#0072B2") if target == 50 else ("Within reach", 2, "#D55E00")
            f = cfg_filters((al, ap, fa, bl, bp, fb)) + ['TREATAS({"On"}, coal_switch[Value])', f'TREATAS({{{k}}}, param_turnout[Value])',
                 f'TREATAS({{{sw / 2}}}, param_swing_national[Value])', f'TREATAS({{"{s}"}}, dim_state[state_pcode])']
            g = dax_file(f'EVALUATE CALCULATETABLE(ROW("label", [Scenario label], "order", [Scenario label order], '
                         f'"colour", [Scenario label colour], "need", [Votes needed]), {", ".join(f)})')[0]
            row = {"setting": [al, ap, fa, bl, bp, fb, s, k, sw / 2], "line": target / 200, "model": g}
            tested.append(row)
            if (g["label"], g["order"], g["colour"]) != want or (target == 50 and g["need"] != 0):
                bad.append(row)
    check("exact hits, switch On: at every reachable setting that puts the coalition exactly on 25% or 20%, the model "
          "shows the at-the-line answer (Secured / Within reach, order, colour; 0 votes needed at 25%)",
          bool(tested) and not bad, {"hit_count": len(hits), "tested": tested, "wrong": bad})


MARGIN = 1E-12   # build_pbip.py Q / F


def smallest_gap():
    """Exact: p1 x 200 = num / den (whole numbers), total swing s in half-points (-80..80), so the distance of the
    capped-free share from a line T is |num/den + s - T| / 200; its smallest non-zero value over every setting."""
    import numpy as np
    ks = np.arange(-50, 51, dtype=np.int64)
    best = {"gap": 1.0, "where": None}

    def scan(C, W, tag):
        num = 200 * C * (100 + ks); den = 100 * W + C * ks
        ok = den > 0
        num, den, kk = num[ok], den[ok], ks[ok]
        r, q = num % den, num // den
        for T in (50, 40):
            for s_needed, gapnum in ((T - q, r), (T - q - 1, den - r)):
                m = (r != 0) & (np.abs(s_needed) <= 80)
                if m.any():
                    g = gapnum[m] / den[m] / 200.0
                    i = int(np.argmin(g))
                    if g[i] < best["gap"]:
                        best.update(gap=float(g[i]), where={"case": tag, "turnout": int(kk[m][i]), "line": T / 200})
    for al in PARTIES:
        for s in VALID:
            scan(100 * VOTES[(s, al)], 100 * VALID[s], ["single", al, s])
            for ap in PARTIES:
                if ap == al:
                    continue
                others = [x for x in PARTIES if x not in (al, ap)]
                for fa in range(0, 101, 5):
                    C = 100 * VOTES[(s, al)] + fa * VOTES[(s, ap)]
                    WA = 100 * VALID[s] - (100 - fa) * VOTES[(s, ap)]
                    for W in {WA} | {WA - (100 - fb) * VOTES[(s, bp)] for bp in others for fb in range(0, 101, 5)}:
                        scan(C, W, ["coalition", al, ap, fa, s, int(W)])
    return best


def coalition_checks():
    coalition_pages_check()
    coalition_simulator_check()
    coalition_invalid_check()
    coalition_switch_off_check()
    coalition_boundary_search()


PARTS = {"core": lambda: core_checks(), "pages": coalition_pages_check, "simulator": coalition_simulator_check,
         "invalid": coalition_invalid_check, "switch_off": coalition_switch_off_check, "boundary": coalition_boundary_search}
PART_DIR = REP / "phase4_parts"


def main():
    args = sys.argv[1:]
    if args[:1] == ["--combine"]:
        return combine()
    part = args[1] if args[:1] == ["--part"] and len(args) > 1 else "all"
    if part != "all" and part not in PARTS:
        sys.exit(f"unknown part {part!r}; choose from {', '.join(PARTS)}")
    OUT["part"] = part
    OUT["path"] = REP / "phase4_validation.json" if part == "all" else PART_DIR / f"{part}.json"
    for f in (PARTS.values() if part == "all" else [PARTS[part]]):
        f()
    out = write_out(True)
    label = "gate" if part == "all" else "part " + part
    print(f"\n  {label} {'PASSED' if not out['failed'] else 'FAILED'}: {out['summary']}")
    return 1 if out["failed"] else 0


def combine():
    """Join the part files (each must be complete) into reports/phase4_validation.json, in the full-run order."""
    missing, parts = [], []
    for name in PARTS:
        f = PART_DIR / f"{name}.json"
        d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
        if not d or not d.get("complete"):
            missing.append(name)
        else:
            parts.append(d)
    if missing:
        sys.exit(f"cannot combine: part(s) missing or incomplete: {', '.join(missing)}")
    checks[:] = [c for d in parts for c in d["checks"]]
    OUT["part"], OUT["path"] = "all (combined from reports/phase4_parts/)", REP / "phase4_validation.json"
    out = write_out(True)
    print(f"  combined {len(parts)} parts: gate {'PASSED' if out['gate_passed'] else 'FAILED'}: {out['summary']}")
    return 0 if out["gate_passed"] else 1


def core_checks():
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

        # rivals, most votes and verdict
        rows = dax(f'EVALUATE CALCULATETABLE(SUMMARIZECOLUMNS(dim_party[party], param_rule[Value], '
                   f'"nat", [Scenario national votes], "share", [Scenario national share], "lead", [Leading rival], '
                   f'"lead_votes", [Leading rival votes], "lead_25", [Leading rival units at 25%], '
                   f'"most", [Has most votes], "verdict", [Verdict]), {filters(st)})')
        vd = []
        for r in rows:
            if r["party"] not in PARTIES:
                continue
            ref = rivals(r["party"], st, int(r["Value"]))
            same = (r["lead"], r["lead_25"], r["most"], r["verdict"]) == (ref["lead"], ref["lead_25"], ref["most"], ref["verdict"]) \
                and abs(r["nat"] - ref["nat"]) <= 1e-6 * max(1, ref["nat"]) \
                and abs(r["lead_votes"] - ref["lead_votes"]) <= 1e-6 * max(1, ref["lead_votes"]) \
                and abs(r["share"] - ref["share"]) <= 1e-9
            if not same:
                vd.append({"party": r["party"], "N": r["Value"], "model": {k: r[k] for k in ref}, "reference": ref})
        check(f"[{label}] rivals, most votes and verdict = reference (N = 24 and 25)",
              len([r for r in rows if r["party"] in PARTIES]) == 8 and not vd,
              {"differences": vd[:4], "sample_APC_N24": rivals("APC", st, 24)})

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

    # coalitions (docs/methodology.md "Coalitions", added 2026-11-16) run as their own parts (see PARTS)


if __name__ == "__main__":
    sys.exit(main())
