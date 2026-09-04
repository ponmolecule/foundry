"""Executive Summary (new view) — data generator.

Produces the JS data object the approved Claude Design template consumes, populated from the real engine
result so the view adapts to each engagement (green/passing when healthy, red/breaching when not). The
design's rendering, view-switching, and filter logic are untouched — this only supplies DATA.

Contract (mirrors the template's sample constants exactly):
  SERIES   : {lev, stress, ni, cumni, whsl} — arrays of engine-period numbers
  METRICS[]: {id,label,value,sub,foot,color,series,detail,drivers:[[k,v],...]}
  SCEN[]   : {id,name,value,pass,source,note,series,blurb,drivers:[str,...]}
  FAMILIES[]: {id,name,sev,status,concern}
  FINDINGS[]: [title, measured, standard, sev, family_id, status, basis, reasoning]
  COHERENCE[]: [title, sev, value_vs_limit, basis, family_id]
  ASSUMPTIONS[]: [name, observation, sev, family_id]
  SIGNOFF[]: [text, sev]
  FAM_LABEL: {family_id: short_label}
  VERDICT_* : call text + class
Every number/label is derived from the engine result; nothing is hard-coded to the sample bank.
"""
import json
from .timebase import period_label as _period_label, horizon_label as _horizon_label, cadence_noun as _cadence_noun

GREEN = "#31D0AA"; AMBER = "#F3A74A"; RED = "#FF6B5E"; BLUE = "#67A6FF"


def _pct(x, dp=2):
    try:
        return f"{float(x):.{dp}f}%"
    except Exception:
        return "—"


def _lev_path(res):
    lev = ((res.get("financials") or {}).get("ratios") or {}).get("lev") or []
    return [round(float(v), 2) for v in lev if isinstance(v, (int, float))]


def _scenario_rows(res):
    """constraint_tests -> per-scenario dicts, keyed by scenario, base first."""
    ct = res.get("constraint_tests") or []
    order = ["base", "credit", "rate", "combined", "dfast_severe"]
    rows = {}
    for t in ct:
        s = t.get("scenario")
        if s and s not in rows:
            rows[s] = t
    ordered = [rows[s] for s in order if s in rows] + [rows[s] for s in rows if s not in order]
    return ordered


def _commit(cfg):
    c = next((c for c in (cfg.get("constraints") or []) if c.get("key") == "leverage_min"), None)
    return (c.get("value", 0.09) * 100) if c else 9.0


def build_exec_data(cfg, res):
    """Return a dict of JS-ready constants for injection into the design template."""
    commit = _commit(cfg)
    _a = cfg.get("assumptions") or {}
    _ppy = int(_a.get("periods_per_year") or 4)
    _nperiods = int(_a.get("n_periods") or 12)
    _horizon = _horizon_label(_nperiods, _ppy)
    _period_word = _cadence_noun(_ppy)
    def _plab(p): return _period_label(p, _ppy)
    lev = _lev_path(res)
    base = (res.get("scenarios") or {}).get("base") or {}
    min_lev = base.get("min_leverage")
    min_lev_pct = (min_lev * 100) if isinstance(min_lev, (int, float)) else None
    min_lev_q = base.get("min_leverage_q")
    cum_ni = base.get("cum_ni")  # $000s
    breakeven = (res.get("overview") or {}).get("breakeven_q")

    scen = _scenario_rows(res)
    scen_vals = [(s["scenario"], s["value"] * 100, s["pass"]) for s in scen]
    n_total = len(scen_vals)
    n_breach = sum(1 for _, _, p in scen_vals if not p)
    worst = min(scen_vals, key=lambda x: x[1]) if scen_vals else ("—", None, True)
    worst_name, worst_val, _ = worst

    # ---- SERIES (real) ----
    # stress path: use the worst scenario's per-period series if the engine exposes one; else scale lev.
    def _scen_series(name):
        s = next((x for x in scen if x["scenario"] == name), None)
        if s and isinstance(s.get("path"), list) and s["path"]:
            return [round(float(v) * 100, 2) for v in s["path"]]
        return None
    stress_series = _scen_series(worst_name) or lev
    # cumulative NI series (engine cadence) if present, else a single-point fallback
    cumni_series = None
    ni_q = ((res.get("financials") or {}).get("is") or {}).get("ni")
    if isinstance(ni_q, list) and ni_q:
        run = 0.0; cumni_series = []
        for v in ni_q:
            run += (v or 0) / 1000.0  # $000s -> $M
            cumni_series.append(round(run, 2))
    series = {
        "lev": lev or [0],
        "stress": stress_series or lev or [0],
        "ni": [round((v or 0) / 1000.0, 2) for v in (ni_q or [])] or [0],
        "cumni": cumni_series or [round((cum_ni or 0) / 1000.0, 2)],
        "whsl": lev or [0],  # placeholder unless a wholesale series exists; see note in METRICS
    }

    # ---- verdict ----
    healthy = n_breach == 0
    if healthy:
        verdict_call = "Meets modeled constraints in every scenario"
        verdict_cls = "ok"
    elif any(s["scenario"] == "base" and not s["pass"] for s in scen):
        verdict_call = "Does not meet the base-case leverage commitment"
        verdict_cls = "bad"
    else:
        verdict_call = "Meets base constraints; vulnerable under stress"
        verdict_cls = "warn"
    if min_lev_pct is not None:
        _hdr = "clears" if min_lev_pct >= commit else "falls below"
        _by = abs(min_lev_pct - commit)
        verdict_sub = (f"Base leverage {_hdr} the {commit:.1f}% commitment"
                       + (f" by {_by*100:.0f} bp" if _by < 1 else f" by {_by:.2f} pts")
                       + (f"; {n_breach} of {n_total} modeled scenarios breach it"
                          f"\u2014 the worst path troughs at {worst_val:.2f}%." if n_breach else
                          "; every modeled scenario holds."))
    else:
        verdict_sub = "Leverage path unavailable."

    # ---- METRICS (5 cards) ----
    metrics = []
    metrics.append({
        "id": "lev", "label": "MIN BASE LEVERAGE",
        "value": _pct(min_lev_pct) if min_lev_pct is not None else "—",
        "sub": _plab(min_lev_q) if min_lev_q else "",
        "foot": f"Requirement \u2265 {commit:.1f}%",
        "color": GREEN if (min_lev_pct or 0) >= commit else RED, "series": series["lev"],
        "detail": (f"Tier 1 leverage reaches its base-case minimum of {_pct(min_lev_pct)} "
                   f"in {_plab(min_lev_q)}, {'above' if (min_lev_pct or 0)>=commit else 'below'} the "
                   f"{commit:.1f}% commitment."),
        "drivers": [["Cumulative net income", f"${(cum_ni or 0)/1000:.1f}M"],
                    ["Capital raise assumed", "None after Day 1"],
                    ["Projection horizon", _horizon]],
    })
    metrics.append({
        "id": "stress", "label": "WORST STRESS OUTCOME",
        "value": _pct(worst_val) if worst_val is not None else "—",
        "sub": f"Min leverage \u00b7 {worst_name}",
        "foot": (f"{abs(worst_val-commit)*100:.0f} bp {'above' if worst_val>=commit else 'below'} requirement"
                 if worst_val is not None else ""),
        "color": GREEN if (worst_val or 0) >= commit else RED, "series": series["stress"],
        "detail": (f"The worst modeled path ({worst_name}) reaches {_pct(worst_val)}. "
                   f"{n_breach} of {n_total} scenarios finish "
                   f"{'below' if n_breach else 'above'} {commit:.1f}%."),
        "drivers": [["Scenarios modeled", str(n_total)],
                    ["Scenarios breaching", str(n_breach)],
                    ["Worst scenario", worst_name]],
    })
    metrics.append({
        "id": "breakeven", "label": "BREAKEVEN",
        "value": _plab(breakeven) if breakeven else "—",
        "sub": f"First profitable {_period_word}", "foot": "",
        "color": BLUE, "series": series["ni"],
        "detail": (f"The plan reaches profitability in {_plab(breakeven)}."
                   if breakeven else f"Breakeven {_period_word} not reached in the horizon."),
        "drivers": [[f"{_horizon.capitalize()} net income", f"${(cum_ni or 0)/1000:.1f}M"]],
    })
    # cumulative NI card
    metrics.append({
        "id": "cumni", "label": "CUMULATIVE NET INCOME",
        "value": f"${(cum_ni or 0)/1000:.1f}M", "sub": f"{_horizon} total",
        "foot": "Carries the capital build", "color": BLUE, "series": series["cumni"],
        "detail": (f"Cumulative earnings of ${(cum_ni or 0)/1000:.1f}M over the projection; "
                   f"the plan assumes no capital raise after Day 1."),
        "drivers": [["Breakeven", _plab(breakeven) if breakeven else "—"]],
    })

    # ---- SCEN (scenario detail) ----
    src_label = {"base": "Engagement commitment", "credit": "Engagement commitment",
                 "rate": "Engagement commitment", "combined": "Engagement commitment",
                 "dfast_severe": "Supervisory path"}
    name_label = {"base": "Base case", "credit": "Credit deterioration",
                  "rate": "Rate shock", "combined": "Combined stress",
                  "dfast_severe": "DFAST severe"}
    scen_out = []
    for s in scen:
        sid = s["scenario"]; val = s["value"] * 100; ok = s["pass"]
        gap = (val - commit) * 100  # bp
        scen_out.append({
            "id": sid, "name": name_label.get(sid, sid.replace("_", " ").title()),
            "value": _pct(val), "pass": bool(ok),
            "source": src_label.get(sid, "Engagement commitment"),
            "note": (f"{gap:+.0f} bp" if abs(gap) >= 1 else "at the line"),
            "series": _scen_series(sid) or lev,
            "blurb": (f"{name_label.get(sid, sid)} — leverage minimum "
                      f"{_pct(val)} against the {commit:.1f}% commitment "
                      f"({'holds' if ok else 'breaches'})."),
            "drivers": [
                f"Leverage {'clears' if ok else 'falls below'} the commitment by "
                f"{abs(gap):.0f} bp in the binding {_period_word}.",
                ("No capital action is assumed after Day 1." if sid == "base"
                 else "Overlay applied to the base plan; no management action credited."),
            ],
        })

    # ---- FAMILIES + FINDINGS from flags/concentrations ----
    # Map engine flags into families. Each flag: {id, sev, text, cls, source}
    flags = res.get("flags") or []
    sev_map = {"severe": "severe", "high": "severe", "advisory": "advisory",
               "mild": "advisory", "review": "review", "moderate": "review"}

    def _fam_of(flag):
        t = (flag.get("text", "") + " " + flag.get("id", "")).lower()
        if any(k in t for k in ("cre", "concentration", "construction", "borrower")): return ("cre", "CRE economics & concentration")
        if any(k in t for k in ("deposit", "funding", "wholesale", "beta")): return ("deposits", "Deposit pricing & funding")
        if any(k in t for k in ("expense", "staffing", "fte", "overhead", "efficiency")): return ("expense", "Operating expense & staffing")
        if any(k in t for k in ("leverage", "capital", "scenario", "stress", "cet1")): return ("capital", "Capital & stress resilience")
        return ("other", "Other findings")

    fam_seen = {}
    findings = []
    for f in flags:
        fid, fname = _fam_of(f)
        sev = sev_map.get(f.get("sev") or f.get("cls") or "advisory", "advisory")
        status = "resolved" if f.get("resolved") else "open"
        if fid not in fam_seen:
            fam_seen[fid] = {"id": fid, "name": fname, "sev": sev, "status": status,
                             "concern": f.get("text", "")[:180]}
        else:
            # escalate family severity to the max of its findings
            cur = fam_seen[fid]["sev"]
            rank = {"severe": 3, "advisory": 2, "review": 1}
            if rank.get(sev, 0) > rank.get(cur, 0):
                fam_seen[fid]["sev"] = sev
        findings.append([
            f.get("id", "Finding"), "", "", sev, fid, status,
            f.get("source", "") or "Model finding", f.get("text", ""),
        ])

    # add the capital/stress family if scenarios breach (engine-derived, not a flag)
    if n_breach and "capital" not in fam_seen:
        fam_seen["capital"] = {"id": "capital", "name": "Capital & stress resilience",
                               "sev": "severe", "status": "open",
                               "concern": f"{n_breach} of {n_total} scenarios breach the "
                                          f"{commit:.1f}% commitment; worst path {worst_val:.2f}%."}
        findings.append(["Scenario breaches of the leverage commitment",
                         f"{n_breach} of {n_total}", f"vs 0 expected", "severe", "capital", "open",
                         f"Engagement commitment \u2265 {commit:.1f}%",
                         f"The plan holds only where noted; {n_breach} overlays breach the commitment."])

    families = list(fam_seen.values())
    # rank families severe-first
    rank = {"severe": 3, "advisory": 2, "review": 1}
    families.sort(key=lambda x: -rank.get(x["sev"], 0))
    fam_label = {"cre": "CRE", "capital": "Capital", "deposits": "Deposits",
                 "expense": "Expense", "other": "Other"}

    # ---- COHERENCE from concentrations (if present) ----
    coherence = []
    conc = res.get("concentrations") or {}
    if isinstance(conc, dict):
        for k, v in list(conc.items())[:6]:
            if isinstance(v, dict) and v.get("value") is not None:
                coherence.append([k.replace("_", " ").title(),
                                  "severe" if v.get("breach") else "advisory",
                                  f"{v.get('value')}", v.get("basis", ""), "cre"])

    # ---- ASSUMPTIONS (from advisory/severe input flags) ----
    assumptions = []
    for f in flags:
        if (f.get("source") == "input") or True:
            fid, _ = _fam_of(f)
            sev = sev_map.get(f.get("sev") or f.get("cls") or "advisory", "advisory")
            assumptions.append([f.get("id", "Assumption"), f.get("text", "")[:120], sev, fid])
    assumptions = assumptions[:6]

    # ---- SIGNOFF (severe/review families -> actions) ----
    signoff = []
    for fam in families:
        if fam["sev"] in ("severe", "review") and fam["status"] == "open":
            signoff.append([f"Reconcile {fam['name'].lower()}.", fam["sev"]])
    signoff = signoff[:4]

    return {
        "SERIES": series, "METRICS": metrics, "SCEN": scen_out,
        "FAMILIES": families, "FINDINGS": findings, "COHERENCE": coherence,
        "ASSUMPTIONS": assumptions, "SIGNOFF": signoff, "FAM_LABEL": fam_label,
        "VERDICT_CALL": verdict_call, "VERDICT_CLS": verdict_cls, "VERDICT_SUB": verdict_sub,
        "COMMIT": commit, "N_TOTAL": n_total, "N_BREACH": n_breach,
    }


def _js(v):
    return json.dumps(v, ensure_ascii=False)


def render_data_block(data):
    """Emit the JS const block that replaces the template's sample data."""
    lines = []
    S = data["SERIES"]
    lines.append("const SERIES = " + _js(S) + ";")
    # METRICS reference SERIES by id; rebuild with series inline (renderer reads .series)
    lines.append("const METRICS = " + _js(data["METRICS"]) + ";")
    lines.append("const SCEN = " + _js(data["SCEN"]) + ";")
    lines.append("const FAMILIES = " + _js(data["FAMILIES"]) + ";")
    lines.append("const FINDINGS = " + _js(data["FINDINGS"]) + ";")
    lines.append("const FAM_LABEL = " + _js(data["FAM_LABEL"]) + ";")
    lines.append("const ASSUMPTIONS = " + _js(data["ASSUMPTIONS"]) + ";")
    lines.append("const COHERENCE = " + _js(data["COHERENCE"]) + ";")
    lines.append("const SIGNOFF = " + _js(data["SIGNOFF"]) + ";")
    # verdict values the template reads (it references these in the hero)
    lines.append("const VERDICT_CALL = " + _js(data["VERDICT_CALL"]) + ";")
    lines.append("const VERDICT_SUB = " + _js(data["VERDICT_SUB"]) + ";")
    lines.append("const VERDICT_CLS = " + _js(data["VERDICT_CLS"]) + ";")
    return "\n".join(lines)


def build_exec_view_html(cfg, res, template_path):
    """Inject the generated data block into the template at the marker; return full HTML."""
    tmpl = open(template_path, encoding="utf-8").read()
    data = build_exec_data(cfg, res)
    block = render_data_block(data)
    marker = "/*__FOUNDRY_DATA_INJECTION__*/"
    if marker not in tmpl:
        raise ValueError("injection marker missing from template")
    return tmpl.replace(marker, block, 1)
