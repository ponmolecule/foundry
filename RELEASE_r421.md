# r421 — Count-authoring layout

Built on r420. This is a presentation correction to the new count authoring feature; engine math and stored band data are unchanged.

Count calculation now shows two labeled radio-card choices: Single multiplier and Weighted breakdown, with short explanations. Sourced derived Account streams use a clean Count per source unit field instead of ambiguous Legacy multiple/Legacy % controls. Weighted bands use numbered, named cards, with Share and Count in aligned columns. Each assumption exposes Flat, Growth and Explicit schedule as visible buttons, reusing the existing Series editor for values and advanced controls. Local styling fixes low-contrast controls and oversized full-width actions. Add band and Remove are compact; layout stacks on narrow screens. Existing deposit and shared-amount editors are untouched.

Switching methods preserves both drafts. Selecting the active method is a no-op, preventing a second selection from resetting the multiplier draft. The Index wording follows the new method label.

Validation: weighted-count engine tests pass; editor tests cover visible choices, all paths, units, draft preservation and idempotent selection. Existing inline/generated JavaScript syntax checks pass. git diff check passes. No engine file changes. Real-browser visual verification was blocked because the cloud browser could not reach the local preview; layout was checked through markup/CSS inspection and the editor harness.
