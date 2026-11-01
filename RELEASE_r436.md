# r436 — Test debt cleared (51 failing modules to 0)

Built on r435 (a4649bd). The full suite had been failing 51 of 262 modules, almost all inherited from earlier releases (44 already failed at r421; all 51 at r432). Each failure was traced to its cause and fixed at the right place: the product where the product was wrong, the test where the test had gone stale. No check was deleted or weakened; replaced behaviour is checked through its replacement. Every changed test line carries an `r436:` note naming the release that changed the product.

## Calculation guards

- **Run fingerprints.** Every complete-result change from r300 to r435 was traced commit by commit on all three pinned fixtures. One touched a financial view: r405 made FTP product contribution subtract fee-stream pass-through costs that the income statement already carried (core: one product's contribution 4,797.35 → 3,940.06; universal: two products; treasury centre offsets). The statements, capital, Call Report, tax and scenarios were identical from r300 to r435. The rest were reporting additions (r356, r360, r368, r376, r418, r419). Pins are re-set with that history in the test, and a new **financial fingerprint** pins financial outputs only, so a reporting addition can no longer hide a calculation change.
- **Parity with the predecessor.** Two deliberate corrections depart from the predecessor's values: r152 (NIM on the earning-asset basis) and r284 (tax-year NOL ledger and interim provisions; in one fixture this carries through Q12 tax, net income and the balance sheet). Those cells are now pinned to their current values with the reason (fixtures/parity/divergences.json); every other cell is still checked against the predecessor.
- **Fee-stream economic baseline.** Moved four times (r138, r152, r279, r284), each a deliberate correction unrelated to fee streams; re-pinned with that history.

## Product fixes

- **The engine no longer changes the configuration it is given.** Running the model wrote acquisition-flow IDs into the caller's channels; they are now derived on a private copy. Results identical.
- **Call Report mapping.** MSR amortization (already netted in RI 5.f) and bank EBITDA (management subtotal) are mapped as detail / memo lines. No reported values change.
- **Guide Me vocabulary** labels the two newer cost kinds (% of balance operating cost, linked formula cost).
- **Paste boxes.** Four schedule paste boxes now enable Load / Apply only once their own box holds values (loan repayment curve; funded-flow schedule in two places, which previously loaded on change; per-month override paste, which enables on any content because blank cells clear overrides).
- **Load (replace) now clears its paste draft.** The draft was restored after loading because the consumed marker was reset as a microtask, before the button re-rendered; it is now reset as a task. The r435 grid paste drawers are marked as paste surfaces too.
- **Funded-flow loans may carry a distributed-balance fee.** The engine supported it (the repayment profile publishes the distributed balance) but validation still required an allocation group. Validation now accepts a funded-flow balance as well. This changes what a configuration may contain; say if you would rather keep the old rule.
- **Universal template coverage.** The template now exercises every fee source and cost kind: account activity, fee-stream quantity, funded flow and distributed balance; per-account, periodic-amount, % of balance and linked-formula costs. Seven streams and one funded-flow lending product ("Point-of-sale finance (funded flow)"). Template results change by design (pinned; net income +$398.7k over the horizon).
- **Reference coverage** re-scanned (300 controls; the stored table said 297).
- **CSS hygiene.** 67 selectors defined more than once at top level were merged into one rule each, later declarations last. 65 screens compared pixel for pixel before and after: identical apart from four that also vary between two runs of the same build.

## Tests brought up to date

About 40 modules, mostly browser harnesses and UI-string checks that predated redesigns (r199, r281, r326, r344, r346, r358, r360, r373, r387–r402, r410, r416, r425) or the r433–r435 field system. Common causes: helpers moved outside the extracted slice, `node -e` arguments too long for the operating system (scripts now go through stdin), renamed labels, one-section-at-a-time product steps, and segmented path buttons. Two alignment checks (r406, r407) now assert the field system's rule (one control edge, one label edge) at 1440 / 1024 / 768.

## Result

Full suite: 0 of 262 failing (r435: 51 of 262).

ZIP contains delivery/foundry-full.bundle. BUILD_STAMP = foundry-r436-test-debt.
