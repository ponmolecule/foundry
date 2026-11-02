# r453 — Live acquisition population weights for customer-linked lending

Adds an opt-in Weight source selector under Shared assumption × factors. Acquisition population uses the selected whole customer-acquisition feed's active band mix monthly. Each shared weighted component maps to exactly one stable acquisition band ID. Unique matching names seed mappings on selection only; ambiguous/missing mappings require author selection and fail validation. Zero active populations resolve to zero balance.

Shared amounts remain referenced live. Authored shared weights, shared factors, consumer factors, input IDs and band IDs are preserved. Only the opted-in loan consumer changes weighting. Switching back restores the shared entered-weight calculation; no engagement migration or automatic opt-in occurs.

A common population amount resolver now serves deposits and lending. Monthly counts and amounts resolve before quarterly period-end sampling or averaging monthly exposures. Loan audit breakdowns retain monthly cadence labels. Factors are applied once, dimensions and complete band coverage are validated, and invalid mappings do not silently fall back.

Validation: 15 population/composition/deposit tests, existing linked-loan suite, browser live-source/mapping/toggle/shared-isolation/factor/reload test, r452 click and headline recovery test, full-engine saved-config round trip and all six pinned fixture fingerprints passed. Actual client engagement is not included in this package and remains to be reconciled after explicit opt-in.

After deployment: Lending → Receivable Advances → Balance → Shared assumption × factors → Weight source → Acquisition population. Map the four TPV components to the four Receivable Advances Accounts bands. Keep the existing advance percentage and shared amount paths. Run and compare M60 to the source; do not change yield or fees as part of this step.
