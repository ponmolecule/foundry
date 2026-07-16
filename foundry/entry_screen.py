"""Entry screen: the Icarus failure modes, checked at the input borders
(wizard finish, FIW import, Mode T finalize) instead of only at run time.

Two severities, deliberately:

- BLOCKERS — arithmetic self-destruction and range nonsense. A bank whose
  organizational costs exceed its raise has negative Day-1 equity; a runoff
  above 100%/quarter mints balances. These cannot mean anything; entry stops.
- WARNINGS — Icarus-style optimism: parameters far outside the engagement
  baseline for their product line (savings paid 1.25% when the baseline says
  2.5%; card charge-offs assumed at half the baseline). These ENTER, with the
  deviation named — a consultant may model a bad bank on purpose, and the
  screen's job is to make sure it is on purpose.

Only filled fields are screened (a config mid-translation legitimately has
gaps — those are the gap engine's jurisdiction, not this screen's).
"""
import json
import os

_BASELINES = None


def _baselines():
    global _BASELINES
    if _BASELINES is None:
        p = os.path.join(os.path.dirname(__file__), "fixtures", "patrick_templates_v31.json")
        _BASELINES = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"loans": [], "deposits": []}
    return _BASELINES


def _num(x):
    return isinstance(x, (int, float))


def entry_screen(cfg):
    """-> {"blockers": [msgs], "warnings": [msgs]} — messages written for the
    person at the door, naming the product and the number."""
    blockers, warnings = [], []
    a = cfg.get("assumptions") or {}
    ts = cfg.get("target_state") or {}

    cap = ts.get("initial_capital")
    org = a.get("org_costs_pre_open")
    if _num(cap) and cap <= 0:
        blockers.append("Initial capital must be positive — a bank cannot open on "
                         f"{cap:,.0f}.")
    if _num(cap) and _num(org) and org >= cap > 0:
        blockers.append(f"Organizational costs (${org:,.0f}) meet or exceed the raise "
                         f"(${cap:,.0f}) — Day-1 equity would be zero or negative.")

    dep_base = {d["name"]: d for d in _baselines().get("deposits", [])}
    loan_base = {l["name"]: l for l in _baselines().get("loans", [])}

    for p in (a.get("deposit_products") or []):
        nm = p.get("name", "deposit product")
        r = p.get("rate_paid_ann")
        if _num(r) and not (0 <= r <= 0.30):
            blockers.append(f"{nm}: rate paid {r:.2%} is outside [0%, 30%] — range nonsense.")
        g = p.get("growth_q")
        if _num(g) and not (-0.5 <= g <= 1.0):
            blockers.append(f"{nm}: growth_q of {g:.2%}/qtr is outside [-50%, 100%].")
        ro = p.get("runoff_q")
        if _num(ro) and not (0 <= ro <= 1.0):
            blockers.append(f"{nm}: runoff {ro:.2%}/qtr outside [0%, 100%] — negative runoff mints balances.")
        b = dep_base.get(nm)
        if b and _num(r) and b.get("rate_paid_ann") and r > 0:
            base = b["rate_paid_ann"]
            if r <= base / 2 or r > base * 3:
                warnings.append(f"{nm}: rate paid {r:.2%} vs engagement baseline {base:.2%} "
                                 "— outside half-to-triple; confirm this is deliberate.")

    for p in (a.get("lending_products") or []):
        nm = p.get("name", "loan product")
        y, co = p.get("yield_ann"), p.get("charge_off_ann")
        if _num(y) and not (0 <= y <= 0.50):
            blockers.append(f"{nm}: yield {y:.2%} is outside [0%, 50%] — range nonsense.")
        if _num(co) and not (0 <= co <= 0.40):
            blockers.append(f"{nm}: charge-offs {co:.2%} outside [0%, 40%].")
        v = p.get("runoff_q")
        if _num(v) and not (0 <= v <= 1.0):
            blockers.append(f"{nm}: runoff {v:.2%}/qtr outside [0%, 100%] — negative runoff mints balances.")
        b = loan_base.get(nm)
        if b and _num(co) and b.get("charge_off_ann"):
            base = b["charge_off_ann"]
            if 0 <= co < base / 2:
                warnings.append(f"{nm}: charge-offs assumed at {co:.2%} vs engagement baseline "
                                 f"{base:.2%} — less than half; Icarus-grade optimism unless justified.")
        if b and _num(y) and b.get("yield_ann") and y > b["yield_ann"] * 2:
            warnings.append(f"{nm}: yield {y:.2%} is more than double the engagement baseline "
                             f"{b['yield_ann']:.2%} — confirm the pricing story.")

    return {"blockers": blockers, "warnings": warnings}
