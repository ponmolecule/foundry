# Foundry r347

Fixes Browse / search failing before its source dialog opens when a fee-economics catalog publisher omits optional measures. Parent r346 / 8c47b4b.

The publisher now provides an empty measures list for fee economics, and the shared browser tolerates missing measures from other publishers. Existing unit/dependency eligibility is preserved. Lending source dropdown labels now identify Monetary throughput and explain that a fee stream contributes its underlying activity quantity, not revenue or cost. Count streams remain ineligible for lending funded volume.

Verification: executable real-dialog regression covers opening, search, incompatible rows, no results and selection with missing optional measures. Source catalog and fee quantity links pass. No engine economics or engagement data changed. Delivery contains the required delivery/ folder; packaged, not deployed.
