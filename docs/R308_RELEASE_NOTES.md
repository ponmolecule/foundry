# r308 — Guide Me source references

Built on r307 (3b90d69). No engine arithmetic, saved-engagement migration, or UI layout change.

- Make product-level AUC sources and coefficient names distinct from stream references in the translator contract.
- A structurally invalid mapping receives one automatic correction request with the original description, clarification history, rejected response and validation error. The replacement must pass the same complete validator. No reference is silently dropped; a second invalid response fails closed with a clear message. Up to two upstream requests, each using the existing request timeout.
- Complete cross-product quantity-source reference validation, dummy engine shape and picker instructions.
- Preserve the existing single-stream equation: average AUC × annual turns / periods per year × throughput fee. User schedules and fee values remain entered assumptions.

Deploy with the usual dynamic deployment script, reload, retry the description.
