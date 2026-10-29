# r418 — Reporting identity in exhibits

Built on r417. Business Plan Tables use product-ID membership everywhere (no name lookups), so ID-based groups and renamed members are presented consistently on every sheet. Allowance/provision reconciliation uses the engine's own opening allowance (new output-only field alllOpen), so entered opening allowances reconcile and export. A missing legacy member is a repairable validation problem rather than a recursion error. No calculation changes.
