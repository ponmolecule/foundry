# r321 validation

31 backend setup checks pass. Five additional regressions cover the reported empty-fee/salary/pre-opening creation and deletion sequence, deleting an original product, legacy workforce residue, protection of timed/linked/scheduled/growing workforce, and protection of populated/unknown fee inputs. Node setup checks pass, including r320 expand/collapse/edit behavior. All 3 pinned fingerprints and all 5 complete legacy outputs match the baseline without dropping fields.

Full suite: 107 modules, 91 pass, same 16 baseline failures. All module exit statuses match r319's recorded suite (r320 changed disclosure UI only). This is not a completely green suite. No live HTTP or rendered browser testing claimed: FastAPI/browser unavailable locally. No engine changes.
