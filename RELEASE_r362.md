# Foundry r362

Parent: r361 / 25073e5d7869ee5959549c54f726c6b76b42effa.

Assign stable result identities to every fee stream, including Flat and Event streams. Existing saved streams receive a missing identity during normalization; guided stream creation also assigns identities consistently. Existing identities remain unchanged. This allows per-stream financial results to reach compact previews, tables and charts without altering fee calculations or broadening eligible quantity-link sources.

Verification: legacy identity backfill and repeat stability across fee, loan and deposit owners; Flat and Event engine-to-public output regression; existing r360 stream output regression. Packaged for deployment, not deployed.
