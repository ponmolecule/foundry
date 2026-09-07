"""Grounded Fee Product "Guide Me" translator.

The LLM is deliberately NOT an economic adviser. It receives only:
  * the user's free-text description of the fee mechanics; and
  * a machine-readable manifest derived from Foundry's current fee-engine vocabulary.

It has no tools, no retrieval and no engagement configuration. The returned plan is
validated against the same fee-stream evaluator before it is rendered to the user.
Anything outside the engine vocabulary fails closed.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import urllib.error
import urllib.request

from .income_modules import (
    _FEE_BASES,
    _FEE_SOURCES,
    _FEE_TRAJECTORIES,
    _FEE_RATE_BEHAVIORS,
    _FEE_COST_KINDS,
    _FEE_NATURAL_PERIODS,
    _validate_fee_stream_shape,
)

GUIDE_SCHEMA_VERSION = 1
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5"


def resolve_anthropic_api_key():
    """Resolve the server-side Anthropic credential without exposing it to the client.

    Foundry historically supported two server configuration paths: the standard
    ``ANTHROPIC_API_KEY`` environment variable and ``config.settings.ANTHROPIC_API_KEY``.
    Guide Me must reuse that existing server configuration rather than require a
    second/parallel secret setup. Environment wins when both are present.
    """
    key = str(os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if key:
        return key, "environment"

    try:
        settings_mod = importlib.import_module("config.settings")
    except Exception:
        settings_mod = None

    if settings_mod is not None:
        value = getattr(settings_mod, "ANTHROPIC_API_KEY", "")
        # Be compatible with SecretStr-like settings objects without depending on
        # pydantic or another configuration package.
        if hasattr(value, "get_secret_value"):
            try:
                value = value.get_secret_value()
            except Exception:
                value = ""
        key = str(value or "").strip()
        if key:
            return key, "config.settings"

        settings_obj = getattr(settings_mod, "settings", None)
        value = getattr(settings_obj, "ANTHROPIC_API_KEY", "") if settings_obj is not None else ""
        if hasattr(value, "get_secret_value"):
            try:
                value = value.get_secret_value()
            except Exception:
                value = ""
        key = str(value or "").strip()
        if key:
            return key, "config.settings.settings"

    return "", None


def anthropic_config_status():
    key, source = resolve_anthropic_api_key()
    return {
        "configured": bool(key),
        "credential_source": source,
        "model": os.environ.get("FOUNDRY_GUIDE_MODEL") or DEFAULT_MODEL,
    }

_BASIS_LABELS = {
    "balance": "Balance — stock × annual rate",
    "transaction": "Transaction / throughput — volume × fee or spread",
    "account": "Account — count × fee",
    "flat": "Flat — periodic amount",
    "event": "Event — one-time amount",
}
_SOURCE_LABELS = {
    "constant": "Constant (you enter)",
    "own_balance": "Own on-book balance",
    "managed_notional": "Managed notional (AUC/AUM)",
    "stream_ref": "Another stream",
    "bank_aggregate": "Bank aggregate",
}
_TRAJECTORY_LABELS = {
    "flat": "Flat",
    "proportional": "Proportional growth",
    "ramp_to_target": "Ramp to target",
    "explicit_schedule": "Explicit schedule",
    "derived": "Derived (× source)",
}
_RATE_LABELS = {
    "flat": "Flat",
    "annual_change": "Annual change",
    "scheduled": "Scheduled",
    "tiered": "Tiered",
    "durbin_capped": "Durbin capped",
}
_COST_LABELS = {
    "none": "None (pure margin)",
    "per_unit": "Cost per unit",
    "pct_of_revenue": "% of revenue / revenue share",
}
_ALLOWED_RATE_BY_BASIS = {
    "balance": {"flat", "annual_change", "scheduled", "tiered"},
    "transaction": {"flat", "tiered", "durbin_capped"},
    "account": {"flat"},
    "flat": {"flat"},
    "event": {"flat"},
}


def fee_guide_manifest():
    """Return the closed fee-engine vocabulary exposed to Guide Me.

    The IDs come from the current evaluator constants, so the guide cannot quietly
    grow a parallel product taxonomy. Labels/instructions mirror the current UI.
    """
    return {
        "schema_version": GUIDE_SCHEMA_VERSION,
        "principle": "Map user-described mechanics to Foundry shapes. Do not invent product types or assumptions.",
        "bases": [{"id": x, "label": _BASIS_LABELS[x]} for x in sorted(_FEE_BASES)],
        "driver_sources": [{"id": x, "label": _SOURCE_LABELS[x]} for x in sorted(_FEE_SOURCES)],
        "driver_trajectories": [{"id": x, "label": _TRAJECTORY_LABELS[x]} for x in sorted(_FEE_TRAJECTORIES)],
        "rate_behaviors": [{"id": x, "label": _RATE_LABELS[x]} for x in sorted(_FEE_RATE_BEHAVIORS)],
        "cost_kinds": [{"id": x, "label": _COST_LABELS[x]} for x in sorted(_FEE_COST_KINDS)],
        "natural_periods": sorted(_FEE_NATURAL_PERIODS - {"model_period"}),
        "rate_behavior_by_basis": {k: sorted(v) for k, v in _ALLOWED_RATE_BY_BASIS.items()},
        "special_rules": [
            "Natural-period flow coefficients are valid only on transaction basis with driver trajectory derived.",
            "A derived flow coefficient kind is multiple (turns × source) or pct (% of source).",
            "Account fees may be stated per month, quarter, or year.",
            "Flat amounts may be stated per month, quarter, or year.",
            "per_unit cost is valid only for transaction basis.",
            "A managed_notional driver means the product's AUC/AUM series; it may come from manual AUC or a Customer-Acquisition feed.",
            "The guide never chooses numeric assumptions. It tells the user which Foundry field should receive each assumption they already have.",
        ],
    }


def _system_prompt():
    manifest = json.dumps(fee_guide_manifest(), sort_keys=True, separators=(",", ":"))
    return f"""You are Foundry Fee Guide, a constrained schema translator.

You are NOT a banking adviser and must not use external facts, market conventions, web knowledge,
or unstated assumptions. The only actionable vocabulary you may use is the Foundry engine manifest
below. Your job is to translate the user's description into the dials already supported by Foundry.
If the description is ambiguous, ask a clarification question. If a requested mechanic cannot be
represented by the manifest, return status=unsupported. Never invent a rate, volume, timing value,
product taxonomy, reporting line, or business assumption.

FOUNDRY_ENGINE_MANIFEST={manifest}

Return ONLY one JSON object with this exact shape:
{{
  "status": "plan" | "needs_clarification" | "unsupported",
  "product_label": "short label using only words from the user's description",
  "managed_notional_source": "manual" | "customer_acquisition_feed" | "not_needed" | "ask",
  "streams": [
    {{
      "name": "short stream label using only words from the user's description",
      "basis": "one manifest basis id",
      "driver_source": "one manifest driver source id",
      "driver_trajectory": "one manifest trajectory id",
      "coefficient_kind": null | "multiple" | "pct",
      "coefficient_period": null | "month" | "quarter" | "year",
      "coefficient_trajectory": null | "flat" | "growth" | "explicit_schedule",
      "rate_behavior": "one rate behavior allowed for that basis",
      "cost_kind": "one manifest cost id"
    }}
  ],
  "questions": ["clarification questions only; empty when status=plan"]
}}

Rules:
- Do not output numeric values from your own knowledge. Numbers explicitly supplied by the user are
  still not needed in this plan; the local Foundry UI will tell them where to enter those numbers.
- For fee/spread on annualized throughput derived from AUC/AUM, use transaction + managed_notional +
  derived with an explicit coefficient kind/period.
- For a fee charged on a stock such as AUC/AUM itself, use balance + managed_notional.
- Use account only when the user's mechanic is count × fee per account/mandate/relationship.
- Use flat only for a recurring fixed amount; event only for a one-time amount.
- Do not mention anything that is not present in the user's description or the manifest.
"""


def _extract_json(text):
    s = str(text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
        s = re.sub(r"\s*```$", "", s)
    try:
        return json.loads(s)
    except Exception:
        # Last-resort extraction of one object; still validated strictly afterward.
        a, b = s.find("{"), s.rfind("}")
        if a >= 0 and b > a:
            return json.loads(s[a:b + 1])
        raise ValueError("Guide Me returned non-JSON output")


def _dummy_stream(item):
    basis = item["basis"]
    traj = item["driver_trajectory"]
    driver = {"source": item["driver_source"], "trajectory": traj, "params": {}}
    if item.get("coefficient_kind") is not None:
        driver["params"]["coefficient"] = {
            "kind": item["coefficient_kind"],
            "value": 0,
            "period": item["coefficient_period"],
            "trajectory": item["coefficient_trajectory"] or "flat",
        }
        if item.get("coefficient_trajectory") == "growth":
            # Satisfy evaluator shape validation without selecting an economic growth assumption.
            driver["params"]["coefficient"]["growth_spec"] = {
                "rate": 0, "period": "year", "method": "smooth", "anchor": "model_year"
            }
        elif item.get("coefficient_trajectory") == "explicit_schedule":
            driver["params"]["coefficient"]["schedule"] = {}
    rate = {"behavior": item["rate_behavior"], "params": {}}
    if basis == "balance":
        rate["params"]["rate"] = 0
    elif basis == "transaction":
        rate["params"]["per_unit"] = 0
    elif basis == "account":
        rate["params"]["unit_fee"] = {"value": 0, "period": "year"}
    elif basis == "flat":
        rate["params"]["flat_amount"] = {"value": 0, "period": "year"}
    elif basis == "event":
        rate["params"]["amount"] = 0
    return {
        "basis": basis,
        "driver": driver,
        "rate": rate,
        "timing": {"start_period": 1},
        "cost": {"kind": item["cost_kind"], "params": {}},
    }


def validate_guide_plan(plan):
    if not isinstance(plan, dict):
        raise ValueError("Guide Me response must be an object")
    allowed_plan = {"status", "product_label", "managed_notional_source", "streams", "questions"}
    extra_plan = set(plan) - allowed_plan
    if extra_plan:
        raise ValueError(f"Guide Me returned unsupported top-level fields: {sorted(extra_plan)}")
    status = str(plan.get("status") or "")
    if status not in {"plan", "needs_clarification", "unsupported"}:
        raise ValueError("Guide Me returned unsupported status")
    mns = str(plan.get("managed_notional_source") or "ask")
    if mns not in {"manual", "customer_acquisition_feed", "not_needed", "ask"}:
        raise ValueError("Guide Me returned unsupported managed-notional source")
    streams = plan.get("streams") or []
    if not isinstance(streams, list) or len(streams) > 20:
        raise ValueError("Guide Me returned invalid stream list")
    if status == "plan" and not streams:
        raise ValueError("Guide Me plan must contain at least one stream")
    out_streams = []
    for raw in streams:
        if not isinstance(raw, dict):
            raise ValueError("Guide Me stream must be an object")
        allowed_stream = {"name", "basis", "driver_source", "driver_trajectory", "coefficient_kind",
                          "coefficient_period", "coefficient_trajectory", "rate_behavior", "cost_kind"}
        extra_stream = set(raw) - allowed_stream
        if extra_stream:
            raise ValueError(f"Guide Me returned unsupported stream fields: {sorted(extra_stream)}")
        item = {
            "name": str(raw.get("name") or "Fee stream")[:120],
            "basis": str(raw.get("basis") or ""),
            "driver_source": str(raw.get("driver_source") or ""),
            "driver_trajectory": str(raw.get("driver_trajectory") or ""),
            "coefficient_kind": raw.get("coefficient_kind"),
            "coefficient_period": raw.get("coefficient_period"),
            "coefficient_trajectory": raw.get("coefficient_trajectory"),
            "rate_behavior": str(raw.get("rate_behavior") or ""),
            "cost_kind": str(raw.get("cost_kind") or "none"),
        }
        if item["basis"] not in _FEE_BASES:
            raise ValueError(f"Guide Me invented unsupported basis {item['basis']!r}")
        if item["driver_source"] not in _FEE_SOURCES:
            raise ValueError(f"Guide Me invented unsupported driver source {item['driver_source']!r}")
        if item["driver_trajectory"] not in _FEE_TRAJECTORIES:
            raise ValueError(f"Guide Me invented unsupported trajectory {item['driver_trajectory']!r}")
        if item["rate_behavior"] not in _FEE_RATE_BEHAVIORS:
            raise ValueError(f"Guide Me invented unsupported rate behavior {item['rate_behavior']!r}")
        if item["cost_kind"] not in _FEE_COST_KINDS:
            raise ValueError(f"Guide Me invented unsupported cost kind {item['cost_kind']!r}")
        has_coef = item["coefficient_kind"] is not None
        if has_coef:
            if item["coefficient_kind"] not in {"multiple", "pct"}:
                raise ValueError("Guide Me returned unsupported coefficient kind")
            if item["coefficient_period"] not in {"month", "quarter", "year"}:
                raise ValueError("Guide Me returned unsupported coefficient period")
            if item["coefficient_trajectory"] not in {"flat", "growth", "explicit_schedule"}:
                raise ValueError("Guide Me returned unsupported coefficient trajectory")
        elif any(item[k] is not None for k in ("coefficient_period", "coefficient_trajectory")):
            raise ValueError("Guide Me returned coefficient metadata without a coefficient")
        _validate_fee_stream_shape(_dummy_stream(item))
        out_streams.append(item)
    questions = plan.get("questions") or []
    if not isinstance(questions, list):
        raise ValueError("Guide Me questions must be a list")
    return {
        "status": status,
        "product_label": str(plan.get("product_label") or "Fee product")[:160],
        "managed_notional_source": mns,
        "streams": out_streams,
        "questions": [str(q)[:500] for q in questions[:8]],
    }


def _stream_steps(item):
    """Deterministically render exact UI instructions from validated engine IDs."""
    steps = [
        f"Add a {item['basis']} stream and name it “{item['name']}”.",
        f"Set Basis to “{_BASIS_LABELS[item['basis']]}”.",
        f"Set Driver source to “{_SOURCE_LABELS[item['driver_source']]}”.",
        f"Set Trajectory to “{_TRAJECTORY_LABELS[item['driver_trajectory']]}”.",
    ]
    if item.get("coefficient_kind"):
        steps.append("Under Flow coefficient, choose “× source” if the assumption is turns/multiple, or “% of source” if it is a percentage; use the selection shown below.")
        steps.append(f"Choose Flow coefficient = “{'× source' if item['coefficient_kind']=='multiple' else '% of source'}”, Per = “{item['coefficient_period'].title()}”, and Coefficient path = “{item['coefficient_trajectory'].replace('_',' ').title()}”.")
        steps.append("Enter your source-model turns/multiple or flow percentage in the corresponding field; Foundry handles cadence conversion.")
    if item["basis"] == "balance":
        steps.append("Enter the annual fee in “Rate (bp/yr on balance)”.")
    elif item["basis"] == "transaction":
        if item.get("coefficient_kind"):
            steps.append("Enter the fee/spread in “Fee (% of throughput)”.")
        else:
            steps.append("Enter the fee in “Fee ($/unit)”.")
    elif item["basis"] == "account":
        steps.append("Enter the amount in “Fee ($000s/account)” and choose its natural Month / Quarter / Year period.")
    elif item["basis"] == "flat":
        steps.append("Enter the recurring amount in “Amount ($000s)” and choose its natural Month / Quarter / Year period.")
    elif item["basis"] == "event":
        steps.append("Enter the one-time “Amount ($)” and the model period when the event occurs.")
    steps.append(f"Set Rate behavior to “{_RATE_LABELS[item['rate_behavior']]}”.")
    steps.append(f"Set Cost side to “{_COST_LABELS[item['cost_kind']]}”.")
    steps.append("Set Revenue start/end/ramp only if your source model specifies timing; otherwise leave the default start and no end.")
    return steps


def render_guide_plan(plan):
    validated = validate_guide_plan(plan)
    validated["stream_guides"] = [
        {"name": st["name"], "steps": _stream_steps(st)} for st in validated["streams"]
    ]
    if validated["managed_notional_source"] == "customer_acquisition_feed":
        validated["product_setup"] = "At the top of the Fee Product, set AUC source to the appropriate Customer-Acquisition feed. Do not duplicate the AUC path inside the fee stream."
    elif validated["managed_notional_source"] == "manual":
        validated["product_setup"] = "At the top of the Fee Product, keep AUC source on Manual and author the product's AUC/AUM trajectory there."
    elif validated["managed_notional_source"] == "not_needed":
        validated["product_setup"] = "This mapping does not require the product-level AUC/AUM source."
    else:
        validated["product_setup"] = "If any stream is driven by AUC/AUM, choose whether that AUC/AUM comes from Manual assumptions or a Customer-Acquisition feed."
    return validated


def _anthropic_request(payload, api_key, timeout=25, http_open=None):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ANTHROPIC_MESSAGES_URL,
        data=data,
        method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
    )
    opener = http_open or urllib.request.urlopen
    try:
        with opener(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Claude API error {e.code}: {detail}") from e
    except Exception as e:
        raise RuntimeError(f"Claude API request failed: {e}") from e


def guide_fee_product(description, api_key=None, model=None, http_open=None):
    desc = str(description or "").strip()
    if not desc:
        raise ValueError("Describe the fee product you are trying to model")
    if len(desc) > 6000:
        raise ValueError("Guide Me description is limited to 6,000 characters")
    if api_key is not None:
        key = str(api_key or "").strip()
    else:
        key, _source = resolve_anthropic_api_key()
    if not key:
        raise RuntimeError("Anthropic credentials are not configured (checked ANTHROPIC_API_KEY and config.settings.ANTHROPIC_API_KEY)")
    mdl = model or os.environ.get("FOUNDRY_GUIDE_MODEL") or DEFAULT_MODEL
    payload = {
        "model": mdl,
        "max_tokens": 2200,
        "system": _system_prompt(),
        "messages": [{"role": "user", "content": desc}],
        # Intentionally NO tools, web search, retrieval, URLs, files, or engagement config.
    }
    raw = _anthropic_request(payload, key, http_open=http_open)
    blocks = raw.get("content") or []
    text = "".join(str(b.get("text") or "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
    plan = _extract_json(text)
    out = render_guide_plan(plan)
    out["model"] = mdl
    out["grounding"] = "Foundry fee-engine manifest only; no tools/retrieval/engagement data supplied"
    return out
