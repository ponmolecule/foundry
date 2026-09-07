# Custody/Trust Fee Product — settled build spec (Claude/GPT convergence)

Verified on tracked build **0e0cefa**. All numbers below are engine-executed, not asserted.
Golden test: `tests_custody_reference.py` (10/10 passing).

## Architecture (both AIs agree)
ONE Fee Product ("Custody / Trust Services"), ONE shared CAC/customer-base AUC feed, SIX computational
fee streams. CAC channels build the AUC; they are not income streams. Split into multiple Fee Products
only when the underlying managed-notional differs (e.g. custody AUC vs wealth AUM).

## The six streams — status on 0e0cefa (AUC = $120MM reference)
| Stream | Basis (works today) | Annual $ | Cadence-stable today? |
|---|---|---|---|
| Custody fee | balance on AUC, 20bp | 240,000 | ✅ yes |
| Settlement fee | balance on derived AUC×4 turns, 5bp | 240,000 | ✅ yes |
| Reserve trustee fee | balance on derived 10%×AUC, 25bp | 30,000 | ✅ yes |
| Conversion income | balance on derived 24%×AUC, 50bp spread | 144,000 | ✅ yes |
| Trustee retainer | account | — | ❌ natural annual entry overstates 12× |
| Escrow add-on | flat | — | ❌ natural annual entry overstates 4× qtr / 12× mo |

## What works TODAY (no engine change): streams 1–4
Represented as balance-basis on a derived AUC quantity, they compute correctly and are cadence-stable.
NOTE (semantic debt, agreed): settlement/conversion are *flow* businesses; balance-basis is
arithmetically correct because its `/ppy` periodizes the annualized throughput, but it overloads
"balance." Usable now; should be relabeled, not enshrined as vocabulary.

## What needs remediation (the settled, narrow spec)
1. **Derived flow coefficients get natural annual periods + trajectories.** `turns × / Year`,
   `% of source / Year`, resolved to native period by ppy; coefficient supports Flat / Growth /
   Explicit schedule. → fixes the FY30 turns ramp AND lets settlement/conversion stay on the
   semantically-correct transaction basis.
2. **Account fees get natural per-Month/Quarter/Year units** (retainer $12k/yr, not hand-$1k/mo).
3. **Flat fees get natural per-Month/Quarter/Year units** (escrow $120k/yr).
4. **Remove the legacy `periods_per_q=3` landmine** in `fee_catalog.py`'s account template (GPT found:
   it overrides cadence-derived factors → monthly $360k vs correct $120k).
5. **Fail closed** on unsupported basis/source/trajectory/rate-behavior/cost — the current
   `unknown basis => 0` (asserted in tests) silently drops revenue; must be a validation error.

## Transition safety (Claude's addition)
When periodizing the derived coefficient (fix #1), guard against **double-periodization**: if a
now-periodized coefficient feeds a basis that already divides by ppy (balance), you'd get `/ppy²`.
The golden test must assert cadence-stability AND no double-division on whichever basis each stream
lands on — write it before the code, not after.

## How this exchange resolved (for the record)
- Claude wrongly claimed settlement/conversion needed a missing flow primitive → GPT correctly showed
  `managed_notional → derived → multiple/pct` expresses it. Claude conceded.
- GPT's initial transaction-basis mapping computed 12× high → Claude showed balance-basis is
  cadence-correct. GPT confirmed and conceded.
- GPT then correctly argued balance-for-flow is semantically wrong (arithmetically-right workaround);
  Claude conceded the design point.
- Every round was resolved by EXECUTION, not assertion. This spec is the converged result.

## Implementation note — post-design contract

The executable golden in `foundry/v2/tests_custody_reference.py` is the authoritative gate.
The implemented contract is opt-in and backward-compatible:

- legacy bare `driver.params.multiple` / `pct` retain raw model-period semantics;
- new `driver.params.coefficient = {kind, value, period, trajectory, ...}` expresses a natural-period flow and is valid only on transaction basis;
- coefficient paths support `flat`, `growth`, and `explicit_schedule`;
- account natural units use `rate.params.unit_fee = {value, period}`;
- flat natural units use `rate.params.flat_amount = {value, period}`;
- `periods_per_q` is retired and ignored by the evaluator; cadence comes from `ppy`;
- unsupported fee basis/source/trajectory/rate behavior/cost fails closed;
- a natural-period coefficient on balance basis is rejected structurally to prevent double-periodization.
