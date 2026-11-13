# Environment note (Phase 0)

Checked: 2026-11-13, on the author's machine. Commands used are PowerShell inventory checks
(`Get-AppxPackage`, `Get-Command`, `py -0p`, `Invoke-WebRequest`) run from this repo.

## Delivery target (decided 2026-11-13)
**Desktop file + recorded walkthrough video.** No Power BI service publishing.
- Source of truth in git: the PBIP project folder in `pbip/` (no data cache committed).
- Downloadable `.pbix`: attached to a GitHub Release, not committed (size + data-licence reasons).
- Video: linked from the README. Recorded with Snipping Tool or Xbox Game Bar (both installed).

Consequence: no service-tier limits apply (refresh schedules, Publish-to-web, tenant settings).
The constraint that matters instead is **viewers need Power BI Desktop on Windows**, so the video
must carry the story for everyone else.

## Inventory

| Item | Found | Notes |
|---|---|---|
| OS | Windows 11 Pro, build 22000 (21H2) | 21H2 is past Microsoft's support end; not a blocker for this project |
| RAM | 15.9 GB | Adequate for a 774-LGA model |
| Free disk (D:) | ~56 GB | Adequate |
| Power BI Desktop | Microsoft Store edition, 2.159.1231.0 | Store edition auto-updates; record version in each release |
| Power BI CLIs (`powerbi-report-author`, `powerbi-desktop`, pbi-tools, Tabular Editor) | Not installed | PBIR files can still be edited by hand; decide in Phase 3 whether a CLI is worth adding |
| Python for data prep | **Pinned: CPython 3.12.13 via uv 0.11.28, project `.venv`** | `pyproject.toml`, `.python-version`, `uv.lock` committed |
| Other Python on PATH | 3.14 (system), miniconda | **Do not use** for this project |
| R | 4.5.2 | Not planned for use |
| Node.js | Installed | Candidate for `mapshaper` (geometry simplification) in Phase 2 — not installed yet |
| GDAL `ogr2ogr` | Not installed | Not needed if mapshaper or Python geo libs are used |
| Screen recording | Snipping Tool 11.2608, Xbox Game Bar 7.326 | Both can record a window to MP4 |

## Network
- Real host (example.com): HTTP 200, response saved to disk.
- Impossible host (`no-such-host-zz9.invalid`): fails with "No such host is known" — so failures
  later will be about the target, not this machine.
- raw.githubusercontent.com: HTTP 200.

## Still to confirm by hand in Power BI Desktop (cannot be checked from the command line)
1. **File > Options > Preview features**: "Power BI Project (.pbip) save option" and
   "Store reports using enhanced metadata format (PBIR)" — on, if still listed (newer versions
   may have made them default).
2. **Map visual choice.** For a desktop-only, offline-checkable file the leading candidate is the
   **Shape Map** visual with our own TopoJSON (preview feature — enable it in the same menu).
   Azure Maps needs a sign-in and internet; the old Bing-based maps are being retired.
   Decide in Phase 3 after the thin slice.

## Adaptations to later phases
- Phase 6 "test the published version" becomes: open the release `.pbix` on a clean machine/profile
  and check it renders; watch the video end to end against the QA list.
- Phase 7 "publish" becomes: tag a release with the `.pbix`, frozen data vintage, and video link.
- Phase 2 geometry output must be **TopoJSON** if Shape Map is chosen.
