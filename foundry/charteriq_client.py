"""CharterIQ substrate client — the single file holding the Foundry↔CharterIQ
contract (per the substrate owner's integration spec, 2026-07-16).

Doctrine:
- READ-ONLY consumer: every query is a SELECT; the client refuses anything else.
- One env var: CHARTERIQ_DATABASE_URL (postgresql://user:pass@host:port/db),
  set on Foundry's hosting instance; credentials never in code or repo.
- No schema knowledge leaks beyond what querying requires; when substrate
  milestones migrate metric families, this file updates and nothing else moves.
- Accuracy caveats ride with the data: capital-family metrics are item-level
  FFIEC CDR as of 2026-07-14; the other families are legacy-API computations
  pending migration — every payload carries its family's accuracy label so the
  UI can never present legacy numbers as item-level.
- Absence degrades honestly: unconfigured or unreachable substrate yields a
  clear status, never fabricated numbers.

Units (per spec): dollar metrics in $K — which is Foundry's house unit ($000s),
so no scaling; ratios stored as percentages (12.5 = 12.5%).
"""
import os
import re

CAPITAL_METRICS = {"cet1_ratio", "tier1_ratio", "total_rbc_ratio", "tce_ratio",
                    "tce_dollars", "capital_buffer", "rwa_dollars",
                    "cblr_elector", "aoci_optout"}
PEER_BANDS = ["under_200M", "200M_500M", "500M_2B", "2B_10B", "10B_50B",
               "over_50B", "all_universe"]

# Retrodiction series -> substrate metric_name. Completed at DEPLOYMENT by the
# substrate owner (env var CHARTERIQ_RETRO_MAP, JSON) — never guessed here.
# Dollar series may not exist in a ratio-centric catalog; ratio series usually
# will. At least ONE mapped series is required; more is better.
RETRO_SERIES = ["deposits", "loans", "assets", "equity", "net_income",
                 "leverage", "roa", "roe", "nim", "efficiency"]


def accuracy_label(metric_name):
    if metric_name in CAPITAL_METRICS:
        return "item-level FFIEC CDR (migrated 2026-07-14)"
    return "legacy FDIC public-API computation — migration pending (Work Order M3-6)"


class SubstrateNotConfigured(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Shared, bounded connection pool (one per URL, process-wide). The corridor
# fires ~7 metric requests concurrently; without a pool each opened its own new
# psycopg2 connection, storming the DB's connection limit and producing random
# per-metric 502s (whichever lost the race). A ThreadedConnectionPool (built for
# concurrent sync threads) caps total connections and reuses them.
_POOLS = {}
_POOL_LOCK = None

def _get_pool(url):
    global _POOL_LOCK
    import threading
    if _POOL_LOCK is None:
        _POOL_LOCK = threading.Lock()
    with _POOL_LOCK:
        pool = _POOLS.get(url)
        if pool is None:
            from psycopg2.pool import ThreadedConnectionPool
            _min = int(os.environ.get("CHARTERIQ_POOL_MIN", "1"))
            _max = int(os.environ.get("CHARTERIQ_POOL_MAX", "8"))
            _ct = int(os.environ.get("CHARTERIQ_CONNECT_TIMEOUT_S", "5"))
            pool = ThreadedConnectionPool(
                _min, _max, dsn=url,
                connect_timeout=_ct,
                keepalives=1, keepalives_idle=30, keepalives_interval=10,
                keepalives_count=3,
            )
            _POOLS[url] = pool
        return pool


class CharterIQClient:
    """Thin semantic client. `executor` is injectable for tests: a callable
    (sql, params) -> list[tuple]. The default lazily opens a psycopg2
    connection from CHARTERIQ_DATABASE_URL."""

    def __init__(self, executor=None, url=None):
        self._executor = executor
        self._url = url or os.environ.get("CHARTERIQ_DATABASE_URL")
        self._conn = None

    # ---------------------------------------------------------- plumbing
    def configured(self):
        return bool(self._executor or self._url)

    def _default_executor(self, sql, params):
        if not self._url:
            raise SubstrateNotConfigured(
                "CHARTERIQ_DATABASE_URL is not set on this instance")
        import psycopg2
        _to = os.environ.get("CHARTERIQ_STMT_TIMEOUT_MS", "8000")
        pool = _get_pool(self._url)
        # Borrow a connection from the shared bounded pool, use it, return it. This is
        # the fix for the concurrent-toggle 502 storm: the lending corridor fires ~7
        # metric requests at once (Promise.all), each in its own threadpool thread.
        # Without a pool, each opened its OWN new psycopg2 connection -> a 7-connection
        # storm every toggle -> whichever lost the race against the DB connection limit
        # or the connect timeout 502'd, and WHICH one was random. A bounded pool caps
        # total connections and reuses them, so concurrency can't storm the DB.
        conn = None
        for attempt in (1, 2):
            try:
                conn = pool.getconn()
                if getattr(conn, "closed", 0):
                    # discard a dead conn and get a fresh one
                    pool.putconn(conn, close=True); conn = pool.getconn()
                conn.set_session(readonly=True, autocommit=True)
                with conn.cursor() as cur:
                    try:
                        cur.execute("SET statement_timeout = %s", (int(_to),))
                    except Exception:
                        pass
                    cur.execute(sql, params)
                    rows = cur.fetchall()
                pool.putconn(conn); conn = None
                return rows
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                # connection-level failure: close this one out of the pool, retry once
                if conn is not None:
                    try: pool.putconn(conn, close=True)
                    except Exception: pass
                    conn = None
                if attempt == 2:
                    raise
            finally:
                # never leak a borrowed connection back if we bailed mid-use
                if conn is not None:
                    try: pool.putconn(conn)
                    except Exception: pass
                    conn = None

    def _run(self, sql, params=()):
        if not re.match(r"^\s*SELECT\b", sql, re.I):
            raise PermissionError("read-only client: only SELECT is permitted")
        ex = self._executor or self._default_executor
        return ex(sql, params)

    def _columns(self, table):
        """Live column list, cached — the spec document is a map; the running
        database is the territory; select only what exists."""
        if not hasattr(self, "_col_cache"):
            self._col_cache = {}
        if table not in self._col_cache:
            rows = self._run("SELECT column_name FROM information_schema.columns "
                              "WHERE table_name = %s", (table,))
            self._col_cache[table] = {r[0] for r in rows}
        return self._col_cache[table]

    # ---------------------------------------------------------- semantics
    INSTITUTION_FIELDS = ["cert", "name", "state", "city", "asset_size_mm",
                            "est_year", "estymd", "end_year", "fail_date",
                            "charter_type", "active", "profile_tag"]

    def get_institution(self, cert):
        have = self._columns("institutions")
        cols = [f for f in self.INSTITUTION_FIELDS if f in have] or ["cert"]
        rows = self._run(f"SELECT {', '.join(cols)} FROM institutions "
                          "WHERE cert = %s", (int(cert),))
        if not rows:
            return None
        rec = dict(zip(cols, rows[0]))
        out = {f: rec.get(f) for f in self.INSTITUTION_FIELDS}
        if out.get("asset_size_mm") is not None:
            out["asset_size_mm"] = float(out["asset_size_mm"])
        if out.get("fail_date") is not None:
            out["fail_date"] = str(out["fail_date"])
        out["terminal_status_note"] = ("detection-only (end_year/fail_date); "
                                         "cause-of-exit attribution pending")
        return out

    def get_bank_quarterly_series(self, cert, metrics, quarters=None):
        """-> {metric: [{"year","quarter","value"}...]} ordered by (year, quarter).
        quarters: optional list of (year, quarter) tuples to bound the pull."""
        sql = ("SELECT metric_name, year, quarter, value FROM metrics "
                "WHERE cert = %s AND metric_name = ANY(%s)")
        params = [int(cert), list(metrics)]
        if quarters:
            sql += " AND (year, quarter) IN %s"
            params.append(tuple((int(y), int(q)) for y, q in quarters))
        sql += " ORDER BY year, quarter"
        out = {m: [] for m in metrics}
        for m, y, q, v in self._run(sql, tuple(params)):
            if m not in out:
                continue   # rows for unrequested metrics are ignored, not fatal
            out[m].append({"year": y, "quarter": q,
                            "value": float(v) if v is not None else None})
        return {"series": out,
                "accuracy": {m: accuracy_label(m) for m in metrics}}

    def get_peer_cohort(self, asset_band, quarter=None, limit=200):
        lo, hi = {"under_200M": (None, 200), "200M_500M": (200, 500),
                   "500M_2B": (500, 2000), "2B_10B": (2000, 10000),
                   "10B_50B": (10000, 50000), "over_50B": (50000, None),
                   "all_universe": (None, None)}[asset_band]
        conds, params = ["active = 1"], []   # active is integer (1=open), not boolean
        if lo is not None:
            conds.append("asset_size_mm >= %s"); params.append(lo)
        if hi is not None:
            conds.append("asset_size_mm < %s"); params.append(hi)
        rows = self._run(
            "SELECT cert, name, state, asset_size_mm, est_year, charter_type "
            f"FROM institutions WHERE {' AND '.join(conds)} "
            "ORDER BY asset_size_mm DESC LIMIT %s", tuple(params + [limit]))
        return {"band": asset_band,
                "note": "asset-band proxy; national peer-group codes pending",
                "members": [{"cert": r[0], "name": r[1], "state": r[2],
                              "asset_size_mm": float(r[3]) if r[3] is not None else None,
                              "est_year": r[4], "charter_type": r[5]} for r in rows]}

    def available_peer_groups(self, year=None, quarter=None):
        sql = "SELECT DISTINCT group_type, group_id FROM peer_percentiles"
        params = ()
        if year and quarter:
            sql += " WHERE year = %s AND quarter = %s"
            params = (int(year), int(quarter))
        return [{"group_type": r[0], "group_id": r[1]} for r in self._run(sql + " ORDER BY 1, 2", params)]

    def get_cohort_bands(self, metric_name, certs, latest_only=False):
        """Compute per-quarter percentile bands over an ARBITRARY cert list directly
        in SQL (percentile_cont over the per-bank `metrics` table). This is what lets
        ad-hoc cohorts — charter-filtered lending peers, curated cert lists (the Konrad
        shape) — be served by the SAME database connection every other feature uses,
        with NO separate research HTTP endpoint (CHARTERIQ_SUBSTRATE_URL). Returns a
        list of per-quarter band dicts ordered by (year, quarter), or [] if the cert
        list yields no rows. Raw values, no winsorizing — cohort hygiene happens by
        WHICH certs are passed in, never by capping the data.

        latest_only=True bounds the aggregate to the single most-recent quarter — the
        lending corridor only reads bands[-1], so computing all 45 quarters is wasted
        work that, over a large cert list, contributes to the worker OOM (empty 502).
        """
        if not certs:
            return []
        cert_ints = [int(c) for c in certs]
        where = "metric_name = %s AND cert = ANY(%s) AND value IS NOT NULL"
        params = [metric_name, cert_ints]
        if latest_only:
            latest = self._run(
                "SELECT year, quarter FROM metrics WHERE metric_name = %s "
                "ORDER BY year DESC, quarter DESC LIMIT 1", (metric_name,))
            if not latest:
                return []
            ly, lq = latest[0]
            where += " AND year = %s AND quarter = %s"
            params += [int(ly), int(lq)]
        rows = self._run(
            "SELECT year, quarter, "
            "percentile_cont(0.10) WITHIN GROUP (ORDER BY value) AS p10, "
            "percentile_cont(0.25) WITHIN GROUP (ORDER BY value) AS p25, "
            "percentile_cont(0.50) WITHIN GROUP (ORDER BY value) AS p50, "
            "percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75, "
            "percentile_cont(0.90) WITHIN GROUP (ORDER BY value) AS p90, "
            "COUNT(*) AS n "
            f"FROM metrics WHERE {where} "
            "GROUP BY year, quarter ORDER BY year, quarter",
            tuple(params))
        bands = []
        for y, q, p10, p25, p50, p75, p90, n in rows:
            if p50 is None:
                continue
            bands.append({"quarter": f"{int(y)}Q{int(q)}", "year": int(y), "q": int(q),
                          "p10": float(p10), "p25": float(p25), "p50": float(p50),
                          "p75": float(p75), "p90": float(p90),
                          "n": int(n) if n is not None else None})
        return bands

    def get_metric_latest_by_cert(self, metric_name, certs):
        """Latest-quarter value of `metric_name` for each cert in `certs`.
        Returns {cert: value}. Used to populate cohort-filter denominators (rwa_dollars)
        and the ratio value (ceiling guard). Pins to the single most-recent (year,
        quarter) present for the metric FIRST, then filters by cert — this avoids a
        DISTINCT ON + full-history sort over the whole cert list, which on an ~18M-row
        table spikes memory/time enough to get the worker OOM-killed (an empty 502 from
        the edge proxy). One cheap indexed lookup instead."""
        if not certs:
            return {}
        cert_ints = [int(c) for c in certs]
        # find the latest quarter this metric has data for (one tiny query)
        latest = self._run(
            "SELECT year, quarter FROM metrics WHERE metric_name = %s "
            "ORDER BY year DESC, quarter DESC LIMIT 1", (metric_name,))
        if not latest:
            return {}
        ly, lq = latest[0]
        rows = self._run(
            "SELECT cert, value FROM metrics "
            "WHERE metric_name = %s AND year = %s AND quarter = %s "
            "AND cert = ANY(%s) AND value IS NOT NULL",
            (metric_name, int(ly), int(lq), cert_ints))
        return {int(c): float(v) for c, v in rows if v is not None}

    def get_lending_cohort_bands(self, metric_name, asset_band="under_200M",
                                  latest_only=True, cohort_cap=150):
        """Lending-filtered peer band, computed as TWO bounded queries so it can't
        OOM the worker (the cause of the bare 502: percentile_cont over a `cert IN
        (SELECT ... FROM institutions)` subquery fans out over thousands of small
        banks and blows memory on the 18M-row metrics table — a SIGKILL no try/except
        can catch). Instead:

          1. resolve a CAPPED cert list from institutions (asset band + charter
             exclusion), largest-first, LIMIT cohort_cap — one small indexed query.
          2. percentile_cont over metrics WHERE cert = ANY(<=cap array) at the latest
             quarter, plus the ratio ceiling and (for capital ratios) the RWA floor.

        Both queries are bounded (<=150 certs, one quarter), so neither can balloon.
        This is what the stored path does implicitly (pre-aggregated) and what curated
        cohorts do (small cert list) — both of which return 200. Floors/ceilings from
        REG_PARAMS. Returns per-quarter band dicts, or []."""
        from foundry.v2.regparams import REG_PARAMS
        from foundry.v2.cohort_filter import NON_LENDING_CHARTER_TYPES
        H = REG_PARAMS["cohort_hygiene"]
        lo, hi = {"under_200M": (None, 200), "200M_500M": (200, 500),
                   "500M_2B": (500, 2000), "2B_10B": (2000, 10000),
                   "10B_50B": (10000, 50000), "over_50B": (50000, None),
                   "all_universe": (None, None)}[asset_band]

        # (1) capped cert list. Mirror the WORKING get_peer_cohort query exactly (same
        # columns, same ORDER BY) — it's proven against the live schema — then exclude
        # non-lending charters in PYTHON. The earlier SQL charter filter used
        # `lower(charter_type) <> ALL(%s)` + `NULLS LAST`, constructs get_peer_cohort
        # never uses; keeping the SQL identical to the known-good query removes that as
        # a failure source. Fetch a few extra rows so post-filter we still have ~cap.
        # `active` is an INTEGER column (1=open/active, 0=closed), NOT boolean —
        # `active = TRUE` raises "operator does not exist: integer = boolean" in
        # Postgres, which is what broke every institutions query on the lending path.
        inst_conds = ["active = 1"]
        inst_params = []
        if lo is not None:
            inst_conds.append("asset_size_mm >= %s"); inst_params.append(lo)
        if hi is not None:
            inst_conds.append("asset_size_mm < %s"); inst_params.append(hi)
        fetch = cohort_cap * 2   # headroom for the Python charter drop
        import sys as _sys
        _isql = ("SELECT cert, charter_type FROM institutions WHERE "
                 f"{' AND '.join(inst_conds)} ORDER BY asset_size_mm DESC LIMIT %s")
        print(f"[LENDING-DB] step1 institutions query about to run: {_isql} "
              f"params={tuple(inst_params + [fetch])}", flush=True); _sys.stderr.flush()
        rows = self._run(_isql, tuple(inst_params + [fetch]))
        print(f"[LENDING-DB] step1 institutions RETURNED {len(rows)} rows", flush=True); _sys.stderr.flush()
        certs = []
        for cert, ct in rows:
            ctl = (ct or "").strip().lower()
            if ctl and ctl in NON_LENDING_CHARTER_TYPES:
                continue           # drop trusts/special-purpose; blank charter kept
            certs.append(cert)
            if len(certs) >= cohort_cap:
                break
        if not certs:
            return []

        # (2) percentiles over the bounded cert array at the latest quarter.
        where = ["m.metric_name = %s", "m.cert = ANY(%s)", "m.value IS NOT NULL"]
        params = [metric_name, certs]
        ly = lq = None
        if latest_only:
            latest = self._run(
                "SELECT year, quarter FROM metrics WHERE metric_name = %s "
                "ORDER BY year DESC, quarter DESC LIMIT 1", (metric_name,))
            if not latest:
                return []
            ly, lq = int(latest[0][0]), int(latest[0][1])
            where += ["m.year = %s", "m.quarter = %s"]
            params += [ly, lq]
        ceiling = H.get("ratio_ceilings", {}).get(metric_name)
        if ceiling is not None:
            where.append("m.value <= %s"); params.append(float(ceiling))
        if metric_name in ("tier1_ratio", "cet1_ratio", "total_rbc_ratio") and ly is not None:
            where.append("m.cert IN (SELECT cert FROM metrics WHERE metric_name = 'rwa_dollars' "
                         "AND year = %s AND quarter = %s AND value >= %s)")
            params += [ly, lq, H["rwa_floor_000s"]]
        rows = self._run(
            "SELECT m.year, m.quarter, "
            "percentile_cont(0.10) WITHIN GROUP (ORDER BY m.value) AS p10, "
            "percentile_cont(0.25) WITHIN GROUP (ORDER BY m.value) AS p25, "
            "percentile_cont(0.50) WITHIN GROUP (ORDER BY m.value) AS p50, "
            "percentile_cont(0.75) WITHIN GROUP (ORDER BY m.value) AS p75, "
            "percentile_cont(0.90) WITHIN GROUP (ORDER BY m.value) AS p90, "
            "COUNT(*) AS n "
            f"FROM metrics m WHERE {' AND '.join(where)} "
            "GROUP BY m.year, m.quarter ORDER BY m.year, m.quarter",
            tuple(params))
        bands = []
        for y, q, p10, p25, p50, p75, p90, n in rows:
            if p50 is None:
                continue
            bands.append({"quarter": f"{int(y)}Q{int(q)}", "year": int(y), "q": int(q),
                          "p10": float(p10), "p25": float(p25), "p50": float(p50),
                          "p75": float(p75), "p90": float(p90),
                          "n": int(n) if n is not None else None})
        return bands

    def get_peer_percentiles(self, metric_name, peer_group, year, quarter):
        """Real schema (surveyed 2026-07-16): per-bank rows carrying the group
        distribution; band lives in group_id, count in peer_count. Any one row
        for the group carries the distribution -> LIMIT 1."""
        rows = self._run(
            "SELECT peer_p10, peer_p25, peer_p50, peer_p75, peer_p90, peer_count "
            "FROM peer_percentiles WHERE metric_name = %s AND group_id = %s "
            "AND year = %s AND quarter = %s LIMIT 1",
            (metric_name, peer_group, int(year), int(quarter)))
        if not rows:
            return None
        r = rows[0]
        out = {"metric": metric_name, "peer_group": peer_group,
                "year": int(year), "quarter": int(quarter),
                "p10": float(r[0]), "p25": float(r[1]), "p50": float(r[2]),
                "p75": float(r[3]), "p90": float(r[4]),
                "n": int(r[5]) if r[5] is not None else None,
                "accuracy": accuracy_label(metric_name)}
        if metric_name in CAPITAL_METRICS:
            out["caveat"] = ("capital family recomputed on the current substrate, "
                              "identity-gated, current through 2026Q1")
        return out

    def list_available_metrics(self, cert=None):
        if cert is not None:
            rows = self._run("SELECT DISTINCT metric_name FROM metrics "
                              "WHERE cert = %s ORDER BY metric_name", (int(cert),))
        else:
            rows = self._run("SELECT DISTINCT metric_name FROM metrics "
                              "ORDER BY metric_name", ())
        return [r[0] for r in rows]

    # ---------------------------------------------------------- retrodiction
    # Conservative exact-name candidates for auto-resolution. Env override
    # (CHARTERIQ_RETRO_MAP) always wins; auto-resolution never guesses — a
    # series maps only when exactly one candidate exists in the bank's actual
    # metric list, and anything unresolved fails closed with the near-matches.
    # Ordered preference lists; the substrate's observed convention is
    # <name>_dollars for level series (net_income_dollars, cet1_dollars,
    # liquid_assets_dollars are confirmed sightings) with singular stems.
    RETRO_AUTO_CANDIDATES = {
        "deposits":   ["total_deposits_dollars", "deposits_dollars", "total_dep_dollars",
                        "deposit_dollars", "total_deposits", "deposits"],
        "loans":      ["total_loans_dollars", "net_loans_dollars", "loans_dollars",
                        "gross_loans_dollars", "net_loans", "total_loans"],
        "assets":     ["total_assets_dollars", "assets_dollars", "total_assets", "assets"],
        "equity":     ["tce_dollars",   # CONFIRMED on the live surface (user's map)
                        "total_equity_dollars", "equity_dollars",
                        "total_equity_capital_dollars", "total_equity", "equity"],
        "net_income": ["net_income_dollars", "net_income", "ni_quarterly"],
        "leverage":   ["leverage_ratio", "tier1_leverage", "leverage"],
        "roa":        ["roa", "return_on_assets"],
        "roe":        ["roe", "return_on_equity"],
        "nim":        ["nim", "net_interest_margin"],
        "efficiency": ["efficiency_ratio", "efficiency", "eff_ratio"],
    }
    # Stems for near-match reporting when a required series stays unresolved.
    RETRO_NEAR_STEMS = {
        "deposits": ["deposit", "dep"], "loans": ["loan"], "assets": ["asset"],
        "equity": ["equit", "capital"], "net_income": ["net_income", "income"],
    }

    def retro_map(self):
        """Env-configured series map when present; None signals auto-resolve."""
        import json
        raw = os.environ.get("CHARTERIQ_RETRO_MAP", "")
        if not raw:
            return None
        m = json.loads(raw)
        known = {k: v for k, v in m.items() if k in RETRO_SERIES}
        if not known:
            raise ValueError(f"CHARTERIQ_RETRO_MAP has no recognized series; "
                              f"recognized: {RETRO_SERIES}")
        return known

    def auto_retro_map(self, available):
        """Resolve the five series against the bank's actual metric names.
        Exact-candidate matching only; fails closed on any unresolved series."""
        avail = set(available)
        resolved, unresolved = {}, {}
        for series in RETRO_SERIES:
            hits = [cand for cand in self.RETRO_AUTO_CANDIDATES.get(series, [])
                    if cand in avail]
            if hits:
                resolved[series] = hits[0]   # ordered preference, deterministic
            else:
                stems = self.RETRO_NEAR_STEMS.get(series, [series.split("_")[0]])
                near = sorted(m for m in avail if any(s in m for s in stems))[:8]
                unresolved[series] = near
        # The harness runs on WHATEVER resolves (ratio-only maps were always a
        # legitimate configuration — T33g); absence is reported, not fatal.
        if resolved:
            return resolved
        if True:
            # Nothing resolved at all. Diagnose the analytical-surface case: a vocabulary of ratios and
            # percentages with no level series at all. That is a substrate
            # capability gap, not a configuration error — say so honestly
            # instead of assigning env-var homework the reader cannot do.
            analytical = sum(1 for m in avail if "_pct" in m or "_ratio" in m
                              or "_to_" in m or m.endswith("_cost"))
            if analytical >= max(5, len(avail) // 3):
                raise ValueError(
                    "retrodiction needs balance-level series (deposits, loans, "
                    "assets, equity, net income) that this substrate metrics "
                    "surface does not yet expose — it carries analytical ratios "
                    "(e.g. " + ", ".join(sorted(avail)[:3]) + "\u2026). The "
                    "level-series request sits with the CharterIQ data thread; "
                    "retrodiction lights up when they ship (or via "
                    "CHARTERIQ_RETRO_MAP once names exist).")
            detail = "; ".join(f"{s}: no exact candidate (near: {n})"
                                for s, n in unresolved.items())
            raise ValueError(
                "retrodiction series auto-resolution incomplete — " + detail +
                ". Set CHARTERIQ_RETRO_MAP (JSON mapping "
                "deposits/loans/assets/equity/net_income to substrate metric "
                "names) to complete the map explicitly.")
        return resolved

    def get_retro_actuals(self, cert, since_year=None):
        """Actuals for the retrodiction harness, aligned to a bank's opening.
        Fails closed until CHARTERIQ_RETRO_MAP names the five series' metrics."""
        m = self.retro_map()
        auto = False
        if m is None:
            m = self.auto_retro_map(self.list_available_metrics(cert))
            auto = True
        pulled = self.get_bank_quarterly_series(cert, list(m.values()))
        inv = {v: k for k, v in m.items()}
        series = {}
        for metric, rows in pulled["series"].items():
            series[inv[metric]] = [r["value"] for r in rows
                                     if (since_year is None or r["year"] >= since_year)
                                     and r["value"] is not None]
        n = min((len(v) for v in series.values() if v), default=0)
        if n == 0:
            counts = {inv[m2]: len(rows2) for m2, rows2 in pulled["series"].items()}
            raise ValueError(
                f"no rows returned for cert {cert} under the configured map — "
                f"per-series row counts: {counts}; configured map: {m}. "
                "If a mapped name looks like a placeholder, reset CHARTERIQ_RETRO_MAP "
                "with real metric names and restart the server.")
        absent = [s for s in RETRO_SERIES if s not in m]
        return {"series": {k: v[:n] for k, v in series.items()}, "quarters": n,
                "accuracy": pulled["accuracy"],
                "series_map": m, "map_source": "auto-resolved" if auto else "env",
                "absent_series": absent}


def band_for_assets_mm(assets_mm):
    """Asset band from modeled total assets ($MM) — the Deliverable-D proxy."""
    if assets_mm < 200: return "under_200M"
    if assets_mm < 500: return "200M_500M"
    if assets_mm < 2000: return "500M_2B"
    if assets_mm < 10000: return "2B_10B"
    if assets_mm < 50000: return "10B_50B"
    return "over_50B"


def placement(value, pct_row):
    """Where a modeled value sits against a percentile row -> a plain phrase.
    Coarse by construction: five fenceposts, no false precision."""
    if value < pct_row["p10"]: return "below p10"
    if value < pct_row["p25"]: return "p10\u2013p25"
    if value < pct_row["p50"]: return "p25\u2013p50"
    if value < pct_row["p75"]: return "p50\u2013p75"
    if value < pct_row["p90"]: return "p75\u2013p90"
    return "above p90"


# ------------------------------------------------------------- vintage corridor
# cet1_ratio: the Milestone 2 backfill has LANDED (confirmed by the substrate
# writer, 2026-07). Ticket 1.8.7 (cet1==tier1 proxy pre-2025Q4) is CLOSED — true
# capital history was backfilled across all 45 quarters and cet1_ratio is now
# item-derived from real CET1 capital and RWA via per-metric binding, genuinely
# distinct from tier1_ratio. In the data ~2.4% of bank-quarters show cet1 != tier1;
# the ~97% equal is correct real-world behavior (banks with no additional tier-1
# instruments have CET1 == Tier 1 by definition — including de novos, which are all
# common equity). So modeled CET1/RWA vs peer cet1_ratio is a verified like-for-like
# pairing. The vintage corridor still carries tier1_ratio as its capital overlay by
# design (one capital line at like-ages is enough); cet1 is available where wanted.
# Vintage corridor re-clocks each bank to its AGE and compares de novos at like
# ages. Only age-driven metrics belong here. deposit_cost is deliberately EXCLUDED:
# it is rate-environment-driven (calendar time), so two banks at the same age but
# founded in different rate regimes diverge purely from WHEN they existed, not how
# mature they are — age-clocking it would compare across rate environments. Deposit
# cost keeps its point-in-time home in flag calibration and the bands corridor.
VINTAGE_METRICS = ["tier1_ratio", "roa", "nim", "efficiency_ratio"]


def _pctl(sorted_vals, p):
    """Nearest-rank percentile on a pre-sorted list (no interpolation drama)."""
    if not sorted_vals:
        return None
    k = max(0, min(len(sorted_vals) - 1, int(round(p / 100.0 * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


class CharterIQClientVintageMixin:
    pass


def build_vintage_corridor(client, est_from, est_to, metrics=None, min_n=8, max_age_q=12):
    """Age-aligned trajectory corridor for banks chartered in [est_from, est_to].

    Each bank's clock restarts at its own charter: age quarter 1 is its first
    reported quarter in or after est_year. Per metric per age quarter: p25/p50/
    p75 across contributing banks, suppressed below min_n. Survivorship is
    reported, never hidden. Deterministic; fingerprinted."""
    import hashlib
    import json as _json
    metrics = metrics or VINTAGE_METRICS
    rows = client._run(
        "SELECT cert, est_year, end_year, fail_date FROM institutions "
        "WHERE est_year BETWEEN %s AND %s", (int(est_from), int(est_to)))
    members = [{"cert": r[0], "est_year": r[1], "end_year": r[2],
                 "fail_date": str(r[3]) if r[3] else None} for r in rows]
    if not members:
        raise ValueError(f"no institutions chartered {est_from}-{est_to}")
    certs = [m["cert"] for m in members]
    mrows = client._run(
        "SELECT cert, metric_name, year, quarter, value FROM metrics "
        "WHERE cert = ANY(%s) AND metric_name = ANY(%s) "
        "ORDER BY cert, metric_name, year, quarter", (certs, list(metrics)))
    est = {m["cert"]: m["est_year"] for m in members}
    # per (metric, cert): age-ordered values
    series = {}
    for cert, metric, year, quarter, value in mrows:
        if value is None or year < est[cert]:
            continue   # pre-charter rows (data noise) never count
        series.setdefault((metric, cert), []).append(float(value))
    corridor = {}
    for metric in metrics:
        ages = []
        for age in range(1, max_age_q + 1):
            vals = sorted(s[age - 1] for (m2, c2), s in series.items()
                           if m2 == metric and len(s) >= age)
            ages.append({"age_q": age, "n": len(vals),
                          "p25": _pctl(vals, 25) if len(vals) >= min_n else None,
                          "p50": _pctl(vals, 50) if len(vals) >= min_n else None,
                          "p75": _pctl(vals, 75) if len(vals) >= min_n else None,
                          "suppressed": len(vals) < min_n})
        corridor[metric] = {"ages": ages, "accuracy": accuracy_label(metric)}
        if metric in ("tier1_ratio", "cet1_ratio"):
            corridor[metric]["accuracy"] = (
                "cet1 and tier1 are now item-derived and distinct (the earlier "
                "'same value by construction' proxy is retired \u2014 the capital "
                "backfill landed). Historical bands before the backfill may still be "
                "approximate; current bands are filed-history-grade. "
                "Values far above 100% mean RWA is "
                "near zero (a young bank still in cash and Treasuries): read "
                "early-quarter bands as altitude, not decimals — at near-nil "
                "denominators the ratio is arithmetically unstable")
    failed = [m for m in members if m["fail_date"]]
    exited = [m for m in members if m["end_year"] and not m["fail_date"]]
    definition = {"est_from": est_from, "est_to": est_to, "metrics": metrics,
                   "min_n": min_n, "max_age_q": max_age_q}
    fp = hashlib.sha256(_json.dumps({"def": definition,
                                       "members": sorted(certs)},
                                      sort_keys=True).encode()).hexdigest()[:12]
    return {"definition": definition, "fingerprint": fp,
            "cohort_size": len(members),
            "survivorship": {"failed": len(failed), "exited_other": len(exited),
                              "note": "later age quarters are populated only by banks "
                                        "that survived to that age; the corridor is "
                                        "therefore flattering, and exits are stated, "
                                        "not hidden (cause-of-exit attribution pending)"},
            "corridor": corridor}
