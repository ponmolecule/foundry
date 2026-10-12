# r318 — Visible, safely editable engagement setup

Built on r317 (00289dd). Includes all r314–r317 changes. No financial engine formulas, product families, top navigation, or color theme are changed.

## What the analyst sees

At the top of Configuration, Engagement setup always shows institution, charter, primary regulator, home state/market, opening date, cadence, forecast years and actual period count, CBLR election, and initial capital. Edit setup opens a compact inline editor; it adds no sidebar or modal. Fields are bounded, wrap on smaller screens, and use the existing theme and buttons.

Edits remain a draft until Apply changes. Cancel leaves the engagement untouched. The editor previews the resolved period count and regulator. Server rejection keeps the draft and shows the specific reason. A response cannot overwrite inputs changed while validation was in flight. Successful edits invalidate old results/errors and recompute; applying with no changes does not rerun or autosave. Snapshot views remain read-only.

## Editing rules

| Setting | Before dependent inputs change | After dependent inputs change |
| --- | --- | --- |
| Cadence | Editable; known template per-period defaults are re-expressed | Protected |
| Charter type | Editable; regulator follows automatically | Protected |
| Opening date | Editable; reference grid follows the calendar | Protected |
| Forecast reduction | Editable if validation accepts it | Protected against truncation |
| Forecast extension | Editable if sources can support it | Still available, checked before applying |
| Institution, state/market, initial capital, CBLR | Editable | Editable; same modeling choices already exposed elsewhere |

Pre-opening expenses and the initial capital amount do not close the early editing window. Newly created engagements store a small authoring baseline of model-input fingerprints, persisted through JSON, saving/reopening and Excel STATE round trips. No irreversible saved/created flag is used: current input dependencies determine protection. Manual reference-curve overrides count as entered inputs. Reading an existing engagement never inserts or resets a baseline.

Existing populated engagements without creation evidence receive a conservative structural lock, with that reason displayed. Their settings are still visible and validated horizon extensions remain possible. Their existing inputs and result fingerprints are not rewritten. A baseline is authoring guidance, not an access-control boundary: existing raw-config/workbook intake paths retain their prior behavior.

Changing an untouched template's cadence converts recognized per-period amount/growth/runoff/decay defaults and representable period timing. Natural month/quarter/year inputs retain their units. Native-period schedules, overrides, unknown per-period quantities, and timing that would require rounding are rejected rather than silently reinterpreted. Cadence changes can affect results through bucket timing; identical financial endpoints across cadences are not promised.

## Horizon and curve safeguards

A 3-year monthly engagement can become 5 years: 36 → 60 periods. Capital and pre-opening costs are preserved, and unchanged identity fields are not rewritten. A mature engagement can also extend if its sources support the added periods; its bank inputs are not migrated or padded by setup. Existing source extension rules still govern the added periods. New validation errors, including explicit error-on-exhaustion schedules, reject the operation atomically.

A managed balance that implicitly ramps over the entire forecast horizon must be given an explicit ramp duration before a horizon change. Otherwise extending the forecast would retime existing revenue. This is detected from the existing managed-notional contract, without a client-specific exception.

Dated rate anchors and manual input points are preserved. The sampled quarterly grid is resized using the existing engine's calendar interpolation and terminal rule. Manual dated curves retain their existing grid prefix when only the horizon extends; added points come from those same dated sources. Missing dates on a legacy manual curve block extension until the curve editor anchors it. No rate source is refreshed from the internet and no manual curve is replaced with FOMC defaults.

## Try the requested case

1. Create a monthly, 3-year engagement with initial capital.
2. Add a pre-opening expense if desired.
3. Configuration → Engagement setup → Edit setup → Forecast horizon: 5 years.
4. Check the 60-period preview and Apply changes. Capital and pre-opening expenses remain intact.
5. Once a deposit/loan/fee source or other dependent model inputs change, reopen setup: cadence/charter/opening and reductions show their protection reason; extensions remain checked rather than automatically locked.

Deploy this ZIP directly with deploy_foundry_dynamic.ps1. Its full-history main is a fast-forward of r317. No intermediate deployment or production/GitHub push has been performed.
