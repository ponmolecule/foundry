# r231a_fix3 · Deposit balance sources and shared retention / sweep policies

History: r230 (`1c3e67d`) → r231a (`30f7ad8`) → r231a_fix1 (`33c2156`) → r231a_fix2 (`55902e6`) → r231a_fix3. The existing product workspace,
branding, six deposit presets, top menus, and ordinary deposit roll-forward remain.
This release adds optional mechanics inside those deposit products.

## Authoring

On an existing deposit card, select **Balance method**:

- **Opening balance + growth / inflows**: historical behavior, including maturity.
- **Enter / link / derive balance**: Flat / Growth / Explicit levels, linked upstream
  monetary balance quantities, or Activity × holding days × share.
- **Shared retention & sweep pool**: select or create one policy and set this
  category's share. Member shares must sum to 100% in each modeled period.

A pool owns its source balance, named additions / deductions, maximum retained
share, optional capacity, and annual swept-balance fee rate. All members observe
that same policy. Separate pools have independent limits.

Activity may be entered with an explicit amount period or linked to a stable
monetary Fee Product quantity. A funded-flow lending product can also supply its
funded volume, with its existing start, ramp and take-up applied once. Shares can
link directly to an existing Fee Product migration / attach coefficient with
explicit `share` semantics; the schedule is not copied or annualized.

Changing balance method preserves the old roll-forward values in a draft and
restores them when returning to that method. Contradictory balance methods and
roll-forward overrides fail validation. Paste schedules use the existing Load /
Clear / Close editor and preview.

## Calculation contract

Available balance = max(0, source + additions − deductions).
Retained balance = min(available, available × retained-share limit, capacity).
Swept balance = available − retained. Swept funds are not bank deposit liabilities.
Annual swept-balance fee = swept-balance basis × annual fee rate / periods per year, where the basis is the
average of opening and ending swept balances, or period-end swept balance, set per pool.
Average is the single default for new and imported pools; period-end must be selected explicitly.
Opening swept balance is entered separately in $000s (zero if omitted), before period 1;
later periods use the previous swept ending balance. It is off-book and does not add deposit liabilities.
Fees are allocated across categories by their pool shares and recognized once.
Interest uses the explicitly selected beginning, ending or arithmetic average balance.
Retained-balance fees remain separately labeled and apply to arithmetic average balances.

Capacity can be entered, linked, derived, or computed from a beginning equity budget:

    max(0, max(0, prior ending equity − capital deductions) / equity allocation ratio
           − beginning lending exposure − liquidity buffer − other committed assets
           − prior operating expense converted to monthly expense × float months)

This is an allocation budget using modeled beginning equity and authored deductions;
it does not enforce bank capital / assets and does not equate book equity to regulatory Tier 1.
For example, 30M equity / 13% permits a 230.769M deposit allocation before commitments;
including equity funding gives 260.769M assets and 11.504% equity / assets, not 13%. Capital deductions and other commitments must reflect the intended
policy. M1 prior operating expense is zero. At most one pool owns the bank equity
budget; several deposit categories can share it.

Static pools can fund deposit-book-linked loan caps. A beginning-equity-budget pool
combined with a current deposit-book lending cap fails closed because that combination
requires a different period-by-period dependency schedule. An entered lending capacity
is supported. Lending cannot depend on quantities owned by its deposit sweep consumer.

Profile A supports the extension; Profile B rejects it explicitly. Finer-cadence level
or migration schedules are rejected where applying them to aggregated activity would
lose precision. Use the native source cadence for those cases.

## Outputs and audit

Product Detail shows interest basis, swept balance and swept-balance fee income.
The pool preview shows retained and swept amounts. Calculation Audit's **Product
Calculations** and **All Series** include pool source, net adjustments, availability,
share limit, capacity, retained, swept, opening swept basis, fee basis, fee, beginning capital and commitments.
`bindingLimit` is an enum: 0 no sweep, 1 share, 2 capacity, 3 both.
Monetary public / workbook values are $000s; engine values remain dollars.

## Validation

Passed deposit integration and UI suites, existing loan allocation, cadence-equivalence,
series architecture, and audit reconciliation suites. Tested actual preview API and
rendered browser card: source switching, persistent shared settings, Load activation,
monetary paste scaling, Clear and Close. No browser JavaScript errors.

The complete unchanged fixture output matches the r230 engine without removing fields.
All three named r230 fingerprints remain unchanged. Floating reference-index labels resolve
from configuration family order (both engines preserve it), including duplicate product names;
no index metadata is added to hashed results. New tests cover independent
pools, binding constraints, zero capacity, excessive deductions, linked migration schedule
changes, stable identity on rename and reorder, linked lending float displacement,
beginning-period equity budgets, explicit M13 starts, and audit export.

The older pastebox inventory suite has four pre-existing failures, reproduced unchanged
on Claude `1c3e67d`; this release introduces no new paste surface.

## Deploy

Use the usual `deploy_foundry_dynamic.ps1` workflow. The delivery contains
`delivery/foundry-full.bundle` with `main` pointing to this release and its complete
compatible history. If your local/GitHub branch is still at `1c3e67d`, importing this
bundle can fast-forward. The deployment script should report the new build stamp.
No remote branch was pushed by this build task.

Outbound pool balances are labeled **Swept out (off-book)** and the revenue is **Fee on swept-out balances**.
Enter the gross program source before retention/capacity limits. Inbound Sweep / Program deposits
remain an ordinary deposit preset; the preset does not automatically opt into pooling.
