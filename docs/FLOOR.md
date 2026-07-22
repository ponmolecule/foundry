# Klaros_Patrick_Roman_BareMinimum
## The Foundry v3 Floor: Complete Capability & Defect Inventory of Both Predecessor Models

**Sources (read in full, formula-by-formula / line-by-line):**
- `Klaros_Bank_Charter_Financial_Model_v1_0_Patrick.xlsx` — 29 sheets, both openpyxl passes (formulas + cached values), all 44 named ranges, embedded Apps Script
- `klaros-pro-forma-modeler.html` — complete ~82KB engine + UI JavaScript

**Purpose.** This document is the floor. Foundry v3 must be able to answer *every* "I did this — can Foundry do that too?" question from either author with "yes," and where the predecessor implementation is defective, with "yes — and I caught and fixed the defect in yours." Every capability below is stated as it exists in the source, at cell/function granularity. Defects carry IDs (`D-P##` Patrick, `D-R##` Roman) and are cross-referenced in the floor checklist (Part III).

**Rules of use.**
1. Nothing here is optional. Absorb, replicate-and-fix, or consciously supersede with a documented equivalence — never silently drop.
2. Per the 2026-07-14 decision, the Foundry engine clock is QUARTERLY, permanently. Patrick's monthly structures are absorbed as **import-time conversions with documented conventions**, never as a native monthly clock.
3. Per REG_PARAMS standing rule: every regulatory threshold in this document enters Foundry via the parameter registry with name/date/status — never as an inline literal.

---

# PART I — PATRICK'S MODEL: COMPLETE INVENTORY

## I.0 Workbook facts

**Sheets (29), in order, with visibility state:**

| # | Sheet | State | Role |
|---|---|---|---|
| 1 | COVER | visible | Branding, metadata echo, navigation, model status, quick-stats dashboard |
| 2 | CONTROL | visible | Master configuration panel (6 sections) |
| 3 | TIME | visible | Master date spine (decorative — see D-P15) |
| 4 | CHECKS | visible | 10-assertion diagnostic panel + master status |
| 5 | ASSM_BS | visible | Balance sheet assumptions (88 rows) |
| 6 | ASSM_IS | visible | Income statement assumptions (56 rows) |
| 7 | ASSM_CAP | visible | Capital assumptions (23 rows) |
| 8 | PRE_OPEN | visible | Pre-opening build (4 sections) |
| 9 | RC | visible | Balance sheet (engine) |
| 10 | RI | visible | Income statement (engine) |
| 11 | ABR | visible | Average balances & rates (engine) |
| 12 | NII_FEE | visible | Non-interest income (engine) |
| 13 | NIE | visible | Non-interest expense (engine) |
| 14 | RC_C | visible | Loan portfolio detail (engine) |
| 15 | DEP | visible | Deposit schedule (engine) |
| 16 | SEC | visible | Securities & cash (engine) |
| 17 | CAP_RAISE | visible | Capital raise schedule (display) |
| 18 | EQ_ROLL | visible | Equity rollforward (engine) |
| 19 | RC_R | visible | Regulatory capital (engine) |
| 20 | CONC | visible | Concentrations & diagnostics (engine) |
| 21 | BHC | **hidden** | Holding company — zero stub |
| 22 | RC_T | **hidden** | Trust/fiduciary — zero stub |
| 23 | INTCHG | **hidden** | Interchange detail — zero stub |
| 24 | BAAS | **hidden** | BaaS/program manager — zero stub |
| 25 | MORT | **hidden** | Mortgage banking — zero stub |
| 26 | CC | **hidden** | Credit card — zero stub |
| 27 | SENS | **hidden** | Sensitivity analysis — zero stub |
| 28 | PEER | **hidden** | Peer benchmark — zero stub with paste-in zone |
| 29 | Script_Code | visible | Google Apps Script source (single cell A1) |

**Named ranges (all 44):**
Metadata: `client_name` (C6), `engagement_id` (C7='KLR-2026-001'), `prepared_by` (C8='Klaros Group'), `model_version` (C9='v1.0'), `projection_date` (C10=DATE(2026,6,29)), `charter_type` (C11='National Bank').
Cadence: `cadence` (C14='Monthly'), `preopening_months` (C15=12), `start_month` (C16=DATE(2026,7,1)); projection years locked at 3 (C17, unnamed).
Scenarios: `label_baseline` (C20), `label_stress1` (C21='Stress 1 — [Advisor to Define]'), `label_stress2` (C22), `stress1_active` (C23='No'), `stress2_active` (C24='No').
Deposit toggles: `tog_retail_dep` (C28=Yes), `tog_mmda` (C29=Yes), `tog_time_dep` (C30=Yes), `tog_brokered` (C31=No), `tog_sweep` (C32=No), `tog_instit_dep` (C33=No).
Loan/asset toggles: `tog_consumer` (C35=No), `tog_cc` (C36=No), `tog_cni` (C37=No), `tog_resi_mtg` (C38=No), `tog_cre` (C39=No), `tog_afs` (C40=No), `tog_htm` (C41=No), `tog_ibcash` (C42=Yes).
Fee toggles: `tog_intchg` (C44=No), `tog_baas` (C45=No), `tog_svc_chg` (C46=No), `tog_trust` (C47=**Yes**), `tog_gos` (C48=No), `tog_other_fee` (C49=No).
Structural toggles: `tog_bhc` (C51=No), `tog_cblr` (C52=Yes), `tog_sens` (C53=No), `tog_peer` (C54=No).
Thresholds: `thr_cet1` (C57=0.065), `thr_t1` (C58=0.08), `thr_total` (C59=0.10), `thr_lev` (C60=0.05), `thr_cblr` (C61=**0.08** — see D-P4).
Display: `unit_scale` (C64='Thousands' — referenced by zero formulas; display metadata only).
Column ranges (on TIME): `rng_PreOpenCols` (C8:N8), `rng_MonthlyCols` (P8:AY8), `rng_QtrCols` (BA8:BL8), `rng_AnnualCols` (BN8:BP8).

**Units:** USD thousands ($000s), currency locked to USD in V1 (CONTROL C65, note at C67).

## I.1 COVER

- Klaros brand block ('◤ KLAROS GROUP'), title "Bank Charter Financial Model," subtitle "Pro Forma Financial Projections — 3 Year (Monthly · Quarterly · Annual)."
- Metadata echo block: client, prepared-by, projection date, version, charter type, cadence — all via named-range formulas.
- **MODEL STATUS** cell (B16) `=CHECKS!$C$16` — surfaces the master check status on the cover.
- **Navigation table** (rows 19–38): Category / Tab / "→ TABNAME" link text for all 17 primary tabs, grouped Configuration / Assumptions / Pre-Opening / Financials / Detail Schedules / Capital / Regulatory / Diagnostics.
- **Optional Modules block** (rows 39–47): the 8 hidden modules each with an activity lamp formula, e.g. `E41: =IF(tog_trust="Yes","● active","○ off")`. In the shipped file, Trust shows "● active" while its tab is an empty hidden stub (D-P13).
- **Quick Stats Dashboard — Baseline (Annual)** (rows 50–59), 8 metrics × Year 1/2/3:
  Total Assets EOP (`='RC'!BH17` → 110,741 / 171,965 / 228,247), Net Loans EOP (`=RC_C!BH57` → 0/0/0 in default config), Total Deposits EOP (`='RC'!BH25` → 70,326 …), NIM (`=ABR!BH39` → 1.67% / 0.52% / 0.24%), Efficiency Ratio (`=NIE!BH21` → 11.5 / 24.2 / 45.1 — dimensionless multiple, not %), ROA (`=RI!BH25` → −4.8% / −3.9% / −3.6%), CET1/CBLR (CBLR-aware switch `=IF(tog_cblr="Yes",RC_R!BH8,RC_R!BH20)` → 50.1% / 24.1% / 13.6%), Net Income (`=RI!BH22` → **−3,884 / −5,597 / −7,257**).
- **Notable emergent fact:** the shipped default configuration is an all-cash bank losing money every year — yet the master status reads "✅ Model Checks: All Pass," because the checks validate *coherence*, not *viability* (contrast with Roman's blended-spread viability flag).

## I.2 CONTROL — configuration surface

Six sections: A Entity & Engagement, B Projection Cadence, C Scenario Configuration, D Product/Module Toggles (four toggle groups: 6 deposit + 8 loan/asset + 6 fee + 4 structural = 24 toggles), E Capital Thresholds ("Display Reference" — but `thr_cblr` and `thr_cet1` are load-bearing in CHECKS/RC_R), F Display & Formatting. Cadence dropdown at C14 drives the Apps Script view switcher (I.10). Pre-opening months constrained 1–18, set to 12. Projection years hard-locked at 3.

## I.3 TIME — date spine

- Rows: 5 Period Type, 6 Calendar (TEXT(EDATE(start_month, offset),"mmm yyyy")), 7 Scenario label, 8 Sequence #.
- Blocks: Pre-Open M1–M12 at C:N (Jul 2025–Jun 2026), M1–M36 at P:AY (Jul 2026–Jun 2029), Q1–Q12 at BA:BL, Year 1–3 at BN:BP.
- Scenario labels planted at C4 (Baseline), P4 (Stress 1), BA4 (Stress 2) — vestigial placement; no scenario column blocks exist on TIME.
- **Critical structural fact (D-P15):** the engine tabs use a *different* column map (I.6). TIME's named column ranges (`rng_MonthlyCols` = TIME!P8:AY8, etc.) are referenced by **zero** engine formulas. TIME is a reference display, not a spine that drives anything. The only formula consuming TIME is CHECKS #8.

## I.4 CHECKS — the 10 assertions (capture all verbatim-in-substance)

| # | Check | Mechanic | Note field |
|---|---|---|---|
| 1 | RC: Assets = Liab + Equity, monthly+quarterly+annual | `ABS('RC'!{col}17−'RC'!{col}36)<1` across cols C,D,O,AB,AO,AR,BH,BI,BJ (opening, M1, M12, M24, M36, Q1, Y1, Y2, Y3) | "Cash modeled as residual; ties in every period & cadence." |
| 2 | EQ_ROLL ending equity = RC Total Equity (all periods) | same 9-column ABS<1 pattern, EQ_ROLL!{col}10 vs RC!{col}35 | equity rollforward reconciles |
| 3 | RI Net Income feeds EQ_ROLL | 4-column spot check (D,O,BH,BJ), EQ_ROLL!{col}6 vs RI!{col}22 | NI flows to retained earnings monthly |
| 4 | "CBLR ≥ 9% every period (if CBLR elected)" | tests `RC_R!{col}8 >= thr_cblr` (which is **8%**, not 9% — D-P4) across 9 columns; auto-passes (TRUE()) when tog_cblr="No" | conditional-check pattern worth keeping |
| 5 | CET1/T1/Total/Leverage ≥ thresholds (if CBLR not elected) | only actually tests CET1 (`RC_R!BH20..BJ20 >= thr_cet1`) despite the label claiming four ratios (D-P16); auto-passes when CBLR elected | "N/A when CBLR elected (default)." |
| 6 | Pre-opening capital sufficiency | `EXACT(PRE_OPEN!$C$33,"SUFFICIENT")` | cumulative capital ≥ minimum Day-1 requirement |
| 7 | No active income line references a deactivated module | if all six fee toggles are "No", assert `ABS(NII_FEE!BH23)<1` | toggle-consistency check |
| 8 | Date spine has no gaps | `TIME!N8−TIME!C8=11 AND TIME!C8=1` | pre-open sequence 1..12 |
| 9 | Annual = sum of quarters | `ABS(RI!BH22 − SUM(RI!AR22:AU22))<1` (Y1 NI vs Q1–Q4) | rollup integrity |
| 10 | All named ranges resolve | `NOT(ISERROR(preopening_months+thr_cblr+'RC'!BH17))` | spot check |

Master status (C16): `IF(COUNTIF(C5:C14,"FAIL")=0,"✅ Model Checks: All Pass","⚠️ Model Checks: N Failures — Review CHECKS Tab")`, echoed on COVER.

## I.5 Assumption tabs — full content

**Universal conventions:** column A = assumption label, B = **Call Report reference** (e.g., RC-7a, RI-2b, RC-13, RC-23/24, or 'n/a'), C = Baseline value, D = Stress 1, E = Stress 2. **Every D and E cell in all three tabs is `=C{row}`** — placeholders (D-P1a).

**ASSM_BS (88 rows):**
- *Loan assumptions, 5 products × 6 params each* (Consumer Installment, Credit Card, Small Business/C&I, Residential Mortgage, CRE): Opening balance Day-1 [RC-7a] (all 0), Monthly net new originations [RC-7a] (1000 / 500 / 1500 / 2000 / 2000), Average annual yield [RI-1a] (8% / 18% / 6.5% / 5.5% / 6%), Annual prepayment/paydown rate (15% / 0% / 10% / 12% / 8%), Annual NCO rate [RI-4] (1.5% / 4% / 0.5% / 0.2% / 0.3%), ALLL reserve rate % of gross [RC-7b] (1.25% / 3% / 1.25% / 0.5% / 1%).
- *Deposit assumptions, 6 products × 5 params each* (Retail Demand, MMDA/Savings, Time/CDs, Brokered, Sweep/Program, Institutional): Opening balance [RC-13] (all 0), Monthly net new growth [RC-13] (3000 / 2000 / 1000 / 0 / 0 / 0), Annual cost of funds [RI-2] (0.5% / 2.5% / 4% / 4.5% / 3% / 3.5%), Average maturity months (0 / 0 / 24 / 12 / 0 / 0 — **all six maturity inputs are dead**, D-P9), Annual runoff rate (5% / 8% / 0% / 0% / 10% / 15%).
- *Securities & cash:* AFS opening/yield/monthly-net-purchases (0 / 4% / 0), HTM same (0 / 4.2% / 0), IB deposits at other banks opening/rate/monthly additions (10,000 / 4.5% / 2,000), Fed funds sold opening/rate (0 / 4.25%).
- *Other assets/liabilities:* Premises opening 1,000 [RC-8]; monthly depreciation 10; FHLB initial draw 0 [RC-16] / rate 4% [RI-2b] / **maturity 36 months (dead input, D-P9)**; Other borrowings 0 [RC-19] / rate 5% [RI-2c]; Other assets = 2% of total assets [RC-11].

**ASSM_IS (56 rows):**
- *Rate assumptions:* Fed funds Y1/Y2/Y3 (4.5/4.0/3.5%), Prime Y1/Y2/Y3 (7.5/7.0/6.5%), 10-yr Treasury Y1/Y2/Y3 (4.2/4.0/3.8%) — **all nine consumed by zero formulas** (D-P2).
- *Fee income:* interchange rate 1.2% on volume [RI-5b] + monthly txn volume (0); BaaS fee $0.005/acct/mo [RI-5c] + account count start (0) + **account growth (dead, D-P10)**; service charge $0.008/acct/mo [RI-5a] + account count (0); trust fee 0.5% bps-style on AUM [RI-5d] + AUM start (0) + **AUM annual growth (dead, D-P10)**; GOS margin 1.5% [RI-5e] + annual volume (0); other fee income $/mo manual [RI-5f].
- *NIE:* FTE counts — Pre-open 8 (**dead input, D-P10** — pre-open comp is a direct $ line on PRE_OPEN), Year 1 = 20, Year 2 = 30, Year 3 = 40 [RI-7a]; fully-loaded comp $150K/FTE/yr; core banking $25K/mo [RI-7b]; tech/infra $15K/mo; occupancy $20K/mo [RI-7c]; marketing $15K/mo; legal & compliance $12K/mo; D&O/fidelity $5K/mo [RI-7d]; FDIC assessment 5bp on assessment base; OCC supervisory fee 1.5bp on assets; other opex = 3% of total NIE.
- *Payment processing (fee/cost per transaction):* ACH 0.10/0.05, Wires 15/5, RTP 1.0/0.5, FedNow 1.0/0.5, Card 0.5/0.2 — a fully-specified unit-economics schedule whose volumes are hardcoded zeros on NII_FEE (D-P11).

**ASSM_CAP (23 rows):**
- Capital raises: Initial 50,000 [RC-23/24] @ DATE(2026,7,1); Round 2 amount 0 @ DATE(2027,7,1); Round 3 amount 0 @ DATE(2028,7,1). Amounts are wired; **dates are decorative** (D-P8).
- Capital targets echo: CBLR target `=thr_cblr` (0.08), CET1 target `=thr_cet1`.
- RWA risk weights [RC-R]: Cash/Fed 0%, Agency securities 20%, Resi 1st-lien ≤80% LTV 50%, C&I/consumer/CRE 100%, Substandard/doubtful 150%.
- AOCI sensitivity: annual ΔAOCI as % of AFS portfolio = −2% [RC-26b].

## I.6 Engine tab column layout (uniform across RC, RI, ABR, NII_FEE, NIE, RC_C, DEP, SEC, EQ_ROLL, RC_R, CONC)

- Row 3 banners: C3 'Baseline — Monthly', AR3 'Baseline — Quarterly', BH3 'Baseline — Annual', BL3 'Stress 1 (Annual)', BP3 'Stress 2 (Annual)'.
- Row 4 headers: **C = Opening**; D–O = M1–M12; **P = Year 1 (inline rollup)**; Q–AB = M13–M24; **AC = Year 2**; AD–AO = M25–M36; **AP = Year 3**; AR–AU = Q1–Q4; **AV = Y1**; AW–AZ = Q5–Q8; **BA = Y2**; BB–BE = Q9–Q12; **BF = Y3**; BH/BI/BJ = Annual Y1/Y2/Y3; BL/BM/BN = S1 Y1/Y2/Y3; BP/BQ/BR = S2 Y1/Y2/Y3.
- Flow rows roll up (quarter = SUM of 3 months; year = SUM of 4 quarters); stock rows take EOP (e.g., RC balance annual cols reference month-12/24/36 EOP or re-derive). CHECKS #9 validates one rollup.
- **Every stress column (BL:BN, BP:BR) in every engine tab is `=BH/BI/BJ`** — a copy of baseline annual (D-P1b).
- Navigation: every engine tab has A1 '← Back to Cover'.

## I.7 Engine tab mechanics, tab by tab

**RC — Balance Sheet.** Asset lines with Call Report refs in column B: Cash and due from banks [RC-1] = **residual**: `C36−(C7+C8+C9+C10+C13+C14+C15+C16)` (total L+E minus every other asset — the balancing convention); IB deposits at other banks [RC-2] `=SEC!{c}27`; Fed funds sold [RC-3] `=SEC!{c}35`; AFS [RC-4a] `=SEC!{c}10`; HTM [RC-4b] `=SEC!{c}19`; Loans gross [RC-7a] `=RC_C!{c}55`; Less ALLL [RC-7b] `=−RC_C!{c}56`; Net loans [RC-7c]; Premises [RC-8] opening `=PRE_OPEN!$C$37`, then prior − depreciation (annual cols step via O14/AB14/AO14); OREO [RC-9] `=0`; Other assets `=2%×(net loans+securities+IB cash+FF)` (note: excludes cash itself and premises from the base). Liabilities: Demand `=DEP!{c}9`; Savings/MMDA `=DEP!{c}16`; **Time <$250K `=DEP!{c}23*0.6` and ≥$250K `=DEP!{c}23*0.4+DEP!{c}44`** (hardcoded 60/40 split, institutional lumped into ≥$250K — D-P7); Brokered `=DEP!{c}30`; Sweep `=DEP!{c}37`; FHLB `=ASSM_BS!$C$83` static every period (D-P12); Other borrowings `=ASSM_BS!$C$86` static; Other liabilities `=0`. Equity rows pull EQ_ROLL components. Row 37 'Memo: Average total assets' `={c}17` — **EOP mislabeled as average** (D-P5).

**RI — Income Statement.** Interest income: loans `=RC_C!{c}59`, securities `=SEC!{c}39`, FF/IB-cash `=SEC!{c}29+SEC!{c}37`; interest expense: deposits `=DEP!{c}49`, borrowings `=ABR!{c}38−DEP!{c}49` (derived by subtraction); NII; provision `=RC_C!{c}60`; NII after provision; total non-interest income `=NII_FEE!{c}23`; total NIE `=NIE!{c}20`; pre-tax; **Income taxes [RI-8b] `=0` labeled "(V1 placeholder)"** (D-P3); net income [RI-9]. KPI block: ROA `=IF(RC!{c}37=0,0,NI/RC!{c}37×k)` with k=1 opening, ×12 monthly, ×4 quarterly (annualization by cadence multiplier); ROE same on EQ_ROLL avg equity row 11; NIM `=ABR!{c}39`; Efficiency `=NIE!{c}21`.

**ABR — Average Balances & Rates.** Five earning-asset blocks (loans, AFS, HTM, IB cash, FF sold), each Average balance / Interest income / Average yield (`inc/avg×12` monthly, ×4 quarterly); totals; two liability blocks (deposits; borrowings = FHLB+other with expense computed `(FHLB×rate+Other×rate)×1/12` directly from assumptions); NIM row 39 = `(TotIntInc−TotIntExp)/TotalEarningAvg×12`. Note: borrowing average balance = static assumption sum, consistent with D-P12.

**NII_FEE — Non-Interest Income.** Six fee lines, each `= assumption-product × IF(tog_x="Yes",1,0)`: interchange `vol×rate`, BaaS `accts×fee`, service charges `accts×fee`, trust `AUM×rate/12`, GOS `annual vol×margin/12`, other `manual $`. **All six are constant every month** — no growth mechanics (D-P10). Payment processing: volume rows 12–16 are **hardcoded literal 0.0 inputs sitting on the engine tab** (D-P11); income rows 18–22 = volume × per-tx fee. Row 23 total.

**NIE — Non-Interest Expense.** Comp `=FTE(year)×comp/12` with a **per-year step**: months 1–12 use Year-1 FTE (C32), months 13–24 Year-2 (C33), months 25–36 Year-3 (C34); pre-open column C is `=0` (pre-open comp lives on PRE_OPEN). Core+tech, occupancy, marketing, legal, D&O: flat monthly $ from assumptions. **FDIC/OCC row 11:** `(avg deposits×FDIC rate + total avg earning assets×OCC rate)×n/12` where n=1 monthly, 3 quarterly, 12 annual — FDIC assessment base approximated as deposits (D-P14). Payment processing expense rows 13–17 = NII_FEE volumes × per-tx cost. Subtotal; **Other opex gross-up:** `=Subtotal×r/(1−r)` with r=3% so "other" is 3% of *total* NIE (a genuinely clever formulation — keep it); Total row 20. Efficiency row 21 = `NIE/(ABR NII + fee income)` — a **ratio to revenue expressed as a multiple** (11.5× in Y1 default, because revenue ≈ 0), displayed on COVER as if a percent.

**RC_C — Loan Portfolio Detail.** Five product blocks × 9 rows (Beginning / New originations / Paydowns / NCO / Ending / Average / Interest income / ALLL / Provision). Monthly algebra per product: `Beg=prior End`; `Orig = ASSM monthly × IF(toggle)`; `Paydowns = Beg × annual prepay/12`; `NCO = Beg × annual NCO/12`; `End = Beg+Orig−Paydowns−NCO`; `Avg=(Beg+End)/2`; `IntInc = Avg × yield/12`; `ALLL = End × reserve rate`; `Provision = ΔALLL + NCO`. Totals rows 55–60 (gross, ALLL, net, avg, interest, provision). No floors: End can go negative in principle (no Math.max guard, unlike Roman).

**DEP — Deposit Schedule.** Six product blocks × 6 rows (Beg / New / Runoff / End / Avg / IntExp). `New = ASSM monthly growth × IF(toggle)`; `Runoff = Beg × annual runoff/12`; `IntExp = Avg × annual cost/12`. Totals rows 47–49. CD/brokered **maturity inputs never consumed** (D-P9) — time deposits behave identically to non-maturity deposits.

**SEC — Securities & Cash.** Four blocks (AFS, HTM, IB cash, FF sold) × up to 9 rows: Beg / Purchases / Maturities-sales / Amortization-accretion / End / Avg / IntInc, plus AFS-only row 13 **Unrealized gain/(loss) on AFS (AOCI)** `= End × ASSM_CAP AOCI sensitivity /12` — the AOCI mechanism, feeding EQ_ROLL row 7. Purchases = ASSM monthly net × toggle; maturities and amortization rows are `=0` structural placeholders.

**CAP_RAISE.** Display table: Event / Date / Amount / Source Type / Cumulative for Initial + Round 2 + Round 3, all referencing ASSM_CAP; total row.

**EQ_ROLL — Equity Rollforward.** Rows: Beginning equity (`=prior End`; opening `=PRE_OPEN!$C$39+...` seeds); Add NI `=RI!{c}22`; Add AOCI change `=SEC!{c}13`; **Add capital raises: opening C8 `=PRE_OPEN!$C$39` (50,000); Round 2 hardwired to Q8/M13 (`Q8: =ASSM_CAP!$C$9`); Round 3 hardwired to AD8/M25 (`=ASSM_CAP!$C$11`); every other month `=0`** (D-P8); Less dividends declared `=0` (plumbed, unused); ENDING EQUITY = components sum; Average equity row 11 `=(Beg+End)/2`; Components: Common stock `=prior+raises`, Surplus `=prior`, Retained `=prior+NI`, AOCI `=prior+ΔAOCI`.

**RC_R — Regulatory Capital.** *Section A CBLR (active if elected):* Tier 1 = `RC common+surplus+retained` (AOCI excluded — implicitly the opt-out); Average Total Assets `=RC!{c}37` (**EOP, D-P5**); CBLR = T1/ATA; threshold row `=thr_cblr`; Flag `=IF(ratio>=thr_cblr,"Well-Capitalized",IF(ratio>=0.08,"Adequately — Monitor","BELOW WELL-CAP"))` — **unreachable middle branch** because thr_cblr=0.08 (D-P4). *Section B Standardized (active if not elected):* AOCI opt-out election input C13='Yes' propagated across columns; CET1 = common+surplus+retained `+IF(optout="No", AOCI, 0)`; Tier 1 = CET1; ALLL eligible Tier 2 `=RC_C!{c}56`; **Tier 2 = MIN(ALLL, 1.25%×RWA)** — the cap correctly applied; Total capital = T1+T2; **RWA row 19 = Resi×50% + (Consumer+CC+C&I+CRE)×100% + (AFS+HTM)×20%** — IB cash at other banks and fed funds sold excluded entirely (D-P6); CET1/RWA, T1/RWA, Total/RWA with divide-by-zero guards; Leverage = T1/RC!{c}37.

**CONC — Concentrations & Diagnostics.** Twelve computed ratios with bracketed thresholds in the labels: CRE/Total RBC [>300%] `=RC_C CRE end / RC_R Total Capital`; **Construction & land/Total RBC [>100%] — numerator hardcoded `0/…`** (no C&D category exists in the taxonomy; the check can never fire — D-P16b); C&I/Total loans; Consumer/Total loans; Single largest borrower ($) — a raw input cell on the engine tab (row 10, default 0); Largest borrower/(Capital+Surplus) [15% LLL]; Brokered/Total deposits [>25%]; Wholesale funding/(Total liabilities) = (FHLB+brokered)/liabilities; Non-core funding/Total assets = (FHLB+brokered)/assets; Loan-to-deposit [70–90% advisory]; NIE/Average assets (burden). Note quirk: column P (inline Y1) of row 6 references BH-annual columns — the inline-annual echo convention.

## I.8 The eight hidden module stubs — intended row structures (this is Patrick's v2 roadmap; capture fully)

- **BHC:** Beginning HC equity / + subsidiary NI / + capital raises / − dividends up-streamed / Ending HC equity / Intercompany eliminations / **Double-leverage ratio**. (Opening + Y1/Y2/Y3 columns; all zeros.)
- **RC_T (Trust):** AUM / Fee income detail / RC-T line items / Total fiduciary revenue.
- **INTCHG:** Transaction count / Average ticket / Network split Visa / Network split Mastercard / Gross interchange / Network fees / Net interchange.
- **BAAS:** Active program count / Accounts per program / Total active accounts / Revenue per account / Total program revenue.
- **MORT:** Origination pipeline / Locked pipeline / Held-for-sale balance / Gain-on-sale waterfall / Net mortgage banking income.
- **CC:** Receivables / Utilization rate / Interchange / Credit losses / Rewards cost / Net card income.
- **SENS:** Variable / Low case / Base case / High case / Output: NIM / Output: ROA / Output: CET1-CBLR (a tornado-style one-variable sensitivity design).
- **PEER:** **FFIEC peer group selector / "Paste-in data zone (below)"** / Benchmark ratios: NIM, ROA, Efficiency, Capital. All zeros. The single strongest demo contrast: his blank is Foundry's product.
- Every stub footer: "Stub tab — structure only. Activate via CONTROL toggle for V2 build."

## I.9 PRE_OPEN — Pre-Opening Build (four sections)

- **A. Expense schedule**, 10 categories × 12 months (flat $/mo in shipped file): Organizational/legal/incorporation 50; OCC/FDIC application & processing 30; Core banking implementation 60; Tech infrastructure buildout 40; Executive & key staff comp 120; Office/lease buildout & occupancy 25; **Consulting & advisory fees (incl. Klaros) 80**; Regulatory exam preparation 20; Marketing & brand launch 30; Contingency reserve 20. Monthly total 475; cumulative row → 5,700 at M12.
- **B. Capital raise schedule** echo of ASSM_CAP, plus "Source of capital" text ('Founder / Institutional').
- **C. Capital sufficiency check:** Net capital cushion = cumulative capital − cumulative pre-open burn (44,300); **Minimum Day-1 opening capital requirement = 20,000 (raw input)**; Sufficiency flag `=IF(cushion>=min,"SUFFICIENT","INSUFFICIENT — REVIEW CAPITAL PLAN")` — feeds CHECKS #6.
- **D. Day-1 opening balance sheet seeds:** Cash Day-1 = total raised − burn − premises − IB cash opening − AFS opening − HTM opening − FF opening (33,300); Premises = ASSM premises opening; Other assets pre-open = 0; Common stock/paid-in = total raised; **Retained earnings/(deficit) = −cumulative pre-open expense (−5,700)** — organizational costs expensed into opening deficit, not capitalized.

## I.10 Script_Code — Google Apps Script view switcher

Full script stored in A1: creates a "Klaros Views" menu (Show Monthly / Quarterly / Annual / All); `onEdit` trigger watches CONTROL C14 (the cadence dropdown) and switches views automatically; `TARGET_SHEETS = [RI, ABR, NII_FEE, NIE, DEP, SEC, CAP_RAISE, EQ_ROLL, CONC, RC, RC_C, RC_R]`; monthly view hides quarterly (cols 44–58) and annual (60–62); quarterly/annual views hide monthly (cols 4–42) with an out-of-bounds guard. **Google-Sheets-only; inert in Excel** (D-P17). The design intent to absorb: one artifact, cadence as a *view*, not separate models.

## I.11 Patrick defect register

| ID | Defect | Evidence | Foundry v3 fix spec |
|---|---|---|---|
| D-P1a | Stress assumption columns are placeholders | Every ASSM_BS/IS/CAP D&E cell is `=C{row}` | Stress scenarios are first-class configs (delta overlays on baseline config), not parallel columns |
| D-P1b | Engine stress columns never read stress assumptions | Every BL:BN/BP:BR cell is `=BH/BI/BJ`; grep: **0** formulas reference ASSM col D or E anywhere | Stress = full engine re-run under overlay (Roman's semantics), surfaced in Patrick's S1/S2 annual presentation shape |
| D-P2 | Macro rate framework is dead circuitry | Fed funds/prime/10Y ×3yrs (ASSM_IS C7:C15): 0 references | Single sourced rate path (SOFR per REG_PARAMS/FOMC SEP) that products actually reprice off |
| D-P3 | Tax `=0` | RI row 21, labeled "V1 placeholder" | NOL-aware tax engine (Roman's), disclosed DTA treatment |
| D-P4 | CBLR parameter 8% vs label 9%; unreachable tier branch | `thr_cblr`=0.08; CHECKS #4 label "≥ 9%"; RC_R flag `IF(x≥thr_cblr,…IF(x≥0.08,…))` | 9% election threshold + 8% two-quarter grace, both from REG_PARAMS with citation; tiered flag with reachable branches |
| D-P5 | "Average total assets" = EOP | RC row 37 `={c}17`; CBLR & leverage denominators use it | True average of period balances in every ratio denominator |
| D-P6 | RWA omits IB cash at other banks and fed funds sold | RC_R row 19 formula terms | Full risk-weight mapping incl. 20% bank-exposure weights; default-config RWA must be nonzero |
| D-P7 | Hardcoded 60/40 insured/uninsured CD split; institutional lumped into ≥$250K | RC rows 21–22 inline literals | Insurance bucketing as a per-product assumption with documented basis |
| D-P8 | Capital raise dates decorative — raises pinned to M13/M25 | EQ_ROLL Q8=`ASSM_CAP!$C$9`, AD8=`$C$11`; date inputs referenced only by display tabs | Staged raises with true effective dates mapped to engine quarters |
| D-P9 | Seven dead maturity inputs | All 6 deposit maturities + FHLB 36-mo maturity: 0 references | Maturity either drives runoff/amortization or is removed; no decorative inputs |
| D-P10 | Fee growth inputs dead; all fee lines static | BaaS acct growth (C21), AUM growth (C26), pre-open FTE (C31): 0 refs; trust/interchange/service formulas constant every month | Fee drivers with growth paths; every displayed input consumed or flagged |
| D-P11 | Payment volumes hardcoded 0 on engine tab | NII_FEE D12:D16 literals | Volumes are Tier-3 config; unit fee/cost pairs from ASSM absorbed as a payments product module |
| D-P12 | FHLB never amortizes; borrowing balances static | RC row 26 `=ASSM_BS!$C$83` all periods | Borrowings as scheduled instruments (draw, rate, amortization/maturity) |
| D-P13 | Trust "active" with empty stub; toggle/lamp inconsistency | CONTROL C47=Yes, RC_T hidden zero stub | Module activation implies a real module; activation state is derived, not asserted |
| D-P14 | FDIC assessment base ≈ avg deposits | NIE row 11 | Assessment base = avg consolidated assets − avg tangible equity, disclosed |
| D-P15 | TIME spine drives nothing; engine columns use a different map | Named col ranges referenced by 0 engine formulas | One canonical period index; all presentation derives from it |
| D-P16 | Check-label overclaims: CHECKS #5 tests only CET1 of four claimed ratios; CONC C&D numerator hardcoded 0 | CHECKS row 9 formula; CONC row 7 `0/RC_R!{c}18` | Checks test exactly what their labels claim; concentration inputs exist for every ratio computed |
| D-P17 | Cadence switcher is Apps Script (Sheets-only) | Script_Code tab | Cadence as native view state |
| D-P18 | Coherence ≠ viability: default config loses money 3 straight years under "✅ All Pass" | COVER NI row 59 vs B16 | Separate check classes: integrity checks AND viability/reasonableness flags (Roman's), both surfaced |

---

# PART II — ROMAN'S MODEL: COMPLETE INVENTORY

## II.0 Artifact facts

Single-file HTML app, Montserrat/Klaros gold branding, SheetJS 0.18.5 from CDN for export. Header states scope: "12-quarter de novo projection — Call Report presentation for charter application development — rate forecast: June 2026 FOMC SEP." Layout: toolbar tab bar + scenario-name input + flags badge + Export button; 340px sidebar (Products list, Add Product, Global Assumptions, SOFR Forecast, Stress Scenario Settings accordions); content pane. Footer confidentiality strip. Seven tabs: **Products, Balance Sheet, Income Statement, Ratios, Product Detail, Stress Testing, Assumptions & Notes.**

## II.1 Data model

**Product object:** `{id, name, cat: asset|liability|offbs, line, rateType: fixed|float, measurement: amortized|fairvalue, open, …fields}`. Call Report line taxonomy: 5 loan lines (`loanCommercial` "Loans: Commercial & Industrial", `loanConsumer`, `loanCreditCard`, `loanMortgage` "Loans: 1-4 Family Residential", `loanOther`), 3 deposit lines (`depDDA` "Deposits: Transaction (DDA)", `depSavings` "Deposits: Savings & MMDA", `depTime`), 1 off-BS line (`obs` "Off-Balance-Sheet Commitments"). Any number of products may map to the same line; aggregation sums carrying values per line.

**Six shipped presets (complete parameter sets):**
1. DDA — liability/depDDA, fixed, amortized: bal0 25,000; growth 12%/q; ratePaid 0.25%; feeRate 0.5%; opexPct 1.0%; opexFixed 150.
2. Savings — liability/depSavings, **float**: bal0 35,000; growth 14%/q; spread −0.7%; feeRate 0.1%; opexPct 0.3%; opexFixed 50.
3. Personal Loans — asset/loanConsumer, fixed: bal0 10,000; orig 5,000/q; origGrowth 5%/q; runoff 8%/q; yld 11%; feeRate 0.5%; chargeOff 4%; reserveRate 3%; opexPct 1.5%; opexFixed 100.
4. Commercial Loans — asset/loanCommercial, **float**: bal0 15,000; orig 7,500; origGrowth 5%; runoff 5%; spread 3.5%; feeRate 0.35%; chargeOff 0.75%; reserveRate 1.25%; opexPct 0.75%; opexFixed 150.
5. Credit Cards — asset/loanCreditCard, fixed: bal0 5,000; orig 2,000; origGrowth 6%; runoff 10%; yld 18%; feeRate 3%; chargeOff 5.5%; reserveRate 8%; opexPct 4%; opexFixed 200.
6. Mortgages — asset/loanMortgage, fixed, **full OTS/MSR config**: bal0 20,000; orig 6,000; origGrowth 4%; runoff 3%; yld 6%; feeRate 0.25%; chargeOff 0.15%; reserveRate 0.5%; **salePct 50%; saleMargin 1.75%; holdQtrs 1; servRetained 100%; servFee 25bp; msrCapRate 1.1%; msrDecay 3%/q**; opexPct 0.4%; opexFixed 100.

**Global fields (13):** capital 60,000; taxRate 21%; overheadQ 1,800/q; overheadG 1%/q; cashFloor 5% of deposits; cashYield 2.5%; secYield 4.0%; borrowRate 5.5%; **levMin 9 (labeled "Min leverage ratio (%) — CBLR 9")**; premises 5,000; intangibles 0; otherAssets 2,000; otherLiab 1,000. Plus SOFR Q1–Q12 editable path and longer-run 3.15%.

**SOFR default path:** [3.70, 3.85, 3.80, 3.75, 3.70, 3.65, 3.60, 3.55, 3.50, 3.45, 3.40, 3.35], documented in-code as interpolated from the **June 17, 2026 FOMC SEP** fed funds medians (3.8% YE26, 3.6% YE27, 3.4% YE28, 3.1% longer run) + ~5bp SOFR/EFFR basis; SOFR 3.68% at 6/30/2026. `makeSofr(path, lr)`: t≤12 reads the path; t>12 glides 5bp/quarter toward the longer-run value and holds (used by the 60-quarter DCF horizon).

**Benchmark bands (`CO_RANGES`, annual NCO % by line):** Commercial 0.05–3.0; Consumer 0.50–8.0; Credit Card 1.50–10.0; Mortgage 0.02–1.50; Other 0.00–8.0. **Defaults when unspecified** (`CO_DEFAULT` / `RES_DEFAULT`): Commercial 0.5/1.25; Consumer 3.0/3.0; Credit Card 4.5/8.0; Mortgage 0.15/0.5; Other 1.0/1.5.

## II.2 `parseProduct` — the defaults-with-disclosure mechanism

Blank fields receive defaults via `take(field, default, label, noteworthy)`; when `noteworthy=true` a note is pushed: "*{name}: {label} not specified — conservative default of {d} applied.*" Full default table:
- All products: bal0→0; feeRate→0; opexPct→0.5 (annual % of avg bal); opexFixed→0.
- Float rate: spread → +2.5 (assets) / −1.0 (liabilities), noteworthy.
- Fair value: discountSpread → the product's spread or the category default, noteworthy; liabilities also fvDecay→10%/q, noteworthy.
- Assets: orig→0; origGrowth→0.5%/q (noteworthy); runoff→5%/q (noteworthy); fixed yld→6% (noteworthy); chargeOff→line default (noteworthy); reserveRate→line default (noteworthy); salePct→0 clamped [0,100]. If selling: saleMargin→1.5% (noteworthy); holdQtrs→1, clamped integer [0,4]; servRetained→0 clamped [0,100]; if servicing: servFee→25bp (noteworthy); msrCapRate→1.1% (noteworthy); msrDecay→3%/q (noteworthy); else all servicing params zeroed.
- Liabilities: growth→0.5%/q (noteworthy); fixed ratePaid→1% (noteworthy).
- Off-BS: growth→0.5%/q (noteworthy).
Field visibility (`fieldsFor`) adapts to cat/rateType/measurement — reserveRate hidden under FVO; discountSpread shown under FVO; fvDecay only for FVO liabilities.

## II.3 Core engine (`computeModel`) — quarter loop mechanics

- **Effective rate:** float = `sofr(t)+spread`; fixed = yld (assets) / ratePaid (liabilities). Quarterly accrual = annual/4 on **average balance** `(beg+end)/2`.
- **Asset rollforward:** `co = beg×chargeOff/4`; `o = orig×(1+origGrowth)^(q−1)`; retained = `o×(1−salePct)`; `end = max(0, beg + retained − beg×runoff − co)` (floored at zero — contrast Patrick). Liability: `end = max(0, beg×(1+growth))`. Off-BS: notional grows at growth.
- **Fees/opex per product:** `fees = avg×feeRate/4`; `opex = avg×opexPct/4 + opexFixed`.
- **ALLL:** amortized-cost assets only: `alll = end×reserveRate`; opening ALLL on bal0. **Provision = ΔALLL + NCO on amortized-cost loans only** (FVO loans excluded — their credit losses route through FV P&L).
- **Non-earning block:** premises + intangibles + otherAssets, static all 12 quarters.
- **Balancing plug (`plug`):** funding = deposits(carry) + otherLiab + equity; investable = funding − net loans − non-earning − MSR; required cash = cashFloor × **contractual deposit balances** (not FV carry — a deliberate distinction); if investable ≥ reqCash → cash=reqCash, securities=excess, borrowings=0; else cash=reqCash, securities=0, borrowings=shortfall.
- **Simultaneity:** securities/cash/borrowing interest accrues on average of beg and the plugged end balances; the plug depends on equity, equity on NI, NI on the plug — solved by fixed-point iteration (up to 60 iterations, convergence 1e-4).
- **Tax/NOL:** `taxable = max(0, pretax − nol)`; `tax = taxable × rate`; NOL accumulates on losses and burns down against profits; ending NOL reported as an IS memo. No DTA booked (disclosed; mirrors regulatory NOL-DTA deduction).
- **Opening (q=0):** day-one FV adjustment (assets − liabilities) goes to **opening retained earnings** with a note if |adj| > 0.5; equity0 = capital + dayOne; plug applied at q=0.

## II.4 Originate-to-sell warehouse

Per product with salePct>0: each quarter's sold cohort `soldOrig = o×salePct`. Cohort j sells in quarter j+holdQtrs. **Interest convention:** half-quarter coupon in origination and sale quarters, full quarters between (mid-quarter origination/sale assumption); holdQtrs=0 → half-quarter only; no runoff/charge-offs during warehouse. Warehouse balance on BS at quarter end for cohorts not yet sold; carried at par (AC) or par×(1+margin) (FVO — marked to expected sale price). **GOS timing:** AC recognizes margin at sale (`soldOrig[q−h]×margin`); FVO marks at origination (`soldOrig[q]×margin`) — pull-forward is the disclosed reason OTS lenders elect FVO. HFS balances aggregate into gross loans as a separate "Loans Held for Sale" line and carry **no ALLL**.

## II.5 MSR module

When servicing retained: settled cohorts add `settled×servRetained%` to serviced UPB; UPB decays at msrDecay%/q. MSR capitalized at `add×msrCapRate%` **into the gain on sale** (non-cash gain component, explicitly modeled); amortized at `msrBal×msrDecay%` per quarter; servicing fee accrues at `avg UPB × servFee bp/4`; **net servicing income = fee − amortization** (own IS line). MSR balance is a BS asset line. Disclosed simplification: static-value MSR, no prepayment-driven revaluation outside the stress haircut.

## II.6 Fair value option (`fvOf`)

DCF of the existing book: 60-quarter horizon; per future quarter t: coupon `b×rate(q+t)/4` (floaters reprice along the glided SOFR path), principal `b×decay` (asset runoff or deposit fvDecay), charge-off `b×co/4`; discount factor compounds at `(sofr(q+t)+discountSpread)/4`; PV accumulates `(interest+principal)×df`; balance nets principal+CO; early exit below 0.0001; **terminal repayment of remaining balance at horizon**. FV adjustment = FV − balance, carried inside the Call Report line; ΔFV flows through "Net Gains (Losses) on Fair Value Instruments," with asset charge-offs routed through FV loss instead of provision; liabilities sign-flipped. In-code disclosure: discounting at the coupon spread prices in expected CO — set discount spread to market yield net of expected losses if par-at-origination is intended.

## II.7 Ratios & capital

Per quarter: ROA = NI×4/avg assets; ROE = NI×4/avg equity; NIM = NII×4/avg earning (gross loans + securities + cash averages); Efficiency = NIE/(NII+fees+fvPnl+gos+servNet), null ("n/m") when revenue ≤ 0; ALLL/gross loans. **Tier 1 leverage:** `t1base = equity − intangibles`; `msrExcess = max(0, MSR − 25%×t1base)` per **12 CFR 3.22(d)** threshold deduction; leverage = `(t1base − msrExcess)/(avgAssets − msrExcess)` — deduction hits numerator and denominator. Disclosed: below-threshold MSAs stay in capital (would be 250% RW in a risk-based ratio, which the model does not compute). **`capShortfall`:** additional opening capital to hold ≥ levMin in every quarter: worst-case `(t×(avgA−msrExcess) − (t1base−msrExcess))/(1−t)`; documented approximations: added capital invested in securities, earnings feedback and shrinking MSA deduction ignored (slightly overstates need); returns 0 under 0.5.

## II.8 Stress engine

Parameters (defaults): coMult 2.5×; resMult 1.5×; shockBp +300 parallel; **four downturn overlays applied in all stress scenarios:** volHaircut 40% (originations fall), gosComp 40% (sale margins compress), msrShock 20% (MSR cap-rate haircut), saleShift 25% (**investor demand dries up: that share of planned sales stays on balance sheet** — in-code note cites the Upstart downside dynamic: volume ~−40% year one, balance-sheet retention roughly doubling). Rate shock shifts the entire SOFR path AND cash/securities/borrowing rates; **fixed coupons do not reprice** (so FVO fixed positions take mark-to-market and floaters reprice — disclosed). Scenario list: Base / Credit (multipliers, no shock) / Rate (shock only) / Combined — each a **full computeModel re-run**. Stress tab outputs: severe callouts per scenario breaching levMin with the capital-shortfall estimate; an all-clear line with the worst-case leverage; **an honesty flag when a stressed scenario out-earns base** (explains reserve-build/acquisition-cost mechanics of slower growth; warns to review Q12 run rate); 14-row summary metrics table (cum NI, Q12 NI, cum provision, cum GOS, cum servicing, cum FV, Q12 assets/equity, peak borrowings, min leverage w/ quarter, Q12 ROA/NIM, ending NOL, capital add); NI-by-quarter × scenario table; leverage-by-quarter × scenario table with sub-minimum cells flagged; memo disclosing the calibration is "in the spirit of a severely adverse supervisory scenario, but a Klaros working assumption — regulators prescribe their own scenarios."

## II.9 Reasonableness flag catalog (every trigger; sev = severe/mild)

Assets: CO above line band (severe — "Examiners will challenge this or the pricing that supports it"); CO below band (mild — "A de novo book with no seasoning rarely outperforms industry loss experience"); Q1 effective yield >25% (severe — usury/fair-lending/UDAAP); yield <2% (mild — below any plausible funding cost); reserveRate < chargeOff/2 on AC products (mild — thin ALLL).
Liabilities: rate paid >5.5% (severe — rate-sensitive funding, "classic de novo exam finding"); DDA paying >2% (mild); deposit growth >25%/q (mild — "the OCC will ask what funds it and what it costs").
FVO: |day-one FV adj| > 2% of balance (mild — off-market pricing or embedded losses; check discount spread).
OTS/MSR: saleMargin >4% (mild — above typical execution ~0.5–4%; investor commitments); saleMargin <0 (severe — selling at a loss); holdQtrs ≥3 (mild — pipeline funding); msrCapRate >2% (mild — typical agency ~0.8–1.5%, third-party valuation); servFee >50bp or 0<fee<12.5bp (mild — outside typical range).
Portfolio-level: blended starting loan yield − blended deposit cost <1% (severe — "the balance sheet cannot cover operating costs at that spread"); min leverage < levMin with quarter identified (severe — cites "CBLR requires >9%; de novo operating agreements often set the floor at or above this level"); OBS >25% of assets any quarter (severe — CBLR ineligibility); assets >$10B by Q12 (mild — CBLR ceiling); msrExcess >0.5 any quarter (severe — servicing outgrowing capital; sell servicing / slow volume / raise capital); borrowings >25% of assets (severe — wholesale-funding supervisory concern); equity <0 at Q12 (severe — "The plan is not viable as specified").
Plus the **Defaults Applied** log (II.2) rendered on Assumptions & Notes and in export.

## II.10 FTP layer

Toggle on Products and Product Detail tabs: charges assets / credits liabilities at forecast SOFR on average balances **including warehouse**; offsetting net position accrues to a "Treasury (FTP mismatch center)" row; **presentation-only, never touches the income statement** (disclosed in the memo, including what the numbers mean with FTP off: deposits get no funding-value credit, loans bear no funding charge). Product Detail table columns: Q12 balance, interest inc/exp, fees, GOS, net servicing, op costs, NCOs, [FTP], direct contribution; per-card summary strips show Q12 balance, 12Q revenue, 12Q contribution with pos/neg coloring.

## II.11 UI behaviors worth preserving

120ms debounced recompute on every input; recompute refreshes the flags badge (count + "hot" styling when any severe) without redrawing the Products tab (the inputs being typed in) — only the per-card stat strips update in place; results tabs re-render on tab switch. Add-product modal: 6 preset buttons (with category captions) + custom name/category creation. Products display chips: SOFR (float), FV (fair value), asset/liability/Off-BS. Scenario name input feeds the export title. Conditional rendering everywhere: zero lines (unused loan/deposit lines, HFS, MSR, OBS, FV memos) are suppressed rather than shown as zeros.

## II.12 Excel export (SheetJS), six sheets

1. **Balance Sheet** — Open + Q1–Q12; sections Assets/Liabilities/Equity; per-line loans/deposits (nonzero only); HFS line; ALLL negative; MSR; memos (OBS notional; FV adjustment in loan and deposit carrying values).
2. **Income Statement** — Q1–Q12 + Total column; full waterfall incl. GOS (incl. MSR cap.), net servicing, FV gains/losses, product opex vs corporate overhead split, tax, memos NCO and ending NOL.
3. **Ratios** — the six ratio rows, quarterly.
4. **Per-Product Detail** — per product: header with line/rate/measurement tags; effective rate by quarter; EOQ balance; originations; sold originations; warehouse balance; GOS; serviced UPB; MSR cap/amort/balance; net servicing; interest; NCOs; ALLL; FV and FV-adjustment rows for FVO; fees; operating costs.
5. **Assumptions** — all globals; the SOFR path with source note; per-product full field dump; **Defaults applied** log; **Reasonableness flags** log with severities.
6. **Stress Testing** — parameter disclosure lines (multipliers, shock, all four overlays), scenario metric matrix.

## II.13 Methodology disclosure (Assumptions & Notes tab)

A ~900-word prose methodology covering, in order: units and rollforward algebra; average-balance accrual; SOFR sourcing and editability; ALLL/provision definition; OTS conventions (half-quarter interest, par+margin sale, AC-vs-FVO gain timing and the FVO pull-forward rationale); HFS no-ALLL; MSR mechanics and the static-value simplification; the 3.22(d) threshold deduction in leverage; CBLR framework assumption + eligibility flags + **"risk-weighted assets and risk-based ratios are not computed"**; capital deductions not modeled (securitization-exposure GOS deduction under 12 CFR 3.22(a) — whole-loan-sale assumption, capital overstated if securitized; DTAs not booked, mirroring the regulatory deduction; unconsolidated-FI investments not threshold-deducted); FVO DCF description incl. the coupon-spread-prices-in-CO caveat; stress module semantics; the iterative balancing solve; tax/NOL; no dividends or raises; closing scope concession: **"a filed business plan requires interest-rate shock scenarios, capital stress, and month-one liquidity detail beyond this scope."**

## II.14 Roman defect / limitation register

| ID | Item | Status in source | Foundry v3 posture |
|---|---|---|---|
| D-R1 | No persistence whatsoever — no save/load/import; state dies on reload (0 storage/import references in code) | undisclosed | Config-as-data (Tier 3 JSON), versioned, loadable — Prairie Digital pattern |
| D-R2 | No pre-opening period | disclosed by omission | Absorb Patrick I.9 as pre-open quarters |
| D-R3 | Quarterly only; no monthly detail | header-disclosed | Quarterly-permanent stands; monthly workbooks convert at import with documented conventions |
| D-R4 | No capital raises, no dividends | disclosed in methodology | Staged raises module (horizon item); dividends plumbed |
| D-R5 | No RWA / risk-based ratios | explicitly disclosed | Standardized approach alongside CBLR (fixing D-P6) |
| D-R6 | No AFS/HTM split, no AOCI (opt-out assumed); securities not marked | disclosed | AFS/HTM with AOCI line + opt-out election (Patrick's SEC/RC_R pattern) |
| D-R7 | Non-earning assets and other liabilities static 12 quarters; no depreciation | visible in export (flat rows) | Scheduled fixed assets with depreciation |
| D-R8 | Corporate overhead = one line, one growth rate | design choice | Patrick's NIE category granularity incl. FTE step model |
| D-R9 | Three deposit lines; no brokered/sweep/institutional concept; no insurance buckets | design choice | Patrick's six-type taxonomy + insured/uninsured bucketing (fixing D-P7) |
| D-R10 | No FDIC/OCC assessment expense | omission | Assessment lines with correct base (fixing D-P14) |
| D-R11 | Concentration coverage = 2 checks (borrowings>25%, OBS>25%) | partial | Full CONC checklist (I.7) as automated flags |
| D-R12 | Benchmark bands hardcoded in source (CO_RANGES, rate thresholds, margin ranges) | static | Same flags recomputed from live CharterIQ peer distributions, dated and cited — the 85/15 centerpiece |
| D-R13 | Tier 1 approximated as equity − intangibles (no other regulatory adjustments) | disclosed | Full capital component build (Patrick RC_R Section B semantics, corrected) |
| D-R14 | Fixed 12-quarter horizon | design choice | Horizon = f(config); 12Q default, 3-year annual presentation preserved |
| D-R15 | No integrity-check panel (balances by construction, but nothing asserts it to a reviewer) | absent | Surface the deterministic test harness as a CHECKS-style panel (absorbing Patrick I.4, fixing D-P16/18) |
| D-R16 | Single-scenario stress params (one credit multiplier set for all products) | design choice | Per-product stress overlays available; global multipliers as the default |
| D-R17 | Off-BS commitments have notional + fees only — no funded-conversion or credit-conversion-factor mechanics | simplification | CCF mapping when standardized RWA is active |
| D-R18 | Total column sums *stock* lines across quarters. The single function `isRow` totals EVERY line it renders as `sum(q=1..12)` — correct for flows (NII, tax, provision, originations, interest, fees, GOS) but meaningless for any running-balance line, where it sums twelve outstanding balances. Affected lines: **income statement** — "Memo: NOL Carryforward (end)"; **per-product detail** (isRow used for every product line) — "End-of-quarter balance", "Warehouse balance (HFS)", "Serviced UPB (end)", "MSR balance (end)", "ALLL", "Fair value (DCF)", "FV adjustment vs balance". Each product's stock-line Total is a sum of twelve balances. Roman's own summary-metrics object (computeModel, ~L619) correctly uses ending values (`nolEnd[12]`, `equityQ12`, `assetsQ12`), so the scenario-comparison and Excel-summary tables are unaffected — the defect is confined to the IS and product-detail **Total columns** | display defect, undisclosed (found 2026-07-21 during hand-replication: quarterly cells matched, the whole post-Q12 Total column differed on stock lines) | Foundry's `rowIS` takes the total as a caller-supplied parameter; stock lines pass their ending value (e.g. NOL passes `nol.slice(-1)[0]`), flow lines fall back to summing. Rule: a stock line's "total" is its ending value, never a cross-quarter sum. Note: the summed total is **display-only in Roman — not consumed by any downstream calculation**; it cannot have propagated into equity, ratios, or any comparison |

---

# PART III — THE FLOOR CHECKLIST

Format: **F-### [origin: P/R/both] — assertion Foundry v3 must satisfy — (defects fixed en route)**. "Origin" answers *whose* "I did this" question the item defends against.

**Configuration & metadata**
- F-001 [P] Engagement metadata: client, engagement ID, prepared-by, model version, projection date, charter type — captured, echoed on outputs.
- F-002 [P] Master configuration surface with product/module toggles across deposits (6), loans/assets (8), fees (6), structural (4); activation state *derived from* module presence (D-P13).
- F-003 [P] Capital-threshold parameter set (CET1 6.5, T1 8, Total 10, Leverage 5, CBLR 9 well-cap / 8 grace) — from REG_PARAMS with citations (D-P4).
- F-004 [both] All monetary values $000s; unit scale declared and actually applied.
- F-005 [R] Config persists: save, load, version — as data, not as spreadsheet state (D-R1).

**Time & cadence**
- F-010 [P] Pre-opening phase precedes projection start (absorbed as quarters; monthly inputs convert at import with documented conventions).
- F-011 [P] One canonical period index driving engine and every presentation cadence (D-P15); annual = Σ quarters verified by check (Patrick CHECKS #9).
- F-012 [P] Cadence is a *view* over one artifact (Script_Code intent), native rather than script-dependent (D-P17).
- F-013 [both] 3-year / 12-quarter default horizon; Patrick's inline year-rollup presentation reproducible.

**Pre-opening (Patrick I.9)**
- F-020 [P] Pre-open expense schedule by category (≥ his 10 categories incl. a Klaros advisory line and contingency), monthly-input convertible, cumulative burn tracked.
- F-021 [P] Capital sufficiency gate: cushion vs. minimum Day-1 requirement, SUFFICIENT/INSUFFICIENT flag wired into the check panel.
- F-022 [P] Day-1 seed balance sheet derived from raise − burn − seeded assets; organizational costs expensed into opening deficit.

**Products & taxonomy**
- F-030 [R] N arbitrary product objects mapped onto Call Report lines; multiple products per line aggregate.
- F-031 [P] Loan taxonomy ⊇ {consumer installment, credit card, C&I, resi mortgage, CRE}; deposit taxonomy ⊇ {retail demand, MMDA/savings, time/CD, brokered, sweep/program, institutional} (D-R9).
- F-032 [P] Time-deposit insurance bucketing (<$250K / ≥$250K) as assumption-driven, not hardcoded 60/40 (D-P7).
- F-033 [R] Off-balance-sheet commitment products (notional, growth, fees) with CCF treatment under standardized RWA (D-R17).
- F-034 [R] Presets with complete parameter sets; custom product creation.
- F-035 [R] Per-field conservative defaults with a disclosure log naming every default applied.
- F-036 [P] Payment-processing product module: per-tx fee/cost pairs for ACH, wires, RTP, FedNow, card; volumes as real config (D-P11).

**Rates**
- F-040 [R] Fixed vs. floating per product; floating = index + spread repricing each period.
- F-041 [R] Editable quarterly SOFR path, sourced (FOMC SEP + basis), with longer-run glide for valuation horizons; single rate framework that products actually consume (fixes D-P2).
- F-042 [both] Every product yield/cost accrues on average balances at period-fraction of annual rate.

**Asset mechanics**
- F-050 [both] Loan rollforward: beg + originations(growth path) − runoff − NCO, floored at zero; averages; interest on averages.
- F-051 [both] ALLL at reserve rate on ending balance (AC only); provision = ΔALLL + NCO.
- F-052 [P] Securities detail: AFS and HTM blocks with purchases/maturities/amortization structure and an AOCI line on AFS (D-R6); IB cash and fed funds as earning-asset blocks.
- F-053 [P] Fixed assets with depreciation schedule (D-R7); other assets driver documented (Patrick: % of asset base — note his base excludes cash/premises; ours must state its base).
- F-054 [R] Originate-to-sell: sold share, cohort warehouse with holdQtrs, half-quarter interest conventions, GOS at sale (AC) vs. at origination (FVO), HFS line with no ALLL.
- F-055 [R] MSR: retained-servicing UPB rollforward, capitalization into GOS, amortization ∝ runoff, net servicing income line, MSR as BS asset.
- F-056 [R] Fair value option per product: DCF (60q, terminal repayment, glided curve), day-one adj to opening RE with note, ΔFV through earnings, FVO credit losses via FV P&L not provision, off-market-pricing warning.

**Liability & funding mechanics**
- F-060 [both] Deposit rollforward: beg + growth − runoff; interest on averages. Maturity inputs either drive behavior or don't exist (D-P9).
- F-061 [P] Borrowings as scheduled instruments: FHLB draws/rate/amortization, other borrowings (D-P12).
- F-062 [R] Balancing convention: cash floor % of contractual deposits; surplus → securities; shortfall → borrowings; simultaneity between plug, funding income, and equity solved to convergence. (Patrick's cash-as-residual is *reproducible as a presentation convention* but the engine convention is Roman's.)
- F-063 [both] Other liabilities line (static acceptable if disclosed).

**Fees & expenses**
- F-070 [both] Fee modules ⊇ {interchange, BaaS/program, service charges, trust/fiduciary, GOS, other} with growth-capable drivers (fixes D-P10).
- F-071 [P] NIE categories ⊇ {comp (FTE × loaded comp with per-year FTE steps), core/tech, occupancy, marketing, legal & compliance, D&O/insurance, FDIC+OCC assessments, payment processing costs, other} (D-R8); keep the other-opex gross-up formulation `sub×r/(1−r)` or a documented equivalent.
- F-072 [P] FDIC assessment on the correct base (avg consolidated assets − avg tangible equity), OCC fee on assets (D-P14).
- F-073 [R] Product-attributed opex (% of avg balance + fixed) distinct from corporate overhead (single line + growth), both reported.

**Tax & equity**
- F-080 [R] Statutory tax on pre-tax after NOL carryforward; NOL ledger tracked and reported; DTA treatment disclosed (fixes D-P3).
- F-081 [P] Equity rollforward with explicit components (common, surplus, retained, AOCI): beg + NI + ΔAOCI + raises − dividends; average equity row.
- F-082 [P] Staged capital raises with true effective dates mapped to engine periods (D-P8); dividends plumbed even if zero.

**Regulatory capital**
- F-090 [both] CBLR: T1/avg assets with **true average** denominator (D-P5), 9%/8% tiering with reachable branches (D-P4), election toggle.
- F-091 [P] Standardized approach when not elected: risk-weight map ⊇ {0% cash/Fed, 20% agency + bank exposures incl. IB cash and FF sold (D-P6), 50% qualifying resi, 100% C&I/consumer/CRE, 150% classified}; CET1/T1; Tier 2 = min(ALLL, 1.25% RWA); all four ratios; AOCI opt-out election.
- F-092 [R] MSA 25%-of-Tier-1 threshold deduction (12 CFR 3.22(d)) hitting capital and average-asset denominator; below-threshold MSAs retained (250% RW under standardized).
- F-093 [R] CBLR eligibility guards: OBS >25% of assets; $10B ceiling.
- F-094 [R] Capital shortfall estimator (added capital to hold the floor), with stated approximations.
- F-095 [R] Disclosed non-modeled deductions carried forward as artifact notes (securitization-exposure GOS under 3.22(a); unconsolidated-FI investments) until modeled.

**Concentrations & diagnostics (Patrick CONC, complete)**
- F-100 [P] CRE/Total RBC vs 300%; C&D/Total RBC vs 100% **with a real C&D input** (D-P16b); C&I/loans; consumer/loans; single largest borrower vs 15% LLL; brokered/deposits vs 25%; wholesale funding/liabilities; non-core funding/assets; loan-to-deposit vs 70–90% advisory; NIE/avg assets burden. Thresholds via REG_PARAMS.

**Stress**
- F-110 [R] Stress = full engine re-runs: credit (CO×, reserve×), rate (parallel bp on path + cash/sec/borrow; fixed coupons don't reprice), combined; four downturn overlays (volume haircut, GOS compression, MSR haircut, sale-share retention) — replacing Patrick's disconnected columns (D-P1) while preserving his S1/S2 annual presentation shape and scenario labels/active flags.
- F-111 [R] Stress outputs: breach callouts with quarter and capital-add estimate; scenario metric matrix; NI-by-quarter and leverage-by-quarter tables; the stressed-out-earns-base honesty flag; calibration provenance disclosed ("working assumption; regulators prescribe their own scenarios").
- F-112 [P] The SENS stub's intent — one-variable low/base/high sensitivity on NIM/ROA/capital — as a distinct feature from scenario stress.

**Checks & flags**
- F-120 [P] Integrity check panel: named assertions ⊇ his 10 (A=L+E all cadences; equity ties; NI→RE; capital floor each period; pre-open sufficiency; toggle consistency; period-index integrity; rollup integrity; parameter resolution) with master status surfaced on the overview; labels test exactly what they claim (D-P16).
- F-121 [R] Reasonableness flag engine ⊇ his full catalog (II.9) in examiner voice with severities — with bands recomputed from live peer data, dated and cited (D-R12): the "well, you did that" centerpiece. **SAT (provisional)**: the substrate consumption path is live — per-quarter percentile bands (p10/p25/p50/p75/p90) over identity-gated Call Report values (corrupt filer values quarantined at ingest by per-family reconciliation gates, exclusion before the value exists rather than post-hoc flag filtering), served with provenance (basis, certified, computed_at, n per point) through /api/v31/peer-bands for both the broad cohort and arbitrary cert-list cohorts (the Konrad shape — one query serves both features); corridor rendering on the Peer tab with small-n honesty (n<8: percentiles approach member values, presented as the range of named peers, not a distribution); metric coverage today: ROA (fixture-provisional), with NIM/efficiency/tier1 arriving as substrate data and deposit-mix pending the substrate's M6a; the *certified* designation flips — a data label, not a schema change — when the substrate's UBPR percentile-reconciliation gate (Deliverable D) blesses the distributions. Gate T60.
- F-121a [P] Tax detail module (origin: Patrick's tax/NOL design note, 2026-07-21): NOL → DTA with ASC 740 current/deferred split, IRC §172 utilization limit, VA modes, full CET1 deduction per 12 CFR 3.22(a) — presence-toggled, off = legacy treatment byte-compatible. SAT; gate T61; ENGINE_SPEC section.
- F-121b [P] Credit regime module (origin: Patrick's CECL/fair-value design note, 2026-07-21, scrutinized: incurred loss not electable under ASC 326, AFS-vs-HFS category fix): ACL vocabulary + day-one provision decomposition, per-product regime census; presentation-only, totals gated byte-identical. SAT; gate T62; ENGINE_SPEC section.
- F-122 [both] Integrity and viability are separate check classes, both visible (D-P18).

**Presentation, FTP, export**
- F-130 [R] FTP toggle: SOFR charge/credit on avg balances incl. warehouse, Treasury mismatch center, presentation-only, memo semantics both states.
- F-131 [R] Product Detail contribution view (per-product 12Q economics incl. GOS, servicing, NCOs, FTP).
- F-132 [P] Quick-stats overview (his 8 metrics × 3 years, CBLR-aware capital metric) and navigation surface.
- F-133 [R] Multi-sheet export ⊇ his 6 sheets (BS, IS, Ratios, Per-Product Detail, Assumptions incl. defaults+flags logs, Stress); [P] plus Call-Report-schedule-named outputs with per-line references (RC/RI/RC-C/RC-R grammar), time-deposit buckets, AOCI line.
- F-134 [R] Zero-suppression: unused lines hidden, not rendered as zeros.
- F-135 [R] Methodology disclosure in the artifact: conventions, simplifications, and scope concessions in prose (his II.13 sets the bar; BUILD_NOTES/ENGINE_SPEC lineage continues it).
- F-136 [R] Live-recompute UX: debounced, badge-updating, input-preserving.

**Module roadmap (Patrick's stubs, I.8 — each becomes a real module or a documented deferral)**
- F-140 [P] BHC/double-leverage; F-141 Trust (AUM detail beyond static fee — fixing the D-P13 inconsistency); F-142 Interchange detail (count × ticket × network split − network fees); F-143 BaaS (programs × accounts × rev/account); F-144 Mortgage banking (pipeline → locked → HFS → GOS waterfall — largely satisfied by F-054/055, mapped explicitly); F-145 Credit card (utilization, interchange, losses, rewards); F-146 Peer benchmark — **superseded by live CharterIQ cohorts; his paste-in zone is the before picture**.

**Count:** ~60 floor assertions, 18 Patrick defects, 17 Roman limitations. A v3 feature that cannot be traced to an F-number is a flourish (welcome, but above the floor); an F-number without a v3 implementation or documented deferral is a floor breach.

---

*End of floor document. Companion narrative: `patrick-vs-roman-comparison.md` (same evidence base, argumentative form).*


**D-P19 — Deposit "Average maturity (months)" is a dead input.** ASSM_BS rows
41/46/51/56/61/66 (all six deposit products; Time carries 24, Brokered 12) are
referenced by zero formulas anywhere in the workbook — verified by a full-sheet
formula scan for `ASSM_BS!$C$41/46/51/56/61/66`. Maturity drives no repricing,
no scheduled rollover, no runoff: the roll uses the annual runoff rate alone.
Same class as the nine-input macro framework (D-P12): an assumption surface
that promises mechanics the model does not have. Foundry implements the intent as a real
mechanic instead: avg_maturity_m drives cohort roll-off on the quarterly clock
(ENGINE_SPEC § Deposit maturity; gates T55a–c) — the defect remains a defect
of the source workbook, where the label drives nothing.

## 35. One save, three doors; freeze is notarization, not storage
All engagement saves route through one dialog-free function: name = the
scenario name (top-right field), banner outcomes, no prompt() anywhere in the
flow (the Start link, the chevron-menu action, and the Configuration Save
button are the same door in three places). Freeze is distinguished in-app:
notarized evidence (config + result hashes, immutable, re-verifiable), never a
reusable profile — the Governance copy states it beside the button, and the
freeze label is the scenario name automatically.
