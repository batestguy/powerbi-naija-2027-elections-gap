"""Pack the public PBIR report and its browser code into a single offline HTML file.

Use the local staging CSVs, or pass --data-vintage with the frozen release ZIP.
Run --check-sources to check the report and data inputs without building HTML.
Run --check to verify that the output matches a fresh build byte for byte.
"""

import argparse
import base64
import csv
import io
import json
import re
import sys
from contextlib import nullcontext
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import BadZipFile, ZipFile


ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
REPORT_DIR = ROOT / "pbip" / "NaijaElectionsGap.Report"
MODEL_TABLES = ROOT / "pbip" / "NaijaElectionsGap.SemanticModel" / "definition" / "tables"
PHOTOS = ROOT / "pbip" / "assets" / "photos"
DEFAULT_OUTPUT = ROOT / "release" / "NaijaElectionsGap.html"

# Publish the model's factual columns without the intermediate reconciliation rows.
STAGED_COLUMNS = {
    "fact_turnout_2023": "state_pcode registered total_valid turnout_pct_reported",
    "fact_result_2023": "state_pcode party candidate votes votes_rule",
    "dim_state": "state_pcode state_name wiki_name zone zone_code is_fct state_code tile_row tile_col",
    "dim_party": "party candidate party_name sort_order colour_hex source",
    "dim_zone": "zone_code zone state_count source",
}
REFERENCE_TABLES = ("tile_grid_layout", "party_display", "party_now", "coalition_names")
INTEGER_FIELDS = {
    "registered", "total_valid", "votes", "sort_order", "state_count",
    "is_fct", "tile_row", "tile_col", "row", "col",
}
IMAGE_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
NUMBER = r"-?\d+(?:\.\d+)?"
SERIES = re.compile(rf"GENERATESERIES\s*\(\s*({NUMBER}),\s*({NUMBER}),\s*({NUMBER})\s*\)")
DEFAULT = re.compile(rf"SELECTEDVALUE\s*\(\s*param_\w+\[Value\],\s*({NUMBER})\s*\)")
PLACEHOLDER = re.compile(r"@@[A-Z_]+@@")
SCRIPT_MARKUP = re.compile(r"</?script|<!--", re.IGNORECASE)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_table(contents, description, columns=None):
    # Reference files have introductory comment lines before the CSV header.
    stream = io.StringIO(contents, newline="")
    offset = stream.tell()
    while stream.readline().startswith("#"):
        offset = stream.tell()
    stream.seek(offset)
    reader = csv.DictReader(stream, strict=True)
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError(f"{description} needs a unique CSV header")
    fields = columns or reader.fieldnames
    missing = set(fields).difference(reader.fieldnames)
    if missing:
        raise ValueError(f"{description} is missing columns {', '.join(sorted(missing))}")

    rows = []
    for row in reader:
        if None in row or None in row.values():
            raise ValueError(f"{description} has an incomplete or extra field near line {reader.line_num}")
        values = {}
        for field in fields:
            value = row[field]
            if value == "":
                values[field] = None
            elif field in INTEGER_FIELDS:
                values[field] = int(value)
            elif field == "turnout_pct_reported":
                values[field] = float(value)
            else:
                values[field] = value
        rows.append(values)
    if not rows:
        raise ValueError(f"{description} has no data rows")
    return rows


def unique_keys(rows, *fields):
    keys = [tuple(row[field] for field in fields) for row in rows]
    if any(None in key for key in keys) or len(keys) != len(set(keys)):
        raise ValueError(f"Missing or duplicate values for key {', '.join(fields)}")
    return set(keys)


def load_tables(vintage):
    tables = {}
    with (ZipFile(vintage) if vintage else nullcontext()) as archive:
        for name, columns in STAGED_COLUMNS.items():
            member = f"staging/{name}.csv"
            if archive:
                contents = archive.read(member).decode("utf-8-sig")
            else:
                path = ROOT / "data" / member
                if not path.is_file():
                    raise ValueError(
                        f"Missing {path}. Run scripts/build_staging.py or use --data-vintage with the release ZIP."
                    )
                contents = path.read_text(encoding="utf-8-sig")
            tables[name] = read_table(contents, member, columns.split())
    for name in REFERENCE_TABLES:
        path = ROOT / "data" / "reference" / f"{name}.csv"
        tables[name] = read_table(path.read_text(encoding="utf-8-sig"), path)

    states = unique_keys(tables["dim_state"], "state_pcode")
    parties = unique_keys(tables["dim_party"], "party")
    zones = unique_keys(tables["dim_zone"], "zone_code")
    if unique_keys(tables["fact_turnout_2023"], "state_pcode") != states:
        raise ValueError("Turnout rows must cover the same states as dim_state")
    if unique_keys(tables["fact_result_2023"], "state_pcode", "party") != {
        state + party for state in states for party in parties
    }:
        raise ValueError("Result rows must cover every state and party in the model")
    if {(row["zone_code"],) for row in tables["dim_state"]} != zones:
        raise ValueError("The state and zone tables disagree about which zones are present")

    tiles = tables["tile_grid_layout"]
    if unique_keys(tiles, "state_pcode") != states or {
        (row["state_pcode"], row["row"], row["col"]) for row in tiles
    } != {(row["state_pcode"], row["tile_row"], row["tile_col"]) for row in tables["dim_state"]}:
        raise ValueError("The reference tile layout and dim_state disagree")
    unique_keys(tiles, "row", "col")
    candidates = parties - {("OTHERS",)}
    if unique_keys(tables["party_display"], "party") != parties:
        raise ValueError("The party display table must cover every model party")
    if unique_keys(tables["party_now"], "party_2023") != candidates:
        raise ValueError("The current-party table must cover every named candidate")
    if unique_keys(tables["coalition_names"], "lead", "partner") != {
        lead + partner for lead in candidates for partner in candidates if lead != partner
    }:
        raise ValueError("The coalition table must cover every ordered candidate pairing")
    return tables


def load_pages():
    pages_dir = REPORT_DIR / "definition" / "pages"
    metadata = read_json(pages_dir / "pages.json")
    pages = []
    for page_id in metadata["pageOrder"]:
        directory = pages_dir / page_id
        page = read_json(directory / "page.json")
        if page.get("visibility") == "HiddenInViewMode" or page.get("type") == "Tooltip":
            continue
        visuals = [read_json(path) for path in (directory / "visuals").glob("*/visual.json")]
        if not visuals:
            raise ValueError(f"{page['displayName']} has no visual definitions")
        visuals.sort(key=lambda visual: (
            visual["position"].get("tabOrder", visual["position"].get("z", 0)),
            visual["position"].get("z", 0),
            visual["name"],
        ))
        pages.append({
            "id": page_id,
            "name": page["displayName"],
            "width": page["width"],
            "height": page["height"],
            "visualInteractions": page.get("visualInteractions", []),
            "visuals": visuals,
        })
    active = metadata["activePageName"]
    if active not in {page["id"] for page in pages}:
        raise ValueError("The report's active page is missing from the visible page order")
    return pages, active


def resource_references(value):
    if isinstance(value, dict):
        if "ResourcePackageItem" in value:
            item = value["ResourcePackageItem"]
            yield item["PackageName"], item["ItemName"]
        for child in value.values():
            yield from resource_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from resource_references(child)


def image_uri(path):
    mime = IMAGE_TYPES[path.suffix.lower()]
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def kush_soundtrack(path):
    audio = path.read_bytes()
    if path.suffix.lower() != ".m4a" or audio[4:8] != b"ftyp":
        raise ValueError(f"{path} must be the M4A recording of Let's Live Together by Kush")
    encoded = base64.b64encode(audio).decode("ascii")
    return {
        "title": "Let's Live Together",
        "artist": "Kush",
        "album": "The Experience",
        "recordingCredit": "℗ 2003 DKG Music, Inc.",
        "creditUrl": "https://www.youtube.com/watch?v=kL2s76KoNCo",
        "audio": f"data:audio/mp4;base64,{encoded}",
    }


def load_resources(pages, tables):
    report = read_json(REPORT_DIR / "definition" / "report.json")
    resources = {
        (package["name"], item["name"]): item
        for package in report["resourcePackages"]
        for item in package["items"]
    }
    static = REPORT_DIR / "StaticResources"
    assets, shapes = {}, {}
    states = unique_keys(tables["dim_state"], "state_pcode")
    for package, name in sorted(set(resource_references(pages))):
        item = resources[package, name]
        path = static / package / item["path"]
        if item["type"] == "Image":
            assets[name] = image_uri(path)
        elif item["type"] == "ShapeMap":
            topology = read_json(path)
            if topology["type"] != "Topology":
                raise ValueError(f"{name} must be TopoJSON")
            properties = [
                feature["properties"]
                for collection in topology["objects"].values()
                for feature in collection["geometries"]
            ]
            if unique_keys(properties, "state_pcode") != states:
                raise ValueError(f"{name} does not cover the same states as dim_state")
            shapes[name] = topology
        else:
            raise ValueError(f"Unsupported resource type {item['type']} for {name}")

    logo_source = read_json(PHOTOS / "logos_manifest.json")["logos"]
    logos = {logo["party"]: logo["data_uri"] for logo in logo_source}
    for row in tables["party_now"]:
        party = row["party_2023"]
        name = f"candidate_{party}.jpg"
        assets[name] = image_uri(PHOTOS / name)
    codes = {row[key] for row in tables["party_now"] for key in ("party_2023", "party_now")}
    for code in sorted(codes.intersection(logos)):
        if not logos[code].startswith("data:image/png;base64,"):
            raise ValueError(f"The {code} logo needs an embedded PNG data URI")
        assets[f"logo_{code}"] = logos[code]

    base_theme = report["themeCollection"]["baseTheme"]
    item = resources[base_theme["type"], base_theme["name"]]
    source_theme = read_json(static / base_theme["type"] / item["path"])
    theme = {key: value for key, value in source_theme.items() if key not in {"visualStyles", "textClasses"}}
    return assets, shapes, theme


def load_parameters():
    parameters = {}
    for path in sorted(MODEL_TABLES.glob("param_*.tmdl")):
        definition = path.read_text(encoding="utf-8-sig")
        series, default = SERIES.search(definition), DEFAULT.search(definition)
        if not series or not default:
            raise ValueError(f"Cannot read slider range and default from {path.name}")
        minimum, maximum, step, initial = (json.loads(value) for value in (*series.groups(), default[1]))
        if step <= 0 or not minimum <= initial <= maximum:
            raise ValueError(f"Invalid slider range or default in {path.name}")
        parameters[path.stem] = {"min": minimum, "max": maximum, "step": step, "default": initial}
    if not parameters:
        raise ValueError("No what-if parameter tables found in the semantic model")
    return parameters


def load_report(vintage=None):
    tables = load_tables(vintage)
    pages, active = load_pages()
    assets, shapes, theme = load_resources(pages, tables)
    return {
        "pages": pages,
        "activePageId": active,
        "assets": assets,
        "tables": tables,
        "shapes": shapes,
        "theme": theme,
        "parameters": load_parameters(),
    }


def inline_json(data):
    # Prevent data from changing HTML's raw-text script parsing state.
    return (json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            .translate(str.maketrans({"<": r"\u003c", ">": r"\u003e", "&": r"\u0026",
                                      "\u2028": r"\u2028", "\u2029": r"\u2029"})))


def inline_script(path):
    content = path.read_text(encoding="utf-8-sig")
    if SCRIPT_MARKUP.search(content):
        raise ValueError(f"{path.name} contains markup unsafe in an inline script block")
    return content


def render_html(report):
    template = (SCRIPTS / "offline-election.html").read_text(encoding="utf-8-sig")
    insertions = {
        "@@REPORT_DATA@@": inline_json(report),
        "@@ENGINE@@": inline_script(SCRIPTS / "offline-election-engine.js"),
        "@@UI@@": inline_script(SCRIPTS / "offline-election-ui.js"),
    }
    tokens = PLACEHOLDER.findall(template)
    if sorted(tokens) != sorted(insertions):
        raise ValueError("The HTML template must contain exactly one placeholder for report data, engine and UI")
    return PLACEHOLDER.sub(lambda match: insertions[match[0]], template).encode("utf-8")


def write_output(path, output):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        partial = Path(stream.name)
        try:
            stream.write(output)
            stream.close()
            partial.replace(path)
        finally:
            stream.close()
            partial.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="destination HTML file")
    parser.add_argument("--data-vintage", type=Path, help="read the staging CSVs from the frozen release ZIP")
    parser.add_argument("--kush-soundtrack", type=Path, help="embed the supplied M4A of Let's Live Together by Kush")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-sources", action="store_true", help="validate source data and PBIR inputs only")
    mode.add_argument("--check", action="store_true", help="compare the destination against a fresh in-memory build")
    args = parser.parse_args()
    try:
        report = load_report(args.data_vintage)
        if args.kush_soundtrack:
            report["soundtrack"] = kush_soundtrack(args.kush_soundtrack)
        if args.check_sources:
            maps = len(report["shapes"])
            print(f"Validated {len(report['pages'])} pages, {len(report['tables'])} tables, "
                  f"{len(report['assets'])} images, {maps} map{'s' if maps != 1 else ''} "
                  f"and {len(report['parameters'])} controls.")
            return 0
        output = render_html(report)
        if args.check:
            if not args.output.is_file() or args.output.read_bytes() != output:
                raise ValueError(f"{args.output} is missing or differs from a fresh build")
            print(f"Verified {args.output} ({len(output):,} bytes)")
        else:
            write_output(args.output, output)
            print(f"Wrote {args.output} ({len(output):,} bytes)")
    except (OSError, ValueError, KeyError, BadZipFile, csv.Error) as error:
        print(f"Offline report build failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
