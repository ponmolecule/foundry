# r323 entry guide — settlement payable and cash interest

Use Configuration → Securities & AOCI. Build one named settlement liability, then allocate existing bank cash. Do not create a new revenue Fee Product for the interest.

## 1. Settlement liability

Under Other liabilities select Formula / level, then + Add settlement liability.

- Give it an engagement label, e.g. Customer payable.
- Opening component liability: 0 ($000s), matching the supplied opening payable. Keep the same liability out of the separate base/opening input; that input is for other opening liabilities.
- Select only the existing fee streams that belong to the eligible migrated book. Choose Reported fee income where the source row is revenue after its contra presentation; choose Fee income less direct cost only when the source includes those costs. These measures are not interchangeable. Do not apply migration again to already migrated streams.
- Source sign: Reverse sign (−1) for the supplied negative eligible revenue.
- Holding period: month, on this monthly engagement.
- Holding weights: `1 1` (current and preceding month).
- Opening revenue history: `0` ($000s), matching Volume!C126. If that observation differs, enter its signed value, not a computed payable.

The selected eligible revenue must independently match source row 126 before downstream cash interest is considered reconciled. Leaving out unselected source-model components is an engagement choice, not an engine rule.

## 2. Cash allocation

Expand Interest-bearing balances. If legacy settings exist, use Use named components: this explicitly preserves existing economic components and disables the legacy branch. Inspect the existing cash components; replace overlapping cash allocations rather than adding a second calculation. Preserve legitimate independent AUA/other earning assets.

Add a Part of bank cash component:

- Balance source: Settlement liability → the component above; multiplier 1 (or no factors).
- Select Cap allocation at available bank cash.
- Interest balance measure: Prior period end.
- First prior-end interest balance: Zero at launch for the supplied zero opening cash/payable comparison.
- Annual yield source: Reference index + spread → Fed Funds (EFFR).
- Annual spread: Flat, −0.50%.

Add or edit the single Remaining bank cash component:

- Interest balance measure: Prior period end.
- First prior-end interest balance: Zero at launch for this comparison.
- Annual yield source: Reference index + spread → Fed Funds (EFFR), spread 0.00%.

Leave Cash earns interest selected, matching Inputs!C81=1. Ensure no leftover overlapping cash-allocation component remains. Independent non-cash components can remain. If rates do not equal the source, reconcile the curve first. For a controlled comparison, the existing entered Explicit annual yield mode can reproduce 3.40%, 3.10%, 3.10% on remaining cash and 2.90%, 2.60%, 2.60% on covered cash; this deliberately uses entered rates rather than a scenario-sensitive index.

## 3. Validate

Audit workbook → Other Liabilities: eligible revenue, lag contributions, component payable and total Other liabilities. Audit → Interest-bearing balances / All Series: requested and capped allocations, pricing balances, annual yields and income posted. Income statement interest on cash/due from banks is the total cash interest, posted once.

With the supplied rounded balances and source Y1 rates, expected cash interest ($000s): M1 0; M2 81.9162; M3 78.75165; M4 81.792225; M5 103.523. These are formula acceptance cases, not a claim that the unentered engagement's entire balance sheet is reconciled.
