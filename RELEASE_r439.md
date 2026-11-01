# r439 — Schedule wording tidy

Built on r438 (e112e30). Text only; no behaviour or stored-value changes.

Three places where the r438 rename left the word doubled now read naturally:
- Path help: "Schedule needs a schedule loaded with Load (replace)." → "Schedule needs its values loaded with Load (replace)."
- Fixed-rate reference text: "Flat, Growth or Schedule schedule." → "Flat, Growth or Schedule path."
- Balance-components reference location: "› Schedule, Schedule cadence Year ›" → "› Schedule path › cadence Year ›".

The control label "Schedule cadence" is unchanged: it names the cadence of a schedule and appears beside a Schedule path, not after the word. Reference coverage re-scanned.

ZIP contains delivery/foundry-full.bundle. BUILD_STAMP = foundry-r439-schedule-wording.
