# r332 — externally determined tax

Built directly on r331 commit 278e9d724483e09b7ce04305ec6c740d00d381e8.

Adds opt-in externally determined tax under Income taxes, preserving calculated tax as the default. Named entered/linked operands and safe derived rules support live bank-pretax allocation and committed prior-period carryforward state, without a mandatory pasted tax schedule. Separate current provision, cash settlement, opening tax payable/receivable and explicitly recognized deferred balances reconcile through NI and the funding solver. Income Taxes / All Series expose operands, rules and postings.

Profile A is supported. Profile B rejects external mode clearly. Nonlinear monthly rules require monthly model cadence; quarterly rules evaluate quarterly. This is an authoring capability, not an automatic consolidated tax or regulatory DTA classification engine. See R332_TAX_RULES.md for exact scope, sign/unit conventions and limitations.

Existing engagements and frozen fingerprints are unaffected unless the mode is selected. No engagement data was included, no deployment or remote push performed. Existing Other liabilities base naming is a separate pending UI task; no balances are moved automatically in this release.
