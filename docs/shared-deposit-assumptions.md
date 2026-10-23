# Shared weighted assumptions for deposit balances (r383)

Under **Customer count × balance per customer**, choose **Amount source → Reusable weighted assumption**. Select an existing money-per-unit assumption, or choose **+ New weighted assumption**. Components use the existing shared registry: named amounts in actual dollars per customer and named percentage weights that must total 100% in every month.

The weighted amount is the sum of each amount × weight. The shared assumption's descriptive time basis does not divide a deposit stock by 12. Use No time basis for a balance per customer. Consumer-specific **Percentage factors** multiply the resolved amount without changing the shared assumption. Separate deposit products can therefore reuse one weighted balance and apply complementary shares with distinct pricing.

Counts stay linked to the existing acquisition feed. Amounts and weights resolve monthly before multiplication with monthly customer observations. Quarterly ending balances sample the final monthly product; quarterly average measures average monthly products. They do not multiply separately averaged counts and amounts.

The existing entered-dollar path remains available and unchanged. No active engagement is automatically converted. Editing a shared assumption intentionally affects all its consumers, including any lending consumer that references it.

**Resolved assumption calculation · latest run** is a collapsed readout of first-month component contributions and the resolved amount. The Calculation Audit Workbook → Product Calculations provides complete monthly/native-period assumption rows, count and calculated balance. Existing source identity appears in the selector; the main balance preview remains the deposit's own calculated output.
