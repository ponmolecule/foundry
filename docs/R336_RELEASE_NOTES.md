# r336 — Rates & Curves

Built as a direct continuation of r335 (88de79d08761e7331f2f633b00735cd4de0fd1b9), with full history retained.

## Where it lives
Configuration → Rates & Curves, first in the existing configuration module navigator. Existing menus remain. The assumptions sidebar now holds a compact source summary and a link rather than the sprawling curve editor.

## Authoring
1. Published evidence: saved policy observations and SEP year-end anchors, longer-run value, FRED series identifiers, retrieval date, and release date only when recorded. A legacy edited snapshot is identified; missing original published values are not reconstructed or represented as verified Fed evidence.
2. Your adjustments: one selected index at a time. Keep its saved curve (default), choose a Fed-based projection, or select an engagement schedule. Policy overrides preserve original evidence. Basis, Step/Linear policy interpolation and the terminal assumption are separate. Month-range index overrides are optional and non-overlapping.
3. Effective index paths: chart, monthly diagnostic table, native engine-period table, per-cell provenance, and a Fed-based comparison. New schedules require an explicit Percent/Decimal choice, source label, Step/Linear selection and after-schedule treatment. Flat paths use one value with Hold; dated or monthly/quarterly/annual undated schedules can be loaded. A multi-index paste can be reused for each selected index using named columns. Each index is explicitly selected and loaded, so an incidental column never activates another curve.

Refresh stages the next FRED snapshot and preserves schedules, policy overrides and basis assumptions. Preview/Apply commits the candidate explicitly. Neither opening the workspace nor running a model fetches network data. An async response cannot cross engagements or apply over a newer draft. Discard restores the saved workspace.

## Rate contract
Rates are annualized decimals internally; schedule frequency determines effective dates, not annualization. A selected engagement schedule bypasses policy anchors and index basis; range overrides apply afterward. Scenario shifts apply once; product spread, deposit beta, floors/caps and applicable product overrides keep their existing engine rules.

Quarterly engines continue to sample the dated index at period-end. The monthly table is diagnostic; it is not a promise that quarterly balance/interest calculations equal monthly accruals. No interest rate is summed. Native dates and rate sampling are disclosed.

Explicit extensions: Hold last rate; switch to Fed-based projection; or fail beyond stated coverage. Before the first engagement point, coverage errors fail closed. Strict extension also applies to future dates required by fair-value valuation. Published policy extrapolation remains a separate visible assumption (hold or the existing 5bp/calendar-quarter glide toward longer run). No engagement curve silently glides to the Fed's policy rate.

## Audit
With a saved Rates & Curves workspace, the workbook adds Rate Assumptions, Effective Rates and Engine Rates. They contain original evidence, entered schedules and labels, interpolation/extension settings, annualized rates at full numeric precision, active source, comparison rates and differences in bp. They do not add reporting fields to legacy run results.

## Compatibility and validation
Unmodified engagements and frozen-run fingerprints retain their r335 behavior. The new configuration field is opt-in on Apply. All five complete public fixture results are identical; no fields stripped. Three identity pins match. Full suite: 123 modules, 105 passing, same 18 baseline failing modules. The two new modules pass.

Browser-rendered QA was unavailable: Chromium was absent and its attempted installation returned invalid downloads. Handler tests, real Python preview integration, script compilation and responsive CSS checks passed; pixel fidelity at laptop/1920 widths is not claimed. Actual client reconciliation remains a separate engagement validation step after entering its rate schedules.
