# Foundry r382 — clear applied and draft rate states

Built on r381 / 76723a8. Packaged; not deployed.

Rates & Curves now states whether rates are applied with no pending changes, a loaded draft awaits application, or schedule edits have not yet been loaded. Applied schedules reopen in a collapsed, read-only disclosure with explicit Edit / replace schedule. Their paste forms no longer look like unfinished input. Preview applied rates displays the effective paths without requiring another Load or Apply. Applying unchanged rates is a no-op, and Apply remains disabled until a changed draft has a matching validated preview.

Schedule edit buffers survive navigation between indices and the rates page within the current engagement, while staying separate from applied model configuration. Cancel edit discards only the unloaded buffer; Discard draft restores applied assumptions. View state is isolated between configuration objects. Schedule disclosures use stable keys and detached-node guards. A stale preview cannot authorize application after schedule text changes. First effective date reflects the loaded schedule, and percentage text avoids floating-point display artifacts while retaining round-trip rate precision.

No backend calculation, curve precedence, interpolation, storage schema or deposit-pricing changes. Existing applied assumptions are not migrated or rescaled. The Applied message describes model application, not a substitute for engagement save confirmation.

Validation: real Chromium exercises the actual editor with backend-generated previews, applied/read-only state, clean five-year percentages, index navigation and serialized engagement reload, unloaded buffer retention, stale-response rejection, engagement isolation, Apply/no-op and discard guards, and downstream deposit yields after application. Controls remain contained at 1440/1024/768 widths; screenshot inspected. Existing rates UI and backend checks pass, including preview isolation, parsing/units, source refresh preservation, stale responses, monthly/quarterly cadence, curve precedence, scenario shocks, deposit interest and audit export. JavaScript syntax and git whitespace checks pass.
