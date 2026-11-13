"""Phase 1 source probe. Re-runnable, standard library only.

Checks each candidate source is reachable and measures what it actually contains.
Writes reports/source_probe.json. Downloads go to a temp folder, not data/ (Phase 2 does acquisition).

Usage (repo root):  uv run python -I scripts/probe_sources.py
"""
import io, json, re, sys, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import date
from pathlib import Path

UA = {"User-Agent": "naija-2027-elections-gap source probe (research; non-commercial)"}
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports" / "source_probe.json"


def get(url, timeout=60, tries=5):
    """GET with backoff on 429/5xx (Wikipedia rate-limits bursts)."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503) or attempt == tries - 1:
                raise
            wait = int(e.headers.get("Retry-After") or 0) or 5 * 2 ** attempt
            time.sleep(min(wait, 60))


def probe_hdx():
    meta_url = "https://data.humdata.org/api/3/action/package_show?id=cod-ab-nga"
    _, body = get(meta_url)
    pkg = json.loads(body)["result"]
    res = next(r for r in pkg["resources"] if r["name"].lower().endswith(".geojson.zip"))
    status_zip, blob = get(res["url"], timeout=300)
    z = zipfile.ZipFile(io.BytesIO(blob))
    adm2_name = next(n for n in z.namelist() if re.search(r"admin2\.geojson$", n))
    fc = json.loads(z.read(adm2_name))
    props = [f["properties"] for f in fc["features"]]
    pcodes = {p.get("adm2_pcode") for p in props}
    states = {p.get("adm1_name") for p in props}
    fct = sorted(p["adm2_name"] for p in props if (p.get("adm1_name") or "").lower().startswith("federal capital"))
    names = [p["adm2_name"] for p in props]
    dup = sorted({n for n in names if names.count(n) > 1})
    return {
        "source": "HDX COD-AB Nigeria (cod-ab-nga)",
        "metadata_url": meta_url, "file_url": res["url"], "http": status_zip,
        "licence": pkg.get("license_title"), "dataset_date": pkg.get("dataset_date"),
        "resource_last_modified": res.get("last_modified"),
        "zip_bytes": len(blob), "adm2_file": adm2_name,
        "lga_features": len(props), "unique_pcodes": len(pcodes), "states": len(states),
        "fields": sorted(props[0].keys()), "fct_units": fct, "duplicate_lga_names": dup,
        "valid_on_values": sorted({str(p.get("valid_on")) for p in props})[:3],
    }


def probe_geoboundaries():
    api = "https://www.geoboundaries.org/api/current/gbOpen/NGA/ADM2/"
    status, body = get(api)
    meta = json.loads(body)
    return {
        "source": "geoBoundaries gbOpen NGA ADM2", "api_url": api, "http": status,
        "licence": meta.get("boundaryLicense"), "source_org": meta.get("boundarySource"),
        "boundary_year": meta.get("boundaryYearRepresented"),
        "feature_count_reported": meta.get("admUnitCount"),
        "topojson_url": meta.get("tjDownloadURL"),
    }


WIKI_API = "https://en.wikipedia.org/w/api.php"
NUM = re.compile(r"\b\d{1,3}(?:,\d{3})+\b|\b\d{3,}\b")


def wiki_titles():
    q = {"action": "query", "list": "search", "srlimit": "50", "format": "json",
         "srsearch": 'intitle:"2023 Nigerian presidential election in"'}
    _, body = get(WIKI_API + "?" + urllib.parse.urlencode(q))
    return sorted(x["title"] for x in json.loads(body)["query"]["search"])


def lga_coverage(title):
    q = {"action": "parse", "page": title, "prop": "wikitext", "format": "json", "formatversion": "2"}
    _, body = get(WIKI_API + "?" + urllib.parse.urlencode(q))
    text = json.loads(body)["parse"]["wikitext"]
    i = text.find("By local government area")
    if i < 0:
        return {"lga_rows": 0, "rows_with_figures": 0, "note": "no LGA section"}
    sec = text[i:]
    j = sec.find("\n==", 30)
    sec = sec[:j] if j > 0 else sec
    rows = [r for r in sec.split("|-") if "[[" in r]  # a data row links its LGA
    filled = [r for r in rows if len(NUM.findall(r)) >= 3 and "TBD" not in r]
    return {"lga_rows": len(rows), "rows_with_figures": len(filled)}


def probe_wikipedia():
    titles = wiki_titles()
    per_state = {}
    for t in titles:
        per_state[t.replace("2023 Nigerian presidential election in ", "")] = lga_coverage(t)
        time.sleep(2)
    tot_rows = sum(v["lga_rows"] for v in per_state.values())
    tot_filled = sum(v["rows_with_figures"] for v in per_state.values())
    return {
        "source": "Wikipedia '2023 Nigerian presidential election in <State>' pages",
        "licence": "CC BY-SA 4.0 (Wikipedia text)", "pages_found": len(titles),
        "lga_rows_total": tot_rows, "lga_rows_with_figures": tot_filled,
        "states_complete": sorted(k for k, v in per_state.items() if v["lga_rows"] and v["rows_with_figures"] == v["lga_rows"]),
        "states_empty": sorted(k for k, v in per_state.items() if v["rows_with_figures"] == 0),
        "per_state": per_state,
        "method_note": "A row counts as filled if it links an LGA, has >=3 numbers of 3+ digits and no 'TBD'. Heuristic, not a parse.",
    }


def main():
    report = {"probed_on": date.today().isoformat(), "results": {}}
    for name, fn in [("hdx_cod_ab", probe_hdx), ("geoboundaries", probe_geoboundaries), ("wikipedia_lga", probe_wikipedia)]:
        try:
            report["results"][name] = {"ok": True, **fn()}
        except Exception as e:  # record the failure, keep probing the rest
            report["results"][name] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        r = report["results"][name]
        print(f"{name:15} {'OK ' if r['ok'] else 'FAIL'} " + json.dumps({k: v for k, v in r.items() if k not in ('per_state', 'fields')})[:600])
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWritten {OUT.relative_to(ROOT)}")
    sys.exit(0 if all(r["ok"] for r in report["results"].values()) else 1)


if __name__ == "__main__":
    main()
