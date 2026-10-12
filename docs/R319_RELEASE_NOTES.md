# r319 — setup false-lock correction

Built directly on r318 (38af1ea); no calculation changes.

## Defect and correction

The Capital & pre-opening renderer called _fixedAssetState while displaying its fixed-assets section. That helper inserted fixed_assets={mode:"simple",assets:[]} even when no asset was entered. r318 fingerprinted that object as a new model dependency, so visiting Configuration disabled cadence, target opening, charter and horizon reduction.

Rendering now reads a local empty fallback instead of writing it into the configuration. The setup guard ignores precisely this inactive shell and recognizes its old r318 baseline digest. Already affected r318 engagements need no reset or re-entry. Authored asset schedules, formula models and unknown substantive fields remain dependencies. Populated legacy engagements without a creation baseline remain protected; this release does not invent creation evidence for them.

## Try after deployment

1. Create a new engagement and visit Configuration → Capital & pre-opening.
2. Optionally add only pre-opening expenses. Open Edit setup: cadence and target opening should remain editable.
3. Change monthly/quarterly cadence or target opening, Apply, and confirm the summary updates. Pre-opening entries and capital must survive unchanged.
4. Add an actual deposit opening balance or asset schedule: structural settings should become protected with a reason.
5. Reopen an affected r318 early-stage engagement: an empty fixed-assets shell alone must no longer lock it.

No menus, theme, default economics, engine posting or result fields changed. A truly populated engagement still cannot be silently retimed.
