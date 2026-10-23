# Shared weighted assumptions for deposit balances (r383)

Under **Customer count × balance per customer**, choose **Amount source → Reusable weighted assumption**. Select an existing money-per-unit assumption, or choose **+ Create weighted assumption…**. Components use the existing shared registry: named amounts in actual dollars per customer and named percentage weights that must total 100% in every month.

The weighted amount is the sum of each amount × weight. The shared assumption's descriptive time basis does not divide a deposit stock by 12. Use No time basis for a balance per customer. Consumer-specific **Percentage factors** multiply the resolved amount without changing the shared assumption. Separate deposit products can therefore reuse one weighted balance and apply complementary shares with distinct pricing.

Counts stay linked to the existing acquisition feed. Amounts and weights resolve monthly before multiplication with monthly customer observations. Quarterly ending balances sample the final monthly product; quarterly average measures average monthly products. They do not multiply separately averaged counts and amounts.

The existing entered-dollar path remains available and unchanged. No active engagement is automatically converted. Editing a shared assumption intentionally affects all its consumers, including any lending consumer that references it.

**Resolved assumption calculation · latest run** is a collapsed readout of first-month component contributions and the resolved amount. The Calculation Audit Workbook → Product Calculations provides complete monthly/native-period assumption rows, count and calculated balance. Existing source identity appears in the selector; the main balance preview remains the deposit's own calculated output.


## Creating and cleaning up entries (r384)

Create opens a dialog: supply a descriptive name and choose Create, or Cancel without changing the engagement. The new assumption is automatically selected and expanded. Duplicate creation names are rejected.

Manage assumptions lists references and allows deletion of unused entries. Existing accidental duplicates are not automatically removed. If the selected entry is accidental, use Unlink here; it can then be deleted only if no other consumer or preserved draft still refers to it. Removing unused entries does not renumber or replace any stable assumption ID.
