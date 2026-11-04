# r468 — Keep CAPEX in place when switching authoring methods

Based on r467 (6bbac12f).

Removed the Formula / level-only full-width grid override introduced in r466. Fixed assets / CAPEX now stays in the same grid slot beside Pre-opening expenses in both authoring modes. The existing responsive table, component editor, and horizontal overflow handling adapt within that card. At the existing narrow-stage breakpoint, both modes follow the same single-column layout.

Presentation only; engine calculations, saved assumptions, and r466 component-table behavior are unchanged.

Validation: existing fixed-asset UI checks and Node inline-script syntax checks pass; reference coverage regenerated. Browser layout checks remain unverified here because Chromium is unavailable.
