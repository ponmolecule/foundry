"""r502: liquidity stress for trust banks first: redemption books, a liquid-resources ladder, the stress-day
intraday test, the 30-day run, and the LCR as a management measure.

Liquidity stress reads a projection (the base, or a stored stress run) and never changes it. Balances come
from the projected balance sheet at the stress month; run rates, timing and haircuts are stress assumptions
with calibration records. Settings live in ``cfg["liquidity_stress"]``, outside the base, like the stress
scenarios, so they never move the base fingerprint or the configuration hash.

Units: entered amounts and the engine's financial statements are both $000s; every output is $000s.

Applicability is three separate statuses per test, never merged: does it apply to this engagement, does
Foundry calculate it, and are its inputs complete. A test with missing inputs is not calculated with an
invented value; it reports what is missing.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
import uuid

from . import stress
from .stress_report import _cap_series, _model, _pkey, base_only, period_label

KEY = "liquidity_stress"
BOOK_TYPES = {"custody_cash": "Client custody cash", "fund_settlement": "Fund share settlement",
              "stablecoin": "Stablecoin", "deposits": "Other deposits"}
SEVERITIES = ("severe", "moderate")
OPEN, CLOSE = 8 * 60, 17 * 60          # business day, minutes from midnight
HOURS = list(range(8, 17))             # nine hourly buckets, 08:00 to 17:00
STEP = 5                               # chart resolution in minutes; the test itself runs minute by minute
# LCR run-off rates under the rule, by category (12 CFR 249 subpart D, simplified to the categories used here)
LCR_RULE = {"operational": (0.25, "Operational deposits"),
            "nonoperational_nonfinancial": (0.40, "Non-operational, non-financial clients"),
            "nonoperational_financial": (1.00, "Non-operational, financial clients"),
            "retail_stable": (0.03, "Retail, stable"),
            "retail_other": (0.10, "Retail, other"),
            "other": (1.00, "Other")}
HQLA_FACTOR = {"1": 1.0, "2A": 0.85, "2B": 0.50}
INFLOW_CAP = 0.75
LCR_ASSET_THRESHOLD = 100_000_000.0    # $000s: $100B; below this the LCR rule does not apply


class LiquidityError(ValueError):
    pass


# ------------------------------------------------------------------ helpers
def _n(x, d=0.0):
    try:
        v = float(x)
        return v if v == v else d
    except (TypeError, ValueError):
        return d


def _hm(s, default=None):
    """'11:30' -> minutes from midnight."""
    if s is None or s == "":
        return default
    try:
        h, m = str(s).split(":")
        v = int(h) * 60 + int(m)
    except (ValueError, TypeError):
        raise LiquidityError(f"times are HH:MM, not {s!r}")
    if not 0 <= v <= 24 * 60:
        raise LiquidityError(f"{s} is not a time of day")
    return v


def _fmt(mins):
    return f"{int(mins) // 60:02d}:{int(mins) % 60:02d}"


def settings(cfg) -> dict:
    return copy.deepcopy((cfg or {}).get(KEY) or {})


def fingerprint(cfg) -> str:
    s = settings(cfg)
    s.pop("version", None)
    return hashlib.sha256(json.dumps(s, sort_keys=True, default=str).encode()).hexdigest()[:16]


def charter_type(cfg):
    cp = (cfg or {}).get("charter_profile") or {}
    return cp.get("charter_type") or ((cfg or {}).get("step_1") or {}).get("charter")


# ------------------------------------------------------------------ defaults (a starting point, never a calibration)
def template(cfg) -> dict:
    """A draft starting point: a custody-cash book on the deposit products the user marks, cash and securities as
    resources. Every rate is a Foundry default flagged as draft until the engagement calibrates it."""
    trust = charter_type(cfg) == "national_trust"
    draft = dict(status="draft", source="Foundry default, not calibrated")
    books = [dict(id="custody", type="custody_cash" if trust else "deposits", name="Client custody cash" if trust else "Deposits",
                  balance=dict(deposit_keys=[]), operational_share=0.5,
                  severities=dict(severe=dict(day1=0.25, days2_30=0.35), moderate=dict(day1=0.10, days2_30=0.15)),
                  hourly=[0.12, 0.18, 0.16, 0.10, 0.09, 0.08, 0.09, 0.10, 0.08],
                  lcr=dict(category="nonoperational_financial", rate=None), calibration=dict(draft))]
    resources = [dict(id="fed", name="Fed account cash", balance=dict(bs="cash", share=1.0), available="08:00", haircut=0.0, hqla="1"),
                 dict(id="sec", name="Securities, repo", balance=dict(bs="sec", share=1.0), available="11:30", haircut=0.02, hqla="1")]
    return dict(version=1, books=books, resources=resources, line=None,
                stress_day=dict(month="lowest_cash", severity="severe", run_days=30), lcr=dict(requested=trust, other_inflows=0.0))


# ------------------------------------------------------------------ validation
def validate(cfg) -> list[str]:
    """Structural errors (the run is refused). Missing calibration inputs are not errors; they are reported per test."""
    s = settings(cfg)
    errs = []
    a = (cfg or {}).get("assumptions") or {}
    keys = {_pkey(p) for p in a.get("deposit_products") or [] if isinstance(p, dict)}
    ids = set()
    for i, b in enumerate(s.get("books") or [], 1):
        nm = b.get("name") or f"book {i}"
        if b.get("type") not in BOOK_TYPES:
            errs.append(f"{nm}: choose a book type")
        if b.get("id") in ids:
            errs.append(f"{nm}: two books share the ID {b.get('id')}")
        ids.add(b.get("id"))
        errs += [f"{nm}: {e}" for e in _src_errors(b.get("balance") or {}, keys)]
        for sev, v in (b.get("severities") or {}).items():
            for k in ("day1", "days2_30"):
                x = (v or {}).get(k)
                if x is not None and not (0 <= _n(x, -1) <= 1):
                    errs.append(f"{nm}: {sev} {k.replace('_', ' to ')} must be between 0% and 100%")
            if v and v.get("day1") is not None and v.get("days2_30") is not None and _n(v["day1"]) + _n(v["days2_30"]) > 1 + 1e-9:
                errs.append(f"{nm}: {sev} run-off over 30 days cannot exceed 100% of the balance")
            if v and v.get("days31_plus") is not None:
                if not 0 <= _n(v["days31_plus"], -1) <= 1:
                    errs.append(f"{nm}: {sev} run-off after day 30 must be between 0% and 100%")
                elif _n(v.get("day1")) + _n(v.get("days2_30")) + _n(v["days31_plus"]) > 1 + 1e-9 and b.get("type") != "fund_settlement":
                    errs.append(f"{nm}: {sev} run-off over the whole run cannot exceed 100% of the balance")
        h = b.get("hourly")
        if h is not None and (len(h) != len(HOURS) or any(_n(x, -1) < 0 for x in h) or sum(_n(x) for x in h) <= 0):
            errs.append(f"{nm}: the day-1 timing needs {len(HOURS)} non-negative hourly weights, 08:00 to 17:00")
        if b.get("operational_share") is not None and not 0 <= _n(b["operational_share"], -1) <= 1:
            errs.append(f"{nm}: the operational share is between 0% and 100%")
        cat = ((b.get("lcr") or {}).get("category"))
        if cat is not None and cat not in LCR_RULE:
            errs.append(f"{nm}: unknown LCR category {cat}")
    rids = set()
    for i, r in enumerate(s.get("resources") or [], 1):
        nm = r.get("name") or f"resource {i}"
        if r.get("id") in rids:
            errs.append(f"{nm}: two resources share the ID {r.get('id')}")
        rids.add(r.get("id"))
        errs += [f"{nm}: {e}" for e in _src_errors(r.get("balance") or {}, keys)]
        try:
            _hm(r.get("available"), OPEN)
        except LiquidityError as e:
            errs.append(f"{nm}: {e}")
        if not 0 <= _n(r.get("haircut"), -1) < 1:
            errs.append(f"{nm}: the haircut is between 0% and 100%")
        if r.get("hqla") not in (None, "", "1", "2A", "2B"):
            errs.append(f"{nm}: HQLA level is 1, 2A, 2B or none")
    errs += _static_allocation_errors(s)
    ln = s.get("line")
    if ln:
        if not _n(ln.get("capacity")) > 0:
            errs.append("contingency line: enter the commitment ($000s)")
        try:
            if _hm(ln.get("available"), OPEN) >= _hm(ln.get("cutoff"), CLOSE):
                errs.append("contingency line: it must become usable before its cutoff")
        except LiquidityError as e:
            errs.append(f"contingency line: {e}")
        if ln.get("term") not in (None, "over_30", "within_30"):
            errs.append("contingency line: the term is over 30 days or within 30 days")
    sd = s.get("stress_day") or {}
    n = int(a.get("n_periods") or 12)
    m = sd.get("month", "lowest_cash")
    if m != "lowest_cash" and not (isinstance(m, int) and 1 <= m <= n):
        errs.append(f"stress day: the month is the lowest-cash month or 1 to {n}")
    if sd.get("severity", "severe") not in SEVERITIES:
        errs.append("stress day: severity is severe or moderate")
    if not 2 <= int(sd.get("run_days") or 30) <= 90:
        errs.append("stress day: the run lasts 2 to 90 days")
    return errs


def _static_allocation_errors(s):
    """The same balance cannot be counted twice: shares of one balance-sheet line sum to at most 100%, a deposit
    product belongs to at most one book, and a book drawing on total deposits cannot also name products."""
    errs, shares = [], {}
    for r in s.get("resources") or []:
        b = r.get("balance") or {}
        if "bs" in b:
            shares[b["bs"]] = shares.get(b["bs"], 0.0) + _n(b.get("share"), 1.0)
        if "entered" in b and b.get("within") not in (None, "", "cash", "sec"):
            errs.append(f"{r.get('name')}: an entered resource is either outside projected cash and securities, or part of one of them")
    lab = {"cash": "projected cash", "sec": "projected securities", "deposits": "projected deposits"}
    for line, tot in shares.items():
        if tot > 1 + 1e-9:
            errs.append(f"resources claim {tot:.0%} of {lab.get(line, line)}; the same balance cannot be counted twice")
    owner, dep_share = {}, 0.0
    for b in s.get("books") or []:
        src = b.get("balance") or {}
        for k in src.get("deposit_keys") or []:
            if k in owner:
                errs.append(f"{b.get('name')}: deposit product {k} is already in {owner[k]}; a balance belongs to one book")
            owner[k] = b.get("name")
        if src.get("bs") == "deposits":
            dep_share += _n(src.get("share"), 1.0)
    if dep_share and owner:
        errs.append("a book on total projected deposits overlaps books on individual deposit products; use one or the other")
    if dep_share > 1 + 1e-9:
        errs.append(f"books claim {dep_share:.0%} of projected deposits; the same balance cannot be counted twice")
    return errs


def _check_allocations(s, P, month):
    """At the stress month: entered resources that are part of projected cash or securities, plus the shares
    resources take of those lines, cannot exceed the line itself."""
    used = {"cash": 0.0, "sec": 0.0}
    for r in s.get("resources") or []:
        b = r.get("balance") or {}
        if b.get("bs") in used:
            used[b["bs"]] += P.bs_at(b["bs"], month) * _n(b.get("share"), 1.0)
        elif "entered" in b and b.get("within") in used:
            used[b["within"]] += _n(b["entered"])
    for line, u in used.items():
        have = P.bs_at(line, month)
        if u > have + 1e-6:
            raise LiquidityError(f"resources take {u:,.0f} of projected {'cash' if line == 'cash' else 'securities'} "
                                 f"({have:,.0f} at the stress month); the same balance cannot be counted twice")


def _src_errors(src, keys):
    if "entered" in src:
        return [] if _n(src["entered"], -1) >= 0 else ["the entered balance cannot be negative"]
    if "bs" in src:
        return [] if src["bs"] in ("cash", "sec", "deposits") else ["balance-sheet source is cash, securities or deposits"]
    if "deposit_keys" in src:
        bad = [k for k in src.get("deposit_keys") or [] if k not in keys]
        return [f"deposit product {k} is not in this engagement" for k in bad]
    return ["choose where the balance comes from"]


# ------------------------------------------------------------------ projection access
class _Proj:
    def __init__(self, cfg, res):
        self.cfg, self.res = cfg, res
        self.bs = res["financials"]["bs"]
        self.m = _model(cfg, res)
        self.n = int((cfg.get("assumptions") or {}).get("n_periods") or 12)

    def bs_at(self, line, month):     # bs carries the opening slot at index 0
        xs = self.bs.get(line) or []
        return _n(xs[month] if month < len(xs) else None)   # financial statements are in $000s

    def deposits_at(self, keys, month):
        tot, found = 0.0, set()
        for p, c in zip(self.m.dep, self.m.dep_cfg):
            k = _pkey(c) if c else None
            if k in keys:
                b = p.get("bal") or []
                tot += _n(b[month] if month < len(b) else None)
                found.add(k)
        return tot, found

    def balance(self, src, month):
        share = _n(src.get("share"), 1.0)
        if "entered" in src:
            return _n(src["entered"]), "Entered"
        if "bs" in src:
            lab = {"cash": "cash", "sec": "securities", "deposits": "deposits"}[src["bs"]]
            return self.bs_at(src["bs"], month) * share, f"Projection: {lab}" + ("" if share == 1 else f" × {share:.0%}")
        keys = list(src.get("deposit_keys") or [])
        v, found = self.deposits_at(set(keys), month)
        names = [c.get("name") for c in self.m.dep_cfg if c and _pkey(c) in found]
        return v * share, "Projection: " + (", ".join(names) if names else "no deposit products selected")

    def lowest_cash_month(self, window):
        vals = [(self.bs_at("cash", i) + self.bs_at("sec", i), i) for i in range(1, min(window, self.n) + 1)]
        return min(vals)[1]


# ------------------------------------------------------------------ applicability: three statuses, kept apart
def applicability(cfg, proj=None, month=None) -> list[dict]:
    s = settings(cfg)
    books = s.get("books") or []
    sev = (s.get("stress_day") or {}).get("severity", "severe")
    has_books, has_res = bool(books), bool(s.get("resources"))
    days = int((s.get("stress_day") or {}).get("run_days") or 30)
    rows = []

    def row(test, applies, calc, missing, note=""):
        needed = applies not in ("not applicable", "not requested")
        rows.append(dict(test=test, applies=applies, calculated=calc,
                         inputs=("complete" if not missing else "missing") if needed else "not needed",
                         missing=missing if needed else [], note=note))

    row("intraday", "applies" if has_books else "not set up", "yes",
        ([m for b in books for m in missing_inputs(b, sev, "intraday", days)]
         + ([] if has_res else ["at least one liquid resource"])) if has_books else ["a redemption book"])
    row("run_30", "applies" if has_books else "not set up", "yes",
        ([m for b in books for m in missing_inputs(b, sev, "run", days)]
         + ([] if has_res else ["at least one liquid resource"])) if has_books else ["a redemption book"])
    lcr = s.get("lcr") or {}
    big = None
    if proj is not None and month is not None:
        big = proj.bs_at("totalAssets", month) >= LCR_ASSET_THRESHOLD
    if big:
        ap, note = "rule may apply", "Total assets are $100B or more: confirm the category under the rule."
    else:
        ap, note = ("management measure" if lcr.get("requested") else "not requested"), "The LCR rule does not apply below $100B in total assets."
    row("lcr", ap, "yes" if lcr.get("requested") or big else "no",
        [m for b in books for m in lcr_missing(b, sev)]
        + ([] if has_res else ["at least one liquid resource"]) + ([] if has_books else ["a redemption book"]), note)
    coins = [b for b in books if b.get("type") == "stablecoin"]
    row("stablecoin_reserves", "applies" if coins else "not applicable", "yes" if coins else "no",
        [f"{b.get('name')}: reserve composition" for b in coins if not b.get("reserves")],
        "" if coins else "No stablecoin is issued in this engagement.")
    ln = s.get("line")
    row("contingency_line", "applies" if ln else "not set up", "yes" if ln else "no", [], "")
    return rows


# ------------------------------------------------------------------ the tests
def _book_rates(b, sev):
    v = (b.get("severities") or {}).get(sev) or {}
    return v.get("day1"), v.get("days2_30")


def missing_inputs(b, sev, test, days=30):
    """Every input a book needs for one test. A test runs only when every book has every input it needs;
    an incomplete book is never skipped while the aggregate is reported as complete."""
    v = (b.get("severities") or {}).get(sev) or {}
    nm, out = b.get("name") or "book", []
    if v.get("day1") is None:
        out.append(f"{nm}: day-1 run-off ({sev})")
    if test == "intraday" and not b.get("hourly"):
        out.append(f"{nm}: day-1 timing")
    if test == "run":
        if v.get("days2_30") is None:
            out.append(f"{nm}: days 2 to 30 run-off ({sev})")
        if days > 30 and v.get("days31_plus") is None:
            out.append(f"{nm}: run-off after day 30 ({sev}), needed for a {days}-day run")
    return out


def lcr_missing(b, sev):
    """Inputs the LCR needs from one book (r504). A run-off derived from the stress assumptions needs every
    component (day 1 and days 2 to 30); an entered LCR override replaces them. The custody split needs its
    operational share. Nothing missing is ever read as zero."""
    nm, out = b.get("name") or "book", []
    lc = b.get("lcr") or {}
    if lc.get("rate") is not None:
        if not 0 <= _n(lc["rate"], -1) <= 1:
            out.append(f"{nm}: LCR run-off override must be between 0% and 100%")
        if b.get("type") != "custody_cash":
            return out
    if b.get("type") == "custody_cash" and b.get("operational_share") is None:
        out.append(f"{nm}: operational share, for the LCR")
    if b.get("type") in ("fund_settlement", "stablecoin") and lc.get("rate") is None:
        v = (b.get("severities") or {}).get(sev) or {}
        for k, lab in (("day1", "day-1 run-off"), ("days2_30", "days 2 to 30 run-off")):
            if v.get(k) is None:
                out.append(f"{nm}: {lab} ({sev}), from which the LCR rate is derived (or enter an LCR override)")
    return out


def line_state(ln, month, month_label=None):
    """One facility-eligibility answer shared by the intraday test, the daily run and the LCR."""
    if not ln:
        return dict(configured=False, eligible=False, intraday=False, capacity=0.0, reason="No line set up.")
    cap = _n(ln.get("capacity"))
    frm = int(ln.get("available_from") or 1)
    lu, lc = _hm(ln.get("available"), OPEN), _hm(ln.get("cutoff"), CLOSE)
    if frm > month:
        return dict(configured=True, eligible=False, intraday=False, capacity=cap, available_from=frm,
                    reason=f"The line is available from period {frm}, after the stress month{f' ({month_label})' if month_label else ''}.")
    return dict(configured=True, eligible=True, intraday=lu < lc, capacity=cap, available_from=frm, usable=lu, cutoff=lc,
                reason=f"Usable from {_fmt(lu)} until the {_fmt(lc)} cutoff.")


def _weights(b):
    h = [_n(x) for x in (b.get("hourly") or [1.0] * len(HOURS))]
    t = sum(h)
    return [x / t for x in h]


def _cum_out(books_out, minute):
    """Cumulative day-1 outflow at a minute: each hour's outflow accrues evenly across the hour."""
    tot = 0.0
    for amt, w in books_out:
        for i, hr in enumerate(HOURS):
            s0 = hr * 60
            frac = min(max((minute - s0) / 60.0, 0.0), 1.0)
            tot += amt * w[i] * frac
    return tot


def intraday(books_out, steps, line=None):
    """Minute-by-minute cushion on the stress day.

    ``books_out``: [(day-1 outflow, hourly weights)]. ``steps``: [(minute usable, usable amount, name)].
    ``line``: (minute usable, cutoff minute, capacity) or None; the line can be drawn between its usable time and
    its cutoff, so it is a resource from its usable time when that is before the cutoff."""
    st = sorted(steps, key=lambda x: x[0])
    if line and line[0] < line[1]:
        st = sorted(st + [(line[0], line[2], "Contingency line")], key=lambda x: x[0])

    def res_at(t):
        return sum(a for (m, a, _) in st if m <= t)

    worst, worst_t, windows, cur = None, None, [], None
    for t in range(OPEN, CLOSE + 1):
        c = res_at(t) - _cum_out(books_out, t)
        if worst is None or c < worst - 1e-9:
            worst, worst_t = c, t
        if c < -1e-9 and cur is None:
            cur = dict(start=t, peak=c, peak_at=t)
        elif c < -1e-9:
            if c < cur["peak"]:
                cur.update(peak=c, peak_at=t)
        elif cur is not None:
            cov = next((nm for (m, a, nm) in st if m == t), None)
            cur.update(end=t, covered_by=cov)
            windows.append(cur)
            cur = None
    if cur is not None:
        cur.update(end=None, covered_by=None)
        windows.append(cur)
    chart = [dict(t=_fmt(t), out=round(_cum_out(books_out, t), 3), res=round(res_at(t), 3)) for t in range(OPEN, CLOSE + 1, STEP)]
    status = "covered" if not windows else ("short_at_close" if windows[-1]["end"] is None else "short_intraday")
    out = dict(status=status, lowest_cushion=round(worst, 3), lowest_at=_fmt(worst_t),
               windows=[dict(start=_fmt(w["start"]), end=_fmt(w["end"]) if w["end"] is not None else None, peak=round(w["peak"], 3),
                             peak_at=_fmt(w["peak_at"]), covered_by=w["covered_by"]) for w in windows],
               day1_outflow=round(sum(a for a, _ in books_out), 3), chart=chart,
               steps=[dict(at=_fmt(m), amount=round(a, 3), name=nm) for (m, a, nm) in st])
    if line:
        lu, lc, cap = line
        first = windows[0]["start"] if windows else None
        if lu >= lc:
            out["line_note"] = f"The line cannot be drawn: it is usable at {_fmt(lu)}, at or after its {_fmt(lc)} cutoff."
        elif first is not None and first < lu:
            out["line_note"] = f"The line is usable from {_fmt(lu)}, after the shortfall starts at {_fmt(first)}: too late for the first gap."
        elif windows:
            out["line_note"] = f"The line is usable from {_fmt(lu)} until the {_fmt(lc)} cutoff."
        else:
            out["line_note"] = f"No shortfall; the line (usable {_fmt(lu)} to {_fmt(lc)}) is not needed."
    return out


def run_30(book_flows, resources_total, line_cap, days):
    """Daily closing liquidity over the run.

    ``book_flows``: [(day-1 out, days 2 to 30 cumulative out, after-day-30 cumulative out or None, repay days or None)].
    The days 2 to 30 amount is spread evenly over those 29 days and stops at day 30; days after 30 use their own
    assumption, spread evenly over the rest of the run. A shorter run takes only its share of the 30-day path."""
    out = [0.0] * (days + 1)
    inflow = [0.0] * (days + 1)
    for flow in book_flows:
        d1, d30, d31, repay = flow if len(flow) == 4 else (flow[0], flow[1], None, flow[2])
        if days > 30 and d31 is None:
            raise LiquidityError("a run longer than 30 days needs a run-off assumption after day 30 for every book")
        for d in range(1, days + 1):
            amt = d1 if d == 1 else (d30 / 29.0 if d <= 30 else d31 / (days - 30))
            out[d] += amt
            if repay:
                if d + repay <= days:
                    inflow[d + repay] += amt

    def closes(extra):
        cum, xs = 0.0, []
        for d in range(1, days + 1):
            cum += out[d] - inflow[d]
            xs.append(resources_total + extra - cum)
        return xs

    no_line = closes(0.0)
    lo = min(no_line)
    res = dict(days=days, closes=[round(x, 3) for x in no_line], outflows=[round(x, 3) for x in out[1:]],
               inflows=[round(x, 3) for x in inflow[1:]], lowest_close=round(lo, 3),
               binding_day=no_line.index(lo) + 1, survives=lo >= -1e-9, line_needed=False)
    fail = next((i + 1 for i, x in enumerate(no_line) if x < -1e-9), None)
    res["survival_days"] = days if fail is None else fail - 1
    if fail is not None and line_cap:
        wl = closes(line_cap)
        lo2 = min(wl)
        res.update(line_needed=True, with_line=dict(closes=[round(x, 3) for x in wl], lowest_close=round(lo2, 3),
                                                    survives=lo2 >= -1e-9, draw=round(min(line_cap, -lo), 3)))
    return res


def lcr(rows_out, hqla_rows, inflows, extra_hqla=0.0, extra_out=0.0):
    l1 = sum(r["counts"] for r in hqla_rows if r["level"] == "1") + extra_hqla
    l2a = sum(r["counts"] for r in hqla_rows if r["level"] == "2A")
    l2b = sum(r["counts"] for r in hqla_rows if r["level"] == "2B")
    # caps: level 2B at most 15% of the stock, level 2 at most 40% (unwind adjustments not modeled)
    l2b_c = min(l2b, 15.0 / 85.0 * (l1 + l2a))
    l2_c = min(l2a + l2b_c, 2.0 / 3.0 * l1)
    hq = l1 + l2_c
    outflows = sum(r["outflow"] for r in rows_out) + extra_out
    inflow_c = min(inflows, INFLOW_CAP * outflows)
    net = outflows - inflow_c
    return dict(hqla=round(hq, 3), level1=round(l1, 3), level2_after_caps=round(l2_c, 3), caps_binding=(l2_c < l2a + l2b - 1e-9),
                outflows=round(outflows, 3), inflows=round(inflows, 3), inflows_counted=round(inflow_c, 3),
                cap_binding=inflows > INFLOW_CAP * outflows + 1e-9, net_outflows=round(net, 3),
                lcr=round(hq / net, 6) if net > 1e-9 else None)


# ------------------------------------------------------------------ the run
def run(cfg, res, projection_label="Base", window=None) -> dict:
    errs = validate(cfg)
    if errs:
        raise LiquidityError("; ".join(errs))
    s = settings(cfg)
    if not s.get("books"):
        raise LiquidityError("add a redemption book first")
    if not s.get("resources"):
        raise LiquidityError("add at least one liquid resource")
    base = base_only(cfg)
    base.pop(KEY, None)
    P = _Proj(base, res)
    sd = s.get("stress_day") or {}
    sev = sd.get("severity", "severe")
    W = window or P.n
    month = P.lowest_cash_month(W) if sd.get("month", "lowest_cash") == "lowest_cash" else int(sd["month"])
    days = int(sd.get("run_days") or 30)
    app = applicability(cfg, P, month)
    status = {r["test"]: r for r in app}

    # books
    books, b_out, flows = [], [], []
    for b in s["books"]:
        bal, src = P.balance(b.get("balance") or {}, month)
        d1, d30 = _book_rates(b, sev)
        repay = int(b["repaid_after_days"]) if b.get("type") == "fund_settlement" and b.get("repaid_after_days") else None
        row = dict(id=b.get("id"), name=b.get("name"), type=b.get("type"), balance=round(bal, 3), source=src,
                   day1_rate=d1, days2_30_rate=d30, calibration=b.get("calibration") or dict(status="none", source=""),
                   day1_outflow=None if d1 is None else round(bal * _n(d1), 3),
                   days2_30_outflow=None if d30 is None else round(bal * _n(d30), 3), repaid_after_days=repay)
        books.append(row)
        d31 = ((b.get("severities") or {}).get(sev) or {}).get("days31_plus")
        row["days31_plus_rate"] = d31
        if not missing_inputs(b, sev, "intraday", days):
            b_out.append((bal * _n(d1), _weights(b)))
        if not missing_inputs(b, sev, "run", days):
            flows.append((bal * _n(d1), bal * _n(d30), None if d31 is None else bal * _n(d31), repay))

    # resources
    ladder, steps = [], []
    for r in s["resources"]:
        amt, src = P.balance(r.get("balance") or {}, month)
        hc = _n(r.get("haircut"))
        use = amt * (1 - hc)
        at = _hm(r.get("available"), OPEN)
        ladder.append(dict(id=r.get("id"), name=r.get("name"), amount=round(amt, 3), available=_fmt(at), haircut=hc,
                           usable=round(use, 3), hqla=r.get("hqla") or None, source=src))
        steps.append((at, use, r.get("name")))
    ln = s.get("line")
    LS = line_state(ln, month, period_label(base, month))
    line_ok = LS["eligible"]
    line = (LS["usable"], LS["cutoff"], LS["capacity"]) if line_ok else None
    _check_allocations(s, P, month)

    out = dict(record_type="liquidity_result", month=month, month_label=period_label(base, month), severity=sev,
               projection=projection_label, applicability=app, books=books, ladder=ladder,
               line=None if not ln else dict(ln, usable_this_month=line_ok), line_state={k: v for k, v in LS.items() if k not in ("usable", "cutoff")},
               total_assets=round(P.bs_at("totalAssets", month), 3))
    if ln and not line_ok:
        out["line_note"] = LS["reason"]

    # intraday
    if status["intraday"]["inputs"] == "complete":
        if len(b_out) != len(books):
            raise RuntimeError("intraday: a book would be left out of a test reported as complete")
        out["intraday"] = intraday(b_out, steps, line)
    else:
        out["intraday"] = dict(status="inputs_missing", missing=status["intraday"]["missing"])

    # 30-day run: intraday timing is irrelevant here; everything usable on the day counts
    total_res = sum(x["usable"] for x in ladder)
    if status["run_30"]["inputs"] == "complete":
        if len(flows) != len(books):
            raise RuntimeError("daily run: a book would be left out of a test reported as complete")
        out["run_30"] = run_30(flows, total_res, line[2] if line else 0.0, days)
    else:
        out["run_30"] = dict(status="inputs_missing", missing=status["run_30"]["missing"])

    # LCR
    if status["lcr"]["calculated"] == "yes" and status["lcr"]["inputs"] == "complete":
        out["lcr"] = _lcr_block(s, P, month, books, ladder, ln, LS)
    else:
        out["lcr"] = dict(status="inputs_missing" if status["lcr"]["inputs"] == "missing" and status["lcr"]["calculated"] == "yes" else "not calculated",
                          applies=status["lcr"]["applies"], note=status["lcr"]["note"], missing=status["lcr"]["missing"])

    # stablecoin reserves
    coins = [b for b in s["books"] if b.get("type") == "stablecoin"]
    out["stablecoin"] = [_coin(b, next(x for x in books if x["id"] == b.get("id"))) for b in coins]
    return out


def _lcr_block(s, P, month, books, ladder, ln, LS=None):
    sev = (s.get("stress_day") or {}).get("severity", "severe")
    gaps = [m for b in s["books"] for m in lcr_missing(b, sev)]
    if gaps:   # guard: the caller only reaches here when inputs are complete
        raise RuntimeError("LCR: missing inputs would be read as zero: " + "; ".join(gaps))
    rows, inflows = [], _n((s.get("lcr") or {}).get("other_inflows"))
    for b, row in zip(s["books"], books):
        bal = row["balance"]
        cat = (b.get("lcr") or {}).get("category")
        over = (b.get("lcr") or {}).get("rate")
        if b.get("type") == "custody_cash":
            op = _n(b.get("operational_share"))
            r0 = LCR_RULE["operational"][0]
            rows.append(dict(book=b.get("name"), category="Custody cash, operational", balance=round(bal * op, 3), rate=r0,
                             outflow=round(bal * op * r0, 3), source="rule"))
            c = cat or "nonoperational_financial"
            rate, srcl = (_n(over), "engagement") if over is not None else (LCR_RULE[c][0], "rule")
            rows.append(dict(book=b.get("name"), category="Custody cash, non-operational", balance=round(bal * (1 - op), 3), rate=rate,
                             outflow=round(bal * (1 - op) * rate, 3), source=srcl))
        elif b.get("type") == "deposits":
            c = cat or "other"
            rate, srcl = (_n(over), "engagement") if over is not None else (LCR_RULE[c][0], "rule")
            rows.append(dict(book=b.get("name"), category=LCR_RULE[c][1], balance=round(bal, 3), rate=rate,
                             outflow=round(bal * rate, 3), source=srcl))
        else:   # settlement advances and stablecoin redemptions: the engagement's 30-day stress rate unless overridden
            stress30 = _n(row["day1_rate"]) + _n(row["days2_30_rate"])
            rate = _n(over) if over is not None else stress30
            rows.append(dict(book=b.get("name"), category=BOOK_TYPES[b["type"]], balance=round(bal, 3), rate=round(rate, 6),
                             outflow=round(bal * rate, 3), source="engagement"))
            if b.get("type") == "fund_settlement" and b.get("repaid_after_days") and int(b["repaid_after_days"]) < 30:
                inflows += bal * rate      # advances repaid inside the 30 days
    hq = [dict(name=x["name"], level=x["hqla"], amount=x["amount"], factor=HQLA_FACTOR[x["hqla"]],
               counts=round(x["amount"] * HQLA_FACTOR[x["hqla"]], 3)) for x in ladder if x["hqla"] in HQLA_FACTOR]
    non = [dict(name=x["name"], amount=x["amount"]) for x in ladder if x["hqla"] not in HQLA_FACTOR]
    before = lcr(rows, hq, inflows)
    blk = dict(status="calculated", outflow_rows=rows, hqla_rows=hq, not_hqla=non, before=before,
               method="Simplified management calculation. Eligibility, operational-deposit qualification, collateral and "
                      "transaction-level treatment under the rule are not validated here. A rule rate means the engagement "
                      "chose the rule's category for that balance, not that the balance has been shown to qualify.")
    if ln:
        draw = _n(ln.get("capacity"))
        pledged = min(_n(ln.get("collateral_hqla")), before["level1"])
        term = lcr(rows, hq, inflows, extra_hqla=draw - pledged)
        short = lcr(rows, hq, inflows, extra_hqla=draw - pledged, extra_out=draw)
        cap = _cap_series(P.res)
        i = month - 1

        def at(k, j):
            xs = cap[k][j]
            return _n(xs[i]) if i < len(xs) and xs[i] is not None else None
        t1, avg = at("leverage", 1), at("leverage", 2)
        cet1, rwa = at("cet1_rwa", 1), at("cet1_rwa", 2)
        lev0 = t1 / avg if t1 is not None and avg else None
        lev1 = t1 / (avg + draw) if t1 is not None and avg else None
        c0 = cet1 / rwa if cet1 is not None and rwa else None
        LS = LS or line_state(ln, month)
        blk["line_draw"] = dict(basis="feasible" if LS["eligible"] else "hypothetical", eligible=LS["eligible"], eligibility=LS["reason"],
                                draw=round(draw, 3), pledged_hqla=round(pledged, 3), term=ln.get("term") or "over_30",
                                lcr=dict(before=before["lcr"], over_30=term["lcr"], within_30=short["lcr"]),
                                leverage=dict(before=lev0, after=lev1), cet1_rwa=dict(before=c0, after=c0),
                                notes=(["Hypothetical: the line cannot be drawn at the stress month, so this is a sensitivity, not an available source."]
                                       if not LS["eligible"] else [])
                                      + ["Drawn cash is Level 1; collateral pledged to the line leaves the HQLA stock.",
                                       "A draw repayable within 30 days is also a 100% outflow.",
                                       "Leverage: the draw is held through the averaging period. Cash carries no risk weight, so CET1 / RWA does not move.",
                                       "Capital figures are a balance-sheet illustration of the draw, not a rerun: fees and drawn interest are not in them. "
                                       "Results › Management actions runs the line through earnings, tax and capital."])
    return blk


def _coin(b, row):
    out_ = row["balance"]
    rs = b.get("reserves") or []
    cover = sum(_n(r.get("amount")) * (1 - _n(r.get("haircut"))) for r in rs)
    same = sum(_n(r.get("amount")) * (1 - _n(r.get("haircut"))) for r in rs if r.get("same_day"))
    d1 = row["day1_outflow"]
    return dict(book=b.get("name"), outstanding=out_, reserves_after_haircut=round(cover, 3),
                coverage=round(cover / out_, 6) if out_ > 0 else None, same_day_reserves=round(same, 3),
                day1_redemptions=d1, same_day_covers_day1=None if d1 is None else same >= d1 - 1e-9,
                status="inputs_missing" if not rs else "calculated")


# ------------------------------------------------------------------ the record
def record(cfg, result, parent=None) -> dict:
    """A stored liquidity run: the result with its identity. It goes stale with the base, the liquidity settings,
    and (on a stress projection) the parent scenario."""
    s = settings(cfg)
    rec = dict(run_id=uuid.uuid4().hex[:12], record_type="liquidity", status="completed", kind="liquidity",
               scenario_name="Liquidity stress" + (f" on {parent.get('scenario_name')} · {parent.get('severity_label')}" if parent else " on the base"),
               severity_id=result["severity"], severity_label=result["severity"].capitalize() + f" · {result['month_label']}",
               base_fingerprint=stress.base_fingerprint(cfg), engine=stress.engine_identity(),
               liquidity_fingerprint=fingerprint(cfg), liquidity_version=s.get("version"),
               started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               checks=dict(structural="passed", zero_shock="not applicable"), errors=[], liquidity=result)
    if parent:
        rec.update(parent_run_id=parent.get("run_id"), scenario_id=parent.get("scenario_id"),
                   scenario_version=parent.get("scenario_version"), scenario_fingerprint=parent.get("scenario_fingerprint"))
    return rec
