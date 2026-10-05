# r284 — Tax-year interim income taxes

Built directly on Claude r283, `b6655ac677f5e3502cdf4deca38044782f013986`.

The previous engine converted each interim loss into a carryforward and applied a carryforward limitation to later income within the same year. It also inferred valuation allowance releases from cumulative earnings. This release replaces those mechanics with a dated tax-year ledger and analyst-supported annual-effective-rate accounting under the documented ASC 740-270 contract.

Changes:

- Same-year loss offsets; annual prior-year NOL limits; reversible provisional deductions; actual fiscal-year-end true-ups.
- Supported annual profit/loss estimates and period revisions, YTD provision catch-ups, explicit future-year recognition assessments, and opening carryforward assets.
- Shared calculation across Profiles A and B. Profile B now honors its authored period horizon, rather than hard-coding 12 quarters.
- Tax assets included in the balance-sheet solver and capital derivation; nonconvergent solves fail closed.
- Compact tax controls within the r283 configuration layout; r283 theme and other workspace structure retained.
- Current/deferred statement detail and provisional tax-loss memos; Income Taxes audit sheet; Call Report other-assets reconciliation.
- Whole-result fingerprint pins deliberately updated, with previous pins retained for review. No output fields are removed from fingerprint comparisons.

This is an intentional results change. Earlier frozen runs retain their recorded results, but re-executing their configuration with r284 can report a fingerprint mismatch. That is expected for this engine correction, not a claim of legacy result identity. See R284_VALIDATION.md for financial comparisons and R284_TAX_METHOD.md for accounting scope and setup.

After deployment, open Configuration → Income taxes. Select Estimated annual effective rate and enter supported full-tax-year ordinary pretax income for each displayed tax year if a reliable annual estimate is available. Review future-year DTA support separately. Without an annual estimate, the default actual-YTD method withholds unsupported loss benefits. Then export the audit workbook and inspect Income Taxes; selecting the method alone is not evidence supporting recognition.
