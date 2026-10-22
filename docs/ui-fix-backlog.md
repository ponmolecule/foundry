# UI fix backlog

## Entered interest income units — open

Reported 2026-10-21. Deployment paused while Railway is unavailable.

Securities & AOCI → Interest-bearing balances → Income calculation → Entered income amount does not make its $000s entry units sufficiently clear, especially for Explicit monthly schedules and pasted values. A user could enter raw dollars and overstate income by 1,000 times.

Future change: show **Income amount ($000s)** and repeat the unit next to the Explicit paste/editor control. Keep **amount period** (monthly/quarterly/annual flow) distinct from schedule cadence. Include a short conversion example where useful: $66,818 → 66.818. Check equivalent monetary schedule controls for the same ambiguity. Preserve stored values and existing scale conversions; no automatic rescaling or engagement migration.

Status: logged only; no UI implementation, release or deployment authorized by this log entry.
