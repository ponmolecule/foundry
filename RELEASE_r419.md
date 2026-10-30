# r419 — Workforce and expense Numbers views

Built on r418. Quiet Numbers links beside the existing M1 workforce and expense summaries open the complete forecast at the engagement cadence. Selected workforce roles, compensation pools and expense categories also offer Numbers links. The existing M1 spot checks remain.

The reusable product Numbers dialog shows resolved values from the latest completed run, with money labeled $000s and counts labeled separately. It supports copying the full series and closing with the close control or Escape. Stale results retain their warning. Detail rows are explicitly identified as included in totals.

Per-category snapshots are output-only diagnostics. No financial calculations, authoring assumptions or save mechanisms change.

Validation: r419 engine and dialog tests, existing r368 Numbers tests, browser-script syntax/balance-formula checks and git diff checks pass. All pre-existing output fields match r418 exactly on the reference fixture, excluding the run hash. A real-browser visual check was unavailable because the browser download failed; dialog behavior was checked with the existing DOM test harness.
