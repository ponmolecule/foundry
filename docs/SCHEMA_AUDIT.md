# CharterIQ Substrate — Schema Audit (Foundry code vs golden schema)

Golden source: `docs/CHARTERIQ_SCHEMA.txt` (read-back token CHARTERIQ_SCHEMA_V1,
generated from the live DB 2026-07-21, PostgreSQL 18.4). That file is authoritative for
table shapes and types. This note records how Foundry's code lines up with its gotchas.

## Gotcha status

1. **`active` is INTEGER 0/1, not boolean.** `WHERE active = TRUE` fails
   ("operator does not exist: integer = boolean") — this caused the lending-cohort 502.
   FIXED: all three call sites now use `active = 1` (get_lending_cohort_bands,
   get_peer_cohort, the app debug endpoint). Applies to `institutions.active` AND
   `flags.active` — any future flags query must use `= 1`, never `= TRUE`.

2. **`institutions.state` is a 2-letter USPS code** ('TX', not 'Texas'), normalised
   2026-07-21. `ffiec_por.state` is separate, varchar(4). No code currently filters on
   state text; if added, compare against 2-letter codes.

3. **`call_report_items.value_num` is USD THOUSANDS**; ratio items carry a literal '%'
   in `value_text`, keyed by `mdrm_code` + `unit`. Foundry reads `metrics`, not
   `call_report_items`, directly today — but any raw-item read must honor the unit column.

4. **`metrics.value` and `peer_percentiles` percentiles are already in the metric's
   natural unit** (ratios in %, e.g. roa 1.43 = 1.43%). Do NOT re-scale. Charge-off rates
   are ANNUALIZED — a modeled quarterly flow must be ×4 before placing against the band
   (engine_q_a.py does this: `is_["nco"] * 4 / avg_loans * 100`).

5. **Time is (year, quarter) integer columns, not a date.** Latest = MAX(year*10+quarter)
   or (year, quarter) tuple compare. '2026Q1' is a display string only, never a column.
   Foundry's latest-quarter lookups use `ORDER BY year DESC, quarter DESC` — consistent.

6. **No per-quarter total assets in `institutions`.** `asset_size_mm` is a STATIC
   present-day value. For historical size use the semantic view's total_assets_mm (item
   2170) or compute from call_report_items. The asset-band cohort filters use this static
   size — acceptable for present-day cohort membership, but NOT a historical size series.

7. **Survivor bias.** For PAST-quarter questions, do NOT filter `active = 1` — that drops
   banks that existed then and have since exited. Filter `active = 1` only for present-day
   questions.
   - Peer cohort (present-day membership): `active = 1` — CORRECT.
   - Lending cohort (present-day membership): `active = 1` — CORRECT.
   - Vintage corridor (historical, est_year cohort): NO active filter, tracks
     end_year/fail_date and reports survivorship — CORRECT.

## Metric tiers (from the catalogue)
- Current (reach 2026Q1): capital (M2), earnings (M4), concentration (M3),
  charge-off (M5, new 2026-07-21: net_charge_off_rate is DEFAULT).
- Legacy (frozen 2025Q4, pending M6a/M6b): deposit_cost, brokered_dep_pct,
  wholesale_funding_ratio, ltd_ratio, npl_ratio, texas_ratio, etc. A metric's latest
  period tells the tier: MAX(year*10+quarter)=20261 current, 20254 legacy.
- CBLR electors lack cet1/tier1/total_rbc/rwa (lawful) — use leverage_ratio for
  all-bank capital questions. (This is why the RWA floor honestly excludes them.)
