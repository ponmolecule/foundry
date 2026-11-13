"""r498: stress scenarios as overrides on named inputs, run through the same engine as the base.

Contract (stage 1)
------------------
A scenario lives in ``cfg["stress_scenarios"]`` (outside ``assumptions``; the base fingerprint
and ``config_hash`` ignore it). It never edits the base: every run works on a deep copy.

    {"id", "name", "question", "kind": "economic" | "method_comparison", "version": int,
     "funding": "inherit" | "show_shortfall" | "automatic_borrowing",
     "severities": [{"id", "label", "overrides": [override, ...]}, ...]}

    override = {"target": "<target key>", "op": "multiply" | "add" | "replace",
                "value": number (engine units: fractions for rates, dollars for money),
                "start": first model period (1-based), "end": last model period or null (horizon)}

A target key names an entered Series input by stable identity:
``<family>:<source_catalog_id>:<field path>`` for products (list hops by element ``id``) and
``bank:assumptions:<field path>`` for bank-level inputs. Position-only list elements are not
targetable, so reordering never retargets a shock.

Operations act on the input's resolved model-period path inside [start, end]; periods outside
the window keep their base values. The stressed input is written back as an explicit
model-period schedule. Two resolutions exist (levels, and natural-period recurring flows); the
executed zero-shock check proves which one reproduces the base exactly before any stress runs.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import time
import uuid
from pathlib import Path

FAMILIES = {"deposit_products": "Deposit", "lending_products": "Lending", "obs_exposures": "Fee product"}
OPS = ("multiply", "add", "replace", "delay")
KINDS = ("macro", "idiosyncratic", "combined", "sensitivity", "economic", "method_comparison", "design", "design_stress")
KIND_LABELS = {"macro": "Macroeconomic", "idiosyncratic": "Idiosyncratic", "combined": "Combined",
               "sensitivity": "Sensitivity", "economic": "Unclassified stress", "method_comparison": "Method comparison",
               "design": "Design alternative", "design_stress": "Design alternative under stress"}
APPROVAL = ("draft", "reviewed", "approved")
# r500: the reference rate path, shifted in parallel through the engine's own rate-shock overlay, so every
# floating product reprices through its index and spread and fixed-rate contracts keep their rates.
RATE_KEY = "bank:rates:parallel_shift_bp"
FUNDING = ("inherit", "show_shortfall", "automatic_borrowing")
_TRAJ = ("flat", "growth", "explicit")
_SKIP_BANK_KEYS = set(FAMILIES) | {"n_periods", "periods_per_year", "balance_components_model"}
_MODEL_PERIOD = {12: "month", 4: "quarter", 1: "year"}
STRESS_KEYS = ("stress_scenarios", "stress_reporting", "liquidity_stress")   # stored beside the base, never part of it
# Supported-input registry bounds by unit kind: a stressed path outside these is rejected by name.
BOUNDS = {"rate": (-1.0, 1.0), "count": (0.0, None)}


# ---------------------------------------------------------------- identity and fingerprints
def _canon(obj):
    return json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))


def _strip_ids(o):
    if isinstance(o, dict):
        return {k: _strip_ids(v) for k, v in o.items() if k != "stable_id"}
    if isinstance(o, list):
        return [_strip_ids(v) for v in o]
    return o


def base_fingerprint(cfg) -> str:
    """Fingerprint of the base configuration, excluding stored stress settings and the stable IDs that
    stress and the Lab assign (inert to every calculation), so giving an input an ID never stales a run."""
    c = _strip_ids({k: v for k, v in (cfg or {}).items() if k not in STRESS_KEYS})
    return hashlib.sha256(_canon(c).encode()).hexdigest()[:16]


def scenario_fingerprint(scenario) -> str:
    keep = {k: scenario.get(k) for k in ("kind", "funding", "severities")}
    return hashlib.sha256(_canon(keep).encode()).hexdigest()[:16]


def engine_identity() -> str:
    root = Path(__file__).resolve().parents[2]
    try:
        return (root / "BUILD_STAMP").read_text().split()[0]
    except Exception:
        return "unknown"


# ---------------------------------------------------------------- target catalog
def _is_entered_series(d) -> bool:
    if not isinstance(d, dict):
        return False
    if str(d.get("source") or "entered") != "entered":
        return False
    t = str(d.get("trajectory") or "").strip().lower()
    if t not in _TRAJ:
        return False
    return ("value" in d) or ("values" in d) or ("base" in d) or ("growth_spec" in d)


_SCALAR_SKIP = {"n_periods", "periods_per_year", "schema_version", "version", "index", "order", "seq"}


def _eid(el):
    return el.get("stable_id") or el.get("id")


def _walk(node, tokens, out, depth=0, loc=(), stable=True):
    """Collect (tokens, value, kind, locator, stable) for Series specs and numeric scalars.

    ``locator`` is the positional path (for assigning stable IDs); ``stable`` is False when a list
    element on the way has no stable ID yet.
    """
    if depth > 12:
        return
    if isinstance(node, dict):
        if tokens and _is_entered_series(node):
            out.append((tuple(tokens), node, "series", loc, stable))
            return
        for k, v in node.items():
            if isinstance(k, str) and k.startswith("_"):
                continue
            if isinstance(v, (dict, list)):
                _walk(v, tokens + [k], out, depth + 1, loc + (k,), stable)
            elif isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)) \
                    and k not in _SCALAR_SKIP and not str(k).endswith("_id") and k not in ("id", "stable_id") \
                    and not _is_timing(k):
                out.append((tuple(tokens + [k]), v, "scalar", loc + (k,), stable))
    elif isinstance(node, list):
        for i, el in enumerate(node):
            if isinstance(el, dict):
                eid = _eid(el)
                _walk(el, tokens + [f"[id={eid}]" if eid not in (None, "") else f"[#{i}]"], out, depth + 1,
                      loc + (i,), stable and eid not in (None, ""))


_CONTAINERS = {"nie_detail": "Operating expense", "workforce": "Workforce", "cac_feeds": "Customer acquisition",
               "other_liabilities_model": "Other liabilities", "managed_securities_portfolios": "Securities",
               "cost_pools": "Cost pools", "loan_rollforward": "Loan production", "balance_driver": "Balance",
               "repayment_profile": "Repayment", "funded_flow_driver": "Funded flow"}
_SILENT = {"categories", "linked_components", "roles", "channels", "driver_specs", "fee_streams", "params",
           "components", "sleeves", "factors", "formula", "driver", "rate", "cost"}


def _named_label(root, tokens) -> str:
    """Readable label using element names along the path (e.g. Operating expense › Marketing › amount)."""
    node, parts = root, []
    for t in tokens:
        if t.startswith("[id=") or t.startswith("[#"):
            el = None
            if isinstance(node, list):
                if t.startswith("[#"):
                    i = int(t[2:-1])
                    el = node[i] if i < len(node) else None
                else:
                    el = next((e for e in node if isinstance(e, dict) and str(_eid(e)) == t[4:-1]), None)
            if isinstance(el, dict) and (el.get("name") or el.get("label")):
                parts.append(str(el.get("name") or el.get("label")))
            node = el
            continue
        if t in _CONTAINERS:
            parts.append(_CONTAINERS[t])
        elif t not in _SILENT and not isinstance(node, list):
            parts.append(_field_label([t]))
        node = node.get(t) if isinstance(node, dict) else None
    s = " › ".join(p for p in parts if p) or _field_label(tokens)
    return s[:1].upper() + s[1:]


_FIELD_WORDS = {"spec": "", "rate": "rate", "amount": "amount", "count": "count", "pct": "%",
                "ann": "annual", "bal": "balance", "q": "", "opex": "operating expense"}


def _field_label(tokens) -> str:
    parts = []
    for t in tokens:
        if t.startswith("[id="):
            continue
        words = [w for w in t.replace("-", "_").split("_") if w]
        words = [_FIELD_WORDS.get(w, w) for w in words]
        words = [w for w in words if w]
        if words:
            parts.append(" ".join(words))
    s = " › ".join(parts) or "value"
    return s[:1].upper() + s[1:]


def _inactive(a, family, product, tokens) -> str | None:
    if product is not None:
        if product.get("_scenario_off") or product.get("enabled") is False or product.get("included") is False:
            return "the product is switched off"
    if tokens and tokens[0] == "loan_rollforward" and product is not None:
        lr = product.get("loan_rollforward") or {}
        if lr.get("enabled") is False:
            return "loan production is off"
        src = lr.get("source")
        owner = {"count_spec": "entered_count", "amount_spec": "entered_money",
                 "percentage_spec": "deposit_balance"}.get(tokens[1] if len(tokens) > 1 else "")
        if owner and src != owner:
            return "it belongs to an origination source that is not selected"
    return None


_TIMING_WORDS = ("start", "end", "lag", "month", "term", "day", "year", "quarter", "delay", "horizon", "maturity", "duration", "tenor", "m", "life", "years", "months", "days")


def _is_timing(key) -> bool:
    k = str(key).lower()
    if not any(ch.isalpha() for ch in k):   # schedule points ("1", "12") and dated anchors ("2026-12-31")
        return True
    return "per_period" not in k and ("period" in k or any(w in k.split("_") for w in _TIMING_WORDS))


def _unit_kind(spec, tokens) -> str:
    u = str((spec or {}).get("unit") or "").lower()
    if u in ("rate", "share", "pct", "percent", "fraction"):
        return "rate"
    if u in ("money", "dollars", "money_per_unit"):
        return "money"
    if u in ("count", "units"):
        return "count"
    last = str(tokens[-1] if tokens else "").lower()
    if any(w in last for w in ("fee_yield", "yield", "rate", "beta", "pct", "share", "spread", "percentage",
                               "charge_off", "runoff", "growth", "delta", "attrition", "conversion", "loss", "multiplier")) \
            or last.endswith("_ann"):
        return "rate"
    if any(w in last for w in ("amount", "balance", "opex", "cost", "fee", "salary", "comp", "spend", "expense",
                               "originations", "capital", "intangible", "auc", "flow", "deposits")) or last.endswith("_m"):
        return "money"
    if any(w in last for w in ("count", "fte", "customers", "accounts", "headcount")):
        return "count"
    return "number"


# ---------------------------------------------------------------- economic class (r503): what an input means
# Delay behavior comes from what an input is, never from which rewrite reproduces the base. The contract is
# explicit, keyed on the field's own name; anything not listed is "other" and a delay must state its fill.
ECON_LABELS = {"flow": "flow (new volume each period)", "stock": "stock (an outstanding level)",
               "quantity": "quantity (a level count)", "price": "price or unit amount", "rate": "rate",
               "other": "other driver"}
DELAY_FILL = {"flow": "zero", "stock": "hold", "quantity": "hold", "price": "hold", "rate": "hold", "other": None}
FILL_LABELS = {"zero": "nothing during the delay (zero)", "hold": "held at the level before the delay"}
# r504: classification reads the whole registered path, not the last name alone. A count of new loans in a loan
# roll-forward is a flow; a role's headcount is a level; both are "count". Context rules come first; a generic
# leaf ("count", "amount", "quantity", "volume") with no recognised context is "other" and the user must choose.
_CONTEXT_RULES = (
    (r"(^|\.)loan_rollforward\.count(_spec)?$", "flow", "new loans per period in a loan roll-forward"),
    (r"(^|\.)loan_rollforward\.(loan_size|average_size)(_spec)?$", "price", "size of each new loan"),
    (r"(^|\.)loan_rollforward\.deferred\.(cost|fee)(_spec)?$", "price", "deferred cost or fee per new loan"),
    (r"origination", "flow", "originations (count or amount) per period"),
    (r"(^|\.)workforce\.roles\.count(_spec)?$", "quantity", "active headcount in a role"),
    (r"(^|\.)driver_specs\.ftes$", "quantity", "active relationship staff"),
    (r"(^|\.)cac_feeds\..*\.(new_customers|new_accounts|spend)(_spec)?$", "flow", "acquisition volume or spend per period"),
    (r"(^|\.)funded_flow_driver\.flow_path$", "flow", "funded flow per period"),
    (r"(^|\.)(nie_detail\.categories|cost_pools\..*components)\.flow(_spec)?$", "flow", "expense flow per period"),
    (r"(^|\.)linked_components\.amount(_spec)?$", "price", "amount per driver unit"),
)
_FLOW_LEAVES = ("new_customers", "new_accounts", "acquisitions", "additions", "gross_adds", "spend", "flow", "flow_path",
                "new_volume", "events", "issuance", "draws", "purchases")
_STOCK_LEAVES = ("balance", "base", "auc", "aum", "outstanding", "deposits", "capital", "intangibles", "level", "stock")
_QTY_LEAVES = ("ftes", "fte", "headcount", "pool", "accounts", "customers", "capacity", "branches")
_PRICE_LEAVES = ("comp_per_fte", "cost_per_customer", "unit_fee", "compensation", "avg_auc_per_customer", "cac",
                 "hourly_rate", "per_fte", "salary", "price", "unit_cost", "loan_size", "average_balance_per_customer")
_AMBIGUOUS = ("count", "amount", "quantity", "volume", "value", "spec")


def _norm_path(tokens):
    import re as _re
    return ".".join(t for t in (str(x) for x in tokens) if not _re.fullmatch(r"\[(#\d+|id=.*)\]", t)).lower()


def econ_classify(tokens, unit_kind) -> dict:
    """{"class", "basis"}: the input's economic class and why, from its full registered path."""
    import re as _re
    path = _norm_path(tokens)
    leaf = str(tokens[-1] if tokens else "").lower()
    for suf in ("_spec", "_path"):
        if leaf.endswith(suf) and leaf not in ("flow_path",):
            leaf = leaf[: -len(suf)]
    if unit_kind in ("rate", "bp"):
        return dict(cls="rate", basis="a rate")
    for rx, cls, why in _CONTEXT_RULES:
        if _re.search(rx, path):
            return dict(cls=cls, basis=why)
    if leaf in _AMBIGUOUS:
        return dict(cls="other", basis=f"'{leaf}' alone does not say whether this is new volume or a level")
    if leaf in _FLOW_LEAVES or leaf.startswith("new_"):
        return dict(cls="flow", basis="new volume per period")
    if leaf in _PRICE_LEAVES:
        return dict(cls="price", basis="a price or unit amount")
    if leaf in _QTY_LEAVES:
        return dict(cls="quantity", basis="a level count")
    if leaf in _STOCK_LEAVES or leaf.endswith("_balance"):
        return dict(cls="stock", basis="an outstanding level")
    return dict(cls="other", basis="not in the classification contract")


def econ_class(tokens, unit_kind) -> str:
    return econ_classify(tokens, unit_kind)["cls"]


def delay_fill(ov, cls):
    """The fill for a delay: the override's explicit choice, else the class default; None when undefined."""
    f = ov.get("fill")
    return f if f in FILL_LABELS else DELAY_FILL.get(cls)


def targets(cfg) -> list[dict]:
    """Every entered Series input and numeric setting a scenario can shock, with stable identity.

    Inputs reached through a list element without a stable ID are listed with ``needs_id`` and a
    positional ``locator``; the console assigns ``stable_id`` to those elements before use.
    """
    a = (cfg or {}).get("assumptions") or {}
    rows = []

    def row(fam, fam_label, pid, idx, pname, tokens, val, kind, loc, stable, why, label_root=None):
        ok = bool(pid) and stable
        rows.append(dict(key=f"{fam}:{pid}:{'.'.join(tokens)}" if ok else None, family=fam, family_label=fam_label,
                         product_id=pid, product_index=idx, product_name=pname, field=".".join(tokens),
                         label=_named_label(label_root, tokens), unit_kind=_unit_kind(val if kind == "series" else {}, tokens),
                         econ_class=econ_class(tokens, _unit_kind(val if kind == "series" else {}, tokens)),
                         econ_basis=econ_classify(tokens, _unit_kind(val if kind == "series" else {}, tokens))["basis"],
                         kind=kind, trajectory=val.get("trajectory") if kind == "series" else None,
                         value=val if kind == "scalar" else None, active=why is None, inactive_reason=why,
                         needs_id=not ok, locator=list(loc)))

    for fam, fam_label in FAMILIES.items():
        for idx, p in enumerate(a.get(fam) or []):
            if not isinstance(p, dict):
                continue
            pid = p.get("source_catalog_id") or p.get("stable_id")
            found = []
            _walk(p, [], found, loc=("assumptions", fam, idx))
            for tokens, val, kind, loc, stable in found:
                row(fam, fam_label, pid, idx, p.get("name") or f"{fam_label} {idx + 1}", tokens, val, kind,
                    loc, stable, _inactive(a, fam, p, tokens), label_root=p)
    found = []
    for k, v in a.items():
        if k in _SKIP_BANK_KEYS or (isinstance(k, str) and k.startswith("_")):
            continue
        if isinstance(v, dict) and _is_entered_series(v):
            found.append(((k,), v, "series", ("assumptions", k), True))
        elif isinstance(v, (dict, list)):
            _walk(v, [k], found, loc=("assumptions", k))
        elif isinstance(v, (int, float)) and not isinstance(v, bool) and k not in _SCALAR_SKIP and math.isfinite(float(v)) \
                and not _is_timing(k):
            found.append(((k,), v, "scalar", ("assumptions", k), True))
    for tokens, val, kind, loc, stable in found:
        row("bank", "Bank", "assumptions", None, "Bank-level", tokens, val, kind, loc, stable, None, label_root=a)
    rows.append(dict(key=RATE_KEY, family="bank", family_label="Bank", product_id="rates", product_index=None,
                     product_name="Rates", field="parallel_shift_bp", label="Reference rate path, parallel shift",
                     unit_kind="bp", kind="rate_shift", trajectory=None, value=0, active=True, inactive_reason=None,
                     needs_id=False, locator=[]))
    return rows


# ---------------------------------------------------------------- resolution
class StressError(ValueError):
    pass


def _split_key(key):
    parts = str(key or "").split(":", 2)
    if len(parts) != 3 or not all(parts):
        raise StressError(f"target {key!r} is not a stable input identity")
    return parts


def resolve_target(cfg, key):
    """Return (parent, field, spec, product, family, tokens) for a target key, or raise."""
    fam, pid, field = _split_key(key)
    a = cfg["assumptions"]
    if key == RATE_KEY:
        return None, None, "rate_shift", None, "bank", ["parallel_shift_bp"]
    if fam == "bank" and (field.split(".")[0] in _SKIP_BANK_KEYS or field.startswith("_") or field.split(".")[0] in _SCALAR_SKIP
                          or (len(field.split(".")) == 1 and _is_timing(field))):
        raise StressError(f"{field} is not a supported stress input (structural or timing setting)")
    if fam == "bank":
        node, product = a, None
    elif fam in FAMILIES:
        hits = [p for p in (a.get(fam) or []) if isinstance(p, dict) and (p.get("source_catalog_id") or p.get("stable_id")) == pid]
        if not hits:
            raise StressError(f"no {FAMILIES[fam].lower()} product has ID {pid!r}")
        if len(hits) > 1:
            raise StressError(f"two {FAMILIES[fam].lower()} products share ID {pid!r}")
        node = product = hits[0]
    else:
        raise StressError(f"unknown target family {fam!r}")
    tokens = field.split(".")
    parent, last = None, None
    for t in tokens:
        parent = node
        if t.startswith("[id=") and t.endswith("]"):
            want = t[4:-1]
            if not isinstance(node, list):
                raise StressError(f"{field}: expected a list at {t}")
            hits = [el for el in node if isinstance(el, dict) and str(_eid(el)) == want]
            if len(hits) != 1:
                raise StressError(f"{field}: {'no' if not hits else 'more than one'} element with id {want!r}")
            last, node = hits[0], hits[0]
            continue
        if not isinstance(node, dict) or t not in node:
            raise StressError(f"{field}: {t!r} is not present")
        last, node = t, node[t]
    if not (_is_entered_series(node) or (isinstance(node, (int, float)) and not isinstance(node, bool))):
        raise StressError(f"{field} is not an entered Series input or numeric setting")
    why = _inactive(a, fam, product, tokens)
    if why:
        raise StressError(f"{field} is not active: {why}")
    if key not in registry_keys(cfg):
        raise StressError(f"{field} is not in the supported-input registry")
    return parent, last, node, product, fam, tokens


def registry_keys(cfg) -> set:
    """The supported-input registry: every key the catalog offers. Backend resolution accepts nothing else."""
    return {r["key"] for r in targets(cfg) if r.get("key") and r.get("active")}


def registry(cfg) -> list[dict]:
    """Registry entries with units, bounds and permitted operations."""
    out = []
    for r in targets(cfg):
        if not (r.get("key") and r.get("active")):
            continue
        lo, hi = BOUNDS.get(r["unit_kind"], (None, None))
        out.append(dict(key=r["key"], label=f"{r['product_name']} · {r['label']}", unit_kind=r["unit_kind"], kind=r["kind"],
                        econ_class=r.get("econ_class") or "rate", delay_fill=DELAY_FILL.get(r.get("econ_class") or "rate"),
                        ops=list(OPS), window=r["kind"] == "series", bounds=[lo, hi]))
    return out


def _resolve_path(spec, mode, n, ppy):
    if mode == "level":
        from .series import resolve_entered_series
        return [float(x) for x in resolve_entered_series(spec, n, ppy)]
    from .periodic_flows import resolve_periodic_flow
    return [float(x) for x in resolve_periodic_flow(spec, n, ppy)]


def _rewrite(spec, mode, path, ppy):
    out = {k: v for k, v in spec.items() if k not in (
        "value", "values", "base", "growth_spec", "trajectory", "cadence", "resolution", "extend",
        "schedule", "year_end_targets", "target_path", "base_position")}
    out.update(source="entered", trajectory="explicit", values=list(path))
    if mode == "level":
        out.update(cadence="model_period", resolution="step")
    else:
        out["period"] = _MODEL_PERIOD[int(ppy)]
    return out


def _apply(path, op, value, start, end, fill=0.0):
    n = len(path)
    lo, hi = max(1, int(start or 1)), min(n, int(end) if end not in (None, "") else n)
    out = list(path)
    if op == "delay":   # shift the path right by `value` periods from `start`; vacated periods take `fill`
        k = int(value)
        for i in range(lo - 1, n):
            j = i - k
            out[i] = path[j] if j >= lo - 1 else fill
        return out
    for i in range(lo - 1, hi):
        if op == "multiply":
            out[i] = path[i] * value
        elif op == "add":
            out[i] = path[i] + value
        else:
            out[i] = value
    return out


# ---------------------------------------------------------------- structural validation
def check_scenario(cfg, scenario) -> dict:
    """Structural checks that need no engine run. Returns {"ok", "errors", "warnings"} per severity."""
    errors, warnings = [], []
    a = cfg.get("assumptions") or {}
    n = int(a.get("n_periods") or 12)
    name = scenario.get("name") or "Scenario"
    if scenario.get("kind", "economic") not in KINDS:
        errors.append(f"{name}: kind must be one of {', '.join(KIND_LABELS[k] for k in KINDS)}")
    if scenario.get("funding", "inherit") not in FUNDING:
        errors.append(f"{name}: funding must be inherit, show_shortfall or automatic_borrowing")
    sevs = scenario.get("severities") or []
    if not sevs:
        errors.append(f"{name}: add at least one severity")
    seen_sev = set()
    for sev in sevs:
        sl = sev.get("label") or sev.get("id") or "Severity"
        if sev.get("id") in seen_sev:
            errors.append(f"{name} · {sl}: duplicate severity id")
        seen_sev.add(sev.get("id"))
        ovs = sev.get("overrides") or []
        if not ovs:
            errors.append(f"{name} · {sl}: no overrides")
        windows = {}
        for j, ov in enumerate(ovs, 1):
            where = f"{name} · {sl} · override {j}"
            try:
                _par, _f, spec, product, fam, tokens = resolve_target(cfg, ov.get("target"))
            except StressError as e:
                errors.append(f"{where}: {e}")
                continue
            lab = "Rates · Reference rate path, parallel shift" if spec == "rate_shift" else \
                f"{(product or {}).get('name') or 'Bank-level'} · {_named_label(product or a, tokens)}"
            where = f"{name} · {sl} · {lab}"
            cal = ov.get("calibration") or {}
            if not (str(cal.get("rationale") or "").strip() and str(cal.get("source") or "").strip()):
                warnings.append(f"{where}: add a rationale and a data source to the calibration record")
            if cal.get("approval") not in (None, "") and cal.get("approval") not in APPROVAL:
                errors.append(f"{where}: approval must be draft, reviewed or approved")
            if spec == "rate_shift":
                if ov.get("op") not in ("add", "replace"):
                    errors.append(f"{where}: shift the rate path by a number of basis points (add)")
                if (ov.get("start") or 1) != 1 or ov.get("end") not in (None, "", n):
                    errors.append(f"{where}: the rate path shifts for the whole horizon in this release; a partial window is not available yet")
                v = ov.get("value")
                if not isinstance(v, (int, float)) or isinstance(v, bool) or abs(v) > 1000:
                    errors.append(f"{where}: enter a shift between -1000 and 1000 basis points")
                windows.setdefault(ov.get("target"), []).append((1, n, j)) if not windows.get(ov.get("target")) else \
                    errors.append(f"{where}: overlaps override {windows[ov.get('target')][0][2]} on the same input; combine them into one")
                continue
            if ov.get("op") == "delay":
                v = ov.get("value")
                if not isinstance(spec, dict):
                    errors.append(f"{where}: a single value for the whole horizon cannot be delayed")
                elif not isinstance(v, int) or isinstance(v, bool) or v < 1 or v >= n:
                    errors.append(f"{where}: delay by a whole number of periods from 1 to {n - 1}")
                if ov.get("end") not in (None, "", n):
                    errors.append(f"{where}: a delay runs to the horizon; values shifted past it are dropped and disclosed")
                if isinstance(spec, dict):
                    cls = econ_class(tokens, _unit_kind(spec, tokens))
                    if ov.get("fill") not in (None, "") and ov.get("fill") not in FILL_LABELS:
                        errors.append(f"{where}: the fill during a delay is zero or held at the prior level")
                    elif delay_fill(ov, cls) is None:
                        errors.append(f"{where}: this input is not classed as a flow, stock, quantity, price or rate; "
                                      f"choose what fills the delay (zero, or held at the prior level)")
            if ov.get("op") not in OPS:
                errors.append(f"{where}: operation must be multiply, add or replace")
            v = ov.get("value")
            if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(float(v)):
                errors.append(f"{where}: enter a number")
            elif ov.get("op") == "multiply" and v < 0:
                errors.append(f"{where}: a multiplier cannot be negative")
            s, e = ov.get("start") or 1, ov.get("end")
            if not isinstance(spec, dict) and (s != 1 or e not in (None, "", n)):
                errors.append(f"{where}: this setting has one value for the whole horizon, so it cannot be shocked for part of it")
            if not isinstance(s, int) or s < 1 or s > n:
                errors.append(f"{where}: start must be a model period from 1 to {n}")
            if e not in (None, "") and (not isinstance(e, int) or e < (s if isinstance(s, int) else 1) or e > n):
                errors.append(f"{where}: end must be between the start and period {n}")
            lo, hi = (s if isinstance(s, int) else 1), (e if isinstance(e, int) else n)
            for (plo, phi, pj) in windows.get(ov.get("target"), []):
                if lo <= phi and plo <= hi:
                    errors.append(f"{where}: overlaps override {pj} on the same input; combine them into one")
            windows.setdefault(ov.get("target"), []).append((lo, hi, j))
    if scenario.get("kind") == "combined":
        warnings += combined_warnings(cfg, scenario)
    return dict(ok=not errors, errors=errors, warnings=warnings)


COMPOSITION_RULE = ("A combined scenario carries frozen copies of its parts' overrides. Two parts may not change the same "
                    "input over overlapping periods: that is a conflict to resolve, never silently summed or overwritten.")
_CREDIT_WORDS = ("charge_off", "loss", "provision", "default", "reserve", "pd", "lgd", "nco")


def combined_warnings(cfg, scenario) -> list:
    """A combined scenario's parts are frozen copies; say when a part has changed or gone since it was frozen."""
    out, name = [], scenario.get("name") or "Scenario"
    parts = scenario.get("parts") or []
    if len(parts) < 2:
        out.append(f"{name}: a combined scenario should reference a macroeconomic and an idiosyncratic part")
    by_id = {s.get("id"): s for s in (cfg.get("stress_scenarios") or [])}
    for p in parts:
        cur = by_id.get(p.get("scenario_id"))
        if cur is None:
            out.append(f"{name}: part {p.get('name') or p.get('scenario_id')} no longer exists; its frozen copy is still used")
        elif cur.get("version") != p.get("version"):
            out.append(f"{name}: part {cur.get('name')} changed since it was frozen (v{p.get('version')} to v{cur.get('version')}); refreeze to include the change")
    return out


def _is_credit_target(key) -> bool:
    return any(w in str(key or "").lower().split(":")[-1] for w in _CREDIT_WORDS)


def coverage(cfg) -> dict:
    """Macroeconomic, idiosyncratic and combined coverage, with design warnings."""
    L = [s for s in (cfg.get("stress_scenarios") or []) if isinstance(s, dict)]
    by = {k: [s for s in L if s.get("kind", "economic") == k] for k in KINDS}
    warn = []
    targets_of = lambda s: {o.get("target") for v in s.get("severities") or [] for o in v.get("overrides") or []}
    for s in by["macro"]:
        t = targets_of(s)
        if not any(_is_credit_target(x) for x in t):
            warn.append(f"{s.get('name')}: a macroeconomic scenario needs a calibrated credit deterioration, not rates alone")
    macro_t = set().union(*[targets_of(s) for s in by["macro"]]) if by["macro"] else set()
    for s in by["idiosyncratic"]:
        dup = targets_of(s) & macro_t
        if dup:
            warn.append(f"{s.get('name')}: changes {len(dup)} input(s) the macroeconomic scenario already changes; an idiosyncratic scenario should complement it")
    for s in by["combined"]:
        warn += combined_warnings(cfg, s)
    for s in L:
        for v in s.get("severities") or []:
            for o in v.get("overrides") or []:
                cal = o.get("calibration") or {}
                if not (str(cal.get("rationale") or "").strip() and str(cal.get("source") or "").strip()):
                    warn.append(f"{s.get('name')} · {v.get('label') or v.get('id')}: calibration records are incomplete")
                    break
            else:
                continue
            break
    return dict(counts={k: len(by[k]) for k in KINDS}, warnings=warn, rule=COMPOSITION_RULE,
                complete=bool(by["macro"] and by["idiosyncratic"] and by["combined"]))


# ---------------------------------------------------------------- building stressed configs
def _set_funding(c, funding):
    if funding in ("show_shortfall", "automatic_borrowing"):
        c["assumptions"]["funding_shortfall_policy"] = funding


def build_config(cfg, scenario, severity_id, *, identity=False, modes=None):
    """Deep copy of the base with one severity's overrides applied (identity=True: zero shock)."""
    c = copy.deepcopy({k: v for k, v in cfg.items() if k not in STRESS_KEYS})
    a = c["assumptions"]
    n, ppy = int(a.get("n_periods") or 12), int(a.get("periods_per_year") or 4)
    sev = next((s for s in scenario.get("severities") or [] if s.get("id") == severity_id), None)
    if sev is None:
        raise StressError(f"severity {severity_id!r} not found")
    resolved = []
    for ov in sev.get("overrides") or []:
        parent, field, spec, product, fam, tokens = resolve_target(c, ov["target"])
        s = int(ov.get("start") or 1)
        if spec == "rate_shift":
            bp = 0.0 if identity else float(ov["value"])
            if bp:
                c["scenario_overlays"] = dict(c.get("scenario_overlays") or {})
                c["scenario_overlays"]["rate_shock_bp"] = float(c["scenario_overlays"].get("rate_shock_bp") or 0) + bp
            resolved.append(dict(target=ov["target"], label="Rates · Reference rate path, parallel shift", op=ov["op"],
                                 value=ov["value"], start=1, end=None, mode="rate", base_at_start=0.0, stressed_at_start=bp,
                                 calibration=copy.deepcopy(ov.get("calibration") or {}),
                                 note="floating products reprice through their index and spread; cash, securities and borrowing "
                                      "yields move with the path; fixed-rate contracts keep their rates", exposure=rate_exposure(c)))
            continue
        dropped = None
        if not isinstance(spec, dict):   # numeric setting: one value for the whole horizon
            base = [float(spec)] * n
            new = float(spec) if identity else _apply([float(spec)], ov["op"], float(ov["value"]), 1, 1)[0]
            parent[field] = new
            stressed = [new] * n
            mode = "scalar"
        else:
            mode = (modes or {}).get(ov["target"], "level")
            base = _resolve_path(spec, mode, n, ppy)
            cls = econ_class(tokens, _unit_kind(spec, tokens))
            fp = delay_fill(ov, cls) if ov["op"] == "delay" else None
            if ov["op"] == "delay" and fp is None and not identity:
                raise StressError(f"{(product or {}).get('name') or 'Bank-level'} · {_named_label(product or c['assumptions'], tokens)}: "
                                  f"choose what fills the delay (zero, or held at the prior level)")
            fill = 0.0 if fp == "zero" else (base[s - 2] if s >= 2 else base[0])
            stressed = list(base) if identity else _apply(base, ov["op"], float(ov["value"]), s, ov.get("end"), fill=fill)
            if ov["op"] == "delay" and not identity:
                k = int(ov["value"])
                tail = base[len(base) - k:] if k else []
                dropped = dict(periods=k, fill=FILL_LABELS[fp], fill_policy=fp, fill_source="chosen" if ov.get("fill") in FILL_LABELS else "class default",
                               econ_class=cls, driver=ECON_LABELS[cls],
                               shifted_past_horizon=round(sum(tail), 6) if cls == "flow" else None,
                               note="values shifted past the horizon are dropped; committed costs are unchanged and move only through existing links")
            parent[field] = _rewrite(spec, mode, stressed, ppy)
        lo, hi = BOUNDS.get(_unit_kind(spec if isinstance(spec, dict) else {}, tokens), (None, None))
        bad = [v for v in stressed if (lo is not None and v < lo - 1e-12) or (hi is not None and v > hi + 1e-12)]
        if bad and not identity:
            raise StressError(f"{(product or {}).get('name') or 'Bank-level'} · {_named_label(product or c['assumptions'], tokens)}: "
                              f"stressed value {bad[0]:g} is outside the supported range "
                              f"{'' if lo is None else lo:}{' to ' if hi is not None else ' or more'}{'' if hi is None else hi}")
        resolved.append(dict(target=ov["target"], label=f"{(product or {}).get('name') or 'Bank-level'} · {_named_label(product or c['assumptions'], tokens)}",
                             op=ov["op"], value=ov["value"], start=s, end=ov.get("end"), mode=mode,
                             base_at_start=base[s - 1], stressed_at_start=stressed[s - 1],
                             calibration=copy.deepcopy(ov.get("calibration") or {}),
                             **({"delay": dropped} if dropped else {})))
    if not identity:
        _set_funding(c, scenario.get("funding", "inherit"))
    return c, resolved


# ---------------------------------------------------------------- runs and metrics
_SERIES_IS = ("ni", "nii", "prov", "borrExp", "tax", "pretax")
_SERIES_BS = ("cash", "deposits", "grossLoans", "borrow", "equity", "totalAssets")


def _engine_run(c):
    from .run_q import run_v2
    return run_v2(copy.deepcopy(c))


def _comparable(res):
    f = res.get("financials") or {}
    fu = res.get("funding") or {}
    return _canon({"f": f, "funding": {k: fu.get(k) for k in ("cash_position", "unfunded_cash", "automatic_borrowing", "cash_shortfall")}})


def metrics(res, cfg) -> dict:
    """Engine-calculated measures only. Money in $000s; ratios as fractions."""
    f = res.get("financials") or {}
    is_, bs, rt = f.get("is") or {}, f.get("bs") or {}, f.get("ratios") or {}
    fu = res.get("funding") or {}
    sc = (res.get("scenarios") or {}).get("base") or {}
    a = cfg.get("assumptions") or {}
    ppy = int(a.get("periods_per_year") or 4)
    ni_full = [float(x or 0.) for x in (is_.get("ni") or [])]
    from .stress_report import report_window
    W = report_window(cfg)["periods"]
    ni = ni_full[:W]
    cum, run = [], 0.
    for x in ni:
        run += x
        cum.append(run)
    first_profit = next((i + 1 for i, x in enumerate(ni) if x > 0), None)
    sustained = None
    for i in range(len(ni)):
        if all(x > 0 for x in ni[i:]):
            sustained = i + 1
            break
    peak_loss = min(cum) if cum and min(cum) < 0 else 0.
    peak_loss_p = (cum.index(min(cum)) + 1) if cum and min(cum) < 0 else None
    auto = [float(x or 0.) / 1000. for x in (fu.get("automatic_borrowing") or [])]
    unfunded = [float(x or 0.) / 1000. for x in (fu.get("unfunded_cash") or [])]
    from .run_q import period_label
    lab = lambda p: period_label(p, ppy) if p else None
    floor = next((c2.get("value") for c2 in (cfg.get("constraints") or []) if c2.get("key") == "leverage_min"), None)
    return dict(
        cum_ni=round(sum(ni), 6), cum_ni_full=round(sum(ni_full), 6), window_periods=W, peak_cum_loss=round(peak_loss, 6), peak_cum_loss_period=lab(peak_loss_p),
        first_profitable=lab(first_profit), sustained_profitable=lab(sustained),
        min_tier1_leverage=sc.get("min_leverage_full"), min_tier1_leverage_period=sc.get("min_leverage_full_label"),
        leverage_floor=floor, capital_shortfall_diagnostic=sc.get("capital_shortfall_est"),
        funding_policy=fu.get("policy"),
        max_unfunded_shortfall=round(max(unfunded, default=0.), 6),
        max_requirement_shortfall=round(float(fu.get("max_cash_shortfall") or 0.) / 1000., 6),
        first_shortfall=lab((fu.get("first_shortfall_period") or 0) or None) if fu.get("first_shortfall_period") is not None else None,
        peak_replacement_borrowing=round(max(auto, default=0.), 6),
        borrowing_expense=round(sum(float(x or 0.) for x in (is_.get("borrExp") or [])), 6),
        cum_provision=round(sum(float(x or 0.) for x in (is_.get("prov") or [])), 6),
        cum_nii=round(sum(float(x or 0.) for x in (is_.get("nii") or [])), 6))


def series(res) -> dict:
    f = res.get("financials") or {}
    is_, bs, rt = f.get("is") or {}, f.get("bs") or {}, f.get("ratios") or {}
    fu = res.get("funding") or {}
    out = {k: list(is_.get(k) or []) for k in _SERIES_IS}
    out.update({k: list((bs.get(k) or [])[1:] if len(bs.get(k) or []) == len(is_.get("ni") or []) + 1 else (bs.get(k) or [])) for k in _SERIES_BS})
    out["lev"] = list(rt.get("lev") or [])
    n = len(out["ni"])
    out["unfunded"] = [float(x or 0.) / 1000. for x in (fu.get("unfunded_cash") or [])][-n:] if n else []
    out["auto_borrowing"] = [float(x or 0.) / 1000. for x in (fu.get("automatic_borrowing") or [])][-n:] if n else []
    c, run = [], 0.
    for x in out["ni"]:
        run += float(x or 0.)
        c.append(run)
    out["cum_ni"] = c
    return out


def run_scenario(cfg, scenario, severity_ids=None, *, base_res=None, attribution=True, keep_results=False) -> list[dict]:
    """Zero-shock check, then each severity. Returns one run record per severity.

    The base configuration is never modified; failures are recorded with the named input.
    """
    a = cfg.get("assumptions") or {}
    base_cfg = {k: v for k, v in cfg.items() if k not in STRESS_KEYS}
    fp, eng, sfp = base_fingerprint(cfg), engine_identity(), scenario_fingerprint(scenario)
    before = _canon(base_cfg)
    sevs = [s for s in (scenario.get("severities") or []) if not severity_ids or s.get("id") in severity_ids]
    records = []
    t0 = time.time()
    base_res = base_res or _engine_run(base_cfg)
    base_cmp = _comparable(base_res)
    base_metrics, base_series = metrics(base_res, cfg), series(base_res)
    from .stress_report import report_window
    win = report_window(cfg)
    chk = check_scenario(cfg, scenario)
    for sev in sevs:
        rec = dict(run_id=uuid.uuid4().hex[:12], scenario_id=scenario.get("id"), scenario_name=scenario.get("name"),
                   scenario_version=scenario.get("version"), scenario_fingerprint=sfp, kind=scenario.get("kind", "economic"),
                   severity_id=sev.get("id"), severity_label=sev.get("label"), base_fingerprint=fp, engine=eng,
                   started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), status="running",
                   funding_setting=scenario.get("funding", "inherit"), definition=copy.deepcopy(sev),
                   checks=dict(structural="passed" if chk["ok"] else "failed", zero_shock="not_run"), errors=[])
        try:
            sev_errors = [e for e in chk["errors"] if f"· {sev.get('label') or sev.get('id')}" in e or "·" not in e.split(":")[0]]
            if sev_errors:
                raise StressError("; ".join(sev_errors))
            modes, bad = {}, []
            for ov in sev.get("overrides") or []:
                pr = probe_target(cfg, ov["target"])
                if pr["ok"]:
                    modes[ov["target"]] = pr["mode"]
                else:
                    _p, _f, _s, product, _fam, tokens = resolve_target(cfg, ov["target"])
                    bad.append(f"{(product or {}).get('name') or 'Bank-level'} · {_named_label(product or cfg['assumptions'], tokens)}: {pr['reason']}")
            if bad:
                rec["checks"]["zero_shock"] = "failed"
                raise StressError("Zero-shock check failed. " + " | ".join(bad))
            zc, _ = build_config(cfg, scenario, sev["id"], identity=True, modes=modes)
            if _comparable(_engine_run(zc)) != base_cmp:
                rec["checks"]["zero_shock"] = "failed"
                raise StressError("Zero-shock check failed: the combined rewrite without a shock does not reproduce the base exactly")
            rec["checks"]["zero_shock"] = "passed"
            sc, resolved = build_config(cfg, scenario, sev["id"], modes=modes)
            sr = _engine_run(sc)
            rd = rate_direction(cfg, scenario, sev["id"], modes, sr) if any(o.get("target") == RATE_KEY for o in sev.get("overrides") or []) else None
            if rd:
                rec["rate_direction"] = rd
            if attribution and len(sev.get("overrides") or []) > 0:
                rec["attribution"] = attribute(cfg, scenario, sev["id"], modes, base_res=base_res)
            rec.update(status="completed", resolved_overrides=resolved,
                       funding_policy=(sr.get("funding") or {}).get("policy"),
                       base=dict(metrics=base_metrics, series=base_series),
                       stress=dict(metrics=metrics(sr, dict(sc, stress_reporting=cfg.get("stress_reporting"))), series=series(sr)),
                       window=dict(periods=win["periods"], label=win["label"]),
                       base_run_hash=base_res.get("run_hash"), stress_run_hash=sr.get("run_hash"),
                       no_effect=_comparable(sr) == base_cmp)
            if keep_results:   # evidence for the archive; the caller removes it before storing the record
                rec["_results"] = dict(base_cfg=base_cfg, base_res=base_res, stress_cfg=sc, stress_res=sr)
        except Exception as e:  # recorded, never a healthy column
            rec.update(status="failed", errors=[str(e)])
        rec["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        rec["seconds"] = round(time.time() - t0, 3)
        records.append(rec)
    if _canon(base_cfg) != before:   # defensive: the base must be untouched
        raise RuntimeError("stress run modified the base configuration")
    return records


def assign_stable_ids(cfg, locator) -> bool:
    """Give the product and every list element on ``locator`` a stable ID (in place). Returns True if any changed.

    IDs are inert to calculations; they let a scenario keep pointing at the same input after renames
    and reordering.
    """
    node, changed = cfg, False
    loc = list(locator or [])
    for i, step in enumerate(loc):
        if isinstance(node, list) and isinstance(step, int):
            el = node[step]
            if isinstance(el, dict) and not (el.get("source_catalog_id") or el.get("stable_id") or (el.get("id") and i > 2)):
                el["stable_id"] = "sid-" + uuid.uuid4().hex[:10]
                changed = True
            node = el
        elif isinstance(node, dict):
            node = node.get(step)
        else:
            break
    return changed


_PROBE_CACHE: dict = {}


def probe_target(cfg, key) -> dict:
    """Executed check for one input: can it be rewritten without a shock and reproduce the base exactly?

    Returns {"ok", "mode", "reason"}. Cached per base fingerprint, engine and target.
    """
    ck = (base_fingerprint(cfg), engine_identity(), key)
    if ck in _PROBE_CACHE:
        return dict(_PROBE_CACHE[ck])
    try:
        _p, _f, spec, *_ = resolve_target(cfg, key)
    except StressError as e:
        return dict(ok=False, mode=None, reason=str(e))
    if spec == "rate_shift":
        out = dict(ok=True, mode="rate", reason=None, exposure=rate_exposure(cfg))
        _PROBE_CACHE[ck] = out
        return dict(out)
    if not isinstance(spec, dict):
        out = dict(ok=True, mode="scalar", reason=None)
        _PROBE_CACHE[ck] = out
        return dict(out)
    base_cfg = {k: v for k, v in cfg.items() if k not in STRESS_KEYS}
    base_cmp = _comparable(_engine_run(base_cfg))
    sc = dict(id="probe", severities=[dict(id="p", overrides=[dict(target=key, op="multiply", value=1, start=1)])])
    reasons = []
    modes = ["level"] + (["flow"] if str(spec.get("period") or "") in ("month", "quarter", "year") else [])
    out = None
    for mode in modes:
        try:
            zc, _ = build_config(cfg, sc, "p", identity=True, modes={key: mode})
            if _comparable(_engine_run(zc)) == base_cmp:
                out = dict(ok=True, mode=mode, reason=None)
                break
            reasons.append(f"{mode} rewrite changes the base")
        except Exception as e:
            reasons.append(str(e).split(";")[0][:160])
    if out is None:
        out = dict(ok=False, mode=None, reason="the model reads this input in a form a scenario cannot rewrite yet (" + "; ".join(reasons) + ")")
    _PROBE_CACHE[ck] = out
    return dict(out)


def attribute(cfg, scenario, severity_id, modes, base_res=None) -> dict:
    """Isolated one-at-a-time effects on cumulative net income, plus the interaction residual.

    Each override runs alone against the base, so order does not matter. Effects that travel through
    links stay inside the override that caused them; they are not separate contributions.
    """
    base_cfg = {k: v for k, v in cfg.items() if k not in STRESS_KEYS}
    base_res = base_res or _engine_run(base_cfg)
    b = metrics(base_res, cfg)["cum_ni"]
    sev = next(s for s in scenario["severities"] if s.get("id") == severity_id)
    rows = []
    for ov in sev.get("overrides") or []:
        one = dict(scenario, severities=[dict(sev, overrides=[ov])])
        c1, res = build_config(cfg, one, severity_id, modes=modes)
        r1 = _engine_run(c1)
        rows.append(dict(target=ov["target"], label=res[0]["label"], effect=round(metrics(r1, dict(c1, stress_reporting=cfg.get("stress_reporting")))["cum_ni"] - b, 6),
                         no_effect=_comparable(r1) == _comparable(base_res)))
    ca, _ = build_config(cfg, scenario, severity_id, modes=modes)
    total = metrics(_engine_run(ca), dict(ca, stress_reporting=cfg.get("stress_reporting")))["cum_ni"] - b
    from .stress_report import report_window
    wl = report_window(cfg)["label"]
    return dict(method="isolated one-at-a-time, interaction residual", metric=f"cumulative net income, {wl}, $000s",
                extra_runs=len(rows), rows=rows, interaction=round(total - sum(r["effect"] for r in rows), 6),
                total=round(total, 6))


def run_state(record, cfg) -> str:
    """Current / Stale for a stored record against the current base and scenario."""
    if record.get("status") != "completed":
        return record.get("status") or "failed"
    if record.get("base_fingerprint") != base_fingerprint(cfg) or record.get("engine") != engine_identity():
        return "stale"
    if record.get("record_type") == "reverse_stress":
        spec = (record.get("reverse") or {}).get("spec") or {}
        if spec.get("kind") != "scale":
            return "current"
    if record.get("record_type") == "liquidity":
        from .liquidity import fingerprint as _lfp
        if record.get("liquidity_fingerprint") != _lfp(cfg):
            return "stale"
        if not record.get("scenario_id"):
            return "current"
    sc = next((s for s in (cfg.get("stress_scenarios") or []) if s.get("id") == record.get("scenario_id")), None)
    if sc is None or scenario_fingerprint(sc) != record.get("scenario_fingerprint"):
        return "stale"
    return "current"


# ---------------------------------------------------------------- rates
def rate_exposure(cfg) -> dict:
    """Which entered rates move with a parallel shift of the reference path, and which do not."""
    a = (cfg or {}).get("assumptions") or {}
    rep_, fixed = [], []
    for fam, lab in (("lending_products", "Lending"), ("deposit_products", "Deposit")):
        for p in a.get(fam) or []:
            if not isinstance(p, dict):
                continue
            nm = f"{lab} · {p.get('name') or 'product'}"
            (rep_ if p.get("rate_type") == "float" else fixed).append(nm)
    bank = [lab for k, lab in (("cash_yield", "Cash yield"), ("securities_yield", "Securities yield"),
                               ("borrow_rate_ann", "Borrowing rate")) if a.get(k) is not None]
    return dict(reprice=rep_, fixed=fixed, bank_yields_shifted=bank,
                note="Fixed-rate contracts keep their entered rates. Rates are floored at zero after the shift.")


def _window_measures(res, cfg):
    from .stress_report import report_window
    W = report_window(cfg)["periods"]
    ni = [float(x or 0.0) for x in ((res.get("financials") or {}).get("is") or {}).get("ni") or []][:W]
    lev = [x for x in (((res.get("capital") or {}).get("rows") or {}).get("leverage") or [])[:W] if x is not None]
    return dict(cum_ni=round(sum(ni), 6), min_leverage=round(min(lev) * 100, 6) if lev else None)


def rate_direction(cfg, scenario, severity_id, modes, applied_res):
    """Run the mirrored rate shift and say which direction is adverse for earnings and for capital.

    Adverse is judged per measure over the reporting window; when the two measures disagree both are reported."""
    sev = next(s for s in scenario["severities"] if s.get("id") == severity_id)
    ov = next((o for o in sev.get("overrides") or [] if o.get("target") == RATE_KEY), None)
    if ov is None or not float(ov.get("value") or 0):
        return None
    mir = dict(scenario, severities=[dict(sev, overrides=[dict(o, value=-float(o["value"])) if o.get("target") == RATE_KEY else o
                                                          for o in sev.get("overrides") or []])])
    mc, _ = build_config(cfg, mir, severity_id, modes=modes)
    mres = _engine_run(mc)
    rc = dict(cfg, stress_reporting=cfg.get("stress_reporting"))
    a, m = _window_measures(applied_res, rc), _window_measures(mres, rc)
    bp = float(ov["value"])
    earn = "applied" if a["cum_ni"] <= m["cum_ni"] else "mirrored"
    cap = None if a["min_leverage"] is None or m["min_leverage"] is None else ("applied" if a["min_leverage"] <= m["min_leverage"] else "mirrored")
    return dict(applied_bp=bp, mirrored_bp=-bp, applied=a, mirrored=m,
                adverse_for_earnings=bp if earn == "applied" else -bp,
                adverse_for_capital=None if cap is None else (bp if cap == "applied" else -bp),
                agree=cap is None or earn == cap, extra_runs=1)


# ---------------------------------------------------------------- reproducibility
def scenario_from_record(record) -> dict:
    """The exact scenario a record ran: its frozen severity definition and funding setting."""
    return dict(id=record.get("scenario_id"), name=record.get("scenario_name"), kind=record.get("kind", "economic"),
                funding=record.get("funding_setting", "inherit"), version=record.get("scenario_version"),
                severities=[copy.deepcopy(record.get("definition") or {})])


def rerun_from_archive(baseline_cfg, record) -> dict:
    """Rebuild and rerun a completed record from its archived baseline. Returns {"reproduced", "run_hash"}."""
    sc = scenario_from_record(record)
    modes = {o["target"]: o["mode"] for o in (record.get("resolved_overrides") or []) if o.get("mode") != "scalar"}
    c, _ = build_config(baseline_cfg, sc, (record.get("definition") or {}).get("id"), modes=modes)
    r = _engine_run(c)
    return dict(reproduced=r.get("run_hash") == record.get("stress_run_hash"), run_hash=r.get("run_hash"),
                expected=record.get("stress_run_hash"))
