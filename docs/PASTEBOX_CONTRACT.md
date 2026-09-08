# Foundry pastebox contract

## Purpose

Pasteboxes are an authoring convenience for model inputs; they must never introduce hidden coupling
between Series, streams, products, or modules. A pastebox may modify only the configuration object
explicitly owned by that control.

## Scalar explicit schedules

All one-dimensional numeric Explicit schedules use the canonical scalar controller/parser.
Supported separators are comma, tab, semicolon, and newline. Currency symbols, percent symbols,
parenthesized negatives, and thousands separators in tab/semicolon/newline-delimited cells are
accepted. Parsing is fail-closed: if any non-empty token is invalid, Load remains disabled and no
partial schedule is written.

The control contract is:

1. Empty/invalid input -> Load disabled.
2. Valid input -> that pastebox's Load button enables immediately.
3. Load (replace) -> replaces only the owning Series schedule and re-renders immediately.
4. Clear -> clears only the owning Series schedule and re-renders immediately.
5. Re-render/reopen -> loaded values remain attached to the owning Series.
6. DOM identity -> stable Series identity where available; never user-visible labels alone.
7. Sequential use -> loading/clearing one pastebox cannot change another pastebox's button state or data.

Audited scalar families:
- Fee Product transaction coefficient schedules;
- Fee Product Flat recurring-amount schedules;
- CAC driver schedules;
- CAC existing-book attrition schedules;
- Workforce Count schedules;
- Workforce Compensation schedules;
- Operating Expense category schedules.

## Structured bulk pasteboxes

Structured import surfaces may retain module-specific row parsers because they accept records rather
than a scalar Series. They must nevertheless satisfy the same state-isolation rules and use unique
control IDs.

Audited structured surfaces:
- Pre-opening expense bulk paste;
- Fixed Assets bulk paste;
- Workforce bulk paste;
- Operating Expense category bulk paste.

## Release gate

The pastebox hardening regression suite inventories every model-authoring textarea, verifies live
activation and unique targeting, exercises sequential scalar and structured boxes, proves Clear/load
isolation, checks collision-resistant CAC IDs, and executes the shipped canonical parser against
comma-separated, tab-separated/thousands-formatted, percentage, and invalid input cases.

Any new model-authoring pastebox must either use the canonical scalar contract or be added explicitly
to the structured-surface inventory and isolation gate.
