# Foundry r346

Simplifies fee-stream cost authoring across account, transaction, percentage and periodic costs. Parent: r345 / 935c8dd.

Flat per-account costs show the dollar amount, Billed per (account/month, quarter or year), and Cost path. The account dollar field is explicitly labeled $/account. Flat cost factors no longer expose an irrelevant path period. Growth and Explicit retain Growth period / Schedule period; periodic dollar amounts retain Amount is per even when Flat because that cadence changes economics.

Absent multipliers appear as + Add multiplier, which creates the existing identity path. Existing authored multipliers remain visible without conversion or deletion. Flat multipliers hide their irrelevant period; Growth and Explicit retain explicitly named multiplier timing controls. No economic calculation, source link, schedule, unit scaling or persisted schema changed.

Validation: executable real-renderer/controller checks cover Flat/Growth/Explicit, separate monthly billing and annual growth, absent/existing multipliers, schedules, legacy values, periodic costs and mutation-free rendering. Customer source picker and audit fee economics (17/0) pass. Fee stream suite: 57 pass, 2 baseline hash expectations fail; no engine or fixture changes in this release. Browser screenshot verification unavailable because this environment lacks a browser executable.

Delivery retains the required delivery/ folder inside the ZIP. Packaged, not deployed.
