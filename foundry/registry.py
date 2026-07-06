"""Engagement registry: the shell's map of configured clients.

No default engagement — callers must name the one they mean. The engine
shouldn't have a favorite client.
"""
import copy
from .client_solstice import CLIENT as SOLSTICE
from .client_blackland import CLIENT as BLACKLAND


def _icarus():
    """Broken-applicant demonstration case (T4 benchmark member)."""
    c = copy.deepcopy(SOLSTICE)
    c["engagement_id"] = "ENG-2026-0002"
    c["client_legal_name"] = "Icarus Financial Corp."
    c["proposed_bank"] = "Icarus Bank (in organization)"
    c["config_version"] = "1.0"
    c["target_state"]["initial_capital"] = 45e6
    c["assumptions"].update({
        "new_accts_per_marketing_dollar": 1 / 22.0,
        "marketing_budget_m": [0.6e6] * 36,
        "savings_rate": 0.0125,
        "card_nco_mature": 0.021,
        "fraud_alerts_per_1k_accts_m": 2.0, "min_per_alert": 8.0,
    })
    return c


ENGAGEMENTS = {
    "solstice": {"label": "Solstice Bank — digital consumer", "config": SOLSTICE},
    "blackland": {"label": "Blackland State Bank — CRE community", "config": BLACKLAND},
    "icarus": {"label": "Icarus Bank — broken applicant (challenge demo)", "config": _icarus()},
}


def register_config(cfg, persist=True):
    """Validate and register an engagement configuration. Returns slug."""
    import json, os
    from .configio import validate_config, slugify
    validate_config(cfg)
    base = slugify(cfg["proposed_bank"].replace("(in organization)", ""))
    slug, n = base, 2
    while slug in ENGAGEMENTS:
        slug = f"{base}-{n}"; n += 1
    ENGAGEMENTS[slug] = {"label": cfg["proposed_bank"].replace(" (in organization)", "")
                                  + " — uploaded", "config": cfg}
    if persist:
        d = os.path.join(os.path.dirname(__file__), "..", "clients_uploaded")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, slug + ".json"), "w") as f:
            json.dump(cfg, f, indent=1)
    return slug


def _load_uploaded():
    import json, os, glob
    d = os.path.join(os.path.dirname(__file__), "..", "clients_uploaded")
    for p in sorted(glob.glob(os.path.join(d, "*.json"))):
        try:
            cfg = json.load(open(p))
            from .configio import validate_config, slugify
            validate_config(cfg)
            slug = slugify(cfg["proposed_bank"].replace("(in organization)", ""))
            if slug not in ENGAGEMENTS:
                ENGAGEMENTS[slug] = {"label": cfg["proposed_bank"].replace(" (in organization)", "")
                                              + " — uploaded", "config": cfg}
        except Exception as e:
            print(f"registry: skipped {p}: {e}")

_load_uploaded()
