# Foundry r349

Corrects automatic module registration for Fee Products and other OBS products. Parent r348 / a832c70.

syncModules now includes balance_driven_obs when obs_exposures contains products, alongside existing deposit/lending/mortgage registration. Previously adding fee-free lending to a deposit-free engagement caused the funding-side gate to fail even when a separate fee product was present. The existing module list is rebuilt from authored products without changing those products. No validation bypass, dummy funding or duplicate fees are introduced.

Verification: regression reproduces the original gate failure, executes the actual browser sync function, then runs a deposit-free linked flow-based lending product plus separate fee product through public run_v2 and confirms returned quantity series. Covers fee-only, empty and product removal cases and unchanged assumptions. Stream-figure recovery and source-browser checks pass.

Delivery includes delivery/ with the full Git bundle. Packaged, not deployed.
