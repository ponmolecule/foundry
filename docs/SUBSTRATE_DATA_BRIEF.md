# CharterIQ Substrate — Data Requirements Brief (v1, 2026-07-14)

For the database rebuild workstream. Two consumers drive these requirements: the Foundry
bank model's peer-evidence layer, and CharterIQ's early-warning feature. One ingest serves
both. Decisions already made: window starts 2009Q1 (pre-2009 judged atypical); the peer
cohort universe remains 2010–2023 de novos; the engine is quarterly.

## 1. Scope of the ingest
- **Window:** 2009Q1 → present, quarterly (~70 quarters), refreshed each filing cycle
  (data usable ~35–50 days after quarter-end; amendments picked up on refresh).
- **Universe:** every FDIC-insured filer, **living and dead** — exits are the point.
  Identity spine: RSSD + CERT, with FDIC structure-change history so mergers and charter
  changes can be followed without losing or double-counting institutions.
- **Volume expectation:** ~500–600K bank-quarters; a few GB curated (Parquet-scale), with
  raw FFIEC CDR archives kept cold. Small data; the work is care, not capacity.

## 2. Fields (bank × quarter is the atom; schedule aggregates are the ceiling)
A curated ~150–250 items from the MDRM dictionary, prioritized:
- **RC** — balance sheet totals.
- **RC-C Part I** — loan mix, incl. the CRE/construction detail.
- **RC-N** — past-due and nonaccrual by loan type (the most predictive early-warning schedule).
- **RC-B** — securities incl. amortized cost vs. fair value (unrealized-loss overhang).
- **RC-E** — deposit composition, brokered, maturity buckets.
- **RC-O** — uninsured deposit estimates.
- **RC-R** — capital components and ratios.
- **RI / RI-B** — income statement; charge-offs and recoveries by loan type.
- **RC-M / RC-L** — borrowings; off-balance-sheet exposures.
- **Critical engineering requirement:** a **versioned field-mapping layer.** Item codes
  mutate across form versions (031/041/051 differences, the 2015 RC-R rebuild, CECL-era
  churn). Every field carries: MDRM code(s) by period, form applicability, and the mapping
  rule. This is the bulk of the build effort; starting at 2009 avoids several older
  mutations but not the recent ones.

## 3. Side tables
- **FDIC failed-bank list**, joined by CERT, each failure hand-tagged with a **mechanism**
  (CRE/ADC concentration · liquidity run · rate/duration · fraud · other) so any model
  trained on failures can disclose its training composition.
- **Public enforcement actions** (FDIC, OCC, FRB), joined by institution — the modern
  era's distress label where failures are scarce (2013–2022).
- **Summary of Deposits**, annual — branch counts and local deposit shares (feeds the
  digital-channel flag and market features).
- **Structure changes** — acquisitions with dates (terminal status for the peer extract).

## 4. What each consumer takes from this
- **Peer extract (Foundry):** must remain producible per PEER_EXTRACT_SPEC — the two
  tables (one row per de novo bank; one row per bank-quarter for each bank's first 16
  quarters) plus the hashed manifest. Requires: quarterly history covering the first 16
  quarters of every 2010–2023 de novo; charter/established dates; terminal status + date;
  SOD branch counts; UBPR peer-group assignment. Vintages are frozen files, never edited.
- **Early warning (CharterIQ):** two layers. Primary — **percentile-outlier scoring
  against live peer distributions each quarter** (growth in the tail, NPL formation vs.
  peers, funding mix, unrealized losses vs. capital): regime-free, needs only current +
  trailing 8–12 quarters. Secondary — a hazard/deterioration model trained on 2009+
  failures and enforcement actions, shipped with its mechanism-composition disclosure.
- **Benchmark strip (Foundry warnings, pilot scope):** current-quarter distributions for
  the assumption-warning thresholds; same tables, prompt refresh.

## 5. Sequencing recommendation
Build **narrow v1 first**: 2010+, ~40 fields, de novos + their peer-group cohorts only —
enough to produce the peer extract and retire Foundry's SYNTHETIC watermark. Days, not
weeks. The full 2009+ / 250-field / all-filers build proceeds behind it on its own
schedule. The pilot never waits on the twenty-year build.

## 6. The one-line contract
Whatever else the new schema does, it must be able to answer: *"for any insured bank,
give me its curated quarterly history, its identity lineage, and how its story ended."*
Everything above is that sentence, itemized.
