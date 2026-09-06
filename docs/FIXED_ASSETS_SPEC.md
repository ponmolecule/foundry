# Fixed Assets / CAPEX — Canonical Foundry Contract

## Purpose

Foundry separates **pre-opening expenses** from **capital expenditures**.

- Pre-opening organizational expenses are expensed before opening and reduce opening retained earnings/equity.
- CAPEX is capitalized into fixed assets. It consumes cash/funding but does **not** create an opening retained deficit merely because it was purchased before M1/Q1.
- Depreciation is an **output of the fixed-asset subsystem**, not an independent expense assumption when Asset Schedule mode is active.

## Authoring modes

### Simple

For source models that provide one aggregate fixed-asset balance and one annual depreciation amount:

- `assumptions.premises_equipment`
- `assumptions.premises_depreciation_annual`

This is the legacy path and remains the default when no fixed-asset schedule is selected.

### Asset Schedule

`assumptions.fixed_assets.mode = "schedule"`

Each new/CAPEX asset can provide:

- `name`
- `cost` — raw dollars
- `in_service_period` — 0 means at opening; 1..N is a native model period
- `useful_life_years`
- `method` — V1 supports `straight_line`
- `residual_value` — optional, default 0

Existing/opening assets are also supported by the resolver using:

- `opening_gross_cost`
- `opening_accumulated_depreciation`
- `remaining_life_years`
- optional `residual_value`

The compact browser UI exposes the common new/CAPEX case. FIW exposes the full record for audit/editing.

## Timing

- `in_service_period = 0`: asset is on the opening balance sheet; depreciation begins in period 1.
- `in_service_period = t > 0`: gross PP&E increases in period `t`; straight-line depreciation begins in that same model period.
- The resolver is native-cadence. A 5-year asset depreciates across 60 periods in a monthly model and 20 periods in a quarterly model.

## Canonical series

The fixed-asset resolver produces opening + native-period series for:

- Gross fixed assets
- Accumulated depreciation
- Net fixed assets
- CAPEX
- Depreciation expense

`financials.bs.premises` remains the net PP&E line for compatibility. Schedule mode additionally exposes:

- `financials.bs.premisesGross`
- `financials.bs.premisesAccumDep`
- `financials.bs.capex`
- top-level `fixed_assets` audit detail

## Pre-opening accounting

Opening organizational expense burn remains:

`opening retained earnings impact = - sum(pre_opening.expenses)`

Pre-opening CAPEX is **not** included in that burn. Instead, it is included in opening fixed assets and therefore reduces available liquid funding through the existing balance-sheet funding waterfall.

The public `pre_open` result distinguishes:

- `burn_total`
- `preopening_capex`
- `cash_uses_total`
- `equity_cushion`
- `cash_after_preopening_uses`

The legacy minimum Day-1 capital test continues to compare post-expense equity cushion against the user-entered minimum; CAPEX is separately disclosed as a liquidity/cash use rather than incorrectly treated as an expense.

## Backward compatibility

If `assumptions.fixed_assets.mode != "schedule"`, Foundry executes the historical `premises_equipment + premises_depreciation_annual` path. Existing fixtures/configurations therefore retain their prior economics.
