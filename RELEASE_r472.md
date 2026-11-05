# r472 — Combine quantities before asset grouping

Based on r471. Retains the existing component table, inline expanded editor, and capital layout.

Quantity-based components now offer an optional “+ Add / subtract quantity” action within their editor. Each additional row has Add / Subtract, an entered quantity path or existing workforce link, and removal. Entered quantity paths retain Flat / Growth / Schedule. Existing single-source components remain unchanged; no migration or re-entry is required.

The engine combines all primary and additional quantities first, then applies lag, the combined pre-M1 quantity, division into groups, rounding, and the amount per group/unit. Depreciation continues to use the resulting component asset level and its own rate. Quarterly/yearly runs evaluate enhanced grouped calculations monthly before aggregating flows and sampling closing balances.

This is a generic signed quantity combination, not an engagement-specific executive/staff or conference-room rule. Up to 32 sources are supported; invalid operations and negative/nonfinite combined quantities fail closed. Source-mode changes preserve the quantity terms with the other mode inputs. Grouped components label their multiplier per group rather than per head. FIW exposes additional quantity inputs and linked identities.

Validation: 30 unittest cases pass (combined quantities, independent assets, existing lag/grouping and switches/frozen All-On hashes); existing fixed-asset checks 48/48, fixed-asset UI 11/11 and growth UI 84/84 pass. Node tests exercise inline combined-source rendering, Add/Subtract selection, mode restoration and removal, existing independent modes and immediate borrowing additions. Inline scripts compile. Reference coverage regenerated. Browser visuals remain unverified in this environment.
