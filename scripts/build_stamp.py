"""Build stamp: a fingerprint of everything a Phase 4 result depends on (review 2026-11-18, SHOULD-FIX 4).

files: SHA-256 of the model files (every .tmdl), the staging and reference tables, the Phase 4 check script and the
       engine script. Line endings are normalised first, so a git checkout (CRLF) and a fresh build (LF) agree.
live:  SHA-256 of the measure names + expressions in the model Desktop has loaded (pbi_engine.ps1 -Action Stamp).

A saved result is reused, or part files are combined, only when both match now. What this does not prove: that the
live model equals the files on disk; only that neither changed since the result was written.
"""
import hashlib, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PS = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "pbi_engine.ps1")]


def stamp_inputs():
    return sorted([*(ROOT / "pbip" / "NaijaElectionsGap.SemanticModel" / "definition").rglob("*.tmdl"),
                   *(ROOT / "data" / "staging").glob("*.csv"), *(ROOT / "data" / "reference").glob("*.csv"),
                   ROOT / "scripts" / "validate_phase4.py", ROOT / "scripts" / "pbi_engine.ps1"])


def files_hash():
    h = hashlib.sha256()
    for f in stamp_inputs():
        h.update(f.relative_to(ROOT).as_posix().encode() + b"\0")
        h.update(f.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def live_hash():
    r = subprocess.run(PS + ["-Action", "Stamp"], capture_output=True, text=True, encoding="utf-8", timeout=420)
    if r.returncode:
        raise RuntimeError(f"pbi_engine.ps1 -Action Stamp failed:\n{r.stderr or r.stdout}")
    return json.loads(r.stdout.lstrip("﻿"))


def build_stamp():
    return {"files_sha256": files_hash(), "files": len(stamp_inputs()), "live_model": live_hash()}


def same_build(a, b):
    """True when two stamps describe the same build (files and live model)."""
    return bool(a and b) and a.get("files_sha256") == b.get("files_sha256") and \
        (a.get("live_model") or {}).get("measures_sha256") == (b.get("live_model") or {}).get("measures_sha256")
