# De Novo Trajectory Extract — Specification v1.0

**Purpose.** Replace Foundry's synthetic 43-bank peer fixture with real reference data:
one table of U.S. de novo banks and their first 12–16 quarters, sufficient to (a) place a
charter candidate in the pre-registered five-feature space, (b) compare its assumptions
against kernel-weighted cohort distributions, and (c) retain non-survivors in the evidence
base. Producer: CharterIQ Call Report warehouse. Consumer: `foundry/peers.py` loader
(single swap point; nothing above it changes).

**Authority note.** Schedule/item references below are authoritative; MDRM mnemonics are
indicative for the FFIEC 041/051 (RCON) series — verify against the current MDRM dictionary
at build time, and use RCFD equivalents where an institution files the 031. Forms evolve;
the item semantics are the contract.

---

## 1. Universe

- **Inclusion:** every FDIC-insured commercial bank or savings institution whose
  *established date* (FDIC institutions file, `ESTYMD`) falls in **2010-01-01 … 2023-12-31**
  and which filed at least **4** quarterly Call Reports.
- **De novo test:** newly organized charters only. Exclude charter conversions,
  thrift-to-bank flips, and shell/bridge charters created for acquisitions (FDIC structure
  data `CHANGECODE` history; exclude where the first event is a conversion or absorption).
- **Keep the dead.** Failed and acquired institutions are *retained* — survivorship
  discipline is the point.
- **Manifest:** every excluded candidate is listed with its exclusion reason in a companion
  `exclusions_<vintage>.csv`. Nothing is silently dropped.
- **Tracking window:** quarters 1..16 from the first filed Call Report ("Q1" = first filing).

## 2. Deliverables

Primary: `denovo_trajectories_<vintage>.csv` — **one row per bank** (schema §5).
Companion (optional but requested): `denovo_quarters_<vintage>.csv` — one row per
bank-quarter with the raw inputs of §4, enabling future metrics without re-extraction.
Both UTF-8 CSV, plus `manifest_<vintage>.json` carrying: vintage date, universe counts,
exclusion tally, source file versions, and the SHA-256 of each CSV. Foundry's loader
validates schema + hash; the cohort_id will embed the vintage and hash prefix, and the
"SYNTHETIC — ILLUSTRATIVE" watermark retires for this dataset, replaced by a provenance
line citing this manifest.

## 3. Feature vector (computed at year 3 = quarter 12; if terminal before Q12, at the
last filed quarter, with `features_at_q` recording which)

| Feature | Definition | Source |
|---|---|---|
| `log_assets_yr3` | log10(total assets, **dollars**) | RC item 12 (RCON2170) |
| `consumer_loan_share` | (RC-C Part I items 6.a credit cards + 6.b other revolving + 6.c automobile + 6.d other consumer) / total loans & leases | RC-C 6.a–6.d (RCONB538, B539, K137, K207) / RC-C 12 (RCON2122) |
| `fee_income_share` | total noninterest income / (net interest income + total noninterest income) | RI 5.m (RIAD4079), RI 3 (RIAD4074) |
| `core_funding_share` | core deposits / total assets, **UBPR core-deposit definition** (total deposits less time deposits > $250k less fully insured brokered per UBPR User's Guide) — CharterIQ's existing UBPR alignment governs | RC-E (RCON2200; memo items incl. J474; brokered RCON2365) per UBPR defn |
| `digital_channel` | 1.0 if ≤ 2 offices at year 3, else 0.0 (offices from FDIC Summary of Deposits, matched on CERT). Optional refinement: 0.5 for 3–5 offices — if adopted, adopt for *all* rows | FDIC SOD |

## 4. Comparison metrics (trajectory-timed as noted)

| Metric | Definition | Source |
|---|---|---|
| `deposit_growth_yr1` | deposits(Q4) / deposits(Q1) − 1 | RC-E / RCON2200 |
| `cost_of_deposits_spread_yr1` | (4·avg quarterly interest expense on deposits over year 1 / avg total deposits over year 1) − avg policy rate over the same four quarters (EFFR through 2018Q1, SOFR after; FRED quarterly averages; state the series used in the manifest) | RI 2.a (RIAD4170 family), RCON2200, FRED |
| `efficiency_q12` | trailing-4-quarter noninterest expense / (net interest income + noninterest income), evaluated at Q12 | RIAD4093, RIAD4074, RIAD4079 |
| `card_nco_mature` | (charge-offs − recoveries on credit cards, quarters 9–12 annualized) / avg credit-card balances over quarters 9–12; **null** if no card book | RI-B Part I 5.a (RIADB514/B515), RCONB538 |
| `cac_per_funded_account`, `opex_per_active_acct` | **Not derivable from public filings** (Call Reports carry no account counts). Columns present, permitted null; these metrics participate only where client-side disclosure exists. Do not proxy. | — |

## 5. Primary schema (one row per bank)

`cert` (int) · `rssd_id` (int) · `name` (str) · `established` (date) ·
`first_call_quarter` (YYYYQn) · `quarters_filed` (int, ≤16 tracked) ·
`features_at_q` (int) · `log_assets_yr3` · `consumer_loan_share` · `fee_income_share` ·
`core_funding_share` · `digital_channel` · `deposit_growth_yr1` ·
`cost_of_deposits_spread_yr1` · `efficiency_q12` · `card_nco_mature` (nullable) ·
`cac_per_funded_account` (null) · `opex_per_active_acct` (null) ·
`terminal` (enum: `operating` / `failed` / `acquired`) · `terminal_quarter` (YYYYQn or null) ·
`terminal_source` (str: FDIC failed-bank list ref, or structure-change transaction ref)

All ratios as decimals (0.0435, not 4.35). Money in dollars before the log.

## 6. Quality rules

1. Dedupe on `rssd_id`; where CERT changes mid-trajectory (rare), follow RSSD.
2. A bank acquired at quarter *q* has metrics computed only from quarters ≤ *q*; year-1
   metrics null if terminal before Q4 (row retained — terminal status is the datum).
3. No winsorizing, no outlier trimming: the kernel weighting and the bounded radius are
   the outlier policy. Extract raw.
4. Expected magnitude: post-2010 de novo formation is thin — anticipate roughly **100–200
   qualifying rows**, not thousands. Sparse regions will trigger INSUFFICIENT EVIDENCE
   disclosures in Foundry; that is correct behavior, not a data defect.

## 7. Acceptance

Foundry-side on receipt: schema validation, hash recorded, loader swap behind
`foundry/peers.py`, then a frozen re-verification demo: one run each of a dense-region
client and a sparse-region client, confirming (a) admissible cohort with real members,
(b) mandatory disclosure fires where n < 8, (c) hashes stable across two loads of the
same vintage. Vintage updates are new files with new manifests — never edits in place.
