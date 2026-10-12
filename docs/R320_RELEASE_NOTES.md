# r320 — collapsible engagement setup

Direct continuation of r319 (c981939). Adds a compact Expand/Collapse button beside Edit. Collapse hides the summary and editor while preserving any draft or in-flight validation. Expand restores them. Edit expands the section and requests the current setup policy. Snapshot users can expand/collapse but cannot edit. Switching engagements resets the view to expanded and clears drafts. Disclosure state is transient: no configuration, result or saved engagement field is added.

Validation: actual JavaScript helper tests cover collapse/expand, untouched configuration, retained draft, Edit from collapsed, snapshot read-only, rejection and stale responses. All 26 backend setup checks pass; complete inline JavaScript syntax and whitespace checks pass. No engine changes. No rendered browser test is claimed (browser unavailable). Full suite not rerun for this isolated disclosure change; r319 baseline recorded 91 passing modules and 16 existing failures.
