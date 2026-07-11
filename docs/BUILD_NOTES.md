
## Preview demo configuration — pinned (post-PC-26)
Client observed Summary Ratios changing between preview bakes. Cause: demo-config drift, not
engine drift — PC-20..PC-23 previews were baked from pf_a_base, PC-26 from pf_a_ots_msr
(+ management_capital_target 0.10), unannounced. Verified: fixtures 9/9 stable across all
commits; management_capital_target leaves financials byte-identical (config_hash differs by
design). Standing rule: the canonical preview config is pf_a_ots_msr with management target
0.10, changed only on client instruction, and any change is called out in the reply.
