# r462 — Linked spend layout

Linked spend now uses a dedicated section instead of inheriting the two-column form-label grid. Each source has a readable name and breadcrumb, a compact Allocation field with a percent suffix, and a remove action. Add source uses explicit readable colors and focus/hover states. One short note replaces the implementation-heavy paragraphs. Source rows adapt to narrower containers.

Acquisition spend calculation, source IDs, allocations and saved inputs are unchanged. Existing r461 links load directly.

Validation: rendered and inspected wide and narrow source sections with a realistic long source name; browser selection, two-source addition, allocation edits, removal, and entered fallback pass. Layout checks cover usable source width, aligned controls, no internal overflow, and readable action color. Existing r460 formula Numbers browser checks pass for all three product families in monthly and quarterly models.
