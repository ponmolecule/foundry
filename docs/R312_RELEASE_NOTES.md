# r312 — Deposit beta and Governance

Built as a direct continuation of r311 (08a278c), itself on r310 (514758d). No new product types and no repayment changes.

## Deposit pricing
Existing floating deposits may set deposit_beta (0–1; omitted or null means 1), deposit_rate_floor and deposit_rate_cap (decimal annual rates; omitted/null unbounded). Annual rate = reference index × beta + existing spread; floor then cap. Fixed deposits ignore these controls. This is index-level participation, not an anchored starting-rate or asymmetric up/down beta. Example: index 5%, beta 40%, spread 0.5% yields 2.5%; index 4% yields 2.1%. Spread overrides retain existing precedence before bounds.

Controls appear in the deposit setup editor for floating rates. Clear optional fields to remove them. Existing curves, interpolation and override calendars are unchanged. Product rateQ and interest expense reflect the calculated rate; the audit Config Snapshot records beta/bounds and All Series retains rateQ. Existing engagements receive no new result fields; omitted beta is 100%.

## Governance
Saved-config lookups safely return no prior value for added list members or missing paths, rather than raising IndexError/KeyError. Regression reproduces newly added fee streams against a shorter saved list. The user's screenshot alone does not prove the precise production stack; this fixes a directly reproducible matching failure.

Nonblocking authoring findings flag a priced source feeding a priced consumer (potential duplicate posting, legitimate compositions remain allowed), and empty explicit coefficients on derived fee drivers. Findings identify the consumer and offer corrective guidance. They do not zero rates or modify schedules. Existing anomaly tests now scope their assertions to schedule findings because legitimate template stream compositions also receive advisory warnings.

## Limitations
Empty coefficients retain their existing engine behavior: Governance warns; this release does not introduce a new run-blocking validation rule. No purchase cohorts, collection-linked repayments or borrower-deposit linkage are added. Browser script compilation is verified; a live deployed browser session was not tested.
