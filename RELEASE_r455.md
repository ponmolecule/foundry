# r455 — Direct deletion beside the shared assumption dropdown

Removes internal IDs from all shared-assumption option labels. Visible Delete selected assumption and Clear empty entries buttons now sit immediately beneath the dropdown. No management disclosure or extra table is required. Explicit deletion removes the selected entry and detaches only this loan, retaining its percentage factors. References elsewhere block deletion with a plain explanation. Clear empty entries retains the narrow blank-placeholder checks from r454. No automatic deletion, engagement migration or engine changes.

Named staged creation from r454 is retained. Opening the selector or cancelling creation never creates an input.

Validation: Chromium regression passes for direct deletion in the decorated production layout, readable labels, blank cleanup, protection of references elsewhere, factor retention, named creation, duplicate commit protection and saved-configuration reload.

After deployment: select a zombie entry and click Delete selected assumption, or click Clear empty entries to remove eligible blank entries together. Select Annual TPV per practice to resume authoring.
