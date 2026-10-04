# r274 — Responsive expense editor and balance previews

Built directly on r273. The category list and editor use the space available inside Configuration, rather than browser width. Opening Assumptions reduces that space and stacks the category list above the editor; wide workspaces retain the side-by-side presentation. Formula factor controls wrap within the editor, while remove-factor buttons stay at the upper right of their own row.

Catalog balance links now display the selected series from the latest run in $000s, labeled by presentation period. Beginning and average measures use the correct opening stock: deposit/lending opening balances, pool-member deposit opening balances, or explicit opening swept balance. The preview is read-only and does not run the model or alter its numbers. If results are unavailable, the UI asks the user to run the model. The hide/show preview control remains separate from the remove-factor button.

Production Chromium coverage checks editor bounds at 1280, 1440, and 1920 pixels with Assumptions open and closed, remove-factor placement, and engine-backed retained balances ($400,000 end; $200,000 first-period average from zero opening). Prior catalog search, source selection, rename, and measure checks remain covered. Engine code is unchanged.
