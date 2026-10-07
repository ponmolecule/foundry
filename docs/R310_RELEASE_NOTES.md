# r310: Guide Me can apply its plan

Built on r309 (f2df715).

Guide Me used to end with a checklist to follow by hand. It now also offers "Review & apply". The review panel shows one card per stream with its name (editable), basis, driver, pricing shape and the values you will need to enter. Where a stream needs a link (customer feed, reference stream, source stream, aggregate, cost pool) you choose it there; Apply is blocked until you do. If the product already has streams you choose Add alongside or Replace. Nothing changes until Apply.

Apply creates the structure only. Every rate, volume and amount is left at zero, so the new streams contribute $0 until filled in. They are marked NEW with a count of values still to enter, and a banner totals them and links to the first. The change is unsaved like any other edit; Discard undoes it.

Also in this release: the unsaved-changes list now names fee-stream additions, removals and edits, which it never did, and no longer reports a change merely because a fee product was opened.

Replace is guarded. If other items read the streams being removed, the panel says which, and the usual deletion confirmation appears. That warning now also names operating-expense lines that read a removed stream; before, deleting such a stream gave no warning and blocked the next run.

Known limit: the NEW chips and the banner last for the session. After a reload the streams remain but are no longer marked.

Engine arithmetic unchanged. "Back to Fee Product with checklist" works as before.

Validation: tests_r310_guide_apply (28 checks: materialiser, engine at zero and with a value, endpoint, console hooks); full flow driven in headless Chromium against the running app with the model call stubbed; full suite against the r309 baseline with no new failures.
