# r430 — Clear explicit Series paste drafts correctly

Built on r429 (85b5d64). Clear now empties both the loaded explicit schedule and the live paste textarea before authoring-state capture, preventing stale pasted text from being restored beside “No values loaded”. The editor remains open for replacement, and Load is disabled until valid new input is supplied. Existing Clear semantics are retained: it removes the loaded schedule, not merely the draft text.

Precision: the rate paste parser stores supplied numeric digits after percentage conversion without display rounding. The engine resolves those stored values directly. Preview percentages are formatted to three decimal places only. Precision already lost in copied Excel text cannot be recovered.

Validation: new UI regression verifies high-precision rate parsing, clearing loaded values and draft text before render, open replacement editor and disabled Load. Direct engine check verifies the supplied precision survives resolution. Inline/generated JavaScript syntax checks pass. No calculation or save mechanism change. No real-browser visual check was available.

ZIP contains delivery/foundry-full.bundle. BUILD_STAMP = foundry-r430-series-clear.
