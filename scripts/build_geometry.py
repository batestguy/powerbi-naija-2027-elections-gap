"""Phase 2 geometry. Builds the two TopoJSON files for the Power BI Shape Map visual.

1. pbip/assets/nga_states.topo.json  - HDX COD-AB admin1 (37 units), topology-preserving
   Douglas-Peucker simplification (shared borders simplified once, so no gaps/overlaps).
2. pbip/assets/nga_tiles.topo.json   - equal-size square tiles laid out by
   data/reference/tile_grid_layout.csv (our own arrangement).
Both carry properties state_pcode (join key) and state_name. A manifest records tool, version,
tolerance, vertex counts and bytes: pbip/assets/geometry_manifest.json.

Usage (repo root):  .venv/Scripts/python.exe -I scripts/build_geometry.py
"""
import csv, hashlib, json, sys, zipfile
from importlib.metadata import version
from pathlib import Path

import itertools

import shapely
import topojson
from shapely.geometry import shape, box, mapping
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "pbip" / "assets"
TOLERANCE_DEG = 0.01        # Douglas-Peucker epsilon in degrees (~1.1 km at Nigeria's latitude)
QUANTIZE = 1e5              # TopoJSON quantization grid (1e5 steps across the bounding box)
TILE_ORIGIN = (3.0, 13.5)   # lon/lat of the top-left tile, so tiles sit over Nigeria
TILE_STEP, TILE_SIZE = 1.0, 0.9


def latest(source):
    return sorted(p for p in (ROOT / "data" / "raw" / source).glob("????-??-??") if p.is_dir())[-1]


def n_vertices_geojson(geom):
    g = geom["coordinates"]
    polys = [g] if geom["type"] == "Polygon" else g
    return sum(len(ring) for poly in polys for ring in poly)


def topo_vertices(tj):
    return sum(len(a) for a in tj["arcs"])


def write(path, obj):
    b = json.dumps(obj, separators=(",", ":")).encode("utf-8")
    path.write_bytes(b)
    return {"file": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}


def build_states():
    d = latest("hdx_cod_ab")
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    zname = next(f for f in man["files"] if f["file"].endswith(".zip"))
    raw = zipfile.ZipFile(d / zname["file"]).read("nga_admin1.geojson")
    fc = json.loads(raw)
    feats = [{"type": "Feature", "geometry": f["geometry"],
              "properties": {"state_pcode": f["properties"]["adm1_pcode"], "state_name": f["properties"]["adm1_name"]}}
             for f in sorted(fc["features"], key=lambda f: f["properties"]["adm1_pcode"])]
    before_vertices = sum(n_vertices_geojson(f["geometry"]) for f in feats)
    topo = topojson.Topology({"type": "FeatureCollection", "features": feats}, prequantize=QUANTIZE,
                             toposimplify=TOLERANCE_DEG, prevent_oversimplify=True, object_name="states")
    # Repair: near-shore islands (~0.0014 deg from the coast in NG003 Akwa Ibom, NG009 Cross River)
    # overlap their own mainland once the coast is simplified, giving self-intersecting multipolygons.
    # Lowering the tolerance does not fix NG009. Union the parts of each invalid feature (same state
    # only, coastal, never a shared border), then rebuild the topology (quantized, no further simplification).
    simplified = json.loads(topo.to_geojson())
    invalid_raw = [f["properties"]["state_pcode"] for f in simplified["features"] if not shape(f["geometry"]).is_valid]
    repaired = []
    for f in simplified["features"]:
        g = shape(f["geometry"])
        if not g.is_valid:
            g = unary_union(list(getattr(g, "geoms", [g])))
        repaired.append({"type": "Feature", "geometry": mapping(g), "properties": f["properties"]})
    topo = topojson.Topology({"type": "FeatureCollection", "features": repaired}, prequantize=QUANTIZE,
                             toposimplify=0, object_name="states")
    tj = json.loads(topo.to_json())
    back = json.loads(topo.to_geojson())
    out = {f["properties"]["state_pcode"]: shape(f["geometry"]) for f in back["features"]}
    src = {f["properties"]["state_pcode"]: shape(f["geometry"]) for f in feats}
    invalid = [p for p, g in out.items() if not g.is_valid]
    empty = [p for p, g in out.items() if g.is_empty]
    overlap = sum(a.intersection(b).area for a, b in itertools.combinations(out.values(), 2))
    area_change = {p: round(abs(out[p].area - src[p].area) / src[p].area, 5) for p in out}
    worst = max(area_change, key=area_change.get)
    rec = write(OUT / "nga_states.topo.json", tj)
    rec.update({"source": f"data/raw/hdx_cod_ab/{d.name}/{zname['file']} -> nga_admin1.geojson",
                "source_sha256": zname["sha256"], "source_geojson_bytes": len(raw),
                "features": len(tj["objects"]["states"]["geometries"]),
                "vertices_before": before_vertices, "vertices_after_arcs": topo_vertices(tj),
                "simplification": {"algorithm": "Douglas-Peucker on shared arcs (topology-preserving)",
                                   "tolerance_degrees": TOLERANCE_DEG, "prevent_oversimplify": True,
                                   "prequantize": QUANTIZE},
                "invalid_after_simplify_before_repair": invalid_raw,
                "repair": "union of own parts for invalid features, then topology rebuilt without simplification",
                "invalid_after_simplify": invalid, "empty_after_simplify": empty,
                "pairwise_overlap_area_deg2": overlap,
                "max_area_change_ratio": {"state_pcode": worst, "ratio": area_change[worst]}})
    return rec


def build_tiles():
    lines = (ROOT / "data" / "reference" / "tile_grid_layout.csv").read_text(encoding="utf-8").splitlines()
    rows = list(csv.DictReader(l for l in lines if not l.startswith("#")))
    feats = []
    for r in rows:
        x0 = TILE_ORIGIN[0] + int(r["col"]) * TILE_STEP
        y1 = TILE_ORIGIN[1] - int(r["row"]) * TILE_STEP
        feats.append({"type": "Feature", "geometry": mapping(box(x0, y1 - TILE_SIZE, x0 + TILE_SIZE, y1)),
                      "properties": {"state_pcode": r["state_pcode"], "state_name": r["state_name"],
                                     "row": int(r["row"]), "col": int(r["col"])}})
    feats.sort(key=lambda f: f["properties"]["state_pcode"])
    topo = topojson.Topology({"type": "FeatureCollection", "features": feats}, prequantize=False, object_name="tiles")
    tj = json.loads(topo.to_json())
    rec = write(OUT / "nga_tiles.topo.json", tj)
    rec.update({"source": "data/reference/tile_grid_layout.csv (own design)", "features": len(feats),
                "tile": {"origin_lonlat": TILE_ORIGIN, "step_deg": TILE_STEP, "size_deg": TILE_SIZE}})
    return rec


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    states, tiles = build_states(), build_tiles()
    man = {"built_by": "scripts/build_geometry.py",
           "tools": {"python": sys.version.split()[0], "topojson": version("topojson"), "shapely": shapely.__version__},
           "outputs": [states, tiles]}
    (OUT / "geometry_manifest.json").write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")
    for r in man["outputs"]:
        print(f"  {r['file']}: {r['features']} features, {r['bytes']:,} bytes"
              + (f", vertices {r['vertices_before']:,} -> {r['vertices_after_arcs']:,}, invalid {r['invalid_after_simplify']}"
                 if "vertices_before" in r else ""))


if __name__ == "__main__":
    main()
