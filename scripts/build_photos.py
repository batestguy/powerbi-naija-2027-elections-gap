"""Decorative photos for the report's side panels (user decision 2026-11-14).

Fetches each chosen Wikimedia Commons file once, as Commons' own 1920-px-wide rendition (Wikimedia asks automated
clients to use its standard thumbnail sizes, and refused full-size downloads with HTTP 429), into
data/raw/photos/<ACCESS_DATE>/ with a manifest (file page URL, download URL, author, licence + licence URL, SHA-256 of
the download, SHA-1 of the Commons original for reference), refusing any
file whose licence is not CC0, public domain, CC BY or CC BY-SA. Then crops each to the side-panel shape around a
chosen focus point, downscales and saves a JPEG (<= 240 KB, EXIF stripped) to pbip/assets/photos/<key>.jpg with
pbip/assets/photos/photos_manifest.json (credits, changes, page, alt text). build_pbip.py embeds these files.

Content rule: neutral election scenes only (queues, registers, ballot boxes, officials, counting); no candidates,
party logos, rallies or posters.

Usage (repo root):  uv run python -I scripts/build_photos.py [--refetch]
Raw files already on disk for ACCESS_DATE are reused (no network) unless --refetch.
"""
import base64, hashlib, io, json, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
ACCESS_DATE = "2026-11-14"
RAW = ROOT / "data" / "raw" / "photos" / ACCESS_DATE
OUT = ROOT / "pbip" / "assets" / "photos"
UA = {"User-Agent": "NaijaElectionsGap-report/1.0 (open-data project)"}
API = "https://commons.wikimedia.org/w/api.php"
ALLOWED = re.compile(r"^(CC0|Public domain|PD.*|CC BY(-SA)? \d\.\d.*)$", re.I)
THUMB_W = 1920                        # a standard Wikimedia thumbnail step (https://w.wiki/GHai)
PANEL_W, PANEL_H = 190, 560          # report side panel in report pixels; images are saved at 2x
MAX_BYTES, MAX_TOTAL = 240_000, 2_000_000

# key, Commons file, report page, horizontal focus (0 = left edge, 1 = right edge), what it shows (for alt text)
PHOTOS = [
    ("overview", "File:2023 Elections in Nigeria 15.jpg", "Candidate overview", 0.45,
     "labelled ballot boxes (Presidential, Senatorial, House of Representatives) on a polling-unit table"),
    ("path", "File:2023 Elections in Nigeria 03.jpg", "Path to 25", 0.40,
     "voters checking their names on the register posted on a wall"),
    ("map", "File:Area shot of polling units.jpg", "Spread map", 0.62,
     "voters gathered at polling units in an open yard"),
    ("simulator", "File:2023 Elections in Nigeria 26.jpg", "What-if simulator", 0.44,
     "an election official setting up a voting cubicle outside a polling unit"),
    ("howto", "File:Voters queue to cast their vote at Pantami, Gombe.jpg", "How to read this", 0.42,
     "voters queueing to vote at Pantami, Gombe"),
    ("technical", "File:NYSC member counting votes during 2023 presidential election in Gombe.jpg", "Technical notes", 0.50,
     "votes being counted in public at a polling unit in Pantami, Gombe"),
    ("sources", "File:2023 Elections in Nigeria 12.jpg", "Data sources", 0.55,
     "polling officials in high-visibility vests working at a table"),
]


def get(url):
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 4:
                raise
            time.sleep(min(120, int(e.headers.get("Retry-After") or 0) or 15 * 2 ** attempt))


def plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def fetch(items=None, raw=None, thumb_w=THUMB_W):
    items, raw = items or PHOTOS, raw or RAW
    raw.mkdir(parents=True, exist_ok=True)
    q = urllib.parse.urlencode({"action": "query", "titles": "|".join(t for _, t, *_ in items), "prop": "imageinfo",
                                "iiprop": "url|size|sha1|extmetadata", "iiurlwidth": str(thumb_w),
                                "format": "json"})
    pages = {p["title"]: p for p in json.loads(get(f"{API}?{q}"))["query"]["pages"].values()}
    files = []
    for key, title, *_ in items:
        ii = pages[title]["imageinfo"][0]
        m = ii["extmetadata"]
        lic = plain(m.get("LicenseShortName", {}).get("value"))
        if not ALLOWED.match(lic):
            sys.exit(f"REFUSED {title}: licence '{lic}' is not CC0 / public domain / CC BY / CC BY-SA")
        url = ii.get("thumburl", ii["url"])
        body = get(url)
        name = key + Path(urllib.parse.urlparse(url).path).suffix.lower()
        (raw / name).write_bytes(body)
        files.append({"key": key, "file": name, "title": title, "file_page": ii["descriptionurl"], "url": url,
                      "rendition": f"Commons thumbnail {ii['thumbwidth']}x{ii['thumbheight']} of the "
                                   f"{ii['width']}x{ii['height']} original", "original_url": ii["url"],
                      "original_sha1": ii["sha1"],
                      "accessed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                      "author": plain(m.get("Artist", {}).get("value")), "licence": lic,
                      "licence_url": plain(m.get("LicenseUrl", {}).get("value")),
                      "credit": plain(m.get("Credit", {}).get("value")),
                      "description": plain(m.get("ImageDescription", {}).get("value"))[:300]})
        time.sleep(5)
    man = {"source": "Wikimedia Commons", "api": API, "user_agent": UA["User-Agent"], "access_date": ACCESS_DATE,
           "licence_rule": "CC0, public domain, CC BY or CC BY-SA only", "files": files}
    (raw / "manifest.json").write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return man


# ---- candidate portraits (user request 2026-11-14): same treatment for all four (square head-and-shoulders crop,
# 160 x 160 px, JPEG), embedded in the model as base64 data URIs (<= 30,000 characters each) so the report works offline.
# Party logos: no free-licence logo of APC, PDP, LP or NNPP was found on Wikimedia Commons (searched 2026-11-14), so the
# report shows a coloured badge with the party's abbreviation for every party; no logo files are used.
CAND_RAW = RAW / "candidates"
CAND_PX, CAND_MAX_URI = 160, 30_000
# party, Commons file, square crop: centre x, centre y (fractions of width / height), side (fraction of width)
CANDIDATES = [
    ("APC", "File:Bola Tinubu portrait (cropped).jpg", 0.50, 0.40, 0.80),
    ("PDP", "File:Atiku Abubakar 2023.jpg", 0.44, 0.19, 0.56),
    ("LP", "File:H.E. Peter Obi (cropped).jpg", 0.52, 0.24, 0.52),
    ("NNPP", "File:Rabiu Kwankwaso (cropped).jpg", 0.53, 0.40, 0.86),
]


def build_candidates(refetch):
    man_path = CAND_RAW / "manifest.json"
    items = [(k, t) for k, t, *_ in CANDIDATES]
    man = (fetch(items, CAND_RAW, 800) if refetch or not man_path.exists()
           else json.loads(man_path.read_text(encoding="utf-8")))
    raw = {f["key"]: f for f in man["files"]}
    out = []
    for party, title, fx, fy, side in CANDIDATES:
        r = raw[party]
        body = (CAND_RAW / r["file"]).read_bytes()
        if hashlib.sha256(body).hexdigest() != r["sha256"]:
            sys.exit(f"{r['file']} on disk does not match its manifest SHA-256")
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(body))).convert("RGB")
        w, h = im.size
        s = round(side * w)
        x0 = min(max(0, round(fx * w - s / 2)), w - s)
        y0 = min(max(0, round(fy * h - s / 2)), h - s)
        small = im.crop((x0, y0, x0 + s, y0 + s)).resize((CAND_PX, CAND_PX), Image.LANCZOS)
        for q in range(85, 40, -5):
            buf = io.BytesIO()
            small.save(buf, "JPEG", quality=q, optimize=True)   # no EXIF written
            uri = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
            if len(uri) <= CAND_MAX_URI:
                break
        if len(uri) > CAND_MAX_URI:
            sys.exit(f"{party}: data URI over {CAND_MAX_URI} characters")
        (OUT / f"candidate_{party}.jpg").write_bytes(buf.getvalue())
        out.append({"party": party, "output": f"pbip/assets/photos/candidate_{party}.jpg", "data_uri_chars": len(uri),
                    "sha256": hashlib.sha256(buf.getvalue()).hexdigest(), "data_uri": uri,
                    "title": r["title"], "file_page": r["file_page"], "author": r["author"], "licence": r["licence"],
                    "licence_url": r["licence_url"], "accessed": man["access_date"], "raw_sha256": r["sha256"],
                    "changes": f"square crop {s}x{s} px at ({x0},{y0}) from {w}x{h}, resized to {CAND_PX}x{CAND_PX}, "
                               f"re-saved as JPEG (quality {q}, metadata removed)"})
        print(f"  candidate {party:5} {len(uri) / 1000:5.1f}k chars  {r['licence']:14} {r['author'][:30]}")
    (OUT / "candidates_manifest.json").write_text(json.dumps(
        {"built_by": "scripts/build_photos.py", "raw_manifest": str(man_path.relative_to(ROOT)).replace("\\", "/"),
         "logos": "none used: no free-licence logo found on Wikimedia Commons for APC, PDP, LP or NNPP (2026-11-14); "
                  "a coloured abbreviation badge is shown for every party",
         "candidates": out}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def crop_panel(im, focus):
    """Largest crop with the panel's aspect ratio, centred on the focus point horizontally (full height)."""
    w, h = im.size
    target = PANEL_W / PANEL_H
    if w / h > target:
        cw = round(h * target)
        x0 = min(max(0, round(focus * w - cw / 2)), w - cw)
        box = (x0, 0, x0 + cw, h)
    else:
        ch = round(w / target)
        y0 = (h - ch) // 2
        box = (0, y0, w, y0 + ch)
    return im.crop(box), box


def main():
    man_path = RAW / "manifest.json"
    man = fetch() if "--refetch" in sys.argv or not man_path.exists() else json.loads(man_path.read_text(encoding="utf-8"))
    raw = {f["key"]: f for f in man["files"]}
    OUT.mkdir(parents=True, exist_ok=True)
    out, total = [], 0
    for key, title, page, focus, subject in PHOTOS:
        r = raw[key]
        body = (RAW / r["file"]).read_bytes()
        if hashlib.sha256(body).hexdigest() != r["sha256"]:
            sys.exit(f"{r['file']} on disk does not match its manifest SHA-256")
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(body))).convert("RGB")
        cropped, box = crop_panel(im, focus)
        small = cropped.resize((PANEL_W * 2, PANEL_H * 2), Image.LANCZOS)
        for q in range(86, 40, -4):
            buf = io.BytesIO()
            small.save(buf, "JPEG", quality=q, optimize=True, progressive=True)   # no EXIF written
            if buf.tell() <= MAX_BYTES:
                break
        data = buf.getvalue()
        if len(data) > MAX_BYTES:
            sys.exit(f"{key}: cannot get under {MAX_BYTES} bytes")
        (OUT / f"photo_{key}.jpg").write_bytes(data)
        total += len(data)
        out.append({"key": key, "page": page, "output": f"pbip/assets/photos/photo_{key}.jpg", "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(), "jpeg_quality": q,
                    "title": r["title"], "file_page": r["file_page"], "author": r["author"], "licence": r["licence"],
                    "licence_url": r["licence_url"], "accessed": man["access_date"], "raw_sha256": r["sha256"],
                    "subject": subject,
                    "changes": f"cropped to {box[2] - box[0]}x{box[3] - box[1]} px at ({box[0]},{box[1]}) from "
                               f"{im.size[0]}x{im.size[1]}, resized to {PANEL_W * 2}x{PANEL_H * 2}, re-saved as JPEG "
                               f"(quality {q}, metadata removed)"})
        print(f"  {key:10} {len(data) / 1000:6.1f} kB  q{q}  {r['licence']:14} {r['author'][:30]}")
    if total > MAX_TOTAL:
        sys.exit(f"total {total} bytes is over {MAX_TOTAL}")
    (OUT / "photos_manifest.json").write_text(json.dumps(
        {"built_by": "scripts/build_photos.py", "raw_manifest": str(man_path.relative_to(ROOT)).replace("\\", "/"),
         "panel_report_px": [PANEL_W, PANEL_H], "total_bytes": total, "photos": out}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(f"  {len(out)} photos, {total / 1000:.0f} kB total -> {OUT.relative_to(ROOT)}")
    build_candidates("--refetch" in sys.argv)
    build_locator()
    build_logos("--refetch" in sys.argv)


# ---- "Where is each state?" locator (user request 2026-11-14): a neutral, static map with each state's ISO code, drawn
# from the same simplified boundaries as the Shape Map (pbip/assets/nga_states.topo.json). Grey fill, white borders,
# black codes on a white halo, so it never competes with the coloured data maps. Codes from data/staging/dim_state.csv.
LOC_W, LOC_H = 640, 520      # pixels (shown at half size in the report)
# a few small states get a short leader line so their codes do not overlap neighbours (dx, dy in pixels)
LOC_NUDGE = {"LA": (-34, 18), "AN": (-34, 10), "IM": (-30, 26), "AB": (6, 34), "EB": (42, -14), "EN": (30, -18),
             "FC": (0, 0), "BY": (-30, 18), "RI": (4, 34), "AK": (34, 20)}


def decode_topojson(topo):
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(ix):
        out = []
        for i in ix:
            seg = arcs[i] if i >= 0 else arcs[~i][::-1]
            out += seg if not out else seg[1:]
        return out
    for g in next(iter(topo["objects"].values()))["geometries"]:
        polys = [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
        yield g["properties"], [[ring(r) for r in poly] for poly in polys]


def build_locator():
    import csv as _csv
    from PIL import ImageDraw, ImageFont
    from shapely.geometry import MultiPolygon, Polygon
    topo = json.loads((ROOT / "pbip" / "assets" / "nga_states.topo.json").read_text(encoding="utf-8"))
    with open(ROOT / "data" / "staging" / "dim_state.csv", encoding="utf-8") as f:
        code = {r["state_pcode"]: r["state_code"] for r in _csv.DictReader(f)}
    x0, y0, x1, y1 = topo["bbox"]
    k = min((LOC_W - 40) / (x1 - x0), (LOC_H - 40) / (y1 - y0))

    def px(lon, lat):
        return 20 + (lon - x0) * k, LOC_H - 20 - (lat - y0) * k
    im = Image.new("RGB", (LOC_W, LOC_H), "white")
    d = ImageDraw.Draw(im)
    feats = list(decode_topojson(topo))
    for _, polys in feats:
        for poly in polys:
            d.polygon([px(*q) for q in poly[0]], fill="#D9D9D9", outline="#FFFFFF")
            for hole in poly[1:]:
                d.polygon([px(*q) for q in hole], fill="white")
    for _, polys in feats:   # borders on top, 2 px white
        for poly in polys:
            d.line([px(*q) for q in poly[0]] + [px(*poly[0][0])], fill="#FFFFFF", width=2)
    font = ImageFont.truetype("segoeuib.ttf", 26)   # shown at half size: ~13 px, about 10 pt
    for props, polys in feats:
        shape = MultiPolygon([Polygon(p[0], p[1:]) for p in polys])
        c = code[props["state_pcode"]]
        pt = shape.representative_point()
        ax, ay = px(pt.x, pt.y)
        dx, dy = LOC_NUDGE.get(c, (0, 0))
        lx, ly = ax + dx, ay + dy
        if dx or dy:
            d.line([(ax, ay), (lx, ly)], fill="#1F1F1F", width=2)
        d.text((lx, ly), c, font=font, fill="#1F1F1F", anchor="mm", stroke_width=3, stroke_fill="white")
    out = OUT / "locator_states.png"
    im.save(out, optimize=True)
    print(f"  locator map {out.stat().st_size / 1000:.1f} kB -> {out.relative_to(ROOT)}")


# ---- party logos (user decision 2026-11-14): the real logos, used for identification only (nominative use in a
# non-commercial civic report). They are trademarks and mostly NOT freely licensed: the source's own licence statement
# is recorded per file. PBIP_NO_LOGOS=1 at build time makes the report show abbreviation badges instead.
LOGO_RAW = ROOT / "data" / "raw" / "party_logos" / ACCESS_DATE
LOGO_PX = 96
# party code, wiki host, file title (as used in each party's Wikipedia infobox, revisions checked 2026-11-14)
LOGOS = [
    ("APC", "en.wikipedia.org", "File:All Progressives Congress logo.png"),
    ("PDP", "en.wikipedia.org", "File:Logo of the Peoples Democratic Party (Nigeria).png"),
    ("LP", "en.wikipedia.org", "File:Labour Party (Nigeria) logo.png"),
    ("NNPP", "en.wikipedia.org", "File:Logo of the New Nigeria People's Party.png"),
    ("ADC", "en.wikipedia.org", "File:African Democratic Congress logo.png"),
    ("NDC", "commons.wikimedia.org", "File:Nigeria Democratic Party Logo.jpg"),
]


def build_logos(refetch):
    man_path = LOGO_RAW / "manifest.json"
    if refetch or not man_path.exists():
        LOGO_RAW.mkdir(parents=True, exist_ok=True)
        files = []
        for code, host, title in LOGOS:
            q = urllib.parse.urlencode({"action": "query", "titles": title, "prop": "imageinfo",
                                        "iiprop": "url|size|extmetadata", "format": "json"})
            page = next(iter(json.loads(get(f"https://{host}/w/api.php?{q}"))["query"]["pages"].values()))
            ii = page["imageinfo"][0]
            m = ii["extmetadata"]
            body = get(ii["url"])
            name = code + Path(urllib.parse.urlparse(ii["url"]).path).suffix.lower()
            (LOGO_RAW / name).write_bytes(body)
            files.append({"key": code, "file": name, "title": title, "file_page": ii["descriptionurl"], "url": ii["url"],
                          "accessed_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                          "licence_as_stated": plain(m.get("LicenseShortName", {}).get("value")),
                          "non_free_flag": plain(m.get("NonFree", {}).get("value")),
                          "author": plain(m.get("Artist", {}).get("value"))})
            time.sleep(3)
        man = {"source": "Wikipedia / Wikimedia Commons file pages", "access_date": ACCESS_DATE,
               "use": "trademarks, identification only (nominative use); not relicensed", "files": files}
        man_path.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    man = json.loads(man_path.read_text(encoding="utf-8"))
    out = []
    for r in man["files"]:
        body = (LOGO_RAW / r["file"]).read_bytes()
        if hashlib.sha256(body).hexdigest() != r["sha256"]:
            sys.exit(f"{r['file']} on disk does not match its manifest SHA-256")
        im = Image.open(io.BytesIO(body)).convert("RGBA")
        im.thumbnail((LOGO_PX, LOGO_PX), Image.LANCZOS)            # same box for every party, aspect kept
        sq = Image.new("RGBA", (LOGO_PX, LOGO_PX), (255, 255, 255, 255))
        sq.alpha_composite(im, ((LOGO_PX - im.width) // 2, (LOGO_PX - im.height) // 2))
        buf = io.BytesIO()
        sq.convert("RGB").save(buf, "PNG", optimize=True)
        uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        if len(uri) > CAND_MAX_URI:
            buf = io.BytesIO()
            sq.convert("RGB").save(buf, "JPEG", quality=85, optimize=True)
            uri = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        if len(uri) > CAND_MAX_URI:
            sys.exit(f"logo {r['key']}: data URI over {CAND_MAX_URI} characters")
        out.append({"party": r["key"], "data_uri": uri, "data_uri_chars": len(uri), "file_page": r["file_page"],
                    "licence_as_stated": r["licence_as_stated"], "non_free_flag": r["non_free_flag"],
                    "accessed": man["access_date"], "raw_sha256": r["sha256"],
                    "changes": f"fitted into a {LOGO_PX}x{LOGO_PX} white square, re-saved"})
        print(f"  logo {r['key']:5} {len(uri) / 1000:5.1f}k chars  {r['licence_as_stated']}")
    (OUT / "logos_manifest.json").write_text(json.dumps(
        {"built_by": "scripts/build_photos.py", "raw_manifest": str(man_path.relative_to(ROOT)).replace("\\", "/"),
         "notice": "Party logos are trademarks of their respective parties, shown for identification only; no endorsement "
                   "implied.", "logos": out}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
