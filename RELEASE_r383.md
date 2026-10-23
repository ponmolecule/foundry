# r383 — reusable deposit assumptions and linked expense calculations

Customer-linked deposit balances can now consume the existing shared weighted amount-per-customer assumptions, with optional consumer percentage factors. Existing entered amounts remain unchanged. A collapsed latest-run calculation and audit rows expose the component contributions.

Operating Expense has an optional Linked calculation component with grouped arithmetic, guarded division, conditional evaluation, linked balance measures, actual product deposit interest, resolved reference rates, and current/cumulative gross acquisition flows. It posts only the final monetary expense, preserves negative results, and rejects incompatible units and circular dependencies. Source-model choices remain authored assumptions; no engagement-specific equations or defaults were added.

UI: nested expression steps are collapsed, open state survives routine edits, weighted editors reuse existing controls, and precise shared weights retain additional input precision. Existing formula and deposit authoring paths are retained.

Validation:
- New backend tests cover live weighted deposits, entered-path equivalence, source immutability after existing flow-ID initialization, monthly and quarterly calculations, negative margins, zero guards, unavailable sources, dimensional errors, a circular expense-funded acquisition, public/audit units, and actual Profile B interest including a minimum top-up.
- Existing r380/r381 deposit tests and source-catalog regression pass. New browser checks cover shared edits, nested measures/observations, component creation, and control containment at 1440/1024/768 including fitControls. Existing pricing-layout browser checks pass.
- Full JSON outputs for all 12 core/parity configuration fixtures are identical to r382.
- A full new-calculation audit workbook exports successfully; intermediate operand diagnostics are included.
- Known baseline test issue: the r366 source-equivalence test's configuration-immutability assertion fails identically on r382 because existing account-activity flow-ID initialization mutates its uninitialized fixture. Its pin/assertion was not changed for this release; other shared-lending tests pass.

Cadence: quarterly expressions evaluate quarterly observations; they do not silently sum monthly nonlinear expressions. Use monthly cadence for monthly source reconciliation.

Includes the updated Engagement 5 source clarification notes. No source-model correction was silently applied. Not deployed or pushed.
