# r507: Stress Testing as an entry tab, Product placed like Configuration, one menu card everywhere

Built on Claude r506 (aa601f6). UI only, following the approved mockups.

## Engine and calculations

Unchanged. No engine, calculation or configuration change.

## Stress Testing is laid out like an entry tab

r506 added a black band across the whole page, above the side menu. Only the non-entry tabs (Balance Sheet, Income Statement) have one. Configuration and Product don't. That band is gone.

- **Rail:** a full-height grey column, 300px wide, with the "Stress Testing" heading on top, as in Configuration.
- **Black band per view:** the content column starts 32px from the rail with the breadcrumb (Analysis / Stress Testing / Scenarios), then a black band for the open view.
  - The band shows the view's icon, name and purpose.
  - The view's actions sit on the right of the band: "+ New scenario" and "Run selected" on Scenarios, "Run liquidity stress" on Liquidity, and so on.
- **Status line:** primary case, window, funding and engagement sit as a plain line under the band.
- **Content:** in its white card below that.

## Product content starts 32px from the rail

The product page used to add 40px to 180px of side padding and center its content in a column up to 1,880px wide. At 1,600px the content started 95px from the rail; at 2,200px about 125px.

It now starts 32px from the rail at every width, the same as Configuration, and fills the width with a 32px margin on the right, up to 1,880px.

The extra width exposed a layout gap in the product editor. The old padding hid it at the widths the tests check, but it would also have shown on screens around 1,550px. Between about 470px and 560px of editor width, fields kept their labels beside the input. In that band, the nested option fields under Credit and Costs ran past their panel.

Two fixes:

- **Label layout:** fields now switch to labels above the input below 560px of editor width, up from 470px.
- **Nested inputs:** inputs in nested option fields shrink to fit.

## One menu card for every section menu

Configuration's section menus now use the Product menu design:

- **One white card:** the menu and the open section share it. The section's own inner border is dropped.
- **Menu column:** near-white (#FAFAF8) with a rule beside it. Items run up to that rule.
- **Selected item:** dark, with a gold left edge and gold step number.

Coverage:

- **Numbered menus:** Rates & Curves, Capital & pre-opening, Other income, Operating expense, Tax detail and Credit regime.
- **Securities & AOCI:** its own menu gets the same card. Each item gains a second line drawn from its section's summary:

  | Section | Second line |
  |---|---|
  | Funding allocation | Hold in cash · floor 5.0% |
  | Interest-bearing balances | Not modeled |
  | Other assets | Flat, no components |
  | Other liabilities | Formula / level · 2 components |
  | Securities | 7 holdings · 4 AFS |
  | AOCI settings | AFS sensitivity 0.5% / yr |

  The line updates when a field in the section changes.
- **Customer acquisition:** its feed menu was already built on the Product design. The r505 overrides that flattened it are removed, so it matches again.

Nothing moves in the page. The card and the menu column are drawn behind the existing layout, so every control keeps its handler.

## Workforce role detail kept

Selecting a role in Operating expense › Workforce still opens its detail. When the Configuration content area is at least 1,400px wide (screens about 1,770px and up), the detail sits to the right of the table, as before. Below that it opens under the table, as before.

## Validation

- New `web/tests_r507_entry_layout_ui.cjs`, run at 1,600px and 2,200px. It checks:
  - **Stress Testing:**
    - no page-wide band;
    - a full-height rail with its heading;
    - the view band 32px from the rail, carrying the view's actions;
    - the breadcrumb.
  - **Product:** content 32px from the rail and filling the width.
  - **Configuration:**
    - the menu card, menu column and gold selected edge on every numbered-menu module;
    - the section beside the menu inside the card;
    - Workforce role detail shown, and on the right at 2,200px.
  - **Securities & AOCI:** in the card, with a second line under every item.
- `web/tests_r505_config_pattern_ui.cjs` now checks the Stress Testing rail heading instead of the r506 band.
- **Updated older tests:**
  - **r352 check** in `tests_r350_flow_lending_ui.py`: now checks the 32px placement instead of the centring.
  - **r434 check:** now checks the 560px label threshold.
  - **r475 schedule preview at 900px:** the wider product page may now show the medium strip. The test still requires the first and last cells and no squeezed cells.
- **Lending layout:** `tests_r370_lending_layout.cjs` (120 layouts, 1,920 to 768px) and `tests_r371_authoring_stability.cjs` pass with the fixes above.
- **Full suite:** 354 modules, 8 failing. These are the same 8 that fail on r506.
- `tools/release_check.py r507` passes. `BUILD_STAMP` reads `foundry-r507-entry-tab-layout`.
