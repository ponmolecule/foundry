"""Executive Summary (data-driven view) — data generator.

Emits the JS `var MODEL=…; var VERDICT=…; …` block the approved data-driven Claude Design template
consumes, populated from the real engine result so the whole view (landing + detail + filter) adapts to
each engagement. The template's rendering/filter/navigation are untouched; this only supplies DATA.

Shapes mirror foundry/v2/assets/exec_view_template.html exactly (named-key objects):
  MODEL, VERDICT{pills[],readiness}, GAUGE, SERIES{lev,stress,ni,cumni,whsl},
  METRICS[]{id,label,value,sub,foot,tone,series,detail,drivers[[k,v]]},
  CONSTRAINT, SCEN[]{id,name,value,pass,source,note,series,blurb,drivers[]},
  FAMILIES[]{id,name,severity,status,concern}, FAM_LABEL,
  FINDINGS[]{title,measured,standard,severity,family,status,basis,reasoning},
  ASSUMPTIONS[]{name,observation,severity,family},
  COHERENCE[]{title,severity,value,basis,family}, SIGNOFF[]{text,severity},
  COPY (static strings), FILTER_DEFS (static).
"""
import json

TONE = {"pass": "pass", "warn": "warn", "fail": "fail", "info": "info"}
_RANK = {"severe": 3, "advisory": 2, "review": 1}


def _pct(x, dp=2):
    try:
        return f"{float(x):.{dp}f}%"
    except Exception:
        return "\u2014"


def _gap_txt(a, b):
    """Gap between two percentages: bp when under 1 pt, otherwise pts. Reads sanely at any distance."""
    g = abs(a - b)
    return f"{g*100:.0f} bp" if g < 1 else f"{g:.2f} pts"


def _lev(res):
    lev = ((res.get("financials") or {}).get("ratios") or {}).get("lev") or []
    return [round(float(v), 2) for v in lev if isinstance(v, (int, float))]


def _commit(cfg):
    c = next((c for c in (cfg.get("constraints") or []) if c.get("key") == "leverage_min"), None)
    return (c.get("value", 0.09) * 100) if c else 9.0


def _scen_rows(res):
    ct = res.get("constraint_tests") or []
    order = ["base", "credit", "rate", "combined", "dfast_severe"]
    seen = {}
    for t in ct:
        s = t.get("scenario")
        if s and s not in seen:
            seen[s] = t
    return [seen[s] for s in order if s in seen] + [seen[s] for s in seen if s not in order]


def _scen_series(res, name, lev):
    s = next((x for x in _scen_rows(res) if x["scenario"] == name), None)
    if s and isinstance(s.get("path"), list) and s["path"]:
        return [round(float(v) * 100, 2) for v in s["path"]]
    return lev


NAME = {"base": "Base case", "credit": "Credit deterioration", "rate": "Rate shock",
        "combined": "Combined stress", "dfast_severe": "DFAST severe"}
SRC = {"dfast_severe": "Supervisory path"}


def build(cfg, res):
    commit = _commit(cfg)
    lev = _lev(res) or [0.0]
    base = (res.get("scenarios") or {}).get("base") or {}
    min_lev = base.get("min_leverage")
    min_lev_pct = (min_lev * 100) if isinstance(min_lev, (int, float)) else None
    min_lev_q = base.get("min_leverage_q")
    cum_ni = base.get("cum_ni")  # $000s
    breakeven = (res.get("overview") or {}).get("breakeven_q")
    rd = (res.get("overview") or {}).get("readiness") or {}

    scen = _scen_rows(res)
    scen_vals = [(s["scenario"], s["value"] * 100, s["pass"]) for s in scen]
    n_total = len(scen_vals)
    n_breach = sum(1 for _, _, p in scen_vals if not p)
    worst = min(scen_vals, key=lambda x: x[1]) if scen_vals else ("\u2014", None, True)
    worst_name, worst_val, _ = worst
    worst_label = NAME.get(worst_name, worst_name)

    # ---- SERIES ----
    ni_q = ((res.get("financials") or {}).get("is") or {}).get("ni") or []
    ni_m = [round((v or 0) / 1000.0, 2) for v in ni_q] or [0]
    cumni_m = []
    run = 0.0
    for v in ni_q:
        run += (v or 0) / 1000.0
        cumni_m.append(round(run, 2))
    if not cumni_m:
        cumni_m = [round((cum_ni or 0) / 1000.0, 2)]
    stress_series = _scen_series(res, worst_name, lev)
    series = {"lev": lev, "stress": stress_series, "ni": ni_m, "cumni": cumni_m, "whsl": lev}

    healthy = n_breach == 0
    base_fail = any(s["scenario"] == "base" and not s["pass"] for s in scen)

    # ---- VERDICT ---- (cls MUST be the design's vocabulary: "ok" | "bad" | "warn")
    if base_fail:
        v_call = "Does not meet the base-case leverage commitment."
        v_cls = "bad"
    elif healthy:
        v_call = "Meets modeled constraints in every scenario."
        v_cls = "ok"
    else:
        v_call = "Meets base constraints; vulnerable under stress."
        v_cls = "warn"
    if min_lev_pct is not None:
        gap = min_lev_pct - commit
        gap_txt = (f"{abs(gap)*100:.0f} bp" if abs(gap) < 1 else f"{abs(gap):.2f} pts")
        clears = "clears" if gap >= 0 else "falls below"
        v_reason = (f"Base leverage {clears} the {commit:.1f}% minimum by {gap_txt}"
                    + (f", but {n_breach} of {n_total} modeled scenarios breach it "
                       f"\u2014 the worst path troughs at {worst_val:.2f}%."
                       if n_breach else "; every modeled scenario holds."))
    else:
        v_reason = "Leverage path unavailable."
    pills = []
    pills.append({"text": "PASS (BASE CASE)" if not base_fail else "BASE CASE FAIL",
                  "tone": "pass" if not base_fail else "fail"})
    if n_breach:
        pills.append({"text": f"STRESS RISK: {'HIGH' if n_breach >= 3 else 'ELEVATED'}", "tone": "warn"})
    else:
        pills.append({"text": "STRESS: CLEARS", "tone": "pass"})
    open_items = rd.get("open_items", 0)
    hard_stops = rd.get("hard_stops", 0)
    verdict = {
        "call": v_call, "cls": v_cls, "reasoning": v_reason, "label": "Overall verdict",
        "pills": pills,
        "readiness": {"status": rd.get("status", ""), "open_items": open_items, "hard_stops": hard_stops},
        "readinessLine": f"\u00b7 {open_items} open item{'s' if open_items != 1 else ''} \u00b7 {hard_stops} hard stop{'s' if hard_stops != 1 else ''}",
    }

    # ---- GAUGE ----
    # Scale must keep BOTH the requirement tick and the model tick readable, with margin so their
    # labels don't collide at the ends. Anchor near the requirement; extend to include the model value
    # plus padding, but keep the requirement off the hard-left edge.
    mv = min_lev_pct if min_lev_pct is not None else commit
    span = max(abs(mv - commit), 1.0)
    # left margin before the requirement, right margin after the model tick, so end labels never collide
    left_pad = max(1.0, span * 0.35)
    right_pad = max(1.5, span * 0.35)
    lo = min(commit, mv) - left_pad
    hi = max(commit, mv) + right_pad
    lo = float(int(lo)); hi = float(int(hi) + 1)
    gauge = {
        "title": "MIN BASE LEVERAGE THRESHOLD",
        "scaleMin": lo, "scaleMax": hi,
        "requirement": {"value": round(commit, 2), "label": "Requirement"},
        "model": {"value": round(min_lev_pct, 2) if min_lev_pct is not None else commit,
                  "label": f"Model (Q{min_lev_q}) \u00b7 "
                           + (f"{_gap_txt(min_lev_pct or 0, commit)} of headroom"
                              if (min_lev_pct or 0) >= commit
                              else f"{_gap_txt(min_lev_pct or 0, commit)} short")},
        "foot": (f"Stress paths reach as low as {worst_val:.2f}%. Scale is linear from {lo:.0f}% to {hi:.0f}%."
                 if worst_val is not None else f"Scale is linear from {lo:.0f}% to {hi:.0f}%."),
    }

    # ---- METRICS ----
    def _tone(ok): return "pass" if ok else "fail"
    metrics = [
        {"id": "lev", "label": "MIN BASE LEVERAGE",
         "value": _pct(min_lev_pct) if min_lev_pct is not None else "\u2014",
         "sub": f"Q{min_lev_q}" if min_lev_q else "", "foot": f"Requirement \u2265 {commit:.1f}%",
         "tone": _tone((min_lev_pct or 0) >= commit), "series": series["lev"],
         "detail": (f"Tier 1 leverage reaches its base-case minimum of {_pct(min_lev_pct)} in "
                    f"Q{min_lev_q}, {'above' if (min_lev_pct or 0) >= commit else 'below'} the "
                    f"{commit:.1f}% commitment."),
         "drivers": [["Cumulative net income", f"${(cum_ni or 0)/1000:.1f}M"],
                     ["Capital raise assumed", "None after Day 1"],
                     ["Projection horizon", f"{len(lev)} quarters"]]},
        {"id": "stress", "label": "WORST STRESS OUTCOME",
         "value": _pct(worst_val) if worst_val is not None else "\u2014",
         "sub": f"Min leverage \u00b7 {worst_label}",
         "foot": (_gap_txt(worst_val, commit) + (" above requirement" if worst_val >= commit else " below requirement")
                  if worst_val is not None else ""),
         "tone": _tone((worst_val or 0) >= commit), "series": series["stress"],
         "detail": (f"The worst modeled path ({worst_label}) reaches {_pct(worst_val)}. "
                    f"{n_breach} of {n_total} scenarios finish {'below' if n_breach else 'at or above'} "
                    f"{commit:.1f}%."),
         "drivers": [["Scenarios modeled", str(n_total)], ["Scenarios breaching", str(n_breach)],
                     ["Worst scenario", worst_label]]},
        {"id": "breakeven", "label": "BREAKEVEN", "value": f"Q{breakeven}" if breakeven else "\u2014",
         "sub": "First profitable quarter", "foot": "", "tone": "info", "series": series["ni"],
         "detail": (f"The plan reaches profitability in Q{breakeven}." if breakeven
                    else "Breakeven is not reached within the projection horizon."),
         "drivers": [["12-quarter net income", f"${(cum_ni or 0)/1000:.1f}M"]]},
        {"id": "cumni", "label": "CUMULATIVE NET INCOME", "value": f"${(cum_ni or 0)/1000:.1f}M",
         "sub": f"{len(lev)}-quarter total", "foot": "Carries the capital build", "tone": "info",
         "series": series["cumni"],
         "detail": (f"Cumulative earnings of ${(cum_ni or 0)/1000:.1f}M over the projection; "
                    f"the plan assumes no additional raise after Day 1."),
         "drivers": [["Breakeven", f"Q{breakeven}" if breakeven else "\u2014"]]},
    ]

    constraint = {"name": "leverage_min", "threshold": round(commit, 2), "thresholdLabel": f"{commit:.1f}%"}

    # ---- SCEN ----
    scen_out = []
    for s in scen:
        sid = s["scenario"]; val = s["value"] * 100; ok = s["pass"]
        gap = (val - commit) * 100
        scen_out.append({
            "id": sid, "name": NAME.get(sid, sid.replace("_", " ").title()),
            "value": _pct(val), "pass": bool(ok), "source": SRC.get(sid, "Engagement commitment"),
            "note": (_gap_txt(val, commit) + (" above" if gap >= 0 else " below")) if abs(gap) >= 0.01 else "at the line",
            "series": _scen_series(res, sid, lev),
            "blurb": (f"{NAME.get(sid, sid)} \u2014 leverage minimum {_pct(val)} against the "
                      f"{commit:.1f}% commitment ({'holds' if ok else 'breaches'})."),
            "drivers": [
                f"Leverage {'clears' if ok else 'falls below'} the commitment by {abs(gap):.0f} bp "
                f"in the binding quarter.",
                ("No capital action is assumed after Day 1." if sid == "base"
                 else "Overlay applied to the base plan; no management action credited."),
            ],
        })

    # ---- FAMILIES + FINDINGS from flags ----
    flags = res.get("flags") or []
    sevmap = {"severe": "severe", "high": "severe", "advisory": "advisory", "mild": "advisory",
              "review": "review", "moderate": "review"}

    def famof(f):
        t = (f.get("text", "") + " " + f.get("id", "")).lower()
        if any(k in t for k in ("cre", "concentration", "construction", "borrower")):
            return ("cre", "CRE economics & concentration")
        if any(k in t for k in ("deposit", "funding", "wholesale", "beta")):
            return ("deposits", "Deposit pricing & funding")
        if any(k in t for k in ("expense", "staffing", "fte", "overhead", "efficiency")):
            return ("expense", "Operating expense & staffing")
        if any(k in t for k in ("leverage", "capital", "scenario", "stress", "cet1")):
            return ("capital", "Capital & stress resilience")
        return ("other", "Other findings")

    fams = {}
    findings = []
    for f in flags:
        fid, fname = famof(f)
        sev = sevmap.get(f.get("sev") or f.get("cls") or "advisory", "advisory")
        status = "resolved" if f.get("resolved") else "open"
        if fid not in fams:
            fams[fid] = {"id": fid, "name": fname, "severity": sev, "status": status,
                         "concern": f.get("text", "")[:180]}
        elif _RANK.get(sev, 0) > _RANK.get(fams[fid]["severity"], 0):
            fams[fid]["severity"] = sev
        findings.append({"title": f.get("id", "Finding"), "measured": "", "standard": "",
                         "severity": sev, "family": fid, "status": status,
                         "basis": f.get("source", "") or "Model finding", "reasoning": f.get("text", "")})

    if n_breach and "capital" not in fams:
        fams["capital"] = {"id": "capital", "name": "Capital & stress resilience", "severity": "severe",
                           "status": "open",
                           "concern": f"{n_breach} of {n_total} scenarios breach the {commit:.1f}% "
                                      f"commitment; worst path {worst_val:.2f}%."}
        findings.append({"title": "Scenario breaches of the leverage commitment",
                         "measured": f"{n_breach} of {n_total}", "standard": "vs 0 expected",
                         "severity": "severe", "family": "capital", "status": "open",
                         "basis": f"Engagement commitment \u2265 {commit:.1f}%",
                         "reasoning": f"{n_breach} modeled overlays breach the leverage commitment."})

    families = sorted(fams.values(), key=lambda x: -_RANK.get(x["severity"], 0))
    fam_label = {"cre": "CRE", "capital": "Capital", "deposits": "Deposits",
                 "expense": "Expense", "other": "Other"}

    # ---- COHERENCE (modeled 'does the bank hold together') ----
    # Real source, matching Classic: flags emitted from modeled outputs + modeled_challenges.
    # NOT raw input flags — these are findings about what the assumptions PRODUCE.
    coherence = []
    modeled_flags = [f for f in flags if f.get("source") == "modeled"]
    modeled_chal = res.get("modeled_challenges") or []
    for f in modeled_flags:
        sev = sevmap.get(f.get("sev") or f.get("cls") or "advisory", "advisory")
        coherence.append({"title": f.get("id", "Finding"),
                          "severity": "severe" if sev == "severe" else "advisory",
                          "value": (f.get("text", "")[:90]),
                          "basis": f.get("basis", "") or "Modeled output",
                          "family": famof(f)[0]})
    for m in modeled_chal:
        if not isinstance(m, dict):
            continue
        sev = sevmap.get(m.get("sev") or m.get("cls") or "advisory", "advisory")
        coherence.append({"title": m.get("id") or m.get("title") or "Modeled challenge",
                          "severity": "severe" if sev == "severe" else "advisory",
                          "value": (m.get("text", "") or m.get("value", ""))[:90] if isinstance(m.get("text", ""), str) else str(m.get("value", "")),
                          "basis": m.get("basis", "") or "Modeled challenge",
                          "family": "capital"})

    # ---- ASSUMPTIONS ----
    assumptions = []
    for f in flags[:6]:
        fid, _ = famof(f)
        sev = sevmap.get(f.get("sev") or f.get("cls") or "advisory", "advisory")
        assumptions.append({"name": f.get("id", "Assumption"), "observation": f.get("text", "")[:120],
                            "severity": sev, "family": fid})

    # ---- SIGNOFF ----
    signoff = [{"text": f"Reconcile {fam['name'].lower()}.", "severity": fam["severity"]}
               for fam in families if fam["severity"] in ("severe", "review") and fam["status"] == "open"][:4]

    # ---- FINANCIALS (annual summary from quick_stats) ----
    qs = res.get("quick_stats") or {}
    fin_rows = []
    periods = []
    if qs.get("rows"):
        nyears = len((qs["rows"][0] or {}).get("y", []))
        periods = [f"Year {i+1}" for i in range(nyears)]
        for row in qs["rows"]:
            label = row.get("label", "")
            is_stock = "EOP" in label or "$000s" in label
            vals = []
            for v in row.get("y", []):
                if v is None:
                    vals.append("\u2014")
                elif isinstance(v, (int, float)):
                    vals.append(f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.2f}")
                else:
                    vals.append(str(v))
            fin_rows.append({"label": label, "values": vals,
                             "strong": is_stock and "Total Assets" in label})
    financials = {"periods": periods, "rows": fin_rows,
                  "note": (qs.get("note", "") + ". Income ratios are averaged over the year\u2019s quarters; "
                           "stock figures are year-end.") if qs.get("note") else ""}

    # ---- MODEL (run identity) ----
    cfg_name = cfg.get("scenario_name") or cfg.get("engagement_id") or ""
    proposed = cfg.get("proposed_bank")
    bank_name = (proposed.get("name") if isinstance(proposed, dict) else proposed) or "Bank model"
    model = {
        "product": bank_name, "section": "Executive Summary",
        "navTabs": [{"label": "Scenarios", "view": "scenarios"},
                    {"label": "Assumptions", "view": "assumptions"},
                    {"label": "Results", "view": "financials"},
                    {"label": "Model Checks", "view": "coherence"}],
        "version": f"Engine {res.get('engine_version', '')}",
        "generated": "", "freshness": "Up to date",
        "runLine": f"Run {str(res.get('config_hash', ''))[:10]} \u00b7 {cfg_name} \u00b7 v2-quarterly "
                   f"\u00b7 Model metrics are for internal review; not independent auditor validation.",
        "downloads": ["Executive summary (PDF)", "Excel exhibit", "Business plan tables"],
    }

    # ---- COPY + FILTER_DEFS (mostly static; counts dynamic) ----
    total_findings = len(findings)
    copy = {
        "attention": {"title": "WHAT NEEDS ATTENTION NOW", "meta": f"{len(families)} families \u00b7 all shown",
                      "link": f"View all {total_findings} findings across families \u2192"},
        "signoff": {"title": "REQUIRED BEFORE SIGN-OFF", "meta": f"{len(signoff)} open",
                    "foot": "Reconciliations between schedules that already exist in the model."},
        "assumptions": {"title": "ARE THE ASSUMPTIONS CREDIBLE?",
                        "lede": "Each input judged against real-peer bands. Click a row for the finding.",
                        "columns": ["ASSUMPTION", "OBSERVATION", "SEVERITY"]},
        "coherence": {"title": "MODEL COHERENCE \u2014 DOES THE BANK HOLD TOGETHER?",
                      "lede": "Concentration and funding checks against the modeled outputs."},
        "evidence": {"title": "THE EVIDENCE BEHIND IT",
                     "lede": f"Scenario outcomes ({n_total} scenarios) \u00b7 leverage_min vs {commit:.1f}%",
                     "action": "View full results",
                     "columns": ["SCENARIO", "MIN LEVERAGE", "LIMIT", "RESULT", "SOURCE", "NOTES"]},
        "findings": {"title": "All findings",
                     "lede": "Every finding across families. Narrow the list to read it \u2014 the summary itself is never filtered.",
                     "empty": "No findings match this combination.", "reset": "Reset",
                     "link": "See all findings across families \u2192"},
        "metricDetail": {"seriesTitle": "TWELVE-QUARTER SERIES", "axisMid": "twelve quarters",
                         "driversTitle": "ASSUMPTIONS THAT MOVE IT"},
        "scenarioDetail": {"eyebrow": "SCENARIO DETAIL", "chartTitle": "LEVERAGE PATH UNDER THIS SCENARIO",
                           "driversTitle": "WHAT DRIVES THE RESULT",
                           "statLabels": ["MIN LEVERAGE", "REQUIREMENT", "GAP", "SOURCE"]},
        "familyDetail": {"eyebrow": "ISSUE FAMILY", "findingsTitle": "FINDINGS IN THIS FAMILY"},
        "back": "\u2190 Back to summary",
    }
    filter_defs = [
        {"key": "severity", "label": "SEVERITY", "options": ["All", "Severe", "Advisory", "Review"]},
        {"key": "family", "label": "FAMILY",
         "options": ["All"] + [fam_label[f["id"]] for f in families if f["id"] in fam_label]},
        {"key": "status", "label": "STATUS", "options": ["All", "Open", "Resolved"]},
    ]

    return {
        "MODEL": model, "VERDICT": verdict, "GAUGE": gauge, "SERIES": series, "METRICS": metrics,
        "CONSTRAINT": constraint, "SCEN": scen_out, "FAMILIES": families, "FAM_LABEL": fam_label,
        "FINDINGS": findings, "ASSUMPTIONS": assumptions, "COHERENCE": coherence, "SIGNOFF": signoff,
        "COPY": copy, "FILTER_DEFS": filter_defs, "FINANCIALS": financials,
    }


def render_block(cfg, res):
    d = build(cfg, res)
    def js(name, val): return f"var {name} = " + json.dumps(val, ensure_ascii=False) + ";"
    # SERIES first so METRICS/SCEN can reference it — but we inline series arrays, so order only cosmetic.
    order = ["MODEL", "VERDICT", "GAUGE", "SERIES", "METRICS", "CONSTRAINT", "SCEN",
             "FAMILIES", "FAM_LABEL", "FINDINGS", "ASSUMPTIONS", "COHERENCE", "SIGNOFF",
             "COPY", "FILTER_DEFS", "FINANCIALS"]
    return "\n".join(js(k, d[k]) for k in order)


def build_html(cfg, res, template_path):
    tmpl = open(template_path, encoding="utf-8").read()
    marker = "/*__FOUNDRY_DATA_INJECTION__*/"
    if marker not in tmpl:
        raise ValueError("injection marker missing from template")
    return tmpl.replace(marker, render_block(cfg, res), 1)
