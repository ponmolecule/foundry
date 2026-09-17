# Fixed Assets / CAPEX — Canonical Foundry Contract

## Purpose

Foundry separates **pre-opening expenses** from **capital expenditures** and exposes two active fixed-asset authoring methodologies. The methods answer different economic questions but converge on the same statement outputs: gross PP&E, accumulated depreciation, net PP&E, depreciation expense, and CAPEX/disposal flow.

- Pre-opening organizational expenses are expensed before opening and reduce opening retained earnings/equity.
- CAPEX is capitalized into fixed assets. It consumes cash/funding but does **not** create an opening retained deficit merely because it was purchased before M1/Q1.
- Depreciation is owned by the fixed-asset subsystem, not duplicated as an unrelated Opex assumption.

## Active authoring methodologies

### Formula / level

`assumptions.fixed_assets.mode = "formula_level"`

Use Formula / level when the source model determines the fixed-asset **level directly** rather than reconstructing it from purchases and asset vintages. The canonical stock equation is:

`period-end net fixed assets = entered base level + Σ(linked Series × multiplier)`

The base and each multiplier may use the ordinary Foundry Flat / Growth / Explicit trajectory grammar. A multiplier is a **stock coefficient** (for example `$5k per employee`) and therefore has no Month / Quarter / Year amount period of its own. The linked Series owns its level and cadence.

The first supported browser driver is the stable Workforce Count Series (total workforce or a role/cohort count). The resolver itself consumes Foundry's typed linked-Series contract rather than branching on display names such as "employee".

Depreciation has two authoring choices:

- **% of asset level** — entered Flat / Growth / Explicit depreciation-rate path multiplied by the resolved period-end net asset level.
- **Entered amount** — entered Flat / Growth / Explicit depreciation expense path.

Both depreciation choices own an explicit natural period where applicable: Month / Quarter / Year. Explicit schedule cadence is a separate concept from the natural period. Foundry periodizes the authored amount/rate exactly once.

The Formula / level stock is authoritative **net PP&E**. Foundry does not invent useful lives or disposal records merely to explain a directly-authored level. Instead it reconciles:

- `accumulated depreciation_t = accumulated depreciation_(t-1) + depreciation_t`
- `implied gross PP&E_t = net PP&E_t + accumulated depreciation_t`
- `implied CAPEX/(disposal)_t = net PP&E_t - net PP&E_(t-1) + depreciation_t`

A negative implied CAPEX value is an implied disposal/reduction; it is not floored away.

### Asset schedule

`assumptions.fixed_assets.mode = "schedule"`

Use Asset schedule when the source model explains the balance through transactions/vintages. Each new/CAPEX asset can provide:

- `name`
- `cost` — raw dollars internally
- `in_service_period` — 0 means at opening; 1..N is a native model period
- `useful_life_years`
- `method` — currently `straight_line`
- `residual_value` — optional, default 0

Existing/opening assets can instead provide:

- `opening_gross_cost`
- `opening_accumulated_depreciation`
- `remaining_life_years`
- optional `residual_value`

The compact browser UI exposes the common new/CAPEX case. FIW exposes the full schedule record for audit/editing.

## Why Formula / level is not a third carve-out

The historical UI called the non-schedule path **Simple**, but that label was too narrow once asset levels could be causally derived. The active conceptual split is now:

- **Formula / level** — determine the state/level directly each period.
- **Asset schedule** — derive the state from transaction/vintage history.

Historical `premises_equipment + premises_depreciation_annual` remains readable as an internal backward-compatibility state. It is not presented as a third active methodology. When explicitly converted in the browser, Foundry materializes an equivalent Formula / level Explicit path so the conversion itself does not silently change economics.

## Timing

For Asset schedule:

- `in_service_period = 0`: asset is on the opening balance sheet; depreciation begins in period 1.
- `in_service_period = t > 0`: gross PP&E increases in period `t`; straight-line depreciation begins in that same model period.

For Formula / level:

- `opening_net` is the opening balance.
- `base_spec` and linked components resolve the period-end net level for periods 1..N.
- depreciation is recognized in the same model period using the chosen entered amount or rate-on-level rule.

Both methods are native-cadence and preserve explicit natural-period semantics.

## Canonical statement series

The fixed-asset subsystem produces:

- Gross fixed assets
- Accumulated depreciation
- Net fixed assets
- CAPEX / implied CAPEX-disposal
- Depreciation expense

`financials.bs.premises` remains the net PP&E line for compatibility. Presentation also exposes:

- `financials.bs.premisesGross`
- `financials.bs.premisesAccumDep`
- top-level `fixed_assets` audit detail

Depreciation feeds the Income Statement's separate depreciation line and therefore Total NIE.

## FIW

Asset schedule uses `ASSM_FIXED_ASSETS`. Formula / level uses `ASSM_FIXED_ASSETS_LEVEL`. The Formula / level sheet keeps the causal grammar visible: base level, existing linked component identity, multiplier paths, depreciation source, and depreciation path. Stable Series IDs are facts in FIW; add/remove or retarget linked components in the app so link identity is never guessed from workbook text.

## Pre-opening accounting

Opening organizational expense burn remains:

`opening retained earnings impact = - sum(pre_opening.expenses)`

Asset-schedule pre-opening CAPEX is **not** included in that burn. Instead, it is included in opening fixed assets and reduces available liquid funding through the existing balance-sheet funding waterfall.

The public `pre_open` result distinguishes `burn_total`, `preopening_capex`, `cash_uses_total`, `equity_cushion`, and `cash_after_preopening_uses`.

## Backward compatibility

Saved configurations with `fixed_assets.mode = "schedule"` remain Asset schedule. Saved configurations using the historical Simple contract or omitting `fixed_assets` continue to execute the old `premises_equipment + premises_depreciation_annual` arithmetic byte-for-byte until the user explicitly chooses Formula / level. That explicit conversion preserves the visible historical path rather than silently reinterpreting the old opening balance as a flat forever balance.
