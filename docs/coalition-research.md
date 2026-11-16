# Coalition research (preliminary) — 2026-11-16

Purpose: evidence for the coalition feature (user decision 2026-11-16: a coalition is at most two 2023 candidates'
parties; head to head is coalition vs one candidate, or coalition vs coalition; a "how many of the partner's voters
follow" slider, non-followers stay home). Status: **research notes, not a data release**. Nothing here is in the model.
Gathered by a research pass on 2026-11-16 (web search and page fetches); items marked *unverified* came from search
summaries only.

## 1. Alignments for 2027 (as of 2026-11-16)

| Person | Party / role | Sources (date) | Note |
|---|---|---|---|
| Bola Tinubu | APC, running mate Shettima | ThisDay INEC final list (~2026-09-13) https://www.thisdaylive.com/2026/09/13/2027-tinubu-atiku-obi-15-others-make-inecs-final-list-of-presidential-candidates/ ; Nairametrics 2026-09-12 https://nairametrics.com/2026/09/12/inec-releases-final-list-of-18-presidential-candidates-for-2027-elections/ | Confirmed |
| Atiku Abubakar | ADC, running mate Amaechi | Channels TV 2026-05-25; ThisDay list (Sep 2026) | **At risk**: Federal High Court Abuja, 2026-11-05, nullified the ADC leadership's decisions incl. the presidential primary (Pulse) https://www.pulse.ng/story/atiku-abubakar-adc-ticket-nullified-court-ruling-2026110511553453175 ; ADC appealing. INEC to abide by a final ruling (Legit.ng 2026-11-12, *unverified*) |
| Peter Obi | NDC presidential candidate | Africanews 2026-05-31; NDC 2026-05-31 https://ndcnigeria.com/news/ndc-special-convention-affirms-peter-obi-kwankwaso-ticket-for-2027-c548f05b | Confirmed |
| Rabiu Kwankwaso | NDC, **Obi's running mate** | NDC 2026-05-31; ThisDay list; Premium Times 2026-05-09 | Africanews 2026-05-31 names a different running mate; three other sources say Kwankwaso — treated as outlier, unresolved |

Others on the ballot: PDP's candidate is Sandy Onor (not Atiku); Seyi Makinde (APM). INEC list: 18 candidates (one
summary says 19; unresolved). Election date: presidential 16 Jan 2027 (Wikipedia "2027 Nigerian general election";
INEC revised timetable via search, *not fetched*). Primaries and nominations closed; campaign runs to mid-Jan 2027.

Pairings among the four 2023 candidates:
- **Obi + Kwankwaso: real** — one NDC ticket since 2026-05-31. The coalition feature's first real case.
- Atiku + Obi: talks reported, no deal; Obi (2026-09-10): alliance must be "party-to-party" https://thewillnews.com/2027-obi-rules-out-personal-deal-with-atiku-says-opposition-alliance-must-be-party-to-party/
- Atiku + Kwankwaso: past (both ADC, Mar–May 2026); ended.
- Atiku + Makinde (not a 2023 candidate): talks reported 2026-11-15 (Naija News, citing Sunday Punch), no deal.
- Tinubu + anyone: nothing found. New INEC party registrations or mergers: none found.

## 2. The 2013 APC merger: 2011 vs 2015 by state

Data: `reports/coalition_2011_2015_preliminary.csv` (37 rows).
- 2011 columns: INEC results site, Wayback capture 2011-05-01
  https://web.archive.org/web/20110501010957/http://www.inecnigeria.org/results/presidential/states.php . No licence
  text. Second copy (EiE Nigeria, https://eie.ng/2011-general-election/) matches but is almost certainly a copy of
  INEC, so not independent. `valid2011` = sum of the 20 parties' state figures.
- 2015 columns: Wikipedia "2015 Nigerian general election", revid 1385023157, By state table (CC BY-SA), citing INEC.
  INEC's own 2015 summary PDF is image-only and was not cross-checked. **No independent second copy yet.**
- Checks: 2011 state sums = INEC national for CPC, PDP, ANPP; **ACN state sum is 11,850 short of the national
  2,079,151** (state not found). 2015 state sums = national for APC and PDP.
- Not yet a proper snapshot: must be re-pulled by script with a manifest (raw → staging) before any use in the model.

Rough first look (arithmetic on the file above, not a published estimate):
- National: CPC + ACN + ANPP 2011 = 15,211,016; APC 2015 = 15,424,921 (×1.01), while all valid votes fell from 38.2 M
  to 28.6 M.
- By state, APC 2015 votes ÷ combined 2011 votes: median 1.19 (middle half 0.95–2.11). The merged party usually got
  **more** than its parts, because PDP also lost voters and politicians to it (incumbent fatigue, defections). So 2015
  cannot isolate "how many of a partner's voters follow"; it bounds it only loosely.
- Where the partner was the main force (ACN in the South West, ANPP in Kano/Yobe), APC's 2015 share was at or above the
  combined 2011 share: Osun 60.5% → 59.7%, Ekiti 46.3% → 40.0%, Lagos 32.2% → 54.9%, Kano 82.0% → 89.4%. Read: little
  sign of partner voters refusing to follow, but confounded.

Confounders: Buhari ran both times; incumbent Jonathan in 2015; turnout fell ~25%; insurgency-affected states (Borno,
Yobe, Adamawa) lost many voters; 2011 southern PDP shares near 99% in places (irregularities noted by observers).

## 3. Published evidence on follow rates

None found that gives a percentage of a partner's voters who followed, for Nigeria or comparable cases (Kenya
searched; Ghana, Zambia not). Qualitative studies of the 2015 merger: Saka (2018); Isyaku et al. (2026); Sule et al.
(2018); Owen & Usman (2015, African Affairs); Atanda et al. (2018, Journal of African Elections); EISA JAE 14(2) 2015.

## Implications for the design (for the user to decide)

1. A real two-partner case exists now: Obi (LP 2023) + Kwankwaso (NNPP 2023) on one NDC ticket.
2. No measured follow rate exists to set the default; 2011→2015 suggests partner voters largely followed when the
   merged party had momentum, but cannot give a number. Keep the slider, state that the default is an assumption.
3. Before using 2011/2015 in the report: second independent copy for 2015, resolve the 2011 ACN gap, script the pull.

## Open
Atiku's ADC ticket (court appeal); Obi's running mate discrepancy (Africanews); 18 vs 19 candidates; 2019 Kano by party
(Kwankwaso bloc 2015→2019→2023) not found.
