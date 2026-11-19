"""Engine timings for the coalition measures (review 2026-11-18, SHOULD-FIX 2: no number without an artifact).

Times each query inside one engine connection (scripts/pbi_engine.ps1 -Action Time): cache cleared, cold run, warm
run, three rounds; reports the medians and the engine's memory after. Setting: the saved preset, NDC (Obi (LP) +
Kwankwaso (NNPP), 100% follow) vs Tinubu (APC) alone, coalition switch On; and the same with the switch Off.
Engine time only: Desktop's drawing of the visuals is extra and not measured.

Requires Desktop open on pbip/NaijaElectionsGap.pbip with data refreshed (scripts/pbi_reopen.ps1).
Usage (repo root):  uv run python -I scripts/time_engine.py      -> reports/engine_timings.json
"""
import json, statistics, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))   # -I leaves the script folder off the path
from build_stamp import build_stamp  # noqa: E402

PS = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "pbi_engine.ps1")]
PRESET = ('coal_a_lead[party] = "LP", coal_a_partner[party] = "NNPP", coal_b_lead[party] = "APC", '
          'coal_b_partner[party] = "NONE", param_follow_a[Value] = 100, param_follow_b[Value] = 100')
SWITCH = {"On": 'coal_switch[Value] = "On"', "Off": 'coal_switch[Value] = "Off"'}
QUERIES = {
    "Deciding state sentence": 'ROW("d", [Deciding state sentence])',
    "Verdict": 'ROW("v", [Verdict])',
    "Result sentence": 'ROW("r", [Result sentence])',
    "Leading rival units at 25%": 'ROW("n", [Leading rival units at 25%])',
    "Head to head verdict + sentence": 'ROW("v", [Head to head verdict], "s", [Head to head sentence])',
    "per-state engine, 37 states": 'SUMMARIZECOLUMNS(dim_state[state_pcode], "p", [Scenario share], '
                                   '"n", [Votes needed], "s", [Votes to spare])',
}


def timed(q):
    with tempfile.NamedTemporaryFile("w", suffix=".dax", delete=False, encoding="utf-8") as f:
        f.write(q)
    try:
        r = subprocess.run(PS + ["-Action", "Time", "-Repeat", "3", "-DaxFile", f.name],
                           capture_output=True, text=True, encoding="utf-8", timeout=900)
    finally:
        Path(f.name).unlink(missing_ok=True)
    if r.returncode:
        raise RuntimeError(r.stderr or r.stdout)
    return json.loads(r.stdout.lstrip("﻿"))


def main():
    out = {"built_by": "scripts/time_engine.py", "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "setting": f"{PRESET}; switch On / Off", "build_stamp": build_stamp(), "results": {}}
    for sw, flt in SWITCH.items():
        for name, q in QUERIES.items():
            raw = timed(f"EVALUATE CALCULATETABLE({q}, {PRESET}, {flt})")
            row = {"median_cold_s": round(statistics.median(raw["cold_s"]), 3),
                   "median_warm_s": round(statistics.median(raw["warm_s"]), 3), "runs": raw}
            out["results"][f"switch {sw}: {name}"] = row
            print(f"  switch {sw:3} {name:34} cold {row['median_cold_s']:6.3f} s   warm {row['median_warm_s']:6.3f} s   "
                  f"engine {raw['engine_mb']} MB", flush=True)
    out["engine_mb_after"] = raw["engine_mb"]
    (ROOT / "reports" / "engine_timings.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
