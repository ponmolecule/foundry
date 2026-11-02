# r451 — Workforce compensation growth inheritance

Built on Claude r450, retaining its deposit layout, full-precision editing and stream Type column.

Compensation now offers Flat, Growth and Schedule. Growth shows Workforce default or Role override. Inherited growth follows the workforce defaults; selecting Role override seeds those settings for editing. A zero rate is an explicit override. Clearing the rate or choosing Workforce default restores inheritance. Flat and Schedule remain independent of default salary escalation.

Existing default-based, partially overridden and explicit compensation growth paths are rendered without migration or calculation changes. The financial engine is unchanged. Browser coverage checks inheritance, override, zero, blank, switching from Flat and retention of saved explicit growth. Existing workforce activation, additive compensation, growth, configuration layout and pinned fixture tests pass.
