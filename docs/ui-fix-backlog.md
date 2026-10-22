# UI fix backlog

## Entered interest income units — open

Reported 2026-10-21. Deployment paused while Railway is unavailable.

Securities & AOCI → Interest-bearing balances → Income calculation → Entered income amount does not make its $000s entry units sufficiently clear, especially for Explicit monthly schedules and pasted values. A user could enter raw dollars and overstate income by 1,000 times.

Future change: show **Income amount ($000s)** and repeat the unit next to the Explicit paste/editor control. Keep **amount period** (monthly/quarterly/annual flow) distinct from schedule cadence. Include a short conversion example where useful: $66,818 → 66.818. Check equivalent monetary schedule controls for the same ambiguity. Preserve stored values and existing scale conversions; no automatic rescaling or engagement migration.

Status: logged only; no UI implementation, release or deployment authorized by this log entry.

## Expense-linked other liabilities / accounts payable and flow-to-balance parity — open

Reported 2026-10-21. Use pasted period-end payable balances temporarily; deployment remains paused.

Extend the existing Other Liabilities formula/link grammar to support recognized expense sources, including selected operating-expense categories and aggregates with explicit inclusions/exclusions. Support a user-authored days-payable factor with clear period/day-count semantics. General example: monthly eligible OpEx × DPO / 30; selecting all eligible categories except prepaid insurance must remain live as expenses change. Preserve expense recognition; this is a liability stock, not another expense posting. Prevent duplication with timing-generated accrued expenses and preserve existing authored liabilities without migration.

Status: requested for the next enhancement list only; not implemented in r375. Temporary entry uses an Explicit monthly Base liability level schedule in $000s.

Scope clarified 2026-10-21: bring named liability components to parity with Other Assets' existing flow-to-balance authoring. Offer **Multiplier / Days payable**, an entered days-payable trajectory, an explicit **Days per year** basis, and an additional multiplier. Calculate period expense × days payable ÷ (days per year / periods per year) × multiplier, respecting monthly/quarterly model cadence. Reuse the existing source × multiplier component design and common flow-to-balance logic where practical; do not create an engagement-specific AP feature. Relevant expense sources must support selected categories and aggregates with explicit exclusions. Preserve named Entered / Explicit liability components as the current pasted workaround. This extends the existing enhancement entry rather than adding a duplicate request.
