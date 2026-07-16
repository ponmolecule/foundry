# APP → PATRICK ASSUMPTION MAP (v1, 2026-07-15)
Direction: every workspace field → its cell in Patrick's workbook, or **ABSENT**.
(The reverse direction — Patrick-has-app-lacks — is in INPUT_CONCORDANCE.md: deposit
maturities, staged raises, pre-opening grid, FTE/comp structure, FDIC/OCC assessments,
payment rails, AOCI.)

## Deposit products (app card fields)
| App field | Patrick cell | Status |
|---|---|---|
| opening_balance | Day-1 opening per deposit type | match |
| growth_q | monthly net-new $ adds (×3) | match (unit) |
| runoff_q | annual runoff rate (/4) | match (unit) |
| rate_paid_ann | cost of funds per type | match |
| rate_type = float + index_spread (deposit beta) | — | **ABSENT** — his deposit costs are flat; no repricing behavior |
| fee_yield_ann (per product) | — (service charges live centrally, per account) | **ABSENT at product level** |
| opex_pct_ann / opex_fixed_m (per product) | — (all costs central) | **ABSENT** |
| per-quarter overrides (any field) | — (one flat scalar rules 36 months) | **ABSENT** |
| call_report_line | implicit in tab layout | match (ours explicit) |

## Lending products (app card fields)
| App field | Patrick cell | Status |
|---|---|---|
| opening_balance | Day-1 opening per loan class | match |
| originations_q | monthly net-new originations (×3) | match (unit) |
| orig_growth_q | — (flat originations forever) | **ABSENT** |
| runoff_q | annual prepayment/paydown (/4) | match (unit) |
| yield_ann | average loan yield | match |
| rate_type = float + index_spread | — (all yields fixed) | **ABSENT** — no floating-rate loans anywhere |
| fee_yield_ann | — | **ABSENT** (loan fees not modeled) |
| charge_off_ann | annual NCO rate | match |
| provision_rate_ann (decoupled from NCO) | — (provision implied by NCO+ALLL only) | **ABSENT** |
| reserve_rate_pct_bal | ALLL reserve rate (% gross) | match |
| measurement (amortized vs fair value, ASC 825) | — | **ABSENT** — no measurement election |
| **mortgage_banking block** — sale_pct_of_orig, gain_on_sale_margin, warehouse_hold_q, servicing_retained_pct, servicing_fee_bp_ann, msr_cap_rate_pct_upb, msr_decay_q | — (his MORT tab is an empty stub) | **ABSENT ×7** — the entire originate-to-sell/MSR economics |
| per-quarter overrides | — | **ABSENT** |

## Globals
| App field | Patrick cell | Status |
|---|---|---|
| rate_path_q (12 quarterly points) | fed funds / prime / 10Y, one per year | coarser match (annual steps) |
| rate_path_longer_run (5bp/qtr glide beyond Q12) | — | **ABSENT** |
| tax_rate | 21% cell | match |
| tax_semantics (NOL carryforward engine) | tax line **= 0** placeholder | **ABSENT** (his own label says so) |
| cash_target_pct_deposits (liquidity policy → derived cash) | IB cash typed as balances | different philosophy: he types the answer; app types the policy |
| securities_yield / cash_yield | AFS/HTM yields; IB cash rate | match |
| borrow_rate_ann (residual funding price) | FHLB rate (typed draws) | partial — his borrowing is typed, ours derived |
| overhead_q + overhead_growth_q | FTE×comp + six cost lines (finer) | match at different aggregation |
| premises_equipment / intangibles / other_assets / other_liabilities | premises + depreciation; other assets % | rough match; intangibles **ABSENT** in his |
| min leverage (chartering commitment, as a constraint w/ source) | threshold display cells | match in value, different in role |

## Stress (app sidebar dials)
charge_off_mult · reserve_mult · rate_shock_bp · origination_volume_haircut ·
gos_margin_compression · msr_value_haircut · sale_share_retention_shift
→ **ALL SEVEN ABSENT** — his SENS tab is an empty stub; his two scenario toggles wire to nothing.

## The count
Of the app's ~70 distinct assumption concepts: **~24 have no home anywhere in Patrick's
workbook.** They cluster in exactly four themes: (1) rate behavior — floating/beta/glide;
(2) accounting elections — fair value, NOL, decoupled provisioning; (3) the
originate-to-sell business — all seven mortgage-banking fields; (4) machinery — per-quarter
overrides and the stress dials. Themes 2–4 are also his own stub tabs (tax placeholder,
MORT, SENS), i.e., things he *named and left unbuilt* — the app's absences from his
workbook are largely his roadmap, shipped.
