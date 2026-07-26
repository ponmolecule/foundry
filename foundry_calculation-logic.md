# Foundry — Calculation Logic

**Engine:** `foundry-engine 0.3.0 / v2-quarterly` · traced from the running code, not from intent

This document captures every calculation in the current Foundry projection engine, in the order the engine computes them, so you can see what feeds what. It is written from the source (`foundry/v2/`), verified against the code that ships today. Where the engine simplifies, the simplification is stated plainly. Dollars in, dollars out; the projection horizon is **12 quarters** and the clock is **permanently quarterly** — monthly inputs are converted at import (§1), never run natively.

The spine: config → validate → (for each scenario) apply overlays → project every product quarter by quarter → aggregate → solve the funding waterfall iteratively → income statement → capital & ratios → contributions (FTP) → checks & flags. Sections below follow that order.

---

## 0. Orchestration — how one run is assembled

`run_v2(cfg)` is the top of the engine. It:

1. Deep-copies the config and **validates** it (fail-closed: nothing is computed if the config is invalid).
2. Computes a `config_hash` (SHA-256, first 12 hex chars) for determinism/auditability — identical config in, identical results out, forever.
3. Builds the **scenario set** (§9) and runs each scenario through the engine independently.
4. Takes the `base` scenario as the reported financials; the stress scenarios feed the scenario table, constraint tests, and capital-shortfall estimate.
5. Assembles the output: financials (balance sheet, income statement, ratios), per-product detail, the FTP contribution view (§8), scenario metrics, constraint tests (§10), flags (§11), and the DFAST three-way charge-off comparison.

Each scenario is run by `run_parity` → `run_pf_a` (the profile-A engine, which is the main projection described here). A parallel profile-B engine (`run_pf_b`) exists for the alternate parity fixture; the calculation logic below is profile A, the production path.

**Unit convention.** The engine computes in **dollars**. The parity/display layer (`_conv`) converts to **$000s** and rounds ratios to 2 decimals for presentation. One field, `ftp_rate`, is deliberately exempt from rounding because it is a decimal rate *consumed* to compute a dollar charge — rounding it corrupts the FTP calculation.

---

## 1. Cadence — monthly inputs become quarterly at import

The engine clock is quarterly and never monthly. Inputs that are naturally monthly are converted once, at import, with documented conversions:

- **Durations** given in months (e.g. `avg_maturity_m`, deposit `duration_months`) are divided by 3 to get quarters (`div3`).
- **Fixed operating cost**: the canonical key is `opex_fixed_q` (per quarter). Legacy configs stored `opex_fixed_m` (per month); those are read at run time and multiplied by 3 to get the quarterly figure. `opex_fixed_q` wins if both are present. (`opex_fixed_q(p)` in `engine_q_a.py`.)
- **Service-charge and BaaS monthly fees** (`fee_m`, `rev_per_acct_m`) are multiplied by 3 inside the fee module to get the quarterly amount.

Nothing in the engine runs on a monthly step; these conversions are the only place months appear.

---

## 2. The rate path — the spine every price hangs off

`rate_fn(path_q, longer_run)` builds the forward annual-rate lookup `rate(t)`:

- For quarters 1–12, `rate(t)` returns the entered `rate_path_q[t-1]` (the SOFR path, e.g. derived from the FOMC SEP).
- Past quarter 12 (used only by the 60-quarter fair-value DCF, §6), it **glides 5 bp per quarter** toward `rate_path_longer_run` — stepping down if the last path rate is above the long-run rate, up if below, and clamping at the long-run level.

Every product's price is read through this path via `_prod_rate(p, t, rate)`, strictly gated by the product's `rate_type`:

- **Floating** (`rate_type == "float"`): rate = `rate(t) + index_spread` (the spread can be overridden per quarter).
- **Fixed lending**: rate = `yield_ann`.
- **Fixed deposit**: rate = `rate_paid_ann`.

The selector is the *type*, never which field happens to exist in the config — an inactive rate field may persist, and the engine ignores it unless the type points at it. Any of these can be overridden for a specific quarter via `overrides` (`_ovq`).

---

## 3. Pre-computed schedules (built once, before the quarter loop)

Before projecting products, the engine lays down several deterministic schedules:

**Capital timeline `cap_t[0..12]`.** Starts at `target_state.initial_capital` in every quarter, then each staged `capital_raise` adds its amount from its stated quarter onward. Raises are additive and land at the *start* of their quarter; the funding waterfall absorbs the cash. (The validator hard-blocks a zero initial capital before raises are read — raises supplement, they don't replace a Day-1 base.)

**Scheduled (term) borrowings `sched_t` and interest `sched_int_t`.** FHLB-style term advances are modeled as **bullet** draws: the full `amount` is held flat for `term_q` quarters (outstanding from `quarter` through `quarter+term_q-1`), then matures to zero. Interest is a full-quarter accrual on the outstanding principal (`amount × rate_ann / 4`) each quarter it is alive, and zero after maturity. A term advance is a discrete lump, so — unlike balance-driven products — it is **not** averaged.

**Premises & depreciation.** `premises_equipment` depreciates straight-line by `premises_depreciation_annual/4` each quarter: `prem_t[q] = max(0, premises − dep_q·q)`. The quarterly depreciation expense `dep_exp_t[q]` is the period-over-period drop, and flows into overhead (§7).

**Non-earning assets `non_earn_t[q]` = premises + intangibles + other_assets** (premises declining as above).

**Securities books (AFS/HTM).** Each security's balance path rolls forward: `bal[q] = max(0, bal[q-1]·(1 + growth_q − runoff_q) + purchases_q)`. Average balance is `(bal[q-1]+bal[q])/2`. HTM income accrues at the security's own fixed coupon and is **not** touched by the rate shock — that is what HTM means (§9).

---

## 4. Per-product projection — deposits & OBS (term-cohort aware)

For each deposit (and off-balance-sheet exposure), the engine walks quarters 1→12. Two modes, chosen by whether the product has a term:

**No term** (`avg_maturity_m` → 0 quarters): a simple balance roll.
```
end = max(0, beg·(1 + growth_q − runoff_q) + new_deposits_q)
```

**Term products** (`avg_maturity_m/3 = mq > 0`): a **cohort ladder**. The opening balance is seeded as a seasoned even ladder — `1/mq` of it in each of `mq` age buckets. Each quarter:
- every existing cohort is reduced by `runoff_q`,
- the cohort that reaches age `mq` **matures and exits** the balance sheet whole,
- new inflow (`growth_amt + new_deposits_q`) forms a fresh cohort,
- the ending balance is the sum of surviving cohorts.

Either way, per quarter the engine records:
- `avg = (beg + end)/2`
- interest **expense** (deposits) = `avg × rate / 4` (rate from §2; OBS pay nothing)
- fee income = `avg × fee_yield_ann / 4`
- operating expense = `avg × opex_pct_ann / 4 + opex_fixed_q`

---

## 5. Per-product projection — lending (the credit engine)

For each lending product, quarters 1→12:

**Balance roll.**
```
charge-off (co) = beg × charge_off_ann / 4
originations (o) = originations_q × (1 + orig_growth_q)^(q−1)      [per-quarter overridable]
retained        = o × (1 − sale_pct)          # the part kept on balance sheet
sold            = o × sale_pct                # the part sold (originate-to-sell)
end = max(0, beg + retained − beg·runoff_q − co)
avg = (beg + end)/2
```

**Interest & the rest, per quarter:**
- interest **income** = `avg × rate / 4` (plus warehouse interest, below)
- fee income = `avg × fee_yield_ann / 4`
- operating expense = `avg × opex_pct_ann / 4 + opex_fixed_q`
- **ALLL (reserve)** carried at `end × reserve_rate_pct_bal` (reserve-maintenance: the balance-sheet reserve is always this fraction of the ending book). For fair-value products, ALLL is zero (no reserve on a mark-to-market asset).

**Warehouse (originate-to-sell hold).** When `sale_pct > 0`, sold loans sit in a held-for-sale warehouse for `warehouse_hold_q` quarters before settlement. The engine walks the cohorts and accrues a **half-quarter coupon** at origination and at sale (weights 0.5 at the entry and exit quarters, 1.0 while fully held), adding that interest to the product's income. The warehouse carry (`_wh`) is a funded asset on the balance sheet during the hold — which is why it also bears an FTP funding charge (§8).

**Gain-on-sale.** Realized at settlement: `sold × gain_on_sale_margin`. For fair-value products the gain is recognized at origination; otherwise it lands `warehouse_hold_q` quarters later, when the loan actually settles.

**MSR (servicing retained).** When a share is retained for servicing, at each settlement:
- `add = settled × servicing_retained_pct` feeds the serviced UPB;
- UPB rolls with `msr_decay_q`: `upb = max(0, upb_beg·(1 − decay) + add)`;
- the MSR asset capitalizes `cap = add × msr_cap_rate_pct_upb` and amortizes `amort = msr_prev × decay`, so `msr = max(0, msr_prev + cap − amort)`;
- servicing fee income = `avg_UPB × servicing_fee_bp_ann / 10000 / 4`;
- net servicing = fee − amortization; the capitalized MSR value is also folded into gain-on-sale at settlement.

**Fair value (FVO).** For fair-value products, the existing book is repriced each quarter by a 60-quarter DCF (`_fv_of`, §6). The fair-value adjustment `fvAdj = fair_value − book` is carried on the balance sheet, and the *change* in that adjustment (net of charge-offs) flows to the income statement as FV P&L (§7).

---

## 6. Fair-value DCF (`_fv_of`) — the 60-quarter mark

For a fair-value product at end of quarter `q`, the engine discounts 60 quarters of projected cash flows on the existing book:

- Each future quarter `t`: interest = `balance × coupon_rate(q+t)/4`, principal = `balance × decay`, charge-off = `balance × charge_off_ann/4`.
- The coupon uses the product's own rate path; the **discount rate** is `rate(q+t) + discount_spread_ann` (the forward path plus a spread), applied quarter-compounded.
- Present value accumulates `(interest + principal) × discount_factor`; the balance amortizes by `principal + charge-off` each step; any residual at the horizon is discounted back.
- For liabilities, decay uses `fv_decay_q` (default 0.10) and no charge-off.

The **day-one** FV adjustment (the mark at q=0) is booked straight into opening retained earnings (§7).

---

## 7. Income statement & the iterative funding solve — the heart

This is where the balance sheet closes on itself. For each quarter, the "easy" income lines are summed directly from the products:

- **loan interest** = Σ lending interest income
- **deposit expense** = Σ deposit interest expense
- **fees** = Σ product fees + fee-module income (§7a)
- **product opex** = Σ product operating expense
- **NCO** = Σ charge-offs; **gain-on-sale** = Σ GOS; **servicing net** = Σ net servicing
- **FV P&L** = Σ (change in FV adjustment − charge-off) over fair-value products
- **provision** = (ALLL_end − ALLL_beg) + accrual-book NCO — i.e. the reserve build/(release) plus replenishing charge-offs
- **book interest** on securities = Σ `avg × yield_ann / 4` (AFS + HTM at their own coupons)

**Overhead** = `overhead_q × (1 + overhead_growth_q)^(q−1) + depreciation`. If the granular NIE module is present, overhead is instead built from FTE-step compensation, category lines, and regulatory assessments — **FDIC** on `max(0, avg assets − avg tangible equity) × 5.0 bp/4` and **OCC** on `avg assets × 1.5 bp/4` — plus the configured "other" gross-up `sub × r/(1−r)`. Fee-module rail costs are added to overhead as well.

Then the circular part. Net interest income depends on cash and securities balances; those balances depend on equity; equity depends on net income; net income depends on net interest income. The engine **iterates to a fixed point** (up to 60 passes, converging when net income moves less than $0.0001):

```
repeat:
    equity_end = cap_t[q] + retained_earnings + ni + AOCI
    (cash, securities, borrowings) = plug(...)          # the funding waterfall, below
    securities interest = (avg securities) × securities_yield/4 + book interest
    cash interest       = (avg cash) × cash_yield/4
    borrowing expense   = (avg borrowings) × borrow_rate_ann/4 + scheduled interest
    NII    = loan_int + sec_int + cash_int − dep_exp − borr_exp
    pretax = NII + fees + FV_PnL + GOS + serv_net − NIE − provision
    tax    = f(pretax, NOL)          # §7b
    new_ni = pretax − tax
    if |new_ni − ni| < 1e-4: stop
```

**The funding waterfall (`plug`).** Given the liability and equity side, the engine plugs the asset side:
```
funding    = deposits + other_liabilities + equity + scheduled_borrowings
investable  = funding − net_loans − non_earning_assets − MSR − securities_books
required_cash = cash_target_pct_deposits × deposits
if investable ≥ required_cash:   cash = required_cash;  securities = the surplus;  borrowings = 0
else:                            cash = required_cash;  securities = 0;  borrowings = the shortfall
```
So cash is held to its floor, any surplus goes to the securities portfolio, and any deficit is filled with borrowings. This is the mechanism that makes the balance sheet balance every quarter.

**Retained earnings** accumulate net income each quarter (`re += ni`), starting from the day-one mark (§6) minus pre-opening burn (§7c). **Equity** = paid-in capital (`cap_t`) + retained earnings + cumulative AOCI. **Total assets** = cash + securities + securities books + net loans + non-earning + MSR (+ DTA if the tax module is on).

### 7a. Fee modules (all default-off, additive)
`fee_module_series` produces quarterly income (and cost) from optional modules, each with its own growth path:
- **Interchange**: `tx_count_q·(1+g)^(q−1) × avg_ticket × (interchange_rate − network_fee_rate)`.
- **Payments rails**: per rail, `vol·fee_per_tx` income and `vol·cost_per_tx` cost (cost lands in overhead).
- **Service charges**: `accounts·(1+g)^(q−1) × fee_m × 3` (monthly fee → quarterly).
- **Trust**: `avg_AUM × fee_bp_ann/10000/4`, AUM growing at `aum_growth_q`.
- **BaaS**: `programs·accts_per_program·(1+g)^(q−1) × rev_per_acct_m × 3`.

### 7b. Taxation — NOL carryforward, optional DTA presentation
The default treatment: losses build a net-operating-loss balance; profits are shielded by it. `taxable = max(0, pretax − NOL)`, `tax = taxable × tax_rate`, and the NOL is drawn down (or grown by the loss) each quarter.

When the `tax_detail` module is on, the same economics are presented under ASC 740: the NOL utilization is capped at **80%** of pretax (`nol_utilization_limit_pct`), current vs. deferred tax are split, a gross DTA (`NOL × tax_rate`) is carried with a valuation allowance (auto when cumulative taxable income is still negative, or a fixed percentage), and the net DTA appears on the balance sheet. The OFF path is byte-identical to the simple shield-everything treatment.

### 7c. Pre-opening burn & day-one equity
Organizational costs (`pre_opening.expenses`) are **expensed into the opening deficit**, not capitalized: `equity0 = initial_capital + day_one_FV_mark − pre_opening_burn`. This is why a de novo opens with negative retained earnings.

### 7d. Credit-regime decomposition (optional, additive)
When `credit_regime` is on, the *same* provision is split for presentation into day-one CECL (`reserve_rate × retained originations`), reserve build/(release), and NCO replenishment. Purely a decomposition — the totals are unchanged.

---

## 8. Contributions & FTP (`_ftp_view`) — who earns what

Funds-transfer pricing charges each asset for the funding it uses and credits each liability for the funding it provides, at the path rate — with a treasury center holding the residual so the whole thing ties to consolidated pretax exactly.

Per product:
```
FTP base = Σ_q (avg_balance[q] + avg_warehouse[q]) × ftp_rate[q] / 4
```
- `ftp_rate` is the forward path rate `rate(q)` (full precision — never rounded).
- The base **includes the held-for-sale warehouse** average (opening warehouse taken as 0 for q1), because warehouse loans are funded assets during the hold.
- **Sign**: lending is charged (−1), deposits are credited (+1), OBS neutral (0).

```
economics    = interest + fees − opex − credit_costs + gos + servNet
contribution = economics + sign × FTP
```
The **treasury center** = consolidated pretax − Σ contributions, so the reconciliation is exact by construction. FTP is presentation-only: it nets to zero across the bank and never touches the income statement or balance sheet. (This is why an FTP bug can hide from the balance-checked test suite — it's a zero-sum overlay.)

---

## 9. Scenarios & stress overlays

`scenarios_from` builds the scenario set from the sidebar stress parameters (defaults shown):

| Scenario | What changes |
|---|---|
| **Base Case** | the plan as entered |
| **Credit Deterioration** | charge-offs ×`charge_off_mult` (2.5), ALLL ×`reserve_mult` (1.5) + downturn overlays |
| **Rate Shock** | parallel `rate_shock_bp` (+300 bp) + downturn |
| **Combined** | credit + rate together |
| **DFAST Severe** | absolute supervisory 9-quarter cumulative loss rates by call-report line, front-loaded, + downturn (always shown) |

The shared **downturn overlays** (applied to all stress scenarios): origination volume haircut (40%), gain-on-sale margin compression (40%), MSR value haircut (20%), sale-share retention shift (25%).

`_apply_overlays` implements them:
- **Rate shock** adds the shock (bp/10000) to cash yield, securities yield, borrow rate, the whole rate path, and the long-run rate — **but not HTM coupons**.
- **Charge-off multiplier** scales each product's `charge_off_ann`; **reserve multiplier** scales `reserve_rate_pct_bal`.
- **DFAST severe** *substitutes* a per-quarter charge-off schedule over the 9-quarter window instead of scaling: per-quarter rate = `weight_q × cum9`, annualized ×4. Weights are level (1/9 each) or **front-loaded** (`0.18, 0.16, 0.14, 0.12, 0.11, 0.09, 0.08, 0.07, 0.05`, summing to 1). The scale mechanism and the substitute mechanism never both run for one scenario.
- Volume haircut cuts originations; GOS/MSR/sale-share haircuts hit the mortgage-banking parameters.

When base-level overlays and scenario overlays combine (`_merge_overlays`): multipliers multiply, rate shocks add, other numerics take the max.

---

## 10. Capital, ratios & constraint tests

**Ratios**, per quarter (annualized where noted):
- **ROA** = `ni × 4 / avg_assets × 100`
- **ROE** = `ni × 4 / avg_equity × 100`
- **NIM** = `NII × 4 / avg_earning_assets × 100` (earning = avg gross loans + avg securities + avg cash)
- **Efficiency** = `(product_opex + overhead) / revenue × 100`, revenue = NII + fees + GOS + servNet
- **ALLL %** = `ALLL / gross_loans × 100`
- **Net charge-off rate** = `NCO × 4 / avg_loans × 100` — current-quarter, annualized ×4, over average loans, matching the peer band's UBPR one-quarter basis exactly (can go slightly negative when recoveries exceed charge-offs).

**Tier 1 / leverage** (12 CFR 3.22(d) simplification):
```
Tier1        = equity − intangibles − DTA_deduction
MSA excess   = max(0, MSR − 0.25 × Tier1)            # MSAs over 25% of Tier 1 are deducted
leverage_ratio = (Tier1 − MSA_excess) / (avg_assets − MSA_excess − DTA_deduction) × 100
```
Deducted MSAs come out of both the numerator and the average-assets denominator.

**CBLR framework** (`_cblr_checks`, presentation): total assets under $10B; OBS ≤ 25% of assets; trading ≤ 5% (structurally zero — no trading book); leverage above the **8%** CBLR requirement (lowered from 9%, effective 2026-07-01); and a grace-period state machine — above 8% is compliant, `(7%, 8%]` is grace (max 4 consecutive quarters, 8-of-20), at or below the **7%** floor is blocking.

**Constraint tests** (`_constraint_tests`): every declared constraint against every scenario, with the source cited — e.g. `leverage_min` (min leverage ≥ commitment) and `wholesale_funding_max_pct_assets` (peak borrowings/assets ≤ cap).

**Capital shortfall estimate**: the smallest additional opening capital to hold the leverage commitment at the worst scenario-quarter — a closed-form estimate that ignores earnings on the added capital (the exact bisection solve runs with the registered engagement).

---

## 11. Reasonableness flags

The challenge layer emits flags (advisory / severe), each carrying its class:
- `COUPLED*` → commercial assumption requiring support
- `REG*` → counsel determination required
- severe → commercial assumption requiring support; otherwise advisory

Where the peer/challenge layer calibrates against the CharterIQ substrate, flags attach peer evidence (cohort, sample size, Call Report category). No synthetic peer data feeds flags on this path — the old invented cohort is retired.

Notable coded flags include `GROWTH-Y1` (Q0→Q4 total-asset growth over 25% fires advisory), `SPREAD-VIAB` (blended-spread viability), and `COUPLED-*` (assumption-coupling). Regulatory thresholds enter via `REG_PARAMS` with name/date/status — never inline literals — and **pending** rules are annotated as proposed but never encoded until final.

---

## 12. Determinism & known simplifications

- **Deterministic**: identical config → identical results, attested by the config hash. No randomness, no wall-clock, no hidden state.
- **Fail-closed**: an invalid config raises before any arithmetic runs.
- **Quarterly, 12 quarters**: the horizon is the model's spine; monthly inputs are converted at import (§1), and the fair-value DCF is the only place the clock runs past Q12 (a 60-quarter valuation tail with a rate glide).

Simplifications stated where they occur above: the leverage denominator uses the current quarter's assets averaged with the prior (assessments accrue on the prior end to avoid a pre-plug circularity); the MSA deduction is the 25%-of-Tier-1 single-threshold form of 12 CFR 3.22(d), not the full three-bucket 250%-CET1 test; the capital-shortfall figure is a closed-form estimate, not the exact solve; FTP is a presentation overlay that never touches the primary statements; and trading assets are structurally zero because the model carries no trading book.

---

*This document describes the engine as it computes today (`foundry-engine 0.3.0`). It supersedes the earlier `foundry-engine 0.2.1` calculation write-up — the projection core is the same shape, but the quarterly-opex convention, warehouse-inclusive FTP, DTA/credit-regime decompositions, DFAST severe overlay, scheduled bullet borrowings, and the current CBLR 8%/7% grace framework are all newer.*
