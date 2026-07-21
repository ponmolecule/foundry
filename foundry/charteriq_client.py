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
        if self._conn is None:
            import psycopg2
            self._conn = psycopg2.connect(self._url)
            self._conn.set_session(readonly=True, autocommit=True)
        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

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
                                         "attribution pending Deliverable A")
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
            out[m].append({"year": y, "quarter": q,
                            "value": float(v) if v is not None else None})
        return {"series": out,
                "accuracy": {m: accuracy_label(m) for m in metrics}}

    def get_peer_cohort(self, asset_band, quarter=None, limit=200):
        lo, hi = {"under_200M": (None, 200), "200M_500M": (200, 500),
                   "500M_2B": (500, 2000), "2B_10B": (2000, 10000),
                   "10B_50B": (10000, 50000), "over_50B": (50000, None),
                   "all_universe": (None, None)}[asset_band]
        conds, params = ["active = TRUE"], []
        if lo is not None:
            conds.append("asset_size_mm >= %s"); params.append(lo)
        if hi is not None:
            conds.append("asset_size_mm < %s"); params.append(hi)
        rows = self._run(
            "SELECT cert, name, state, asset_size_mm, est_year, charter_type "
            f"FROM institutions WHERE {' AND '.join(conds)} "
            "ORDER BY asset_size_mm DESC LIMIT %s", tuple(params + [limit]))
        return {"band": asset_band,
                "note": "asset-band proxy; UBPR peer-group codes arrive via "
                          "Deliverable D partial (ETA TBD)",
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
            out["caveat"] = ("percentiles computed on the legacy substrate; "
                              "capital-family recomputation pending Milestone 1 "
                              "propagation — treat p50 as approximate until refreshed")
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
    RETRO_AUTO_CANDIDATES = {
        "deposits":   ["total_deposits", "deposits", "total_dep"],
        "loans":      ["net_loans", "total_loans", "loans_net", "gross_loans"],
        "assets":     ["total_assets", "assets"],
        "equity":     ["total_equity", "equity", "total_equity_capital"],
        "net_income": ["net_income", "ni_quarterly", "net_income_q"],
        "leverage":   ["leverage_ratio", "tier1_leverage", "leverage"],
        "roa":        ["roa", "return_on_assets"],
        "roe":        ["roe", "return_on_equity"],
        "nim":        ["nim", "net_interest_margin"],
        "efficiency": ["efficiency_ratio", "efficiency", "eff_ratio"],
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
        required = ("deposits", "loans", "assets", "equity", "net_income")
        resolved, unresolved = {}, {}
        for series in RETRO_SERIES:
            hits = [cand for cand in self.RETRO_AUTO_CANDIDATES.get(series, [])
                    if cand in avail]
            if len(hits) == 1:
                resolved[series] = hits[0]
            elif series in required:
                near = sorted(m for m in avail if series.split("_")[0] in m)[:5]
                unresolved[series] = near
        if unresolved:
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
        return {"series": {k: v[:n] for k, v in series.items()}, "quarters": n,
                "accuracy": pulled["accuracy"],
                "series_map": m, "map_source": "auto-resolved" if auto else "env"}


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
# cet1_ratio deliberately absent: per the substrate owner's provenance brief
# (2026-07-16), pre-2025Q4 capital history carries the same proxy value under
# both cet1 and tier1 names (ticket 1.8.7) — showing both would be one proxy
# in two costumes. Corridor carries tier1 alone until the Milestone 2 backfill
# replaces proxy history with item-derived values (in place; corridor inherits
# the correction automatically).
VINTAGE_METRICS = ["tier1_ratio", "roa", "nim", "efficiency_ratio",
                    "deposit_cost"]


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
                "history through 2025Q3 is a regulatory-capital PROXY "
                "(cet1 and tier1 carry the same value by construction); "
                "item-derived from 2025Q4; proxy history is replaced in place "
                "by the Milestone 2 backfill — treat historical bands as "
                "approximate until then. Values far above 100% mean RWA is "
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
                                        "not hidden (attribution pending Deliverable A)"},
            "corridor": corridor}
