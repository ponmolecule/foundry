# r437 — Field system on Configuration editors

Built on r436 (a635fa3). Presentation only: controls move into the label column; handlers, values and accessible names are unchanged.

- **Workforce populations** (Operating expense › Workforce): one label column. Count and Compensation carry their path as Flat | Growth | Schedule (Compensation adds Escalation) beside the value; a growth path's rate line sits directly under the value it grows ("Count growth", "Compensation growth"); compensation basis and period on their own row ("Amount basis: Per FTE per Year"); Active from start to end month on one row ("open" when blank); benefits / payroll as a % of compensation; count method. The "Advanced trajectories" disclosure is gone for flat paths; for a schedule it shows the schedule editor directly.
- **Expense categories**: Category name, Amount (path · value · $000s per period) and Growth (rate · per · step/smooth · anchor) on separate labelled rows instead of one wrapped line; Remove category in the editor header.
- **Other income lines**: Name, Classification, Source and Income amount (path · value · $000s per period) on the label column; Remove line below.
- **Capital raises and scheduled borrowings**: small tables with column headings (Month, Amount; Borrowing, Month, Amount, Rate, Term) instead of inline captions; a borrowing no longer wraps out of its card.
- Securities, tax, rates and assessments already used label-and-value rows and are unchanged.

Validation: tests_r437_config_fields (py + node): non-mutation across every module, label alignment, path buttons writing count and category paths, the growth line under the count, role name still editing, capital table headings and one-line rows inside the card, other income rows. Full suite: 0 of 264 failing.

ZIP contains delivery/foundry-full.bundle. BUILD_STAMP = foundry-r437-config-fields.
