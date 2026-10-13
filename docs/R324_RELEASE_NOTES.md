# r324 — clearer product-family navigation

Direct continuation of r323 (24f8e0b). The product navigator now separates Lending, Deposits and Off-balance-sheet with compact charcoal header bands, gold disclosure arrows, explicit white labels, small count badges and consistent space above each group. Hover and keyboard-focus treatment use the existing gold accent. Product selection, family collapse, search, drag/reordering and rendering markup are unchanged. No engine/configuration changes.

Validation: full inline JavaScript syntax and git whitespace checks pass; existing setup and settlement helper checks pass. No browser executable is available, so rendered visual inspection is not claimed. The screenshot was reviewed to identify the weak heading hierarchy. This narrowly scoped CSS change does not require repeating the engine suite; r323 validation remains included.
