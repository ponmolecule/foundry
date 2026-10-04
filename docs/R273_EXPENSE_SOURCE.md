# r273 — Choose expense sources explicitly

Built directly on r272 (8ccc715). New Formula / driver expense components and newly added linked factors start with Select a source. The dropdown and Browse / search both support choosing a source; clearing the dropdown removes the link. No source is silently substituted for an empty or unknown selection. Existing authored links and legacy defaults remain intact.

An incomplete linked factor is rejected with “formula/driver linked factor: select a source” rather than generating expense against an arbitrary series. Production browser coverage creates a component, checks the empty prompt, adds another empty linked factor, and then selects a pool balance through the catalog. Existing rename and measure checks continue to pass. Three pinned fixture fingerprints are unchanged.
