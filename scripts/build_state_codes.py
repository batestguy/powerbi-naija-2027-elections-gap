"""State abbreviations: ISO 3166-2:NG subdivision codes without the "NG-" prefix (user request 2026-11-14).

Source: the Wikipedia page "ISO 3166-2:NG" (which lists the ISO codes), fetched once through the MediaWiki API and pinned
to its revision id. The raw response + manifest go to data/raw/iso3166_ng/<ACCESS_DATE>/; the parsed table goes to
data/reference/state_codes_iso3166.csv (37 rows, matched to data/staging/dim_state.csv by name). Fails unless all 37
codes are unique, two letters, and every dim_state row is matched exactly once.

Usage (repo root):  uv run python -I scripts/build_state_codes.py [--refetch]
Then re-run scripts/build_staging.py, which joins state_code into dim_state.
"""
import csv, hashlib, json, re, sys, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACCESS_DATE = "2026-11-14"
RAW = ROOT / "data" / "raw" / "iso3166_ng" / ACCESS_DATE
OUT = ROOT / "data" / "reference" / "state_codes_iso3166.csv"
UA = {"User-Agent": "NaijaElectionsGap-report/1.0 (open-data project)"}
PAGE = "ISO_3166-2:NG"
# the only name that differs between the ISO list and dim_state (HDX names)
NAME_FIX = {"Abuja Federal Capital Territory": "Federal Capital Territory"}


def fetch():
    RAW.mkdir(parents=True, exist_ok=True)
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": PAGE, "prop": "wikitext|revid", "format": "json"})
    body = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
    (RAW / "iso_3166-2_NG.parse.json").write_bytes(body)
    revid = json.loads(body)["parse"]["revid"]
    man = {"source": f"https://en.wikipedia.org/wiki/{PAGE}", "api_url": url, "revid": revid,
           "pinned_url": f"https://en.wikipedia.org/w/index.php?title={PAGE}&oldid={revid}",
           "licence": "CC BY-SA 4.0 (Wikipedia text); the codes themselves are ISO 3166-2 identifiers",
           "accessed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "files": [{"file": "iso_3166-2_NG.parse.json", "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}]}
    (RAW / "manifest.json").write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")


def main():
    if "--refetch" in sys.argv or not (RAW / "manifest.json").exists():
        fetch()
    man = json.loads((RAW / "manifest.json").read_text(encoding="utf-8"))
    body = (RAW / man["files"][0]["file"]).read_bytes()
    if hashlib.sha256(body).hexdigest() != man["files"][0]["sha256"]:
        sys.exit("raw file does not match its manifest")
    wt = json.loads(body)["parse"]["wikitext"]["*"]
    # table rows: | {{mono|NG-AB}} \n | [[Abia State|Abia]]
    rows = re.findall(r"\|\s*\{\{mono\|NG-([A-Z]{2})\}\}\s*\n\|\s*\[\[[^|\]]+\|([^\]]+)\]\]", wt)
    codes = {NAME_FIX.get(n.strip(), n.strip()): c for c, n in rows}
    with open(ROOT / "data" / "staging" / "dim_state.csv", encoding="utf-8") as f:
        dim = list(csv.DictReader(f))
    missing = [r["state_name"] for r in dim if r["state_name"] not in codes]
    extra = sorted(set(codes) - {r["state_name"] for r in dim})
    if len(rows) != 37 or len(set(codes.values())) != 37 or missing or extra:
        sys.exit(f"ISO table: {len(rows)} rows, {len(set(codes.values()))} unique codes; unmatched dim_state {missing}; "
                 f"unmatched ISO {extra}")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# ISO 3166-2:NG codes without the 'NG-' prefix. Source: {man['pinned_url']} (accessed "
                f"{man['accessed_utc'][:10]}); built by scripts/build_state_codes.py. FCT = 'FC'.\n")
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["state_pcode", "state_name", "state_code", "iso_3166_2"])
        for r in sorted(dim, key=lambda r: r["state_pcode"]):
            w.writerow([r["state_pcode"], r["state_name"], codes[r["state_name"]], "NG-" + codes[r["state_name"]]])
    print(f"  37 codes, revid {man['revid']} -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
