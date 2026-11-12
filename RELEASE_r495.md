# r495 — Disclosures that look openable

Console only. No engine change. Built on GPT's r494 (ca84e45).

## The problem

About 50 collapsible sections in the console used the browser's default disclosure: a small grey triangle and plain text ("▸ Tax treatment & shared references", "▸ Posting & accounting", "▸ Sources"). Several row editors used a 9px "▸" after the name. Data entry and settings sat behind controls that read as captions.

## What r495 does

- **Plain disclosures** (tax notes, posting & accounting, source rows, derived rules, carryforward limit, model checks, reporting, more settings, advanced trajectories and the rest): a bordered control with a drawn chevron, bold dark label, hover state and keyboard focus ring. The chevron turns down and the control tints gold when open.
- **Section headers that open** (Sources, Advanced · Derived rules, balance-component cards, securities sleeves and sections, formula-base items): a 20px chevron box at the left, which turns when open, plus a hover background on the header row.
- **Row names that open an editor** (fixed assets, pre-opening expenses): underlined like links, with a 16px chevron box in place of the 9px triangle.
- Disclosures that already had their own design keep it: factor cards, schedule previews, customer-acquisition feed cards, guide navigation and options, governance categories, adoption cards, settings groups.

One stylesheet block; no markup or behaviour changes.

## Verification

- New: web/tests_r495_disclosure_affordance.cjs (bordered control and chevron, open state, section chevron box, custom disclosures unchanged, row-editor link, Enter toggles).
- Reference coverage regenerated.
