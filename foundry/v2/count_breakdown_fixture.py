"""Test fixture: the universal template with a weighted count breakdown on an Account stream (r421)."""
import copy
import json
import os

_FIX = os.path.join(os.path.dirname(__file__), "..", "fixtures", "universal_template_bank.json")
BANDS = [("5–10 practitioners", 0.735415, 7.5), ("11–24 practitioners", 0.192687, 17.5),
         ("25–49 practitioners", 0.048006, 37.0), ("50+ practitioners", 0.023892, 75.0)]


def flat(v, unit):
    return {"source": "entered", "trajectory": "flat", "value": v, "unit": unit}


def config(bands=BANDS):
    with open(_FIX, encoding="utf-8") as fh:
        cfg = json.load(fh)
    p = cfg["assumptions"]["obs_exposures"][2]
    p["fee_streams"].append({
        "name": "Practitioner accounts", "basis": "account", "quantity_series_id": "fee-qty-practitioners",
        "cost": {"kind": "none", "params": {}}, "timing": {"start_period": 1},
        "rate": {"behavior": "flat", "params": {"unit_fee": {"period": "month", "trajectory": "flat", "value": 0.0}}},
        "driver": {"source": "stream_ref", "ref": "Enabled accounts", "trajectory": "derived",
                   "params": {"count_multiplier_spec": {"source": "weighted_sum", "unit": "scalar", "components": [
                       {"id": f"band-{k + 1}", "name": n, "weight_spec": flat(w, "share"), "amount_spec": flat(c, "scalar")}
                       for k, (n, w, c) in enumerate(bands)]}}}})
    return cfg


def stream(cfg):
    return cfg["assumptions"]["obs_exposures"][2]["fee_streams"][-1]


def copy_config():
    return copy.deepcopy(config())
