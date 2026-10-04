# r280 — Clear fee Activity paste drafts

Built directly on r279. Clear now explicitly empties the matching live textarea before rerender for the derived coefficient, entered monetary flow, and account count Activity schedule handlers. This prevents authoring-state restoration from repopulating a consumed draft when the callback runs without the generic click interception. Other unsubmitted drafts remain intact. No engine or stored configuration schema changes.

Validation: browser regression fails against r279 with the cleared draft still containing 2/3/4 and passes on r280 for all three handlers. Checks empty schedules, empty visible text, disabled Load, unrelated draft preservation, subsequent rerenders, ordinary edit preservation, and replacement load. Existing production formula layout regression, pinned result identities, and inline JavaScript syntax checks pass. Full suite was not repeated for this scoped UI change.
