# r390 — searchable Foundry Index

Built on r389; no financial engine, persistence or input schema changes.

Index appears immediately to the right of Governance. The initial view contains six subject cards, a search field and Search button, and short links to common controls. Sections are Balances & lending; Customers & sources; Streams & pricing; Formulas & schedules; Results & units; Saving & recovery.

27 curated topics explain 86 choices/concepts. Search covers titles, aliases, definitions and examples, with section filtering, match counts and a clear empty state. Search and article state remain outside the engagement configuration. Explanations are read-only. Links open the relevant authoring tab without choosing a product or changing its inputs.

Articles separate location, exact option labels, when-to-use explanations, illustrative values, cautions and related topics. Details expand on demand. All four lending Balance authoring methods and all four deposit Balance method choices are documented individually. Their live dropdowns and the reference use the same option-label lists. Other content is curated, not an automatically complete manual of every Foundry control. The first edition states its scope through its topic menu; future controls require corresponding documentation and review.

Layout: charcoal/cream/gold theme, constrained reading width, six-card landing rather than a long article dump, sticky desktop section navigation, responsive mobile section strip, keyboard-native buttons/forms/details, visible focus, escaped search text, reduced-motion support and scoped narrow-screen app-header wrapping. No fetched/generated images or production engagement content is included; numerical visual examples are self-contained.

Validation: dedicated browser checks for placement, exact balance-option coverage, reference integrity, search/keyboard submission, escaped queries, no-match/reset, section filtering, related links, authoring navigation, no engagement mutation and containment at 1440/1024/768/390. Existing r389 authoring and real HTTP save/recovery browser regressions pass. Fifteen existing backend save/formula/deposit-rate cases pass. Inline JavaScript syntax and diff whitespace checks pass. Screenshots reviewed and landing density reduced after visual review.

Reversal is isolated to navigation, Index rendering/content/styles and shared option-label lists; no saved engagement data must be reversed. Not deployed or pushed. Confirm build stamp foundry-r390-index after deployment.
