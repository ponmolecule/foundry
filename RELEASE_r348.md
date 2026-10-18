# Foundry r348

Repairs fee stream Driver-column recovery after blank or failed previews. Parent: r347 / 572b48a.

Each stream list now carries its product owner index explicitly. In-place preview refresh no longer discovers ownership through calculation icons, which are absent when all quantities are unavailable. Successful results repopulate the existing rows; unavailable results clear old quantities; the Driver period heading follows the current result horizon. Inputs are not rerendered or modified. Economic calculations are unchanged.

Verification: executable refresh regression covers an all-dash startup, successful results, multiple product owners, clearing on failure, recovery and header updates. Cost-control and source-browser regressions pass. A failed engine preview still produces unavailable quantities rather than invented figures; this release fixes display recovery, not invalid model inputs.

Delivery contains delivery/ with the full Git bundle and release metadata. Packaged, not deployed.
