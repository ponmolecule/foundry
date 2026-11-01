# r443 — Product field spacing and repayment-profile alignment

Built on r442 (1aa25a01). Presentation only; no calculation or configuration schema changes.

Restore 14px separation between native field rows in the block-based product setup grids. This covers Volume source, Day count, Target retained share, Funded volume held aside, Interest accrues on, yield and ALLL reserve sections.

The Monthly repayment cohorts panel no longer inherits a misplaced field-label column. Repayment basis, Loss basis, Balance loss / stress exposure and Annual loss rate (or Lifetime loss at funding) use consistent left-aligned label rows, stacking above their controls in narrow panels.

Validation: browser layout checks at 2048, 1440 and 1100 pixels test spacing, consistent label edges, panel containment and unchanged configuration. Related repayment-profile and field-system regression tests retained; r442 local-label assertion now permits responsive stacking.
