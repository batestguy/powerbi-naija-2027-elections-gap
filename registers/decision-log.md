# Decision log

| Date | Decision | Alternatives considered | Rationale |
|------|----------|-------------------------|-----------|
| 2026-11-13 | Keep phase numbering from the brief (0–8); add a one-state thin slice at the start of Phase 3 | Build full model first | Brief asks for end-to-end with simplest assumptions first |
| 2026-11-13 | Deliver as desktop file + walkthrough video; no Power BI service publishing | Free service sharing (viewers need paid licences); Publish-to-web (needs work/school account and admin approval, makes data fully public) | Free, no account dependency, fully re-runnable from the repo; video covers viewers without Windows/Desktop |
| 2026-11-13 | PBIP folder in git; `.pbix` only as a GitHub Release asset | Commit `.pbix` | Keeps binaries and embedded data out of git; release asset can be withheld if a data licence forbids redistribution |
| 2026-11-13 | Pin Python 3.12.13 in project `.venv` via uv | System Python 3.14; conda | Isolated, lockfile-reproducible; 3.12 has the broadest geo-library support |
| 2026-11-13 | Map visual = Shape Map with own TopoJSON | Azure Maps; legacy Bing maps | GA since 2.155, works offline without sign-in; fits desktop-only delivery |
| 2026-11-13 | Geometry = HDX COD-AB `nga_admin2`; join on `adm2_pcode` via a name+state→P-code crosswalk | geoBoundaries (names only, misspelt); join on names | P-codes remove the duplicate-name trap (Bassa, Ifelodun, Irepodun, Nasarawa, Obi, Surulere appear in two states each) |
| 2026-11-13 | Threshold default: candidate has ≥25% of valid votes in ≥24 of 37 units (36 states + FCT counted as a unit); show 25-of-37 as a sensitivity | Treat FCT as a separate mandatory 25% test | 2023 tribunal + Supreme Court held FCT has no special status and is treated like a state; the court did not state the number, so the number is our reading and is labelled as such |
