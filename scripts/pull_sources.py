"""Phase 2 acquisition. Downloads raw inputs exactly as received.

Each source lands in data/raw/<source>/<YYYY-MM-DD>/ with a manifest.json listing, per file:
url, access time (UTC), HTTP status, bytes, SHA-256 and, for Wikipedia, the page revision ID.
Wikipedia sections are fetched by heading name, then pinned to the revision ID seen first
(oldid=...), so all sections of one page come from the same revision.

Usage (repo root):  .venv/Scripts/python.exe -I scripts/pull_sources.py [--skip-mundx] [--only src1,src2]
Re-running on the same day overwrites that day's folder; a new day makes a new folder.
"""
import hashlib, json, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

UA = {"User-Agent": "naija-2027-elections-gap/0.1 (research; non-commercial)"}
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
TODAY = date.today().isoformat()
WIKI_API = "https://en.wikipedia.org/w/api.php"
MAIN_PAGE = "2023_Nigerian_presidential_election"
ZONES_PAGE = "Geopolitical_zones_of_Nigeria"
HDX_META = "https://data.humdata.org/api/3/action/package_show?id=cod-ab-nga"
NIGERIALAWYER = "https://thenigerialawyer.com/inigeriaelections2023-final-results-of-2023-presidential-election-as-declared-by-ineci/"
AGADA = ("https://raw.githubusercontent.com/AGADA-BI/Nigeria-2023-election-data/HEAD/"
         "2023%20Nigeria%20Presiential%20Election%20Results%20(Based%20on%20results%20declared%20by%20INEC).xlsx")
MUNDX = "https://mundx.com/assets/2023-map/data/lgas.json"
THISDAY = "https://www.thisdaylive.com/2023/03/01/live-updates-final-results-of-2023-presidential-election-as-declared-by-inec-2/"
# Vanguard (https://www.vanguardngr.com/2023-presidential-election-results-by-states/) refuses scripted requests
# (HTTP 403). It is NOT pulled here: data/raw/vanguard/2026-11-14/ is a one-off manual save, described in its manifest.
INEC_REPORT = "https://thenigerialawyer.com/wp-content/uploads/2024/02/INEC-REPORT-2023.pdf"


def get(url, timeout=120, tries=6):
    """GET with backoff on 429/5xx (Wikipedia rate-limits bursts). Returns (status, bytes)."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == tries - 1:
                raise
            wait = int(e.headers.get("Retry-After") or 0) or 5 * 2 ** attempt
            time.sleep(min(wait, 60))


class Snapshot:
    """One source's dated folder + manifest."""

    def __init__(self, source, note=""):
        self.source, self.dir = source, RAW / source / TODAY
        self.dir.mkdir(parents=True, exist_ok=True)
        self.files, self.note = [], note

    def save(self, name, url, **extra):
        accessed = datetime.now(timezone.utc).isoformat(timespec="seconds")
        status, body = get(url)
        (self.dir / name).write_bytes(body)
        rec = {"file": name, "url": url, "accessed_utc": accessed, "http_status": status,
               "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), **extra}
        self.files.append(rec)
        print(f"  {self.source}/{TODAY}/{name}: HTTP {status}, {len(body):,} bytes")
        return body

    def write_manifest(self):
        m = {"source": self.source, "snapshot_date": TODAY, "note": self.note,
             "user_agent": UA["User-Agent"], "files": self.files}
        (self.dir / "manifest.json").write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8", newline="\n")


def wiki_url(**q):
    return WIKI_API + "?" + urllib.parse.urlencode({"format": "json", "formatversion": "2", **q})


def section_index(sections, heading):
    hits = [s["index"] for s in sections if s["line"].strip() == heading]
    if len(hits) != 1:
        raise RuntimeError(f"expected one section titled {heading!r}, found {hits}")
    return hits[0]


def pull_wikipedia_main():
    s = Snapshot("wikipedia_main", "Sections 'By state' and 'By geopolitical zone' of the main 2023 page, "
                                   "pinned to one revision. CC BY-SA 4.0.")
    body = s.save("sections.json", wiki_url(action="parse", page=MAIN_PAGE, prop="sections|revid", redirects="1"))
    parsed = json.loads(body)["parse"]
    revid, secs = parsed["revid"], parsed["sections"]
    s.files[-1]["revid"] = revid
    for heading, fname in [("By state", "by_state.json"), ("By geopolitical zone", "by_zone.json")]:
        idx = section_index(secs, heading)
        time.sleep(1.5)
        b = s.save(fname, wiki_url(action="parse", oldid=str(revid), section=idx, prop="wikitext|text|revid"),
                   revid=revid, section_index=idx, section_heading=heading)
        assert json.loads(b)["parse"]["revid"] == revid
    s.write_manifest()
    return revid, s.dir / "by_state.json"


def pull_wikipedia_states(by_state_path):
    """The 37 state pages are the ones the By-state table links to."""
    import re
    wt = json.loads(by_state_path.read_text(encoding="utf-8"))["parse"]["wikitext"]
    titles = re.findall(r"\[\[(2023 Nigerian presidential election in [^|\]]+)", wt)
    titles = list(dict.fromkeys(titles))
    if len(titles) != 37:
        raise RuntimeError(f"expected 37 state page links in By state table, found {len(titles)}")
    s = Snapshot("wikipedia_states", "Full wikitext of the 37 per-state 2023 presidential pages linked from "
                                     "the main page's By state table. CC BY-SA 4.0.")
    for t in titles:
        time.sleep(1.5)
        fname = re.sub(r"[^A-Za-z0-9]+", "_", t.replace("2023 Nigerian presidential election in ", "")).strip("_") + ".json"
        b = s.save(fname, wiki_url(action="parse", page=t, prop="wikitext|revid", redirects="1"), title=t)
        s.files[-1]["revid"] = json.loads(b)["parse"]["revid"]
    s.write_manifest()


def pull_zones():
    s = Snapshot("zones", "Wikipedia 'Geopolitical zones of Nigeria' (source for state -> zone). CC BY-SA 4.0.")
    b = s.save("zones.json", wiki_url(action="parse", page=ZONES_PAGE, prop="wikitext|revid", redirects="1"), title=ZONES_PAGE)
    s.files[-1]["revid"] = json.loads(b)["parse"]["revid"]
    s.write_manifest()


def pull_hdx():
    s = Snapshot("hdx_cod_ab", "HDX COD-AB Nigeria administrative boundaries. CC BY-IGO. Zip kept local only.")
    meta = json.loads(s.save("package_show.json", HDX_META))["result"]
    res = [r for r in meta["resources"] if r["name"].lower().endswith(".geojson.zip")]
    if len(res) != 1:
        raise RuntimeError(f"expected one .geojson.zip resource, found {[r['name'] for r in res]}")
    r = res[0]
    s.save(r["name"], r["url"], resource_id=r.get("id"), resource_last_modified=r.get("last_modified"),
           licence=meta.get("license_title"))
    s.write_manifest()


def pull_simple(source, fname, url, note):
    s = Snapshot(source, note)
    s.save(fname, url)
    s.write_manifest()


SIMPLE = {
    "nigerialawyer": ("results.html", NIGERIALAWYER, "Secondary copy of the INEC declaration (cross-check only)."),
    "agada": ("agada_results.xlsx", AGADA, "AGADA-BI state table 'based on results declared by INEC'. No licence; "
                                           "one of five copies used to reconcile state results."),
    "thisday": ("page.html", THISDAY, "ThisDay state table 'as announced by INEC' (four parties). Shares every "
                                      "discrepancy with thenigerialawyer.com, so treated as the same copy."),
    "inec_report": ("INEC-REPORT-2023.pdf", INEC_REPORT,
                    "INEC 'Report of the 2023 General Election' (mirror; not found on inecnigeria.org). Annexure 2, "
                    "PDF page 457: national Declaration of Results (image). National totals only, no state breakdown."),
    "mundx": ("lgas.json", MUNDX, "Mundx four-party LGA rollup. NO LICENCE: local only, never commit the data file. "
                                  "Used only for an accuracy-ratio report."),
}


def main():
    only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
    want = lambda s: only is None or s in only
    skip_mundx = "--skip-mundx" in sys.argv
    print(f"Snapshot date {TODAY}")
    if want("wikipedia_main") or want("wikipedia_states"):
        revid, by_state = pull_wikipedia_main()
        print(f"  main page revid {revid}")
        pull_wikipedia_states(by_state)
        time.sleep(1.5)
    if want("zones"):
        pull_zones()
    if want("hdx_cod_ab"):
        pull_hdx()
    for src, (fname, url, note) in SIMPLE.items():
        if want(src) and not (src == "mundx" and skip_mundx):
            pull_simple(src, fname, url, note)
    print("Done.")


if __name__ == "__main__":
    main()
