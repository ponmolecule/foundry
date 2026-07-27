-- Verify that Calamity's FUND-DDA deposit rate lands above the 90th percentile of the peer cohort.
--
-- This reproduces EXACTLY what peer_annotate() shows, using the real substrate schema
-- (foundry/charteriq_client.py + foundry/v2/peer_bands.py._db_bands):
--   * FUND-DDA maps to metric_name = 'deposit_cost'  (FLAG_METRIC_MAP, peer_calibration.py)
--   * a stored asset-band cohort is read from the peer_percentiles table (NOT recomputed from certs)
--   * the band is one row per (metric_name, group_id, year, quarter) with peer_p10..peer_p90 + peer_count
--   * corridor_position() returns 'above p90' when the client value >= peer_p90
--
-- Ratios are stored as percentages (7.0 = 7.0%), so the client value 6.78 compares directly.
--
-- IMPORTANT — set :group_id to Calamity's ACTUAL asset band. Calamity's modeled assets are ~$1,983MM,
-- which is the 500M_2B band, NOT under_200M. If the on-screen clause said n=1192 for under_200M, that
-- tells you the corridor resolved the under_200M cohort for this run — run BOTH and compare the
-- peer_count to the n you saw on screen to confirm which cohort actually drove the clause.

-- === 1. The band the corridor read (latest quarter), with the client value bucketed against it ======
WITH client AS (
    SELECT 6.78::numeric AS client_value          -- Calamity balance-weighted Q1 deposit rate (%)
),
band AS (
    -- DISTINCT ON collapses the per-bank duplicate rows to one distribution per quarter,
    -- exactly as _db_bands does; ORDER BY ... DESC + LIMIT 1 takes the latest quarter.
    SELECT DISTINCT ON (year, quarter)
           year, quarter,
           peer_p10, peer_p25, peer_p50, peer_p75, peer_p90, peer_count
    FROM   peer_percentiles
    WHERE  metric_name = 'deposit_cost'
      AND  group_id    = :group_id                -- e.g. 'under_200M' or '500M_2B'
    ORDER  BY year DESC, quarter DESC
    LIMIT  1
)
SELECT b.year, b.quarter,
       c.client_value,
       b.peer_p10, b.peer_p25, b.peer_p50, b.peer_p75, b.peer_p90,
       b.peer_count AS n,
       CASE
         WHEN c.client_value <  b.peer_p10 THEN 'below p10'
         WHEN c.client_value <  b.peer_p25 THEN 'p10-p25'
         WHEN c.client_value <  b.peer_p50 THEN 'p25-p50'
         WHEN c.client_value <  b.peer_p75 THEN 'p50-p75'
         WHEN c.client_value <  b.peer_p90 THEN 'p75-p90'
         ELSE 'above p90'
       END AS corridor_position,
       (c.client_value >= b.peer_p90) AS confirms_above_p90
FROM   band b CROSS JOIN client c;

-- Expected: corridor_position = 'above p90', confirms_above_p90 = true, and n matches the
-- number shown in the on-screen clause. If confirms_above_p90 is false, the on-screen clause and
-- the table disagree — that would be a real bug to chase.


-- === 2. (Optional) Ground-truth the percentile from the RAW per-bank metrics table =================
-- The peer_percentiles table is precomputed. To prove the precomputed p90 itself is right, recompute
-- it from the raw `metrics` table over the same asset-band cohort and confirm the client value's true
-- rank. This is the independent check that the stored band isn't stale or mis-grouped.
WITH latest AS (
    SELECT year, quarter
    FROM   metrics
    WHERE  metric_name = 'deposit_cost'
    ORDER  BY year DESC, quarter DESC
    LIMIT  1
),
cohort_certs AS (                                  -- asset-band membership, mirrors get_peer_cohort()
    SELECT cert
    FROM   institutions
    WHERE  active = 1                              -- 1 = open (integer, not boolean)
      AND  asset_size_mm >= :band_lo               -- e.g. 500  (NULL-safe: pass 0 for open-ended low)
      AND  asset_size_mm <  :band_hi               -- e.g. 2000 (pass a huge number for open-ended high)
),
vals AS (
    SELECT m.value
    FROM   metrics m
    JOIN   latest  l ON m.year = l.year AND m.quarter = l.quarter
    WHERE  m.metric_name = 'deposit_cost'
      AND  m.value IS NOT NULL
      AND  m.cert IN (SELECT cert FROM cohort_certs)
)
SELECT COUNT(*)                                                   AS n_raw,
       percentile_cont(0.90) WITHIN GROUP (ORDER BY value)        AS raw_p90,
       6.78                                                       AS client_value,
       -- fraction of the cohort at or below the client value = the client's empirical percentile
       ROUND(100.0 * AVG(CASE WHEN value <= 6.78 THEN 1 ELSE 0 END), 1) AS client_percentile_pct
FROM   vals;

-- Expected: client_percentile_pct >= 90 (the 6.78% rate is at or above ~90% of the cohort), and
-- raw_p90 close to the peer_percentiles peer_p90 from query 1. A large gap between raw_p90 and the
-- stored peer_p90 means the precomputed table is stale or grouped differently than the raw metrics.
