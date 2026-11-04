# r465 — Persist the displayed annual component depreciation period

Fixes r464's new Rates by component controls showing Year while a newly edited rate could omit its stored period. Selecting component rates now initializes the base and component rate paths with Year; newly added components do the same. The engine interprets missing or empty periods on component depreciation rate paths as the displayed annual default, so affected saved inputs run without re-entry. Explicit invalid periods remain validation errors. Existing rates, components and workforce inputs are preserved.

Validation: 6 driver/depreciation regression tests, 48 fixed-asset checks, and 11 UI authoring checks pass. Console inline JavaScript compiles. Delivery bundle main is verified against the release commit by fresh clone. No rendered browser check performed.
