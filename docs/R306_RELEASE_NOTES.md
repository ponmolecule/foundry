# r306 — Zero funding and FDIC defaults

Built directly on r305 (398d6db).

New-engagement templates now explicitly default these assumptions to zero:
- Cash target as a percentage of deposits.
- Cash yield.
- Borrowing annual rate.
- Residual securities yield.
- FDIC assessment under Assessment & other NIE.

The wizard and blank canvas already reset funding fields. This release also neutralizes the underlying embedded fallback, both server template endpoints, and the downloadable universal FIW template. It does not rewrite any saved engagement, imported configuration, sample fixture, or user-authored value. Existing engagements must be updated by the user as requested.

No engine arithmetic changed. Explicit yields, borrowing rates, cash targets and FDIC assumptions still work when authored. Fixtures and their frozen-run fingerprints are unchanged.
