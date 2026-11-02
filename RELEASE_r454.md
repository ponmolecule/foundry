# r454 — Shared lending assumption controls and cleanup

New shared assumptions begin as an unsaved named draft. Opening or cancelling the draft leaves the saved model untouched; Create requires a distinct nonempty name and commits once. Choosing an existing assumption or changing weights never creates another input. Creating/selecting an assumption retains the loan consumer factors. Switching between entered and shared amount modes retains both authored drafts within the current editing session.

Manage shared assumptions lists usage and allows explicit removal of unused inputs. Remove unused empty entries clears exact legacy zero-value placeholders only when unused or referenced solely by the current loan; a current placeholder is detached without altering factors. References anywhere in the configuration, including other shared inputs, protect deletion. Configured or shared referenced inputs are never automatically removed. Duplicate legacy names display their stable IDs to distinguish them. No cleanup or financial-input migration runs on load.

The shared area separates selection, creation, management and editing. Shared/component name edits no longer replace the DOM on blur, preserving adjacent first-click actions. Button contrast is corrected.

Validation: real Chromium checks cover repeated draft opening, cancel without config mutation, duplicate names and duplicate commits, factor retention, amount-mode round trip, selection/weight changes without input creation, disambiguation, cleanup of unused/current placeholders, protection of references elsewhere, explicit unused-input deletion, saved JSON reload and decorated production fields. The r453 browser population-mapping regression, four r453 engine tests and r452 Apply/headline browser regression also pass. No engine changes. Actual client engagement data is not included.

After deployment: Balance → Shared assumption × factors → Manage shared assumptions → Remove unused empty entries. Select Annual TPV per practice, then Acquisition population and map the four bands as needed. Existing meaningful assumptions and references are retained; no client entries are deleted by deploying this release.
