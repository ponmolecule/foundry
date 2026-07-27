"""Deterministic Executive-Summary verdict generation (Python side, for the exported artifact).

Mirrors the JS generator in web/console_v2.html exactly, so the downloaded workbook OPENS with the
same judgment shown on screen, bound to the same immutable run. Every string/number is assembled from
a named result field — no free-composed prose, meets/does-not-meet language (never viable/clean),
constraint SOURCE drives the noun, Precedence 0 (integrity/completeness) gates the verdict.

See docs/EXEC_SUMMARY_REDESIGN.md.
"""
from __future__ import annotations


def _constraint_noun(src: str) -> str:
    s = str(src or "").lower()
    if "regulat" in s:
        return "capital requirement"
    if "charter" in s or "application" in s:
        return "capital commitment"
    if "board" in s or "management" in s or "target" in s:
        return "management capital target"
    if "commitment" in s:
        return "capital commitment"
    return "engagement capital threshold"


def _precedence_zero(res: dict) -> str | None:
    """Return a gating call string, or None if the model can support a verdict."""
    if not res or not res.get("financials") and not res.get("bs"):
        # results_workbook passes the parity-shaped res (has 'bs'); run_v2 has 'financials'
        if not (res or {}).get("bs"):
            return "Assessment incomplete \u2014 required inputs unresolved"
    rows = ((res.get("checks") or {}).get("rows")) or []
    if any(x.get("class") == "integrity" and x.get("pass") is False for x in rows):
        return "Results unavailable \u2014 model integrity issue"
    return None


def verdict_call(cfg: dict, res: dict) -> dict:
    """The verdict call word + class, from constraint/flag state. meets/does-not-meet only."""
    p0 = _precedence_zero(res)
    if p0:
        return {"call": p0, "cls": "bad", "gated": True}
    ct = res.get("constraint_tests") or []
    base_fails = [t for t in ct if t.get("scenario") == "base" and t.get("pass") is False]
    stress_fails = [t for t in ct if t.get("scenario") != "base" and t.get("pass") is False]
    severe = any(f.get("sev") == "severe" for f in (res.get("flags") or []))
    if base_fails:
        src = next((c for c in (cfg.get("constraints") or []) if c.get("key") == base_fails[0].get("key")), None)
        noun = _constraint_noun(src.get("source") if src else None) if base_fails[0].get("key") == "leverage_min" else "stated constraints"
        return {"call": f"Does not meet the stated {noun}", "cls": "bad", "noun": noun}
    if stress_fails:
        return {"call": "Meets base constraints; vulnerable under stress", "cls": "warn"}
    if severe:
        return {"call": "Meets modeled constraints; material assumptions require support", "cls": "warn"}
    if res.get("flags"):
        return {"call": "Meets modeled constraints; review items remain", "cls": "mut"}
    return {"call": "No modeled exceptions identified", "cls": "ok"}


_NUMWORD = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


def _numword(n: int) -> str:
    return _NUMWORD[n] if 0 <= n < len(_NUMWORD) else str(n)


def _money000(v: float) -> str:
    m = v / 1000.0
    if abs(m) >= 1:
        return f"${m:,.1f}M"
    return f"${round(v):,}k"


def verdict_lines(cfg: dict, res: dict) -> list[str]:
    """The full verdict as a list of prose lines (call first, then binding/finding/shortfall).

    Each line is field-sourced; a line is omitted (not guessed) when its field is null."""
    v = verdict_call(cfg, res)
    lines = [v["call"] + "."]
    if v.get("gated"):
        return lines
    base = (res.get("scenarios") or {}).get("base") or {}
    ct = res.get("constraint_tests") or []
    lev_con = next((c for c in (cfg.get("constraints") or []) if c.get("key") == "leverage_min"), None)
    commit = (lev_con.get("value") * 100) if lev_con and lev_con.get("value") is not None else None
    scen_total = len({t.get("scenario") for t in ct})
    scen_fail = len({t.get("scenario") for t in ct if not t.get("pass")})
    if base.get("min_leverage") is not None and commit:
        min_pct = base["min_leverage"] * 100
        breaches = scen_fail > 0 or min_pct < commit
        if breaches:
            if scen_fail == scen_total and scen_total:
                tail = f"; all {_numword(scen_total)} modeled scenarios breach it"
            elif scen_fail:
                tail = f"; {scen_fail} of {scen_total} modeled scenarios breach it"
            else:
                tail = ""
            lines.append(
                f"Base leverage bottoms at {min_pct:.2f}% in Q{base.get('min_leverage_q')} "
                f"against the stated {commit:.1f}% threshold{tail}."
            )
        else:
            lines.append(
                f"Base leverage holds above the stated {commit:.1f}% threshold in every modeled "
                f"scenario (low of {min_pct:.2f}% in Q{base.get('min_leverage_q')})."
            )
    # highest-priority finding — the top issue family's headline (a flag's own text)
    fams = issue_families(res)
    if fams:
        lines.append("Highest-priority finding: " + fams[0]["headline"])
    shortfall = base.get("capital_shortfall_est")
    if shortfall is not None and shortfall > 0 and commit:
        lines.append(
            f"Estimated additional opening capital to maintain the {commit:.1f}% base-case threshold "
            f"through Q12: {_money000(shortfall)} (estimate)."
        )
    return lines


# ---- issue families (mirrors the JS: product-prefix first, then anchored ID rules) ----------------
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


def _classify(f: dict) -> str:
    text = str(f.get("text") or "")
    prefix = text.split(":")[0] if ":" in text else ""
    for rx, fam in _PRODUCT_FAMILY:
        if rx.search(prefix):
            return fam
    fid = str(f.get("id") or "")
    for rx, fam in _ID_FAMILY:
        if rx.search(fid) or rx.search(text):
            return fam
    return "Other assumptions & structure"


def issue_families(res: dict) -> list[dict]:
    flags = res.get("flags") or []
    groups: dict[str, list] = {}
    for f in flags:
        groups.setdefault(_classify(f), []).append(f)
    out = []
    for fam, hits in groups.items():
        sev = "severe" if any(h.get("sev") == "severe" for h in hits) else "advisory"
        headline = next((h for h in hits if h.get("sev") == "severe"), hits[0]).get("text")
        out.append({"family": fam, "sev": sev, "count": len(hits), "headline": headline})
    out.sort(key=lambda d: (d["sev"] != "severe", -d["count"]))
    return out


def sign_off_actions(res: dict) -> list[dict]:
    """Up to 3 generated required-before-sign-off statements, linked to the top families."""
    ACTION = {
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
    out = []
    for f in issue_families(res)[:3]:
        out.append({
            "text": ACTION.get(f["family"], f"Review the {f['family'].lower()} assumptions."),
            "sev": f["sev"],
            "affects_verdict": bool(verdict_linked and f["sev"] == "severe"),
        })
    return out
