"""Freeze the data vintage for a GitHub release (Phase 7).

Writes release/naija-elections-data-<vintage>.zip with:
  staging/      the staging tables the Power BI model reads (data/staging/*.csv), EXCEPT Mundx-derived files
                (no licence to redistribute: open questions 3 and 15)
  staging/manifest.json
  reference/    data/reference/*.csv (hand-made or sourced reference tables; provenance in registers/sources.md)
  SHA256SUMS    one line per file
  VINTAGE.md    what this is, git commit, build date, what it does not claim
and release/SHA256SUMS for the zip and the .pbix (if present).

A frozen vintage is never edited: corrections ship as a new vintage stating what changed and why.

  uv run python -I scripts/build_release.py --vintage 2026-11-20
"""
import argparse
import hashlib
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "release"
EXCLUDE = ("mundx",)   # never redistributed


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vintage", required=True, help="vintage label, e.g. 2026-11-20")
    a = ap.parse_args()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "data", "scripts"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    files = []
    for p in sorted((ROOT / "data" / "staging").glob("*.csv")):
        if not any(x in p.name.lower() for x in EXCLUDE):
            files.append((f"staging/{p.name}", p))
    files.append(("staging/manifest.json", ROOT / "data" / "staging" / "manifest.json"))
    files += [(f"reference/{p.name}", p) for p in sorted((ROOT / "data" / "reference").glob("*.csv"))]
    left_out = sorted(p.name for p in (ROOT / "data" / "staging").glob("*.csv") if any(x in p.name.lower() for x in EXCLUDE))

    OUT.mkdir(exist_ok=True)
    zp = OUT / f"naija-elections-data-{a.vintage}.zip"
    if zp.exists():
        print(f"{zp} exists: a frozen vintage is never overwritten; use a new --vintage label.", file=sys.stderr)
        return 1
    sums = "".join(f"{sha(p)}  {arc}\n" for arc, p in files)
    rows = "".join(f"| `{arc}` | {sum(1 for _ in p.open(encoding='utf-8')) - 1 if p.suffix == '.csv' else '-'} |\n"
                   for arc, p in files)
    vintage_md = f"""# Data vintage {a.vintage}

Frozen copy of the tables behind the Power BI report `NaijaElectionsGap.pbix` released with it.
Built {date.today().isoformat()} by `scripts/build_release.py` from git commit `{commit}`{" (with uncommitted data/script changes!)" if dirty else ""}.
Source, access date, licence and transform of every table: `registers/sources.md`, `staging/manifest.json`,
`docs/data-profile.md` in https://github.com/batestguy/powerbi-naija-2027-elections-gap

Left out on purpose: {", ".join(left_out) or "none"} (Mundx data: no licence to redistribute).

## Licence and attribution
The tables are facts (vote counts, registered voters, zones, codes) compiled from the sources listed in
`registers/sources.md`; each source keeps its own terms (e.g. Wikipedia tables CC BY-SA 4.0; news pages and the
AGADA-BI table state no licence). Credit those sources when you reuse the data. One of the five result copies
(Vanguard) was fetched once with a browser identity after the site refused a scripted request; its terms were not
checked. The report file also embeds Wikimedia Commons photos (CC BY-SA 4.0 / CC BY 4.0 / CC0 / public domain;
credits on its Data sources page) and party logos (trademarks, identification only).

| File | Rows (CSV, excl. header; comment lines count) |
|---|---|
{rows}
## What this does not claim
- The 2023 state results are a reconciliation of five copies of INEC's declaration, not INEC's own state collation
  sheets (Form EC8D is not public). Three cells were decided by hand (`reference/result_cell_decisions.csv`).
- Registered voters come from Wikipedia state pages and sum to 120,281 fewer than INEC's national figure.
- "Party now" and coalition names come from dated news reports, not an official INEC list.
- This vintage never changes. Corrections ship as a new vintage stating what changed and why.
"""
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, p in files:
            z.write(p, arc)
        z.writestr("SHA256SUMS", sums)
        z.writestr("VINTAGE.md", vintage_md)
    lines = [f"{sha(zp)}  {zp.name}\n"]
    pbix = OUT / "NaijaElectionsGap.pbix"
    if pbix.exists():
        lines.append(f"{sha(pbix)}  {pbix.name}\n")
    (OUT / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")
    print(f"wrote {zp.name}: {len(files)} files; left out: {left_out}; commit {commit[:7]}{' DIRTY' if dirty else ''}")
    print("".join(lines), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
