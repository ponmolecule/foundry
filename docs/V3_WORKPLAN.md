# Foundry v3 Work Plan (plain-language v2, 2026-07-14)

Companion to PROJECT_PLAN.md (the short checklist). This document explains what we're
building, why, and in what order. Sources we're drawing from: Roman's model (already the
core of our engine), Patrick's workbook (tells us how applications and regulators actually
work), the other AI build's capital tab (already adopted), the peer-governance draft, and
the pilot dates: demo to Patrick July 24, checkpoint July 29, Klaros decides Aug 11.

---

## Part I — The CharterIQ database rebuild: where we need it, and whether it delays us

CharterIQ's database is being restructured in a separate workstream. Five Foundry features
eventually need data from it. For each: what we need, when, and what we do in the meantime.

| # | Foundry feature | What it needs from CharterIQ | When | What we use until then | Delayed? |
|---|---|---|---|---|---|
| I-1 | Real peer data (so we can remove the "SYNTHETIC" watermark) | The de novo bank history table described in PEER_EXTRACT_SPEC | August, after the checkpoint | The invented 43-bank dataset, clearly watermarked | **No** |
| I-2 | UBPR peer-group comparison (the backup when a custom cohort is too small) | UBPR peer-group stats | Same time as I-1 | Leave it out for now | **No** |
| I-3 | Retrodiction (run a real bank's history through our model to prove accuracy) | 2–3 real banks' quarterly filings | July 29 | Download the filings straight from the FFIEC website — doesn't touch CharterIQ at all | **No** |
| I-4 | Warning thresholds tied to live FDIC percentiles | A percentile lookup | Aug 11 phase | Synthetic percentiles, watermarked | **No** |
| I-5 | Filling Patrick's PEER tab with real numbers | Same as I-1/I-2 | After the pilot | Fill it with watermarked synthetic numbers for the demo | **No** |

**Bottom line: the database rebuild does not delay us.** Everything for July 24 and July 29
runs on the engine plus clearly-labeled synthetic data, or on files downloaded directly
from the FFIEC.

**The risk actually runs the other way:** if the rebuilt database throws away things the
peer extract needs, our August work gets harder. So the first action item is a short memo
from Ponmile to the database team listing what the new design must keep:
(1) full quarterly history back to 2010, not just the latest quarter; (2) each bank's
charter date; (3) whether/when each bank failed or was acquired; (4) branch counts by year;
(5) each bank's UBPR peer-group number; (6) the ability to export the two tables the
extract spec describes. Six bullets — now expanded into docs/SUBSTRATE_DATA_BRIEF.md (window 2009Q1+, field priorities incl. RC-N/RC-O/RC-B, mechanism-tagged failures, enforcement actions, versioned field mapping, narrow-v1-first sequencing). Hand the brief, not just the bullets. As long as those survive, Foundry only touches
CharterIQ at one point in the code (peers.py), so nothing else can break.

---

## Part II — What Patrick's model teaches us, and what we do about each lesson

| # | Lesson from his workbook | What we do in Foundry |
|---|---|---|
| II-1 | **Charter applications think in calendar months** — his model runs monthly, with dated events and a start month; ours runs in abstract quarters | Now: the importer converts his monthly numbers to quarterly (multiply by 3; yearly rates spread over 4 quarters), and writes the conversion into the config so nothing is hidden. **Decided 2026-07-14: the engine stays quarterly.** Monthly inputs are converted at import (documented in the config); outputs report quarters, with the start month shown so calendar timing stays readable |
| II-2 | **The model starts before the bank opens** — he has a pre-opening expense schedule, application fees, day-one balances, and a minimum day-one capital check | Add a "pre-opening" section to the config; opening equity = money raised minus pre-opening spending; day-one starting balances; a pre-opening check on the Overview page |
| II-3 | **Capital comes in rounds** — he has three dated raises | Let the engine accept capital injections in later quarters, not just at the start |
| II-4 | **Deliverables must look like regulatory forms** — his tabs are named RC, RI, RC-R; he has an average-balance sheet and a concentration checker | Make Foundry's outputs match his tab layouts (we have Patrick's row-by-row worksheets); add the average-balance table and the concentration checks |
| II-5 | **Costs have real structure** — headcount × salary, named cost lines, FDIC/OCC fees that scale with bank size | Add a proper expense section: staff counts by year, named cost lines, and the FDIC/OCC fees computed from assets |
| II-6 | **Fee businesses are priced per account and per transaction** — and Patrick himself said: for version 1, just take fee income as a flat monthly number | For now the importer converts his per-account math into flat dollar amounts. Native per-account inputs come later |
| II-7 | **One settings page a banker can read** — his CONTROL tab | Our Configuration tab gets the same layout: who the client is, the timeline, and which modules this bank uses |
| II-8 | **Risk-weighting can start simple** — five buckets (0%/20%/50%/100%/150%) | Use his five buckets as the input format for the risk-weighted capital build |
| II-9 | **His inputs and ours are nearly the same language** — about 90% of his 165 inputs already have a matching field in our config | This is the good news: importing his workbook is mostly unit conversion, not new engineering |
| II-10 | **What NOT to copy** — thresholds typed into random cells, toggles wired to nothing, hidden stub tabs, no saved history | We already solved these (versioned rule parameters, tested modules, the freeze registry). Don't import the bad habits |

---

## Part III — The full inventory, three buckets

### A. What we have that's good — keep it, show it off (no work needed)
A1 An engine that gives the same answer every time, with fingerprints (hashes) proving it.
A2 39 automated tests plus 9 locked example banks that must reproduce to within $1,000 per
line per quarter on every change. A3 Freeze a run, come back later, click Re-verify, watch
it reproduce exactly — the live demo moment. A4 Two ways in: a config file or an Excel
intake workbook; incomplete input gets rejected with a list of questions instead of guesses.
A5 Any assumption can be overridden for any single quarter. A6 The hard product mechanics:
mortgage servicing (with the capital deduction), fair-value election, loan sales, warehouse.
A7 Stress testing with adjustable dials, every constraint re-checked in every scenario, and
an estimate of the capital needed to cure a breach. A8 Automatic challenge flags, including
the "these two assumptions can't both be true" checks. A9 The peer-comparison method: rules
fixed in advance, honest about small samples, failed banks kept in the data. A10 The
examiner Q&A generator. A11 Regulatory numbers kept in one versioned, cited place — with a
watch list for proposed rules. A12 A register of what the model deliberately doesn't do.
A13 Every output row labeled with its Call Report line. A14 The capital math shown
step-by-step and proven to match the engine. A15 Three intact versions (v2 / v2.1 / v3) —
nothing old ever broke. A16 A documented, login-protected API.

### B. What Patrick has that we don't — build it (size · deadline · notes)
| ID | What | Size | Deadline | Notes |
|---|---|---|---|---|
| B-1 | **Importer for his input style** (flat dollars per month; rates set per year) | Medium | **Jul 24** | Multiply monthly by 3; spread yearly rates over quarters; convert dollar deposit growth using our per-quarter overrides; write every conversion into the config file |
| B-2 | **Pre-opening phase** (expenses, application fees, day-one balances, minimum-capital check) | Medium | Jul 24 simple / Jul 29 full | Simple version: subtract documented pre-opening spending from opening capital. Full version: a proper pre_open config section plus an Overview check |
| B-3 | **Capital raises after opening** (his three dated rounds) | Medium | **Jul 29** | Equity injections in later quarters; add a test bank that uses it |
| B-4 | **Risk-weighted capital** (five weight buckets → CET1 / Tier 1 / Total ratios + PCA categories, laid out like his RC-R tab) | Medium-Large | **Jul 29** | Already promised in the pilot; each product gets a weight-bucket tag in the config |
| B-5 | **Average-balance-and-rate table** (the classic examiner view) | Small | Jul 29 | We already compute every number it needs; it's just a new page |
| B-6 | **Concentration checks** (CRE, C&I, brokered deposits, loans-to-deposits vs. their limits) | Small-Med | Jul 29 | Ratios plus limits stored in the versioned rule set, with sources; breach raises a flag |
| B-7 | **Structured expenses** (staff × salary by year; named cost lines; FDIC/OCC fees that scale with assets) | Medium | Jul 29 for the FDIC/OCC fees; August for the rest | New expense lines in the engine |
| B-8 | **Per-account / per-transaction fee inputs** (his five payment rails, account fees, trust fees) | Small now / Medium later | Jul 24 (converted to flat dollars by the importer) / August (native fields) | Patrick's own advice blesses the flat-dollar interim |
| B-9 | **Output pages shaped like his RC and RI tabs** | Medium | **Jul 24** | His worksheets tell us exactly which row is which; RC-R comes with B-4 |
| B-10 | **Client header** (client name, engagement ID, preparer, version) | Small | Jul 24 | A few config fields shown at the top of Configuration |
| B-11 | **CD maturity ladders** (his time deposits have terms; ours don't) | Medium | **Decide Aug 11** | More realism vs. more scope — a decision, not a default; note it in the caveat register meanwhile |
| B-12 | **AFS securities with AOCI** (market-value swings hitting equity) | Large | **Decide Aug 11** | Interacts with B-4; caveat-registered until decided |
| B-13 | Holding-company view | — | Parked | It's an empty stub even in his workbook |

### C. What we have that needs adjusting, based on his
| ID | Adjustment | Size | Deadline |
|---|---|---|---|
| C-1 | Configuration tab laid out like his CONTROL tab: client header (B-10), timeline, and a list of which modules this bank actually uses | Small-Med | Jul 24 |
| C-2 | Decide: fold the average-balance view into the Ratios tab, or give it its own tab (B-5) — one or the other, not both | Small | Jul 29 |
| C-3 | Let users enter fee income as a plain dollar amount per quarter, not only as % of balances | Small | Jul 29 |
| C-4 | Let users type rates per year and have them spread across quarters automatically | Small | Jul 29 |
| C-5 | Day-one starting balances (cash, premises, other) as explicit config fields | Small | Jul 24 |
| C-6 | Link the "what this model doesn't do" register from the Configuration tab, where clients will look | Small | Jul 29 |
| C-7 | Add a second saved bank: Patrick's own workbook, imported — the proof the importer works | Small | Jul 24 |

---

## Part IV — Order of work

**Sprint 1, finishes July 24 (the demo).** In order: B-10 and C-5 (new config fields) →
B-1 the importer (Patrick's workbook in; every conversion documented) → C-1 (Configuration
page layout) → B-9 (RC and RI output pages) → the gap-flagging conversation ("this bank
has deposits but no loans") → the Prairie Digital import (already planned) → saved-bank
roster v0 (needs the Railway volume) → write and rehearse the demo script around the seven
contrasts (his empty PEER tab vs. our Peer Cohort; his tax =0 vs. our NOL engine; his
stress stub vs. our stress engine; his mortgage stub vs. our shipped module; his 10 checks
vs. our re-verify-live moment; opening on his own no-loans default bank; and the CBLR rule
drift, held in reserve). Rule unchanged: nothing is "done" without a green test run.

**Sprint 2, finishes July 29 (the checkpoint).** B-4 risk-weighted capital → B-3 staged
raises → B-5 average-balance table → B-6 concentration checks → B-7 FDIC/OCC fees →
C-2/C-3/C-4/C-6 → retrodiction v0 (filings downloaded straight from FFIEC) → hardening,
because Klaros will use it unsupervised while Ponmile travels.

**Sprint 3, August window → Aug 11.** Load the real peer data when CharterIQ's rebuild
delivers it (remove the watermark, do a real parameter freeze, add the UBPR backup) →
ratify the peer-governance rules → build the
deferred-tax layer (four known pieces: the 80% usage cap on loss carryforwards; the
temporary-difference DTA with its 25% capital threshold; the valuation-allowance release
when the bank turns profitable; state taxes or an explicit federal-only note) → decide
B-11 and B-12.

**Waiting on Ponmile this week:** the Railway volume (so saved runs survive redeploys);
the six-bullet memo to the database team; nothing else — the go-ahead for importing
Patrick's workbook is given by this plan.
