"""Phase 2 exit checks. Reads data/staging/*, pbip/assets/*, reports/unmatched_keys.csv and writes
reports/phase2_validation.json (one entry per check: pass/fail + evidence) and
reports/mundx_state_accuracy.csv (ratios only - Mundx absolute figures are not redistributed).

Exits 1 if any *gate* check fails. Checks marked "info" record a finding but do not gate.

Usage (repo root):  .venv/Scripts/python.exe -I scripts/validate_phase2.py
"""
import csv, json, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STG, REP, ASSETS = ROOT / "data" / "staging", ROOT / "reports", ROOT / "pbip" / "assets"
REF = ROOT / "data" / "reference"
PARTIES = ["APC", "PDP", "LP", "NNPP"]
EXPECTED_T25 = {"APC": 29, "PDP": 21, "LP": 16, "NNPP": 1}   # PLAN Phase 2 / INEC declaration
INEC_REGISTERED_NATIONAL = 93_469_008                          # INEC 2023 register, as cited in PLAN
TURNOUT_TOL_PP = 0.5                                           # infobox vs table turnout, percentage points

checks = []


def check(name, ok, evidence, gate=True):
    checks.append({"check": name, "status": "pass" if ok else ("fail" if gate else "flag"),
                   "gate": gate, "evidence": evidence})


def info(name, evidence):
    """A finding recorded for the reader; it cannot fail, so it is not counted as a pass."""
    checks.append({"check": name, "status": "info", "gate": False, "evidence": evidence})


def read(name):
    with open(STG / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    return None if v in ("", None) else float(v)


def main():
    dim = read("dim_state.csv")
    zones = read("dim_zone.csv")
    res = read("fact_result_2023.csv")
    turn = read("fact_turnout_2023.csv")
    nat = {r["source"]: r for r in read("national_totals_reported.csv")}
    mundx = read("mundx_state_rollup.csv") if (STG / "mundx_state_rollup.csv").exists() else []

    keys = {r["state_pcode"] for r in dim}

    # 1. Shape of the dimension tables
    check("dim_state: 37 rows, unique keys", len(dim) == 37 and len(keys) == 37, {"rows": len(dim), "unique": len(keys)})
    check("dim_state: exactly one FCT", sum(r["is_fct"] == "1" for r in dim) == 1,
          {"fct": [r["state_name"] for r in dim if r["is_fct"] == "1"]})
    zc = Counter(r["zone_code"] for r in dim)
    check("zones: 6 zones, counts agree with dim_zone, sum 37",
          len(zones) == 6 and all(zc[z["zone_code"]] == int(z["state_count"]) for z in zones) and sum(zc.values()) == 37,
          {"from_dim_state": dict(zc), "dim_zone": {z["zone_code"]: int(z["state_count"]) for z in zones}})
    check("dim_state: no nulls", all(all(v != "" for v in r.values()) for r in dim), {})

    # 2. Results fact: grain, nulls, duplicates
    grain = Counter((r["state_pcode"], r["party"]) for r in res)
    check("fact_result: 185 rows = 37 states x 5 (APC, PDP, LP, NNPP, OTHERS), no duplicates",
          len(res) == 185 and max(grain.values()) == 1 and {k for k, _ in grain} == keys,
          {"rows": len(res), "max_per_grain": max(grain.values()), "parties": sorted({p for _, p in grain})})
    check("fact_result: no null votes", all(r["votes"] != "" for r in res),
          {"null_votes": [(r["state_pcode"], r["party"]) for r in res if r["votes"] == ""]})

    votes = defaultdict(dict)
    for r in res:
        votes[r["state_pcode"]][r["party"]] = int(r["votes"])
    tv = {r["state_pcode"]: int(r["total_valid"]) for r in turn}

    # 3. INEC national declaration (hand-transcribed reference) is self-consistent
    with open(REF / "inec_national_declaration_2023.csv", encoding="utf-8") as f:
        ref = list(csv.DictReader(l for l in f if not l.startswith("#")))
    cand = {r["party"]: int(r["value"]) for r in ref if r["measure"] == "candidate_votes"}
    inec = {r["measure"]: int(r["value"]) for r in ref if r["measure"] != "candidate_votes"}
    check("INEC reference: 18 candidates sum to valid votes; valid + rejected = cast",
          len(cand) == 18 and sum(cand.values()) == inec["valid_votes"]
          and inec["valid_votes"] + inec["rejected_votes"] == inec["votes_cast"],
          {"candidates": len(cand), "candidate_sum": sum(cand.values()), **inec})
    inec_others = sum(v for p, v in cand.items() if p not in PARTIES)

    # 4. Reconciled state sums = INEC national declaration, exactly (four main parties)
    sums = {p: sum(votes[k][p] for k in votes) for p in PARTIES + ["OTHERS"]}
    sums["total_valid"] = sum(tv.values())
    diff4 = {p: sums[p] - cand[p] for p in PARTIES if sums[p] != cand[p]}
    check("reconciled state sums = INEC national declaration (APC, PDP, LP, NNPP)", not diff4,
          {"state_sums": {p: sums[p] for p in PARTIES}, "inec": {p: cand[p] for p in PARTIES}, "differences": diff4})
    check("OTHERS and total valid: state sums = INEC national",
          sums["OTHERS"] == inec_others and sums["total_valid"] == inec["valid_votes"],
          {"others_state_sum": sums["OTHERS"], "others_inec": inec_others, "others_diff": sums["OTHERS"] - inec_others,
           "total_valid_state_sum": sums["total_valid"], "total_valid_inec": inec["valid_votes"],
           "total_valid_diff": sums["total_valid"] - inec["valid_votes"],
           "note": "OTHERS per state exists only in Wikipedia and AGADA (identical); no third copy to settle the gap"},
          gate=False)
    w = nat["wikipedia_main_total_row"]
    check("Wikipedia's own national total row = INEC declaration",
          all(int(w[p]) == cand[p] for p in PARTIES) and int(w["total_valid"]) == inec["valid_votes"],
          {"wikipedia_total_row": {p: int(w[p]) for p in PARTIES + ["total_valid"]}})
    wsum = {p: sum(int(r["votes_wikipedia"]) for r in res if r["party"] == p) - cand[p] for p in PARTIES}
    check("Wikipedia By-state rows (unreconciled) sum to INEC national", not any(wsum.values()),
          {"differences": wsum, "note": "why reconciliation exists"}, gate=False)
    tvw = {r["state_pcode"]: int(r["total_valid_wikipedia"]) for r in turn}
    tva = {r["state_pcode"]: int(r["total_valid_agada"]) for r in turn if r["total_valid_agada"]}
    info("derived total valid per state vs Wikipedia and AGADA reported totals", {"differs_from_wikipedia": {k: tv[k] - tvw[k] for k in tv if tv[k] != tvw[k]},
           "differs_from_agada": {k: tv[k] - tva[k] for k in tva if tv[k] != tva[k]}})

    # 5. 25% rule count, recomputed from reconciled votes (not from the reported flag)
    t25 = {p: sum(votes[k][p] * 4 >= tv[k] for k in votes) for p in PARTIES}
    flag = {p: sum(r["threshold_flag_reported_wikipedia"] == "1" for r in res if r["party"] == p) for p in PARTIES}
    check("25% count recomputed from votes = 29/21/16/1", t25 == EXPECTED_T25, {"recomputed": t25, "expected": EXPECTED_T25})
    check("25% count recomputed = reported flags in Wikipedia table", t25 == flag, {"recomputed": t25, "reported_flags": flag})
    kano = {r["party"]: int(r["votes"]) for r in res if r["state_pcode"] == "NG020"}
    alt = 517_341 / (tv["NG020"] - kano["APC"] + 517_341)
    check("Kano APC decision does not change the 25% outcome", (kano["APC"] * 4 >= tv["NG020"]) == (alt >= 0.25),
          {"chosen_share": round(kano["APC"] / tv["NG020"], 4), "alternative_517341_share": round(alt, 4)})
    near = sorted((round(100 * votes[k][p] / tv[k], 3), k, p, round(votes[k][p] - tv[k] / 4, 1))
                  for k in votes for p in PARTIES if abs(votes[k][p] / tv[k] - 0.25) < 0.005)
    info("states within 0.5 pp of 25% (rounding risk)", {"cases [pct, state, party, votes above(+)/below(-) 25%]": near})

    # 6. Turnout table
    check("fact_turnout: 37 rows, keys match dim_state", len(turn) == 37 and {r["state_pcode"] for r in turn} == keys,
          {"rows": len(turn)})
    check("registered voters present for all 37", all(r["registered"] != "" for r in turn),
          {"missing": [r["state_pcode"] for r in turn if r["registered"] == ""]})
    reg = sum(int(r["registered"]) for r in turn if r["registered"])
    check("registered voters: state sum = INEC national 93,469,008", reg == INEC_REGISTERED_NATIONAL,
          {"state_sum": reg, "inec_national": INEC_REGISTERED_NATIONAL, "difference": reg - INEC_REGISTERED_NATIONAL}, gate=False)
    acc = sum(r["accredited"] != "" for r in turn)
    check("accredited voters per state available", acc == 37, {"states_with_accredited": acc}, gate=False)
    rj = sum(r["rejected"] != "" for r in turn)
    check("rejected / total cast per state available", rj == 37,
          {"states_with_rejected": rj, "note": "total_cast_implied_from_turnout is an inference (registered x turnout%), not a published figure"},
          gate=False)
    tdis = []
    for r in turn:
        a, b = num(r["turnout_pct_reported"]), num(r["infobox_turnout_pct"])
        if a is not None and b is not None and abs(a - b) > TURNOUT_TOL_PP:
            tdis.append({"state_pcode": r["state_pcode"], "table": a, "infobox": b})
    check(f"turnout: table vs state-page infobox within {TURNOUT_TOL_PP} pp", not tdis,
          {"compared": sum(num(r["infobox_turnout_pct"]) is not None for r in turn), "disagreements": tdis}, gate=False)
    ebox = [{"state_pcode": r["state_pcode"], "table": int(r["total_valid"]), "state_page": int(r["ebox_total_valid"])}
            for r in turn if r["ebox_total_valid"] and int(r["ebox_total_valid"]) != int(r["total_valid"])]
    check("total valid: main table vs state-page result box", not ebox,
          {"compared": sum(r["ebox_total_valid"] != "" for r in turn), "disagreements": ebox}, gate=False)

    # 7. Reconciliation across the five copies
    with open(REP / "result_reconciliation.csv", encoding="utf-8") as f:
        rec = list(csv.DictReader(f))
    srcs = ["wikipedia", "agada", "nigerialawyer", "thisday", "vanguard"]
    chosen_ok = [r for r in rec if r["chosen"] not in {r[s] for s in srcs if r[s]}]
    by_rule = Counter(r["rule"] for r in rec)
    check("reconciliation: every chosen value is printed by at least one copy", not chosen_ok,
          {"violations": chosen_ok, "non_unanimous_cells": dict(by_rule)})
    fact_match = [r for r in rec if votes[r["state_pcode"]][r["party"]] != int(r["chosen"])]
    check("reconciliation: fact_result carries the reconciled values", not fact_match, {"mismatches": fact_match})
    info("reconciliation: hand decisions (ties and overrides)", {"decisions": [{k: r[k] for k in ("state_pcode", "party", "chosen", "reason")} for r in rec if r["rule"] == "decision"]})
    dissent = Counter(s for r in rec for s in srcs if r[s] and r[s] != r["chosen"])
    info("reconciliation: cells where each copy differs from the chosen value", dict(dissent))

    # 8. Join-key gate
    with open(REP / "unmatched_keys.csv", encoding="utf-8") as f:
        unmatched = list(csv.DictReader(f))
    check("reports/unmatched_keys.csv is empty", not unmatched, {"rows": len(unmatched)})
    for fname, obj in (("nga_states.topo.json", "states"), ("nga_tiles.topo.json", "tiles")):
        tj = json.loads((ASSETS / fname).read_text(encoding="utf-8"))
        g = {x["properties"]["state_pcode"] for x in tj["objects"][obj]["geometries"]}
        check(f"geometry {fname}: keys = dim_state keys", g == keys,
              {"features": len(tj["objects"][obj]["geometries"]), "missing": sorted(keys - g), "extra": sorted(g - keys)})
    gm = json.loads((ASSETS / "geometry_manifest.json").read_text(encoding="utf-8"))["outputs"][0]
    check("geometry (as reported by build_geometry.py manifest): no invalid or empty shapes, no overlaps",
          not gm["invalid_after_simplify"] and not gm["empty_after_simplify"] and gm["pairwise_overlap_area_deg2"] == 0,
          {k: gm[k] for k in ("invalid_after_simplify_before_repair", "invalid_after_simplify", "empty_after_simplify",
                              "pairwise_overlap_area_deg2", "max_area_change_ratio", "bytes")})
    if mundx:
        check("mundx rollup keys = dim_state keys", {r["state_pcode"] for r in mundx} == keys, {"rows": len(mundx)}, gate=False)

    # 9. Mundx accuracy report - ratios only
    acc_rows = []
    for r in sorted(mundx, key=lambda r: r["state_pcode"]):
        k = r["state_pcode"]
        row = {"state_pcode": k, "state_name": next(d["state_name"] for d in dim if d["state_pcode"] == k)}
        for p in PARTIES:
            row[f"{p.lower()}_ratio"] = round(int(r[p.lower()]) / votes[k][p], 4) if votes[k][p] else ""
        official4 = sum(votes[k][p] for p in PARTIES)
        row["four_party_ratio"] = round(int(r["four_party"]) / official4, 4)
        row["polling_unit_coverage"] = round(int(r["polling_units_included"]) / int(r["inventory"]), 4) if int(r["inventory"]) else ""
        acc_rows.append(row)
    if acc_rows:
        with open(REP / "mundx_state_accuracy.csv", "w", encoding="utf-8", newline="\n") as f:
            f.write("# Mundx four-party rollup / reconciled state votes (data/staging/fact_result_2023.csv). Ratios only.\n")
            wr = csv.DictWriter(f, fieldnames=list(acc_rows[0]), lineterminator="\n")
            wr.writeheader(); wr.writerows(acc_rows)
        r4 = sorted(x["four_party_ratio"] for x in acc_rows)
        info("mundx four-party accuracy (info)", {"min": r4[0], "median": r4[len(r4) // 2], "max": r4[-1],
               "states_within_2pct": sum(abs(x - 1) <= 0.02 for x in r4)})

    failed = [c["check"] for c in checks if c["status"] == "fail"]
    flagged = [c["check"] for c in checks if c["status"] == "flag"]
    out = {"built_by": "scripts/validate_phase2.py", "gate_passed": not failed,
           "summary": {"checks": len(checks), "pass": sum(c["status"] == "pass" for c in checks),
                       "fail": len(failed), "flag": len(flagged),
                       "info": sum(c["status"] == "info" for c in checks)},
           "failed": failed, "flagged": flagged, "checks": checks}
    (REP / "phase2_validation.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    for c in checks:
        print(f"  [{c['status'].upper():4}] {c['check']}")
    print(f"\n  gate {'PASSED' if not failed else 'FAILED'}: {out['summary']}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
