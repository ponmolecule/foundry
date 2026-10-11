# r315 — Explicit expense gross-up eligibility

Direct continuation of r314. This is a configured expense calculation, not an accounting reclassification.

Configuration → Operating Expense → Assessments & other NIE → Gross-up eligibility provides a compact, collapsible inventory. Group defaults can be overridden on individual compensation roles, additive compensation, expense categories, linked components, scheduled-asset depreciation, product operating expense and fee-stream costs. A component inherits its category unless explicitly overridden. Overrides stay on the source objects, so renaming/reordering preserves them. Monetary expense is always posted once; only the gross-up base changes.

Absent eligibility settings preserve the old base exactly: compensation + categories + linked components + assessments + depreciation + product operating expense. Fee-stream costs remain excluded unless opted in. Charge = eligible base × r / (1 − r). Reversals retain their sign. New engagement templates start with r = 0; saved engagement rates are untouched.

The Expense Gross-up audit sheet lists each expense, eligibility, included amount, period base, rate and charge. It uses $000s; internal audit data is engine dollars. No gross-up audit field is published for engagements without eligibility settings.

Profile A and B support the policy. Formula/legacy aggregate depreciation follows its group setting; scheduled assets can have individual eligibility. Balance-component product operating costs without a separate product line follow the product-operating-expense group. Guide Me does not author the policy automatically.

Verification compares complete results for all five runnable fixtures against r314 with no fields stripped. New tests cover group and line overrides, inventory reconciliation, no expense reposting, public-engine charge reconciliation, Profile B and audit output; Node tests execute the actual compact editor helpers.
