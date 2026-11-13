# r505: One page pattern for Configuration, matching side menus, correct build stamp

Built on Claude r504 (ac697b8). A UI release, following the approved Configuration mockups.

## Engine and calculations

Unchanged. No engine, calculation or configuration change. Rendering a module leaves the configuration exactly as it was.

## Configuration: one page pattern for every module

All eight modules now use the same frame:

1. **Breadcrumb.**
2. **Header band.** It has the same height on every module, with icon, module name, a one-line purpose and the on/off switch. Rates & Curves shows "Always on".
3. **Status line.** It shows the module's method choice where it has one: Simple overhead or Detailed for Operating expense, Calculated or Externally determined for Tax.
4. **Four key figures**, in one tile style.
5. **A numbered section menu** on the left, with one section open and a numbered section header.
6. **One footer.**

How each module maps onto it:

- **Rates & Curves:**
  - Published Fed projections;
  - EFFR, SOFR and Prime as their own sections (each opens the adjustments for that index);
  - Effective index paths.
- **Capital & pre-opening:**
  - Staged raises;
  - Scheduled borrowings;
  - Pre-opening expenses (with minimum day-1 capital);
  - Fixed assets / CAPEX.
- **Securities & AOCI:** its existing section menu is kept, restyled to the shared menu.
- **Other income:** Income lines.
- **Operating expense:**
  - Workforce, Expense categories, and Assessments & other NIE, which replace the tab strip;
  - the Simple/Detailed choice sits in the status line;
  - the existing key figures move into the tile row.
- **Customer acquisition:**
  - its feed menu is kept, restyled to the shared menu;
  - "+ Create feed" sits in the status line;
  - four key figures.
- **Tax detail:**
  - Calculated tax: Interim provision, then Deferred-tax recognition.
  - Externally determined tax: one section per panel (Shared assumptions, Calculation blocks, Sources, Derived rules, Provision & settlement).
- **Credit regime:** Vocabulary and provision, with product measurement counts as figures.

Also changed:

- **Rail sub-list removed.** The list under the selected module in the Configuration rail is gone; each module's own menu replaces it.
- **Header controls removed.** "Collapse" buttons in module headers are gone.

Nothing is removed from any module. Every control keeps its handler and writes the same field.

## Stress Testing side menu matches Product and Configuration

- **Layout:** the rail now has a page heading ("Stress Testing") above a white card.
- **Items:** caps group labels, and each item has an icon in a bordered square.
- **Selected item:** a gold wash with a gold left bar, and a dark icon square with a gold icon.
- **Content:** sits in its own card beside the rail.

## Build stamp

- **The stale stamp is fixed.** `BUILD_STAMP` had stayed at r501 since r502, so the footer and the engine identity recorded on stress runs showed r501. It now reads `foundry-r505-config-module-pattern`, in the plain `foundry-r<NNN>-<slug>` format the older checks expect (no date suffix).
- **New release check.** `tools/release_check.py r505` refuses to package when the stamp, the latest release notes and the requested release disagree. It runs before every package.
- **New test.** `foundry/v2/tests_r505_release_stamp.py` checks the same agreement, and that stress runs record the stamp.
- **Stress runs from before r505 will show as stale** once r505 is deployed, because the engine identity now reads r505 instead of r501. Rerun them on r505 to make them current again.

## Validation

- `foundry/v2/tests_r505_release_stamp.py`: 4 checks pass.
- `web/tests_r505_config_pattern_ui.cjs` checks:
  - every module renders the shared frame and the configuration is unchanged;
  - section menus select one section;
  - each module's controls still write their fields;
  - the Stress Testing rail uses the shared menu style.
- Existing Configuration and Stress Testing UI tests pass.
