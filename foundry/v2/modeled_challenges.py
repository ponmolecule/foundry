"""Modeled challenges — findings derived from the ENGINE'S OWN OUTPUTS, never from raw inputs.

This is the counterpart to input reasonableness, and the boundary between them is absolute:

  * Input reasonableness (challenge_q.py) judges a RAW ASSUMPTION against a band: "your 3.5% card
    charge-off is high for the product." The claim is about the CREDIBILITY OF AN INPUT.

  * Modeled challenges (this module) judge a MODELED OUTPUT against a supervisory/economic standard:
    "the projected book charges off 1.24% while carrying 0.88% reserves." The claim is about whether
    THE PROJECTED BANK HOLDS TOGETHER.

The two never share a number. A modeled challenge cites only values the engine computed (ratios,
balances, scenario aggregates) — the blended, emergent quantities from the Product-detail waterfall —
so it answers "are the bank's prospects sound?" rather than "is this assumption reasonable?".

Each challenge is deterministic, reads only `res` (the run_v2 result), and returns a finding dict:
    {"id", "sev", "text", "basis"}  where basis names the modeled quantities it read.

Findings carry cls="modeled" so downstream code can route them to the modeled-challenges section and
keep them out of the input-reasonableness review.
"""
from __future__ import annotations

from .timebase import period_label, horizon_label


def _last(seq):
    return seq[-1] if seq else None


def _q(seq, i):
    return seq[i] if seq and len(seq) > i and seq[i] is not None else None


def modeled_challenges(res: dict) -> list[dict]:
    """Return modeled-output-derived findings. Reads only engine outputs, never cfg inputs."""
    out: list[dict] = []
    fin = res.get("financials") or {}
    rat = fin.get("ratios") or {}
    base = (res.get("scenarios") or {}).get("base") or {}
    cad = res.get("cadence") or {}
    ppy = int(cad.get("periods_per_year") or 4)
    np = int(cad.get("n_periods") or max((len(rat.get("roa") or []) - 1), 12))
    terminal = period_label(np, ppy)
    horizon = horizon_label(np, ppy)
    sub_p = int(cad.get("submission_end_period") or np)
    submission = cad.get("submission_label") or period_label(sub_p, ppy)
    # ratio arrays normally carry an opening slot; flows do not.
    def _at_submission(seq):
        if not seq:
            return None
        i = sub_p if len(seq) == np + 1 else sub_p - 1
        return seq[i] if 0 <= i < len(seq) else seq[-1]

    roa = rat.get("roa") or []
    eff = rat.get("eff") or []
    nim = rat.get("nim") or []
    lev = rat.get("lev") or []
    nco = rat.get("nco_rate") or []
    alll = rat.get("alllPct") or []

    # 1. Portfolio reserve coverage (MODELED) — blended net charge-off vs blended ALLL. This is the
    #    book-level counterpart to the per-product RES-THIN INPUT flag: RES-THIN asks "is this one
    #    product's reserve assumption credible?"; this asks "does the projected book's reserve keep up
    #    with the projected book's losses?". Different question, different (modeled) numbers.
    nco12, alll12 = _at_submission(nco), _at_submission(alll)
    if nco12 is not None and alll12 is not None and nco12 > 0:
        if alll12 < nco12:
            out.append({
                "id": "MOD-RESERVE-COVERAGE", "sev": "severe", "cls": "modeled",
                "text": (f"Projected reserves cover under one year of projected losses: the modeled "
                         f"allowance is {alll12:.2f}% of loans at {submission} while the modeled book charges "
                         f"off {nco12:.2f}% a year. A bank that provisions below its own modeled loss "
                         f"rate is releasing reserves it will need — examiners read this as an ALLL "
                         f"shortfall, not a capital tailwind."),
                "basis": f"modeled ALLL% and blended net charge-off rate ({submission})"})
        elif alll12 < nco12 * 1.25:
            out.append({
                "id": "MOD-RESERVE-THIN", "sev": "mild", "cls": "modeled",
                "text": (f"Projected reserve coverage is thin at the portfolio level: {alll12:.2f}% "
                         f"allowance against a modeled {nco12:.2f}% annual charge-off leaves little "
                         f"cushion if losses arrive faster than the ramp assumes."),
                "basis": f"modeled ALLL% and blended net charge-off rate ({submission})"})

    # 2. Modeled earnings trajectory — is the bank projected to earn its way to durability, or is Y3
    #    still negative? Reads modeled net income, not any input.
    ni12 = base.get("ni_q12")
    cum = base.get("cum_ni_full", base.get("cum_ni"))
    if ni12 is not None and ni12 < 0:
        out.append({
            "id": "MOD-EARNINGS-NEG-Y3", "sev": "severe", "cls": "modeled",
            "text": (f"The plan does not reach durable profitability inside the projection: modeled "
                     f"{submission} net income is still negative. A de novo that has not turned the corner by "
                     f"the regulator-facing Year-3/Q12 submission point carries its losses into the capital base "
                     f"and invites a going-concern question at renewal."),
            "basis": f"modeled submission-period net income ({submission}, base scenario)"})
    elif cum is not None and cum < 0:
        out.append({
            "id": "MOD-EARNINGS-CUM-NEG", "sev": "mild", "cls": "modeled",
            "text": (f"Cumulative modeled earnings over the {horizon} projection are negative even though {submission} "
                     f"turns positive — the bank consumes capital before it builds it, so the opening "
                     f"raise has to carry more of the plan than a headline submission-period figure suggests."),
            "basis": "modeled cumulative net income (base scenario)"})

    # 3. Modeled operating efficiency — a projected efficiency ratio that never comes down signals a
    #    cost base the modeled revenue can't support.
    eff12 = _at_submission(eff)
    if eff12 is not None and eff12 > 85:
        out.append({
            "id": "MOD-EFFICIENCY-HIGH", "sev": "mild", "cls": "modeled",
            "text": (f"The modeled efficiency ratio is still {eff12:.0f}% at {submission} — the projected cost "
                     f"base consumes most of projected revenue at the regulator-facing Year-3/Q12 point. Either the revenue ramp "
                     f"or the expense plan is doing more work than the market usually allows."),
            "basis": f"modeled efficiency ratio ({submission})"})

    # 4. Modeled wholesale-funding reliance — peak modeled borrowings as a share of modeled assets.
    peak = base.get("peak_borrowings")
    ta12 = base.get("q12_total_assets")
    if peak is not None and ta12 and ta12 > 0 and (peak / ta12) > 0.10:
        out.append({
            "id": "MOD-WHOLESALE-RELIANCE", "sev": "mild", "cls": "modeled",
            "text": (f"Modeled wholesale funding peaks near {peak / ta12 * 100:.0f}% of projected "
                     f"assets — the plan leans on borrowings to fund the ramp, a concentration that "
                     f"examiners test for rate and rollover risk in a de novo's first cycle."),
            "basis": "modeled peak borrowings vs modeled total assets"})

    # 5. Modeled leverage trajectory — if leverage erodes sharply across the projection (even while
    #    still above the floor), that trend itself is a finding the point-in-time minimum can hide.
    lev1, lev12 = (_q(lev, 1) if len(lev) == np + 1 else _q(lev, 0)), _at_submission(lev)
    if lev1 is not None and lev12 is not None and lev1 > 0 and (lev1 - lev12) / lev1 > 0.5 and lev12 > 0:
        out.append({
            "id": "MOD-LEVERAGE-EROSION", "sev": "mild", "cls": "modeled",
            "text": (f"Modeled leverage falls from {lev1:.1f}% to {lev12:.1f}% from the first modeled period to the submission endpoint — "
                     f"the ramp burns capital faster than earnings rebuild it. The plan stays above "
                     f"the floor, but the trajectory is downward, so a slower revenue ramp would test "
                     f"the constraint before the regulator-facing submission endpoint."),
            "basis": f"modeled leverage ratio trajectory (first period vs {submission})"})

    return out
