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

`period-end fixed-asset level = entered base level + Σ(linked Series × multiplier)`

The base and each multiplier may use the ordinary Foundry Flat / Growth / Explicit trajectory grammar. A multiplier is a **stock coefficient** (for example `$5k per employee`) and therefore has no Month / Quarter / Year amount period of its own. The linked Series owns its level and cadence.

The first supported browser driver is the stable Workforce Count Series (total workforce or a role/cohort count). The resolver itself consumes Foundry's typed linked-Series contract rather than branching on display names such as "employee".

Depreciation has two authoring choices:

- **% of asset level** — entered Flat / Growth / Explicit depreciation-rate path multiplied by the resolved period-end asset level on the selected basis.
- **Entered amount** — entered Flat / Growth / Explicit depreciation expense path.

Both depreciation choices own an explicit natural period where applicable: Month / Quarter / Year. Explicit schedule cadence is a separate concept from the natural period. Foundry periodizes the authored amount/rate exactly once.

Formula / level owns an explicit `level_basis`:

- **`gross` (default)** — the authored stock is gross PP&E. Depreciation increases accumulated depreciation and reduces net PP&E. A flat gross level therefore does **not** create replacement CAPEX merely because depreciation is recognized. Signed implied CAPEX/(disposal) is the change in authored gross PP&E. If the gross level falls, Foundry relieves the same proportion of existing accumulated depreciation so the reduction occurs at carrying value rather than leaving depreciation attached to disposed assets. Depreciation is capped at the remaining depreciable carrying basis.
- **`net`** — the authored stock is an intentional net-PP&E target. Foundry reconciles gross PP&E as `net + accumulated depreciation`, and implied CAPEX/(disposal) is `Δnet + depreciation`. This mode is appropriate only when the source model truly intends depreciation to be replaced so the stated net level remains the target.

This explicit basis fixes the r119 accounting bug in which Formula / level silently assumed every authored stock was net PP&E. Under that hidden assumption, a flat asset level caused gross PP&E and implied CAPEX to rise every period by the depreciation charge. r120 defaults missing r119 `level_basis` values to **gross**, while retaining explicit `net` as an available target-maintenance contract.

Foundry does not invent useful lives or asset vintages merely to explain a directly-authored Formula / level stock.

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

- `level_basis` is `gross` or `net`; new/r120 authoring defaults to `gross`.
- `opening_level` is the opening balance on that selected basis. r119's `opening_net` remains a read-compatibility alias.
- `opening_accumulated_depreciation` records opening accumulated depreciation. On gross basis it cannot exceed opening gross PP&E.
- `base_spec` and linked components resolve the period-end level on the selected basis for periods 1..N.
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

Asset schedule uses `ASSM_FIXED_ASSETS`. Formula / level uses `ASSM_FIXED_ASSETS_LEVEL`. The Formula / level sheet keeps the causal grammar visible: level basis, opening level, opening accumulated depreciation, base level, existing linked component identity, multiplier paths, depreciation source, and depreciation path. Stable Series IDs are facts in FIW; add/remove or retarget linked components in the app so link identity is never guessed from workbook text.

## Pre-opening accounting

Opening organizational expense burn remains:

`opening retained earnings impact = - sum(pre_opening.expenses)`

Asset-schedule pre-opening CAPEX is **not** included in that burn. Instead, it is included in opening fixed assets and reduces available liquid funding through the existing balance-sheet funding waterfall.

The public `pre_open` result distinguishes `burn_total`, `preopening_capex`, `cash_uses_total`, `equity_cushion`, and `cash_after_preopening_uses`.

## Backward compatibility

Saved configurations with `fixed_assets.mode = "schedule"` remain Asset schedule. Saved configurations using the historical Simple contract or omitting `fixed_assets` continue to execute the old `premises_equipment + premises_depreciation_annual` arithmetic byte-for-byte until the user explicitly chooses Formula / level. That explicit conversion preserves the visible historical path by creating an explicit **net-basis** Formula / level schedule.

r119 Formula / level configurations remain readable. Their `opening_net` field is accepted as an alias for `opening_level`; because r119 did not expose a basis selector and its hidden net assumption was the bug being repaired, an r119 Formula / level configuration with no `level_basis` is interpreted as **gross** in r120. Users who intentionally need a maintained net-PP&E target can explicitly choose `level_basis = "net"`.
