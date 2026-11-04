# r466 — Fixed assets Formula / level as one component table

Presentation only. No engine, validation or saved-input change.

The Formula / level editor was three stacked groups (Opening position, Balance derivation, Depreciation) that listed the same components twice and spread one calculation across a long column of inputs. It now reads top to bottom as one calculation:

1. **Two method controls** at the top as buttons: Level basis (Gross PP&E / Net PP&E target) and Depreciation (Rate by component / One rate on total / Entered amount). These are the existing `level_basis` and `depreciation.kind` fields; "One rate on total" is the former "% of asset level". Net PP&E and Rate by component disable each other, matching the engine rule that component rates require Gross PP&E.
2. **Opening position** on one line: Gross − Accumulated depreciation = Net (Net + Accumulated = Gross on the net basis).
3. **Components table**, one row per component: name, what sets its level, level at M12 (Q4 on quarterly runs), depreciation rate with implied useful life (33.33% / yr ≈ 3.0-year life), and depreciation for M1–M12. A total row closes the table. "Rate period" moved into the FLAT ▾ path editor; rates read as annual unless that editor says otherwise.
4. **Component editor** opens under its row: driver, timing (lag, headcount before M1), multiplier, and an equation using the latest run (Level in month t = Operations at t − 1 mo × $1.0k · M12 = 6 × $1.0k = 6.0). Units per group and rounding sit behind "Add grouping" unless already set.
5. **Check** when the M1 gross level falls below the opening book: states the gap and that it is treated as an M1 disposal, and points to Base asset level and Headcount before M1. It does not prescribe a number, since the opening book can include assets (e.g. furniture) that no headcount driver explains.
6. **Roll-forward M1–M12**: gross (opening + additions − disposals), accumulated depreciation (opening + depreciation − relieved) and net. Depreciation in the table and the roll-forward is the same figure (closing − opening accumulated + relief), so the display foots exactly.

Flat cells keep full precision: a rate shown as 33.33 stores 1/3 unless the value is actually changed (r450 behaviour).

Finding for the engine owner (not changed here): in the run payload, `fixed_assets.formula_level.components[].depreciation` is in dollars while `amount`, `multiplier`, `base` and the top-level fixed-asset arrays are in $000s (parity.py scales the others). The console converts it.

Validation: web/tests_r466_fixed_assets_ui.cjs (11 rendered checks: engine reconciliation, footing, check text, precision, path editors, component editor, method buttons, names, removal, preview keys). tests_fixed_assets_ui.py string checks updated to the new labels. Embedded reference coverage regenerated (tools/reference_scan.py --write).

Full suite on 08d8db7: 297 modules, 15 failing. Every one of the 15 also fails on GPT's r465 (b43e285) unchanged, with the same error, and all passed at r450, so they were introduced between r451 and r465. One of them (tests_r394_reference, stale embedded coverage) is fixed in this release; tests_r394_reference, tests_fixed_assets_ui and tests_r466 pass on the final commit. The 14 still open, for GPT:

- tests_cac_shapeshifter: "Component inclusion IDs must be unique" raised by component_switches.py on the audit config.
- tests_series_architecture: "config validation fails closed on broken links and duplicate stable IDs".
- tests_growth_ui (11 checks) and tests_r350_flow_lending_ui (py and cjs): renderer harness errors.
- tests_r360_stream_outputs (py and cjs): "loanUnusedReserveHtml is not defined" in the harness.
- tests_account_activity, tests_authoring_stability ("lastErrs is not defined"), tests_authoring_state, tests_r366_shared_lending, tests_r368_result_numbers, tests_r419_expense_numbers ("_calculatedInputs is not defined"), tests_r445_product_consistency.
