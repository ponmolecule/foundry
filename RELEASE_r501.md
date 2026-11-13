# r501: Reverse stress through the Bank Design Lab, management actions

Built on Claude r500 (5fe3210). Implements r501 of the shared release plan with GPT's amendments: the Lab is the front end for reverse stress, exploration stays separate from formal evidence, Lab results never overwrite the baseline, and management actions are compared before and after with their costs.

## Engine and calculations

Base calculations and results are unchanged. One identity change: the base fingerprint now ignores the `stable_id` keys that stress and the Lab assign to inputs (verified inert to every calculation since r498), so giving an input an ID no longer makes earlier runs stale. All other fingerprint behavior is as before.

## Shared solver

`foundry/v2/solver.py` holds the bisection the Lab's Goal Seek used, now shared with reverse stress, plus grid, sign-change and monotonicity helpers. Goal Seek behavior is unchanged (Lab tests pass).

## Reverse stress (Bank Design Lab > Reverse Stress)

- **What moves:** one change to a supported input (multiplier, added amount, delay in periods, or the rate path in basis points), or a whole saved scenario scaled by λ. Scaling rules:
  - multipliers scale their deviation from 1;
  - additions and the rate shift scale their size;
  - delays scale and round;
  - replaced values cannot be scaled.
- **When it breaks:**
  - default: the first breach of any selected threshold (regulatory, commitment, bank policy) by any of the four ratios, naming the binding ratio, tier and period;
  - Tier 1 leverage only is available as a diagnostic.
- **Search:** a grid across the user's bounds, then bisection inside every interval where the breach status changes.
  - Every engine run is recorded with its margin, binding threshold and net income.
  - Results read as one of: breaking point found, several crossings, no breach within bounds, or breached throughout the bounds.
  - Limitations state the searched bounds, the grid and tolerance, a non-monotonic response, and the evaluation budget.
- **Explore, then promote:** exploration returns evidence without storing it. "Promote to formal" reruns the same search on the saved base and stores a reverse-stress record with its archived baseline. Formal records go stale with the base (and, for a scaled scenario, with that scenario). They appear in Stress Testing > Runs and as "Breaking points" in Results.

## Lab results never overwrite the baseline

"Adopt into model" is gone from Goal Seek and Optimizer. A result offers two actions:

- **Create revised plan** saves a new named version with provenance (source version, Lab mode, changes, time). The open plan is unchanged.
- **Compare under stress** stores the result as a design alternative (replace changes on the frozen baseline) and runs it unstressed and under the primary (or latest current) stress scenario. Results shows it as a row of the comparison grid beside the base design. A design that changes an input the stress also changes is refused as a conflict.

## Management actions (Results)

Actions run against a stored stress result. The unmitigated stress is kept as it was, and the comparison is before and after.

- **Capital injection:** an amount in a period.
- **Contingency line:**
  - commitment, spread over the borrowing rate, commitment fee (annual basis points on the full commitment), other collateral or covenant costs, and the period from which it is available;
  - shortfalls are borrowed at the higher rate, and the fees and costs are posted as operating expense, outside the expense gross-up;
  - draws above the commitment, or before the line is available, are reported (the engine does not cap draws).
- **Reduced growth:** a supported input multiplied by a factor from a period.

The before-and-after table shows each ratio's lowest point, net income, peak shortfall, peak draw, facility fees and other costs, and added drawn interest. Action records are stored with their own archive and linked to the parent run.

## Not included

Intraday liquidity, redemptions and LCR remain the r502 capability extension, applicable per engagement.

## Validation

- `foundry/v2/tests_r501_reverse_and_actions.py`: 28 checks pass (shared solver, breaking point with an independent rerun confirming the breach, every evaluation recorded, base untouched, no-breach, leverage-only, rate path below zero, λ scaling, validation, explore versus formal, staleness, actions stored and linked, exact facility costs, pre equals the stored stress, injection lifts leverage, invalid action refused, reduced growth).
- `web/tests_r501_reverse_actions_ui.cjs` passes; r498 to r500 stress tests and the Lab tests still pass.
- Browser walkthrough against a live server: CRE ×25 with a capital injection and a contingency line; Lab reverse stress explored and promoted; a Lab design compared under stress as a grid row; a revised plan saved as a new version with the open plan unchanged.
