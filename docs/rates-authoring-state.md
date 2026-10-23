# Rates & Curves authoring state

r382 separates three visible states without changing the rate engine or stored assumptions:

- **Applied — no pending rate changes.** The rate workspace matches the configuration currently used by the model. This is model application status; engagement save/server persistence continues to use the normal save feedback.
- **Draft rate changes — not applied to the model.** Settings or a loaded schedule differ from the applied workspace. Preview validates the complete candidate configuration; Apply is enabled only for the matching, current preview.
- **Schedule edits not loaded.** Text or schedule form settings have been edited but have not been loaded into the rate draft. Load (replace) & preview is required before Apply. Applied rates remain active meanwhile.

Returning to a workspace with applied schedules shows a compact read-only schedule disclosure. The paste form is not automatically repopulated on the main view; Edit / replace schedule explicitly opens it. Inspection, opening the edit form, switching indices and previewing applied rates do not write assumptions or make rates dirty. A serialized engagement reload reconstructs the applied state from its configuration rather than requiring an in-memory confirmation flag.

Load stages a schedule and previews it; Apply changes commits the validated draft to the model and invokes the existing engagement save/run mechanisms. Applying an unchanged workspace is a no-op. Applied previews can remain visible while current; unrelated configuration changes invalidate a preview's applicability rather than making a stale preview authoritative. Reloaded workspaces can use Preview applied rates to display index paths without reloading or reapplying the schedule.

Schedule edit buffers and disclosure state are view-local and keyed by index within the current configuration object. They survive index/page navigation within the current engagement, but are not persisted as applied assumptions until loaded and applied. Cancel edit drops only that unloaded edit buffer. Discard draft restores the model-applied workspace. Switching configuration objects clears view-local state, and stale asynchronous responses cannot cross engagements or supersede newer edits. Disclosure state uses stable panel keys, not positions in the document; detached elements cannot overwrite it.

Saved dates, rates, units, source labels, interpolation, coverage, extension and timestamps are retained. The edit form uses the schedule's actual first effective date. The percentage formatter selects a short decimal spelling that parses back to the identical stored rate where possible, avoiding display artifacts such as 3.6000000000000005 without rounding stored rates or changing interpolation/pricing. Read-only schedule tables remain bounded and scrollable.
