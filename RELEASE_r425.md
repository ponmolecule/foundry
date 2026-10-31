# r425 — Linked stream quantities across product families

Built on r424 (5b959dd). Account, Balance and Transaction streams owned by Fee Products/OBS, Deposits or Lending can select a compatible quantity from any of those families. The source picker labels the family, product and stream. Links use stable IDs, survive renaming/reordering, reject stock/count/flow mismatches and exclude stream dependency cycles. Browsing does not mutate inputs. Same-product “Another stream” remains available.

The planner now covers all three families and evaluates ready dependencies in stages as parent balances become available. Each node posts its own revenue/cost once under its own product. A quantity link never copies the source’s income or expense. Shared monthly account-cost replay and explicit billing periods remain in force. Deposit pool revaluation receives the same stable quantity/definition registry. Catalog units, audit inference, authoring checks, lending-flow validation, Guide Me source label and the Index use the expanded families.

HYS servicing may therefore be authored as an Account stream under the HYS deposit, linked to the existing shared HYS Accounts stream, with Cost per account = $100/year. Existing inflation multipliers remain supported. This release does not move existing streams automatically or alter the save mechanism; remove an old charge only after the replacement is reconciled to avoid charging both.

Dependency boundary: retention-pool own-balance/distributed-balance stream quantities are provisional until bank-state allocation. They are withheld as fee-quantity exports and an attempted stored link fails explicitly. Independent account-count links into pool-owned streams work. Existing published deposit/pool formula sources remain available for their supported consumers. Existing deposit/funding balance-source eligibility is retained; this release does not make downstream statement quantities upstream operands.

Validation:
- Seven new integration tests (including all nine source/consumer family pairs): monthly/quarterly HYS servicing ownership and equality with the old placement; cross-family chains; rename/reorder; loan beginning-balance quantities; pool-owned count costs; missing/duplicate/type/cycle rejection; incremental evaluation without duplicate posting.
- New all-family picker harness and existing linked-quantity, deposit-count picker and JavaScript syntax harnesses pass.
- Existing linked-quantity integration (4), account activity (33), repayment profiles (37), profile completion (40), quantity-unit rules, linked-loan balance, funded-flow timing, source catalog/dialog, customer deposits (5), deposit amount reuse (5) and r424 deposit count links (5) pass.
- Full public outputs compared directly with r424: core bank, universal template bank and existing cross-fee-product linked fixture are identical.
- Existing fee-stream suite: 57 pass / 2 stale fingerprint failures, already present before this change. The deposit-retention suite is blocked by the same existing fingerprint pin. Existing Guide Me tests also stop on missing cost vocabulary labels (linked_formula_opex and pct_of_balance_opex), reproduced on r424. These baseline maintenance issues are not changed here.

No real-browser visual verification was available; picker logic and generated/inline JavaScript syntax were checked. No engagement data, deployment or remote repository push is included.
