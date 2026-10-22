# Foundry r375 — prepaid operating expenses on the Balance Sheet

Built on r374 (bb26beb), including all subsequent documentation updates.

The Balance Sheet displays the engine's existing prepaidOpex series as Prepaid Operating Expenses, after Other Assets. The row appears only when the series contains a nonzero balance and uses the existing balance-sheet period selection and $000s formatting. No accounting calculations, engagement settings or migrations change.

Validation: a real engine/API fixture with annual cash settlement and monthly recognition produces a $320,833.33 M1 prepaid asset on a $350,000 annual expense, falling to zero in M12. Chromium verifies the visible row and formatted amount, and hides it for zero or absent balances without runtime errors.

Packaged; not deployed. Deployment remains paused.
