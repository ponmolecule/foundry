# r467 — Fixed-asset units, component identity, and regression harness repairs

Based on Claude r466 (`bf254267`); retains its component-table presentation.

## Engine and public output

- Fixed-asset Formula / level component `depreciation` now passes through the same dollars → $000s parity conversion as component `amount` and `multiplier`. Raw engine/audit calculations remain dollars. Removed the compensating `/1000` from the console table and its r466 rendered test.
- Legacy components that share a Series alias (including an acquisition feed and its channel) receive distinct, scoped implicit switch identities. Parent links are rebuilt against those identities. Explicit duplicate inclusion IDs still fail closed. Browser inventory uses the same rule, and conversion to persisted inclusion IDs preserves group membership.
- Validation resolves legacy publication metadata on a private copy. Run/parity callers use that normalized copy, preserving historical output/config hashes without modifying the caller's saved assumptions. The returned input retains authored exclusions for disclosure and All-On comparisons.

## Regression harnesses

- Growth renderer loads the actual switch and unused-commitment helpers, without the page-level render wrapper; all 84 checks pass.
- Flow-lending and stream-output renderers load the unused-commitment reserve editor. Stream-output checks select Pricing for financial results and Activity for quantities.
- Authoring stability supplies run-error globals; authoring state supplies the calculation badge host.
- Account activity checks include the cumulative gross acquisition source introduced after their original assertions.
- Shared lending follows the named-draft creation workflow before testing saved assumptions.
- Numbers harnesses provide configuration/calculation snapshot state and the shell status hook needed for modal copying.
- Product consistency expects the current “Funded provision / (release)” label and writes screenshots under the OS temporary directory.
- Legacy stream identity harness supplies the window global used by publication guards.
- Reference coverage regenerated with `python tools/reference_scan.py --write`.

## Verification

New Python coverage verifies monetary conversion at monthly/quarterly/annual cadence, end-to-end public depreciation units, non-mutating conversion, legacy feed/channel collisions, explicit duplicate rejection, parent exclusion, and ownership/group propagation. New Node coverage verifies matching browser inventory identities, persisted group migration, restoration, direct public-unit consumption, and inline script syntax.

The r458 All-On frozen output hash gate remains unchanged and passes, as do switch exclusion/disclosure tests and the requested available engine/Node harnesses. Browser-rendered tests require Chromium, which is unavailable in this environment; those checks are unverified, not reported as passing. See delivery/VERIFY.txt for final module counts and bundle-clone verification.
