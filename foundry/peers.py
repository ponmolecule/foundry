"""Peer evidence engine (step 4).

Bounded-radius similarity with pre-registered parameters, mandatory
disclosures, kernel-weighted priors. Reference data here is a SYNTHETIC
FIXTURE (42 invented de novo trajectories) standing in for the real
Call Report / UBPR reference warehouse; the methodology is the real one.

Pre-registered parameters (frozen 2026-06-12, criteria doc v1.2):
  feature space  : [log10 target assets yr3, consumer loan share,
                    fee income share, core funding share, digital flag]
  distance       : Euclidean on standardized features
  radius r       : 1.10
  widen step     : 0.15   max admissible radius: 1.70
  min cohort n   : 8
  kernel         : Gaussian, bandwidth 0.60
"""
import math, random, statistics

PARAMS = {"r": 1.10, "widen": 0.15, "r_max": 1.70, "min_n": 8, "bw": 0.60,
          "criteria_doc": "v1.2", "frozen": "2026-06-12"}

FEATURES = ["log_assets_yr3", "consumer_loan_share", "fee_income_share",
            "core_funding_share", "digital_channel"]

def _fixture():
    """43 synthetic de novo banks, 2011-2023 classes. Deterministic seed. fixture-v2 (adds CAC metric)."""
    rng = random.Random(20260612)
    banks = []
    archetypes = [  # (n, assets_mu, cons_share, fee_share, core, digital, base metrics)
        ("digital consumer", 10, 8.90, 0.23, 0.25, 0.94, 1.0),
        ("community commercial", 14, 8.55, 0.08, 0.09, 0.88, 0.0),
        ("consumer lender", 7, 8.75, 0.55, 0.12, 0.72, 0.6),
        ("fintech sponsor", 6, 8.65, 0.05, 0.55, 0.60, 1.0),
        ("CRE specialist", 6, 8.70, 0.03, 0.06, 0.80, 0.0),
    ]
    i = 0
    for name, n, a_mu, cs, fs, cf, dig in archetypes:
        for _ in range(n):
            i += 1
            failed = rng.random() < (0.16 if name != "community commercial" else 0.07)
            banks.append({
                "id": f"DN-{i:03d}",
                "archetype": name,
                "class_year": rng.choice(range(2011, 2024)),
                "log_assets_yr3": rng.gauss(a_mu, 0.18),
                "consumer_loan_share": max(0.0, rng.gauss(cs, 0.06)),
                "fee_income_share": max(0.02, rng.gauss(fs, 0.06)),
                "core_funding_share": min(1.0, max(0.3, rng.gauss(cf, 0.07))),
                "digital_channel": dig if dig in (0.0, 1.0) else (1.0 if rng.random() < dig else 0.0),
                "terminal": "failed" if failed else ("acquired" if rng.random() < 0.12 else "operating"),
                # observed trajectory metrics (what priors are drawn from)
                "deposit_growth_yr1": max(0.15, rng.gauss(1.05 if dig else 0.62, 0.30)),
                "cost_of_deposits_spread": rng.gauss(-0.0075 if dig else -0.0165, 0.0042),
                "card_nco_mature": max(0.012, rng.gauss(0.049 if cs > 0.15 else 0.031, 0.011)),
                "opex_per_active_acct": max(28.0, rng.gauss(66.0 if dig else 118.0, 17.0)),
                "efficiency_q12": min(2.6, max(0.62, rng.gauss(1.18 if dig else 0.98, 0.24))),
            })
    # fixture-v2 columnar extension: CAC added via independent per-bank RNG
    # streams so existing draws (and therefore cohorts) are stable under
    # extension. Reference data must never silently regenerate.
    for b in banks:
        r2 = random.Random("cac:" + b["id"])
        dig = b["digital_channel"] == 1.0
        b["cac_per_funded_account"] = max(45.0, r2.gauss(155.0 if dig else 340.0, 45.0))
    return banks

REFERENCE = _fixture()

def _standardize(vals):
    mu = statistics.mean(vals); sd = statistics.pstdev(vals) or 1.0
    return mu, sd

def select_cohort(query):
    """Returns cohort + mandatory disclosures per v2.1 step 4."""
    stats = {f: _standardize([b[f] for b in REFERENCE]) for f in FEATURES}
    def z(b, f): mu, sd = stats[f]; return (b[f] - mu) / sd
    qz = {f: (query[f] - stats[f][0]) / stats[f][1] for f in FEATURES}
    dists = []
    for b in REFERENCE:
        d = math.sqrt(sum((z(b, f) - qz[f]) ** 2 for f in FEATURES))
        dists.append((d, b))
    dists.sort(key=lambda t: t[0])

    r0 = PARAMS["r"]; r = r0
    while True:
        cohort = [(d, b) for d, b in dists if d <= r]
        if len(cohort) >= PARAMS["min_n"] or r >= PARAMS["r_max"]:
            break
        r = round(min(r + PARAMS["widen"], PARAMS["r_max"]), 4)

    insufficient = len(cohort) < PARAMS["min_n"]
    w = [math.exp(-(d / PARAMS["bw"]) ** 2 / 2) for d, _ in cohort]
    ess = (sum(w) ** 2 / sum(x * x for x in w)) if w else 0.0
    return {
        "cohort_id": "SOLSTICE-DIGCON-2026Q2-F01",
        "frozen": PARAMS["frozen"], "criteria_doc": PARAMS["criteria_doc"],
        "params": PARAMS,
        "radius_original": r0, "radius_final": r,
        "n": len(cohort), "effective_n": round(ess, 1),
        "insufficient_evidence": insufficient,
        "distance_distribution": [round(d, 3) for d, _ in cohort],
        "members": [{"id": b["id"], "archetype": b["archetype"], "class": b["class_year"],
                     "distance": round(d, 3), "terminal": b["terminal"]} for d, b in cohort],
        "terminal_summary": {
            "failed": sum(1 for _, b in cohort if b["terminal"] == "failed"),
            "acquired": sum(1 for _, b in cohort if b["terminal"] == "acquired"),
            "operating": sum(1 for _, b in cohort if b["terminal"] == "operating"),
        },
        "_pairs": cohort, "_weights": w,
    }

def _wpct(pairs, weights, metric, x):
    """Kernel-weighted percentile of value x within cohort metric distribution."""
    tw = sum(weights)
    below = sum(w for (d, b), w in zip(pairs, weights) if b[metric] <= x)
    return round(100.0 * below / tw, 0)

def _wq(pairs, weights, metric, q):
    vals = sorted(((b[metric], w) for (d, b), w in zip(pairs, weights)), key=lambda t: t[0])
    tw = sum(w for _, w in vals); acc = 0.0
    for v, w in vals:
        acc += w
        if acc >= q * tw: return v
    return vals[-1][0]

def priors(cohort, client_values):
    """client_values: {metric: value}. Returns per-metric prior + placement."""
    pairs, w = cohort["_pairs"], cohort["_weights"]
    out = {}
    for m, x in client_values.items():
        out[m] = {
            "p25": round(_wq(pairs, w, m, 0.25), 4),
            "p50": round(_wq(pairs, w, m, 0.50), 4),
            "p75": round(_wq(pairs, w, m, 0.75), 4),
            "client": round(x, 4),
            "client_percentile": _wpct(pairs, w, m, x),
        }
    return out
