# Foundry r404 — Readable engagement names

Direct continuation of r403 / 8289f15. The saved-engagement menu grows from 373px to 640px where the screen permits, and longer bank, version and storage names wrap instead of clipping. Existing viewport clamping, selection, delete and recovery controls remain. No engagement data, engine or save/recovery behavior changes.

Real-browser checks cover long names, unclipped wrapping, menu controls and viewport containment at 1600, 1024 and 768 pixels, plus the r403 header/selector checks. The desktop layout was visually inspected. Inline JavaScript syntax and whitespace checks pass.
