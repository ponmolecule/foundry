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
RETRO_SERIES = ["deposits", "loans", "assets", "equity", "net_income"]


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

    # ---------------------------------------------------------- semantics
    def get_institution(self, cert):
        rows = self._run(
            "SELECT cert, name, state, city, asset_size_mm, est_year, estymd, "
            "end_year, fail_date, charter_type, active, profile_tag "
            "FROM institutions WHERE cert = %s", (int(cert),))
        if not rows:
            return None
        r = rows[0]
        return {"cert": r[0], "name": r[1], "state": r[2], "city": r[3],
                "asset_size_mm": float(r[4]) if r[4] is not None else None,
                "est_year": r[5], "estymd": r[6], "end_year": r[7],
                "fail_date": str(r[8]) if r[8] else None,
                "charter_type": r[9], "active": r[10], "profile_tag": r[11],
                "terminal_status_note": "detection-only (end_year/fail_date); "
                                          "attribution pending Deliverable A"}

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

    def get_peer_percentiles(self, metric_name, peer_group, year, quarter):
        rows = self._run(
            "SELECT peer_p10, peer_p25, peer_p50, peer_p75, peer_p90, sample_size "
            "FROM peer_percentiles WHERE metric_name = %s AND peer_group = %s "
            "AND year = %s AND quarter = %s",
            (metric_name, peer_group, int(year), int(quarter)))
        if not rows:
            return None
        r = rows[0]
        out = {"metric": metric_name, "peer_group": peer_group,
                "year": int(year), "quarter": int(quarter),
                "p10": float(r[0]), "p25": float(r[1]), "p50": float(r[2]),
                "p75": float(r[3]), "p90": float(r[4]), "n": int(r[5]),
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
    def retro_map(self):
        """The deployment-completed series map. Fails closed when absent."""
        import json
        raw = os.environ.get("CHARTERIQ_RETRO_MAP", "")
        if not raw:
            return None
        m = json.loads(raw)
        missing = [s for s in RETRO_SERIES if s not in m]
        if missing:
            raise ValueError(f"CHARTERIQ_RETRO_MAP incomplete — missing {missing}")
        return m

    def get_retro_actuals(self, cert, since_year=None):
        """Actuals for the retrodiction harness, aligned to a bank's opening.
        Fails closed until CHARTERIQ_RETRO_MAP names the five series' metrics."""
        m = self.retro_map()
        if m is None:
            avail = self.list_available_metrics(cert)
            raise ValueError(
                "retrodiction series map not configured: set CHARTERIQ_RETRO_MAP "
                "(JSON mapping deposits/loans/assets/equity/net_income to substrate "
                f"metric names). This bank's available metrics: {avail}")
        pulled = self.get_bank_quarterly_series(cert, list(m.values()))
        inv = {v: k for k, v in m.items()}
        series = {}
        for metric, rows in pulled["series"].items():
            series[inv[metric]] = [r["value"] for r in rows
                                     if (since_year is None or r["year"] >= since_year)
                                     and r["value"] is not None]
        n = min((len(v) for v in series.values() if v), default=0)
        if n == 0:
            raise ValueError(f"no overlapping quarterly history for cert {cert}")
        return {"series": {k: v[:n] for k, v in series.items()}, "quarters": n,
                "accuracy": pulled["accuracy"]}
