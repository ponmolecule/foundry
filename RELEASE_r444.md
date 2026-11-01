# r444 — Repayment-profile funding from derived populations

Built on r443 (aa8a9797).

Repayment profiles replay their linked funding streams on a canonical monthly graph. That graph registered acquisition feeds' primary customer counts but omitted the size-band counts and weighted populations published by population composition. A linked physician -> HYS -> personal-card -> purchase chain consequently failed with Canonical monthly customer count unavailable, blocking the run and leaving Yield applied blank.

Register the already-calculated composition counts in the repayment-profile monthly source map, using the same period-end, period-average and annual-count measures as the main engine. No change to population, repayment, interest or allowance formulas. Previously failing configurations can now run; existing result fingerprints are unchanged.

Regression: reproduces the exact failure before the fix; tests cross-product population/account/purchase funding at monthly and quarterly cadence, band availability, full engine funded volumes, and published zero/nonzero applied yields. Existing repayment-profile (37 checks), composition (6 tests), r440 validation (3 checks) and all six result-identity checks pass.
