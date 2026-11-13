"""r501: management actions, run against a stored stress result and compared before and after.

Unmitigated stress stays as it was; actions are applied to a copy of that stressed configuration. Every
action states its timing and cost, and costs reach earnings and capital through the engine:

- capital injection: a capital raise of an amount in a period;
- contingency line: shortfalls are borrowed at the modeled borrowing rate plus a spread, a commitment fee
  (annual basis points on the full commitment) and other facility costs (annual, collateral or covenant)
  are charged as operating expense; the engine does not cap draws, so draws above the commitment are
  reported, not hidden;
- reduced growth: a supported input multiplied by a factor from a period (for example originations).
"""
from __future__ import annotations

import copy
import time
import uuid

from . import stress
from .stress_report import base_only, capital_assessment, report_window

TYPES = ("capital_injection", "contingency_line", "reduced_growth")
_PER = {12: "month", 4: "quarter", 1: "year"}


def validate(actions, cfg):
    n = int((cfg.get("assumptions") or {}).get("n_periods") or 12)
    if not actions:
        raise stress.StressError("add at least one management action")
    for i, a in enumerate(actions, 1):
        t = a.get("type")
        if t not in TYPES:
            raise stress.StressError(f"action {i}: type must be capital injection, contingency line or reduced growth")
        per = a.get("period") or a.get("available_from") or a.get("start") or 1
        if not isinstance(per, int) or per < 1 or per > n:
            raise stress.StressError(f"action {i}: the period must be between 1 and {n}")
        if t == "capital_injection" and not (isinstance(a.get("amount"), (int, float)) and a["amount"] > 0):
            raise stress.StressError(f"action {i}: enter a positive amount ($000s)")
        if t == "contingency_line":
            if not (isinstance(a.get("capacity"), (int, float)) and a["capacity"] > 0):
                raise stress.StressError(f"action {i}: enter the line's commitment ($000s)")
            for k in ("spread_bp", "commitment_fee_bp", "other_costs"):
                if not isinstance(a.get(k, 0), (int, float)) or a.get(k, 0) < 0:
                    raise stress.StressError(f"action {i}: {k.replace('_', ' ')} cannot be negative")
        if t == "reduced_growth":
            stress.resolve_target(cfg, a.get("target"))
            if not (isinstance(a.get("factor"), (int, float)) and 0 <= a["factor"] <= 1):
                raise stress.StressError(f"action {i}: the growth factor is between 0 and 1")


def apply(stress_cfg, actions):
    """Copy of the stressed configuration with the actions applied, plus what each action did."""
    c = copy.deepcopy(stress_cfg)
    a = c["assumptions"]
    n, ppy = int(a.get("n_periods") or 12), int(a.get("periods_per_year") or 4)
    notes, fee_path = [], [0.0] * n
    growth = []
    for act in actions:
        t = act["type"]
        if t == "capital_injection":
            a["capital_raises"] = list(a.get("capital_raises") or []) + [dict(amount=float(act["amount"]) * 1000.0, period=int(act["period"]))]
            notes.append(f"Capital injection of {act['amount']:,.0f} ($000s) in period {act['period']}.")
        elif t == "contingency_line":
            frm = int(act.get("available_from") or 1)
            a["funding_shortfall_policy"] = "automatic_borrowing"
            a["borrow_rate_ann"] = float(a.get("borrow_rate_ann") or 0.0) + float(act.get("spread_bp") or 0) / 10000.0
            annual = float(act.get("commitment_fee_bp") or 0) / 10000.0 * float(act["capacity"]) + float(act.get("other_costs") or 0)
            for i in range(frm - 1, n):
                fee_path[i] += annual * 1000.0 / ppy
            notes.append(f"Contingency line of {act['capacity']:,.0f} ($000s): shortfalls borrowed at the modeled rate plus "
                         f"{act.get('spread_bp', 0):g} bp; commitment fee {act.get('commitment_fee_bp', 0):g} bp a year on the full "
                         f"commitment and other costs {act.get('other_costs', 0):,.0f} ($000s a year) from period {frm}.")
        else:
            growth.append(dict(target=act["target"], op="multiply", value=float(act["factor"]), start=int(act.get("start") or 1), end=None))
            notes.append(f"Reduced growth: {act['target'].split(':')[-1]} × {act['factor']:g} from period {act.get('start') or 1}.")
    if any(fee_path):
        cat = dict(name="Management action: contingency line costs", series_id="stress-action-facility", owner_module="operating_expense",
                   linked_components=[], gross_up_eligible=False,
                   flow_spec=dict(source="entered", trajectory="explicit", values=fee_path, period=_PER.get(ppy, "quarter")))
        if a.get("nie_detail") and isinstance(a["nie_detail"].get("categories"), list):
            a["nie_detail"]["categories"] = list(a["nie_detail"]["categories"]) + [cat]
        else:   # summary operating-expense mode: the same cost through the overhead line
            raise stress.StressError("facility costs need detailed operating expenses in this engagement")
    if growth:
        modes = {}
        for g in growth:
            pr = stress.probe_target(c, g["target"])
            if not pr["ok"]:
                raise stress.StressError(f"reduced growth: this input cannot be changed yet ({pr['reason']})")
            modes[g["target"]] = pr["mode"]
        sc = dict(id="actions", kind="sensitivity", funding="inherit", severities=[dict(id="a", overrides=growth)])
        c, _ = stress.build_config(c, sc, "a", modes=modes)
    return c, dict(notes=notes, fee_path=fee_path)


def _measures(cfg, res, settings, win):
    cap = capital_assessment(dict(cfg, stress_reporting=settings), res, win)
    is_ = res["financials"]["is"]
    W = win["periods"]
    fu = res.get("funding") or {}
    auto = [float(x or 0) / 1000.0 for x in (fu.get("automatic_borrowing") or [])][-len(is_["ni"]):][:W]
    unf = [float(x or 0) / 1000.0 for x in (fu.get("unfunded_cash") or [])][-len(is_["ni"]):][:W]
    return dict(capital=cap, cum_ni=round(sum(float(x or 0) for x in is_["ni"][:W]), 3),
                borrowing_expense=round(sum(float(x or 0) for x in (is_.get("borrExp") or [])[:W]), 3),
                peak_draw=round(max(auto, default=0.0), 3), draws=auto, peak_unfunded=round(max(unf, default=0.0), 3))


def run(cfg, parent, stress_cfg, stress_res, actions, label=None) -> dict:
    """Pre (the stored stress result, unchanged) versus post (the same stress with actions)."""
    validate(actions, stress_cfg)
    settings = cfg.get("stress_reporting")
    win = report_window(dict(base_only(cfg), stress_reporting=settings))
    post_cfg, info = apply(stress_cfg, actions)
    post_res = stress._engine_run(post_cfg)
    pre, post = _measures(stress_cfg, stress_res, settings, win), _measures(post_cfg, post_res, settings, win)
    fees = round(sum(info["fee_path"][:win["periods"]]) / 1000.0, 3)
    line = next((x for x in actions if x["type"] == "contingency_line"), None)
    exceeded = None
    if line:
        exceeded = next((i + 1 for i, d in enumerate(post["draws"]) if d > float(line["capacity"]) + 1e-9), None)
        early = next((i + 1 for i, d in enumerate(post["draws"]) if d > 1e-9 and i + 1 < int(line.get("available_from") or 1)), None)
    costs = dict(facility_fees_and_other=fees, drawn_interest=round(post["borrowing_expense"] - pre["borrowing_expense"], 3))
    warn = []
    if exceeded:
        warn.append(f"Draws exceed the {line['capacity']:,.0f} commitment from period {exceeded}; the engine does not cap draws, so the excess is shown, not funded by the line.")
    if line and early:
        warn.append(f"Draws start in period {early}, before the line is available (period {line.get('available_from')}).")
    for k in ("draws",):
        pre.pop(k), post.pop(k)
    return dict(record_type="actions", run_id=uuid.uuid4().hex[:12], parent_run_id=parent.get("run_id"), status="completed",
                scenario_id=parent.get("scenario_id"), scenario_name=f"{parent.get('scenario_name')} · with actions",
                severity_id=parent.get("severity_id"), severity_label=label or parent.get("severity_label"), kind="actions",
                base_fingerprint=parent.get("base_fingerprint"), engine=stress.engine_identity(), scenario_fingerprint=parent.get("scenario_fingerprint"),
                started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), checks=dict(structural="passed", zero_shock="not applicable"),
                errors=[], actions=copy.deepcopy(actions), notes=info["notes"], warnings=warn, costs=costs,
                window=dict(periods=win["periods"], label=win["label"]), pre=pre, post=post,
                _results=dict(base_cfg=None, base_res=None, stress_cfg=post_cfg, stress_res=post_res))
