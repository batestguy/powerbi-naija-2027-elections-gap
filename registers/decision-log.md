# Decision log

| Date | Decision | Alternatives considered | Rationale |
|------|----------|-------------------------|-----------|
| 2026-11-13 | Keep phase numbering from the brief (0–8); add a one-state thin slice at the start of Phase 3 | Build full model first | Brief asks for end-to-end with simplest assumptions first |
| 2026-11-13 | Deliver as desktop file + walkthrough video; no Power BI service publishing | Free service sharing (viewers need paid licences); Publish-to-web (needs work/school account and admin approval, makes data fully public) | Free, no account dependency, fully re-runnable from the repo; video covers viewers without Windows/Desktop |
| 2026-11-13 | PBIP folder in git; `.pbix` only as a GitHub Release asset | Commit `.pbix` | Keeps binaries and embedded data out of git; release asset can be withheld if a data licence forbids redistribution |
| 2026-11-13 | Pin Python 3.12.13 in project `.venv` via uv | System Python 3.14; conda | Isolated, lockfile-reproducible; 3.12 has the broadest geo-library support |
