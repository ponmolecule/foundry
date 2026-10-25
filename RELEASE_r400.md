# Foundry r400 — Income Statement display periods

Direct continuation of r399 / 77236a5. Presentation only; no engine, engagement cadence, saved-schema or save/recovery changes.

The Income Statement header has a small View button group. Monthly models offer Monthly, Quarterly and Annual; quarterly models offer Quarterly and Annual; annual models show Annual. Choices never offer finer detail than the model computes. The default is the native cadence; a compatible choice may remain selected for the browser session. It lives outside cfg and does not cause a run or an unsaved edit.

Income/expense flows, subtotals and component-interest lines sum the native observations in each displayed group. DTA, remaining NOL and current tax-year loss-to-date memos use the last observation. Flow Total cells sum the displayed horizon (including the provision/current/deferred-tax memo flows, whose previous Total used the final period); balance memo totals show the final observation. The existing annual ratio summary is unchanged. Money stays in $000s. Hover breakdowns aggregate the same periods instead of showing only their first month's components.

Groups are model-relative, starting at forecast period 1, consistent with Year 1 / Q1. An incomplete final group is explicitly marked partial. Missing observations stay blank; they are not coerced to zero. Arrays that include an opening observation exclude it from income summation. No underlying result array is modified.

Reference > Balance Sheet & Income Statement now explains View and gives a sum-versus-closing-memo example. Controls use existing graphite/gold styling; the group wraps below the title on narrow screens. Existing horizontal financial-table scrolling remains.

Validation: new real-browser regression checks Monthly/Quarterly/Annual clicks, exact flow/subtotal/component/memo values, full-horizon totals, partial groups, nulls, opening slots, fallback from an incompatible finer choice, and byte-identical cfg/results with clean lifecycle. Desktop and 390px layouts inspected. r394 Reference: 20/20 checks including browser behavior. Both r399 browse regressions pass. All inline script blocks parse; git whitespace check passes. No full-suite claim; existing fingerprint pins and legacy harness issues remain outside scope.
