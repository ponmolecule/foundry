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
from .timebase import period_label as _period_label, horizon_label as _horizon_label, cadence_noun as _cadence_noun

TONE = {"pass": "pass", "warn": "warn", "fail": "fail", "info": "info"}
_RANK = {"severe": 3, "advisory": 2, "review": 1}

# Family classification — mirrors Classic _issueFamilies (product-prefix then id/keyword).
import re as _re
_PRODUCT_FAMILY = [
    (_re.compile(r"credit card", _re.I), "Card pricing & credit losses"),
    (_re.compile(r"commercial real estate", _re.I), "CRE economics & concentration"),
    (_re.compile(r"construction|land", _re.I), "CRE economics & concentration"),
    (_re.compile(r"residential mortgage|jumbo mortgage|mortgage \(hfs\)", _re.I), "Mortgage-banking execution"),
    (_re.compile(r"small business|c&i|c & i", _re.I), "Commercial & industrial credit"),
    (_re.compile(r"retail demand|time deposit|cd|savings|money market|deposit", _re.I), "Deposit pricing & growth"),
    (_re.compile(r"subsidized|community loan", _re.I), "Mission & subsidized lending"),
]
_ID_FAMILY = [
    (_re.compile(r"^CONC-|CONCENTRATION", _re.I), "CRE economics & concentration"),
    (_re.compile(r"^CAP-|^PREOPEN|CAPITAL|LEVERAGE", _re.I), "Opening capitalization & Day-1 funding"),
    (_re.compile(r"^SPREAD|VIAB|NIM|MARGIN.*NEG|NEGATIVE.*SPREAD", _re.I), "Net-interest margin & viability"),
    (_re.compile(r"^FUND-|GROWTH-Y1", _re.I), "Deposit pricing & growth"),
    (_re.compile(r"^COUPLED", _re.I), "Cross-assumption consistency"),
    (_re.compile(r"NIE|OPEX|OVERHEAD|STAFF|FTE", _re.I), "Expense & staffing"),
    (_re.compile(r"EVIDENCE|CITATION", _re.I), "Evidence & citation gaps"),
]
_FAMILY_CONCERN = {
    "Card pricing & credit losses": "Card yield, fee, and loss assumptions and how they hang together.",
    "CRE economics & concentration": "CRE/construction pricing, losses, reserves, and concentration levels.",
    "Mortgage-banking execution": "Gain-on-sale, warehouse, and MSR assumptions in the mortgage plan.",
    "Commercial & industrial credit": "C&I pricing and loss assumptions.",
    "Deposit pricing & growth": "Deposit rate and growth strategy and its funding support.",
    "Opening capitalization & Day-1 funding": "Opening capital and Day-1 funding adequacy.",
    "Net-interest margin & viability": "Whether the modeled margin sustains the plan.",
    "Cross-assumption consistency": "Internal contradictions across coupled assumptions.",
    "Expense & staffing": "Operating-expense and staffing plan coherence.",
    "Mission & subsidized lending": "Subsidized/community lending economics.",
    "Evidence & citation gaps": "Assumptions asserted without supporting evidence.",
    "Other assumptions & structure": "Assumptions and structural items outside the main families.",
}
# short id for the filter/family nav
_FAMILY_SLUG = {
    "Card pricing & credit losses": "card", "CRE economics & concentration": "cre",
    "Mortgage-banking execution": "mortgage", "Commercial & industrial credit": "ci",
    "Deposit pricing & growth": "deposits", "Opening capitalization & Day-1 funding": "capital",
    "Net-interest margin & viability": "nim", "Cross-assumption consistency": "coupled",
    "Expense & staffing": "expense", "Mission & subsidized lending": "mission",
    "Evidence & citation gaps": "evidence", "Other assumptions & structure": "other",
}


def _classify_family(f):
    text = str(f.get("text", "")); fid = str(f.get("id", ""))
    prefix = text.split(":")[0] if ":" in text else ""
    for rx, fam in _PRODUCT_FAMILY:
        if rx.search(prefix):
            return fam
    for rx, fam in _ID_FAMILY:
        if rx.search(fid) or rx.search(text):
            return fam
    return "Other assumptions & structure"


def _money000(v):
    if v is None:
        return "n/m"
    try:
        v = float(v)
    except Exception:
        return "n/m"
    a = abs(v)
    if a >= 1000:
        return ("-" if v < 0 else "") + f"${a/1000:,.1f}M"
    return ("-" if v < 0 else "") + f"${a:,.0f}K"


def _resolve_thresholds(cfg, res):
    """Call the challenge-thresholds logic server-side (same as /api/v31/challenge-thresholds POST)."""
    try:
        from foundry.v2.challenge_q import CHALLENGE_THRESHOLDS, PROVENANCE
        ta = (((res.get("financials") or {}).get("bs") or {}).get("totalAssets") or [0])[-1] or 0
        if ta and ta > 0:
            try:
                from foundry.v2.peer_calibration import calibrate_thresholds
                rows, prov = calibrate_thresholds(CHALLENGE_THRESHOLDS, ta)
                return {"provenance": prov, "thresholds": rows, "tier": "provisional_peer"}
            except Exception:
                pass
        return {"provenance": PROVENANCE, "thresholds": CHALLENGE_THRESHOLDS, "tier": "static"}
    except Exception:
        return {"provenance": "", "thresholds": [], "tier": "static"}


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
    _a = cfg.get("assumptions") or {}
    _ppy = int(_a.get("periods_per_year") or 4)
    _nperiods = int(_a.get("n_periods") or 12)
    _period_word = _cadence_noun(_ppy)
    _horizon = _horizon_label(_nperiods, _ppy)
    def _plab(p): return _period_label(p, _ppy)
    lev = _lev(res) or [0.0]
    base = (res.get("scenarios") or {}).get("base") or {}
    min_lev = base.get("min_leverage")
    min_lev_pct = (min_lev * 100) if isinstance(min_lev, (int, float)) else None
    min_lev_q = base.get("min_leverage_q")
    # Generic Executive Summary cumulative earnings follow the full computational
    # horizon. Regulator-facing scenario tables continue to use base["cum_ni"],
    # which is intentionally limited to the submission window.
    cum_ni = base.get("cum_ni_full", base.get("cum_ni"))  # $000s
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
                  "label": f"Model ({_plab(min_lev_q)}) \u00b7 "
                           + (f"{_gap_txt(min_lev_pct or 0, commit)} of headroom"
                              if (min_lev_pct or 0) >= commit
                              else f"{_gap_txt(min_lev_pct or 0, commit)} short")},
        "foot": (f"Stress paths reach as low as {worst_val:.2f}%. Scale is linear from {lo:.0f}% to {hi:.0f}%."
                 if worst_val is not None else f"Scale is linear from {lo:.0f}% to {hi:.0f}%."),
    }

    # ---- METRICS ----
    def _tone(ok): return "pass" if ok else "fail"
    metrics = [
        {"id": "lev", "unit": "pct", "label": "MIN BASE LEVERAGE",
         "value": _pct(min_lev_pct) if min_lev_pct is not None else "\u2014",
         "sub": _plab(min_lev_q) if min_lev_q else "", "foot": f"Requirement \u2265 {commit:.1f}%",
         "tone": _tone((min_lev_pct or 0) >= commit), "series": series["lev"],
         "detail": (f"Tier 1 leverage reaches its base-case minimum of {_pct(min_lev_pct)} in "
                    f"{_plab(min_lev_q)}, {'above' if (min_lev_pct or 0) >= commit else 'below'} the "
                    f"{commit:.1f}% commitment."),
         "drivers": [["Cumulative net income", f"${(cum_ni or 0)/1000:.1f}M"],
                     ["Capital raise assumed", "None after Day 1"],
                     ["Projection horizon", _horizon]]},
        {"id": "stress", "unit": "pct", "label": "WORST STRESS OUTCOME",
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
        {"id": "breakeven", "unit": "money", "label": "BREAKEVEN", "value": _plab(breakeven) if breakeven else "\u2014",
         "sub": f"First profitable {_period_word}", "foot": "", "tone": "info", "series": series["ni"],
         "detail": (f"The plan reaches profitability in {_plab(breakeven)}." if breakeven
                    else "Breakeven is not reached within the projection horizon."),
         "drivers": [[f"{_horizon.capitalize()} net income", f"${(cum_ni or 0)/1000:.1f}M"]]},
        {"id": "cumni", "unit": "money", "label": "CUMULATIVE NET INCOME", "value": f"${(cum_ni or 0)/1000:.1f}M",
         "sub": f"{_horizon} total", "foot": "Carries the capital build", "tone": "info",
         "series": series["cumni"],
         "detail": (f"Cumulative earnings of ${(cum_ni or 0)/1000:.1f}M over the projection; "
                    f"the plan assumes no additional raise after Day 1."),
         "drivers": [["Breakeven", _plab(breakeven) if breakeven else "\u2014"]]},
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
                f"in the binding {_period_word}.",
                ("No capital action is assumed after Day 1." if sid == "base"
                 else "Overlay applied to the base plan; no management action credited."),
            ],
        })

    # ---- FAMILIES + FINDINGS (Classic classification, per-family counts) ----
    flags = res.get("flags") or []
    sevmap = {"severe": "severe", "high": "severe", "advisory": "advisory", "mild": "advisory",
              "review": "review", "moderate": "review"}
    fam_groups = {}
    for f in flags:
        fam_groups.setdefault(_classify_family(f), []).append(f)

    families = []
    findings = []
    for fam, fl in fam_groups.items():
        if any(sevmap.get(x.get("sev") or x.get("cls"), "advisory") == "severe" for x in fl):
            sev = "severe"
        elif any(sevmap.get(x.get("sev") or x.get("cls"), "advisory") == "advisory" for x in fl):
            sev = "advisory"
        else:
            sev = "review"
        slug = _FAMILY_SLUG.get(fam, "other")
        families.append({"id": slug, "name": fam, "severity": sev, "status": "open",
                         "concern": _FAMILY_CONCERN.get(fam, ""), "count": len(fl)})
        for f in fl:
            fsev = sevmap.get(f.get("sev") or f.get("cls") or "advisory", "advisory")
            findings.append({"title": f.get("id", "Finding"), "measured": "", "standard": "",
                             "severity": fsev, "family": slug,
                             "status": "resolved" if f.get("resolved") else "open",
                             "basis": f.get("source", "") or "Model finding", "reasoning": f.get("text", "")})

    if n_breach and not any(fm["id"] == "capital" for fm in families):
        families.append({"id": "capital", "name": "Opening capitalization & Day-1 funding",
                         "severity": "severe", "status": "open",
                         "concern": f"{n_breach} of {n_total} scenarios breach the {commit:.1f}% commitment.",
                         "count": n_breach})
        findings.append({"title": "Scenario breaches of the leverage commitment",
                         "measured": f"{n_breach} of {n_total}", "standard": "vs 0 expected",
                         "severity": "severe", "family": "capital", "status": "open",
                         "basis": f"Engagement commitment \u2265 {commit:.1f}%",
                         "reasoning": f"{n_breach} modeled overlays breach the leverage commitment."})

    families.sort(key=lambda x: (-_RANK.get(x["severity"], 0), -x.get("count", 0)))
    _short = {"cre": "CRE", "capital": "Capital", "deposits": "Deposits", "expense": "Expense",
              "card": "Card", "mortgage": "Mortgage", "ci": "C&I", "coupled": "Coupled",
              "nim": "NIM", "mission": "Mission", "evidence": "Evidence", "other": "Other"}
    fam_label = {fm["id"]: _short.get(fm["id"], fm["name"][:8]) for fm in families}

    # ---- resolved peer-band thresholds ----
    thr = _resolve_thresholds(cfg, res)
    peer_tier = thr.get("tier") == "provisional_peer"
    peer_by_id = {th["id"]: th["peer"] for th in thr.get("thresholds", []) if th.get("peer")}

    # ---- REASONABLENESS LEDGER (bands in effect) ----
    _fired_ids = set(str(f.get("id", "")) for f in flags)
    _LEDGER_TO_FLAGS = {"FUND-HOT": ["FUND-HOT"], "FUND-DDA": ["FUND-DDA"], "FUND-GROWTH": ["FUND-GROWTH"],
                        "GROWTH-Y1": ["GROWTH-Y1"], "CO-BAND": ["BAND-CO-HI", "BAND-CO-LO"], "MSR-FEE": ["MSR-FEE"]}
    ledger = []
    for th in thr.get("thresholds", []):
        emitted = _LEDGER_TO_FLAGS.get(th["id"], [th["id"]])
        p = th.get("peer")
        peer_str = (f"{float(p['p10']):.2f}\u00b7{float(p['p50']):.2f}\u00b7{float(p['p90']):.2f} "
                    f"({p.get('vintage','')} n={p.get('n','')})") if (peer_tier and p) else ""
        ledger.append({"id": th["id"], "rule": th.get("rule", ""), "trigger": th.get("trigger", ""),
                       "peer": peer_str, "fired": any(e in _fired_ids for e in emitted),
                       "severity": th.get("sev", "")})
    ledger_prov = thr.get("provenance", "")

    # ---- COHERENCE (modeled 'does the bank hold together') ----
    # Classic splits Model Checks into INTEGRITY (does the accounting tie out / completeness — gates the
    # verdict) and VIABILITY (does the bank actually work — margin, earnings, reserve adequacy).
    import re as _re2
    _INTEGRITY_RX = _re2.compile(r"balance|tie|ties|complete|reconcil|capital structure|identity|foots?|schedule", _re2.I)
    _VIABILITY_RX = _re2.compile(r"margin|nim|spread|reserve|allowance|charge.?off|earn|income|growth|viab|coverage|liquidity|funding", _re2.I)

    def _check_kind(title, text):
        blob = (str(title) + " " + str(text))
        if _INTEGRITY_RX.search(blob):
            return "integrity"
        if _VIABILITY_RX.search(blob):
            return "viability"
        return "viability"  # default: most modeled challenges are viability-type

    coherence = []
    for f in [x for x in flags if x.get("source") == "modeled"]:
        sev = sevmap.get(f.get("sev") or f.get("cls") or "advisory", "advisory")
        coherence.append({"title": f.get("id", "Finding"),
                          "severity": "severe" if sev == "severe" else "advisory",
                          "value": f.get("text", ""), "basis": f.get("basis", "") or "Modeled output",
                          "family": _FAMILY_SLUG.get(_classify_family(f), "capital"),
                          "kind": _check_kind(f.get("id", ""), f.get("text", ""))})
    for m in (res.get("modeled_challenges") or []):
        if not isinstance(m, dict):
            continue
        sev = sevmap.get(m.get("sev") or m.get("cls") or "advisory", "advisory")
        coherence.append({"title": m.get("id") or m.get("title") or "Modeled challenge",
                          "severity": "severe" if sev == "severe" else "advisory",
                          "value": (m.get("text") or str(m.get("value", ""))),
                          "basis": m.get("basis", "") or "Modeled challenge", "family": "capital",
                          "kind": _check_kind(m.get("id") or m.get("title") or "", m.get("text", ""))})

    # ---- MODEL CHECKS (from the engine's r.checks — same source Classic renders) ----
    # Integrity = the arithmetic holds together; Viability = the plan clears its commitments.
    # These are separate classes by design (a coherent model of a failing bank passes integrity,
    # fails viability). Do NOT synthesize — take the engine's classed rows verbatim.
    _rc = res.get("checks") or {}
    _rows = _rc.get("rows") or []

    def _check_group(kind, label):
        items = [{"id": x.get("id"), "label": x.get("label", ""), "pass": bool(x.get("pass")),
                  "note": x.get("note") or x.get("detail") or ""}
                 for x in _rows if x.get("class") == kind]
        n_fail = sum(1 for x in items if not x["pass"])
        return {"kind": kind, "label": label, "items": items, "n": len(items),
                "n_fail": n_fail, "n_pass": len(items) - n_fail,
                "status": "fail" if n_fail else "ok"}

    checks = {
        "master": _rc.get("master", ""),
        "doctrine": _rc.get("doctrine", ""),
        "integrity_pass": bool(_rc.get("integrity_pass", True)),
        "viability_pass": bool(_rc.get("viability_pass", True)),
        "groups": [
            _check_group("integrity", "Integrity Check"),
            _check_group("viability", "Viability Check"),
        ],
    }

    # ---- ASSUMPTIONS (rich: Input/Observation/Peer band/Comparability/Severity/Conclusion) ----
    CONCL = {"likely_regulatory_objection": "Likely regulatory objection",
             "commercial_assumption_requiring_support": "Needs supporting evidence",
             "counsel_determination_required": "Counsel determination",
             "advisory": "Review item", "satisfied": "Within range"}
    FLAG_TO_RULE = {"FUND-HOT": "FUND-HOT", "FUND-DDA": "FUND-DDA", "FUND-GROWTH": "FUND-GROWTH",
                    "GROWTH-Y1": "GROWTH-Y1", "BAND-CO-HI": "CO-BAND", "BAND-CO-LO": "CO-BAND", "MSR-FEE": "MSR-FEE"}
    assumptions = []
    for f in [x for x in flags if x.get("source") != "modeled"]:
        text = str(f.get("text", ""))
        ci = text.find(":")
        inp = text[:ci].strip() if ci > 0 else (f.get("id", "assumption"))
        obs = text[ci + 1:].strip() if ci > 0 else text
        fsev = sevmap.get(f.get("sev") or f.get("cls") or "advisory", "advisory")
        rule = FLAG_TO_RULE.get(f.get("id", ""))
        p = peer_by_id.get(rule) if rule else None
        if not peer_tier:
            band, comp = "", ""
        elif p:
            band = f"{float(p['p10']):.2f}\u00b7{float(p['p50']):.2f}\u00b7{float(p['p90']):.2f}"
            comp = "insufficient sample" if p.get("small_n") else "like-for-like"
        else:
            band, comp = "\u2014", "not comparable"
        assumptions.append({"input": inp, "observation": obs, "band": band, "comparability": comp,
                            "severity": "High" if fsev == "severe" else "Advisory", "sev_key": fsev,
                            "conclusion": CONCL.get(f.get("cls"), "Review item"),
                            "family": _FAMILY_SLUG.get(_classify_family(f), "other")})
    peer_tier_flag = peer_tier

    # ---- SIGNOFF ----
    ACTIONS = {
        "Opening capitalization & Day-1 funding": "Revise or support the opening capitalization and Day-1 funding plan.",
        "CRE economics & concentration": "Reconcile CRE pricing, losses, reserves, and concentration assumptions.",
        "Deposit pricing & growth": "Support the deposit-rate and growth strategy with pipeline and market evidence.",
        "Card pricing & credit losses": "Support credit-card pricing and loss assumptions with product-level evidence.",
        "Commercial & industrial credit": "Reconcile C&I pricing and loss assumptions.",
        "Mortgage-banking execution": "Support the mortgage-banking gain-on-sale, warehouse, and MSR assumptions.",
        "Expense & staffing": "Reconcile the operating-expense and staffing plan.",
        "Cross-assumption consistency": "Resolve the internal contradictions flagged across coupled assumptions.",
    }
    verdict_linked = any(t.get("scenario") == "base" and not t.get("pass") for t in (res.get("constraint_tests") or []))
    signoff = []
    for fam in families:
        if fam["severity"] in ("severe", "review") and fam["status"] == "open":
            signoff.append({"text": ACTIONS.get(fam["name"], f"Reconcile {fam['name'].lower()}."),
                            "severity": fam["severity"],
                            "affects_verdict": bool(verdict_linked and fam["severity"] == "severe")})
    signoff = signoff[:3]

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
                  "note": (qs.get("note", "") + f". Income ratios are aggregated from the model\u2019s {_period_word}s; "
                           "stock figures are year-end.") if qs.get("note") else ""}

    # ---- DECISION DRIVERS (Classic 6-card set) ----
    y3ni = None
    for row in (qs.get("rows") or []):
        if _re.search(r"net income", row.get("label", ""), _re.I):
            ys = row.get("y", [])
            y3ni = ys[2] if len(ys) > 2 else (ys[-1] if ys else None)
            break
    day1_borrow = (((res.get("financials") or {}).get("bs") or {}).get("borrow") or [None])[0]
    drivers = [
        {"k": "Min base leverage", "v": _pct(min_lev_pct) if min_lev_pct is not None else "n/m",
         "s": f"{_plab(min_lev_q)} \u00b7 vs {commit:.1f}%", "neg": (min_lev_pct or 0) < commit},
        {"k": "Worst stress outcome", "v": _pct(worst_val) if worst_val is not None else "n/m",
         "s": f"min leverage \u00b7 {worst_label}", "neg": (worst_val or 0) < commit},
        {"k": "Breakeven", "v": (_plab(breakeven) if breakeven and breakeven > 0 else f"not in {_horizon}"),
         "s": f"first profitable {_period_word}", "neg": (not breakeven or breakeven < 0)},
        {"k": "Opening wholesale funding", "v": _money000(day1_borrow) if day1_borrow is not None else "n/m",
         "s": "at Day 1", "neg": (day1_borrow or 0) > 0},
        {"k": "Earnings durability", "v": _money000(y3ni) if y3ni is not None else "n/m",
         "s": "Year-3 net income", "neg": (isinstance(y3ni, (int, float)) and y3ni < 0)},
        {"k": "Cumulative net income", "v": _money000(cum_ni) if cum_ni is not None else "n/m",
         "s": f"{_horizon} total", "neg": (isinstance(cum_ni, (int, float)) and cum_ni < 0)},
    ]

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
        "periodStartLabel": _plab(1), "periodEndLabel": _plab(_nperiods),
        "horizonLabel": _horizon,
        "generated": "", "freshness": "Up to date",
        "runLine": f"Run {str(res.get('config_hash', ''))[:10]} \u00b7 {cfg_name} \u00b7 v2-cadence-aware "
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
                        "lede": "Each input assumption judged on its own terms against real-peer bands. This is about whether the plan\u2019s inputs are believable \u2014 not yet about what they add up to.",
                        "columns": (["INPUT", "OBSERVATION", "PEER BAND (p10\u00b7med\u00b7p90)", "COMPARABILITY", "SEVERITY", "CONCLUSION"]
                                    if peer_tier_flag else ["INPUT", "OBSERVATION", "SEVERITY", "CONCLUSION"]),
                        "empty": "No input assumption fell outside its reasonableness band. The plan\u2019s inputs are jointly consistent and within typical ranges.",
                        "ledgerTitle": "Reasonableness bands in effect \u2014 the standards these inputs were judged against",
                        "ledgerColumns": ["RULE ID", "RULE", "TRIGGER", "PEER BAND", "YOUR PLAN", "SEVERITY"],
                        "ledgerProv": ledger_prov},
        "drivers": {"title": "DECISION DRIVERS"},
        "families": {"title": "TOP ISSUE FAMILIES \u2014 WHAT TO FOCUS ON"},
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
        "metricDetail": {"seriesTitle": f"{_horizon.upper()} SERIES", "axisMid": _horizon,
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
        "DRIVERS": drivers, "LEDGER": ledger, "PEER_TIER": peer_tier_flag, "CHECKS": checks,
    }


def render_block(cfg, res):
    d = build(cfg, res)
    def js(name, val): return f"var {name} = " + json.dumps(val, ensure_ascii=False) + ";"
    # SERIES first so METRICS/SCEN can reference it — but we inline series arrays, so order only cosmetic.
    order = ["MODEL", "VERDICT", "GAUGE", "SERIES", "METRICS", "CONSTRAINT", "SCEN",
             "FAMILIES", "FAM_LABEL", "FINDINGS", "ASSUMPTIONS", "COHERENCE", "SIGNOFF",
             "COPY", "FILTER_DEFS", "FINANCIALS", "DRIVERS", "LEDGER", "PEER_TIER", "CHECKS"]
    return "\n".join(js(k, d[k]) for k in order)


def build_html(cfg, res, template_path):
    tmpl = open(template_path, encoding="utf-8").read()
    marker = "/*__FOUNDRY_DATA_INJECTION__*/"
    if marker not in tmpl:
        raise ValueError("injection marker missing from template")
    return tmpl.replace(marker, render_block(cfg, res), 1)
