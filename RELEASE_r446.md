# r446 — Fee-stream cost field order

Cost path now precedes its amount or rate. Growth cadence and growth rate follow the starting value; Resolution follows those controls. Schedule cadence precedes Resolution and the schedule editor. Flat paths omit Resolution.

The change applies to the shared fee-stream cost editor, including percentage, per-unit, per-account and periodic-amount costs. Existing field handlers, stored values, units and calculations are unchanged.

Validation: browser coverage of five cost types across Flat, Growth and Schedule; existing fee-field, cost-control and result-identity checks.
