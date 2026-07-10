"""Run registry for Foundry v2.2 — freeze, list, re-verify.

A frozen run is a notarized artifact: the full configuration plus the hashes it
produced, written to disk. Re-verification re-executes the frozen configuration
through the engine of record and compares hashes; a match proves the deployed
engine still reproduces the filed numbers bit-for-bit (G4 determinism made
demonstrable).

Storage is a plain directory of JSON files under FOUNDRY_DATA_DIR (default
./data). On ephemeral hosting the registry survives only until redeploy;
`status()` reports which mode the deployment is in so the surface can say so
honestly instead of implying durability that is not configured.
"""
import json
import os
import time
import uuid

from .run_q import run_v2


def _data_dir():
    return os.environ.get("FOUNDRY_DATA_DIR", os.path.join(os.getcwd(), "data"))


def _reg_dir():
    d = os.path.join(_data_dir(), "registry")
    os.makedirs(d, exist_ok=True)
    return d


def status():
    """Persistence honesty: explicit FOUNDRY_DATA_DIR => operator attached
    storage; default cwd/data on ephemeral hosting dies with the container."""
    explicit = "FOUNDRY_DATA_DIR" in os.environ
    return {"persistent": explicit, "dir": _data_dir(),
            "note": None if explicit else
            "FOUNDRY_DATA_DIR is not set: frozen runs live in the container "
            "and will not survive a redeploy. Attach a volume and set "
            "FOUNDRY_DATA_DIR to make the registry durable."}


def freeze(cfg, label=None):
    """Run the configuration through the engine of record and notarize it."""
    res = run_v2(cfg)  # fail-closed: raises/errors upstream if cfg invalid
    entry = {
        "id": uuid.uuid4().hex[:12],
        "frozen_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "label": (label or cfg.get("scenario_name") or "unlabeled").strip()[:120],
        "proposed_bank": cfg.get("proposed_bank"),
        "config_hash": res["config_hash"],
        "run_hash": res["run_hash"],
        "engine_version": res.get("engine_version"),
        "config": cfg,
    }
    path = os.path.join(_reg_dir(), entry["id"] + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entry, f, indent=1, sort_keys=True)
    return {k: v for k, v in entry.items() if k != "config"}


def list_entries():
    out = []
    d = _reg_dir()
    for name in sorted(os.listdir(d)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, name), encoding="utf-8") as f:
                e = json.load(f)
            out.append({k: e.get(k) for k in
                        ("id", "frozen_at_utc", "label", "proposed_bank",
                         "config_hash", "run_hash", "engine_version")})
        except Exception:
            continue
    out.sort(key=lambda e: e.get("frozen_at_utc") or "", reverse=True)
    return out


def get_entry(entry_id):
    path = os.path.join(_reg_dir(), entry_id + ".json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def verify(entry_id):
    """Re-execute the frozen configuration; hashes must match exactly."""
    e = get_entry(entry_id)
    if e is None:
        return None
    res = run_v2(e["config"])
    match = (res["run_hash"] == e["run_hash"]
             and res["config_hash"] == e["config_hash"])
    return {"id": entry_id, "match": bool(match),
            "frozen": {"config_hash": e["config_hash"], "run_hash": e["run_hash"]},
            "now": {"config_hash": res["config_hash"], "run_hash": res["run_hash"]}}
