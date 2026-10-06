# r307 — Repair Guide Me vocabulary and annual-change mapping

Built directly on r306 (5a56b67).

The reported 'distributed_balance' exception was a vocabulary-construction KeyError before any upstream model request. Guide Me inherited all fee-engine source IDs, including loan-only sources absent from its labels. Fee Product Guide Me now scopes out distributed_balance and product_funded_flow, and labels the compatible cross-product fee_stream_quantity source. A completeness guard and manifest/schema regression cover every exposed vocabulary family.

Also corrects the balance-stream annual_change translation: validation now exercises the actual annual-change rate behavior instead of replacing it with flat, and rendered instructions point to Annual rate change, Starting rate and its Flat/Growth/Explicit change path. Explicit annual-change paths require Year/Step; the first change applies after Year 1. The translator prompt distinguishes fee-rate levels from changes in those rates. No engagement or engine arithmetic is changed.

Deploy this ZIP with the usual deployment script, reload Foundry, then retry the same Guide Me description. No credential change is needed for the reported vocabulary error.
