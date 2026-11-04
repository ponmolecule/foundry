# r469 — Full-width capital workspace and immediate scheduled borrowing additions

Based on r468; reverses its Formula / level grid change.

Restores r467/Claude’s full-width Formula / level component table. Capital & pre-opening now uses the full available stage width rather than the generic 1280px card cap. Its graphite header and panel grid widen together; Scheduled borrowings and schedule-mode CAPEX share the larger column space. Existing responsive breakpoints remain in effect.

Fixes Add scheduled borrowing: the handler added saved rows but refreshed only the global inspector. It now renders the content immediately as well, matching Add a raise, so pending additions do not wait for an unrelated click.

Validation: Node handler regression checks immediate rendering, one new row per click, repeated clicks, and monthly/quarterly/annual event fields; inline scripts compile. Existing fixed-asset UI and authoring-state checks pass. Reference coverage regenerated. Browser layout remains unverified here because Chromium is unavailable.
