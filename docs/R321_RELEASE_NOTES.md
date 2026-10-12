# r321 — protect current inputs, not empty cards or deletion history

Direct continuation of r320 (d101bc3). No engine or economic changes.

## Cause

r318–r320 compared entire assumption-section fingerprints against creation fingerprints. Creating an empty fee card or workforce section therefore locked setup. Removing a section present at creation also counted as a difference. Deleting roles leaves the workforce's mode, generated total-count ID and defaults, which were incorrectly treated as timing dependencies.

## Correction

Protection now tests current content before using a fingerprint difference. Missing or empty sections do not keep a historical lock. Empty fee products with no streams, balance, yield or expense are safe, including their unused template ramp. Workforce roles containing flat compensation in explicit month/quarter/year units, flat count and period-1 hiring are safe. Pre-opening expenses continue to be excluded.

Actual fee streams, volumes, links, workforce growth/count schedules, timed hiring, assessments, additive compensation and unknown substantive fields remain protected. This is a conservative exception for known cadence-independent grammar, not a wholesale unlock of populated engagements. Salary/count values and pre-opening costs are preserved. Legacy files without creation metadata use the same content checks. No creation baseline is fabricated for populated legacy inputs.

## Deployment check

Open Edit setup after deploying. Cadence and target opening must be active when the only entries are an empty fee card, flat salary role, and pre-opening expenses. They must remain active after deleting those entries. Add a role beginning in period 13 or an explicit count schedule: structural editing must be protected again. No need to delete salary-only roles to revise setup.

Expand/Collapse/Edit from r320 remains included.
