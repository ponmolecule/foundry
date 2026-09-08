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
import tempfile

from .income_modules import (
    _FEE_BASES,
    _FEE_SOURCES,
    _FEE_TRAJECTORIES,
    _FEE_RATE_BEHAVIORS,
    _FEE_COST_KINDS,
    _FEE_NATURAL_PERIODS,
    _validate_fee_stream_shape,
)

GUIDE_SCHEMA_VERSION = 4
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5"


def _foundry_data_dir():
    return os.environ.get("FOUNDRY_DATA_DIR") or os.path.join(os.getcwd(), "data")


def anthropic_key_file_path():
    """Return the server-local secret file used by Foundry Guide Me.

    The path may be overridden for managed deployments, otherwise it lives on the
    same persistent data volume as Foundry authentication/session state. The file
    is never served to the browser or included in deployment bundles.
    """
    override = str(os.environ.get("FOUNDRY_ANTHROPIC_KEY_FILE") or "").strip()
    if override:
        return os.path.abspath(os.path.expanduser(override))
    return os.path.join(_foundry_data_dir(), "secrets", "anthropic_api_key")


def store_anthropic_api_key(api_key):
    """Persist an Anthropic key server-side with restrictive permissions.

    This is intended for the authenticated admin setup endpoint. It deliberately
    stores only the secret itself -- no engagement/model data and no browser-readable
    configuration artifact.
    """
    key = str(api_key or "").strip()
    if len(key) < 20 or any(ch.isspace() for ch in key):
        raise ValueError("Enter a valid Anthropic API key")
    path = anthropic_key_file_path()
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".anthropic_api_key.", dir=parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(key + "\n")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
    return path


def resolve_anthropic_api_key():
    """Resolve the server-side Anthropic credential without exposing it to the client.

    Resolution order is intentionally deployment-safe:
      1. ANTHROPIC_API_KEY (standard shared deployment secret)
      2. FOUNDRY_ANTHROPIC_API_KEY (Foundry-specific deployment secret)
      3. Foundry's persistent server-side secret file
      4. config.settings fallback for co-located/legacy deployments

    Foundry never copies a credential from another application's source tree and
    never ships a credential in a release bundle.
    """
    key = str(os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if key:
        return key, "environment"

    key = str(os.environ.get("FOUNDRY_ANTHROPIC_API_KEY") or "").strip()
    if key:
        return key, "foundry_environment"

    path = anthropic_key_file_path()
    try:
        with open(path, encoding="utf-8") as fh:
            key = str(fh.read() or "").strip()
        if key:
            return key, "foundry_secret_file"
    except (OSError, UnicodeError):
        pass

    try:
        settings_mod = importlib.import_module("config.settings")
    except Exception:
        settings_mod = None

    if settings_mod is not None:
        value = getattr(settings_mod, "ANTHROPIC_API_KEY", "")
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
        "flat_amount_trajectories": ["flat", "growth", "explicit_schedule"],
        "rate_behavior_by_basis": {k: sorted(v) for k, v in _ALLOWED_RATE_BY_BASIS.items()},
        "special_rules": [
            "Natural-period flow coefficients are valid only on transaction basis with driver trajectory derived.",
            "A derived flow coefficient kind is multiple (turns × source) or pct (% of source).",
            "Account fees may be stated per month, quarter, or year.",
            "Flat amounts may be stated per month, quarter, or year and may use flat, growth, or explicit_schedule amount trajectories.",
            "per_unit cost is valid only for transaction basis.",
            "A managed_notional driver means the product's AUC/AUM series; it may come from manual AUC or a Customer-Acquisition feed.",
            "The guide never chooses numeric assumptions. It tells the user which Foundry field should receive each assumption they already have.",
        ],
    }


def _guide_output_schema():
    """Compact JSON Schema used for Anthropic Structured Outputs.

    Keep the transport schema deliberately shallow. Foundry's local validator remains
    authoritative for semantic compatibility (for example, which rate behaviors are
    valid for a given basis). This avoids compiling five near-duplicate ``anyOf``
    branches on the first Guide Me request, which can create unnecessary latency at
    web-proxy boundaries.
    """
    stream_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string"},
            "basis": {"type": "string", "enum": sorted(_FEE_BASES)},
            "driver_source": {"type": "string", "enum": sorted(_FEE_SOURCES)},
            "driver_trajectory": {"type": "string", "enum": sorted(_FEE_TRAJECTORIES)},
            # Anthropic Structured Outputs currently rejects an enum on a
            # nullable type-array in some API paths (for example
            # type=["string","null"] with enum=["multiple",...,null]).
            # Keep the transport grammar simple and string-only; the sentinel is
            # normalized back to None before Foundry's semantic validator runs.
            "coefficient_kind": {
                "type": "string", "enum": ["multiple", "pct", "not_applicable"]
            },
            "coefficient_period": {
                "type": "string", "enum": ["month", "quarter", "year", "not_applicable"]
            },
            "coefficient_trajectory": {
                "type": "string",
                "enum": ["flat", "growth", "explicit_schedule", "not_applicable"],
            },
            "flat_amount_trajectory": {
                "type": "string",
                "enum": ["flat", "growth", "explicit_schedule", "not_applicable"],
            },
            "rate_behavior": {"type": "string", "enum": sorted(_FEE_RATE_BEHAVIORS)},
            "cost_kind": {"type": "string", "enum": sorted(_FEE_COST_KINDS)},
        },
        "required": [
            "name", "basis", "driver_source", "driver_trajectory",
            "coefficient_kind", "coefficient_period", "coefficient_trajectory",
            "flat_amount_trajectory", "rate_behavior", "cost_kind",
        ],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "status": {"type": "string", "enum": ["plan", "needs_clarification", "unsupported"]},
            "product_label": {"type": "string"},
            "managed_notional_source": {
                "type": "string",
                "enum": ["manual", "customer_acquisition_feed", "not_needed", "ask"],
            },
            "streams": {"type": "array", "items": stream_schema},
            "questions": {"type": "array", "items": {"type": "string"}},
            "unsupported_mechanics": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "status", "product_label", "managed_notional_source",
            "streams", "questions", "unsupported_mechanics",
        ],
    }


def _system_prompt():
    manifest = json.dumps(fee_guide_manifest(), sort_keys=True, separators=(",", ":"))
    return f"""You are Foundry Fee Guide, a constrained schema translator.

You are NOT a banking adviser and must not use external facts, market conventions, web knowledge,
or unstated assumptions. The only actionable vocabulary you may use is the Foundry engine manifest
below. Your job is to translate the user's description into the dials already supported by Foundry.
Never invent a rate, volume, timing value, product taxonomy, reporting line, or business assumption.

FOUNDRY_ENGINE_MANIFEST={manifest}

The API constrains your response to Foundry's JSON schema. Populate it under these rules:
- status=plan only when every requested mechanic maps cleanly and no clarification is needed.
- status=needs_clarification when the mechanic is supported but the user's description omits a
  choice/value needed to select the correct Foundry path. Put targeted questions in questions.
- status=unsupported when any requested mechanic cannot be represented by the manifest. For a mixed
  request, STILL put every supported stream in streams and list only the unsupported pieces in
  unsupported_mechanics. Do not discard a supported stream just because another one is unsupported.
- Keep unsupported_mechanics empty unless status=unsupported. Keep questions empty when status=plan.
- Treat separate revenue equations as separate streams; do not collapse them into one stream.
- Do not output numeric values from your own knowledge. Numbers explicitly supplied by the user are
  not needed in the mapping object; the local Foundry UI tells the user where to enter them.
- If the user describes a ramp/normalization/path but does not give enough values or a growth rule to
  author that path, ask for those values/rule rather than inventing them.
- For fee/spread on annualized throughput derived from AUC/AUM, use transaction + managed_notional +
  driver_trajectory=derived with an explicit coefficient kind/period. The turns/multiple path belongs
  in coefficient_trajectory; never place that path in driver_trajectory.
- For a fee charged on a stock such as AUC/AUM itself, use balance + managed_notional.
- Use account only when the user's mechanic is count × fee per account/mandate/relationship.
- Use flat for a recurring fixed-dollar amount and set flat_amount_trajectory to flat, growth, or
  explicit_schedule according to the user's stated amount path. A changing Flat amount is supported
  through Amount path; do not confuse that with Rate behavior, which remains flat for the Flat basis.
- Use event only for a one-time amount. Obey rate_behavior_by_basis exactly.
- For coefficient_kind, coefficient_period, coefficient_trajectory, and flat_amount_trajectory, use the string "not_applicable" when that field does not apply to the stream.
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
        fat = item.get("flat_amount_trajectory") or "flat"
        rate["params"]["flat_amount"] = {"value": 0, "period": "year", "trajectory": fat}
        if fat == "growth":
            rate["params"]["flat_amount"]["growth_spec"] = {
                "rate": 0, "period": "year", "method": "smooth", "anchor": "model_year"
            }
        elif fat == "explicit_schedule":
            rate["params"]["flat_amount"]["schedule"] = {"1": 0}
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
    allowed_plan = {"status", "product_label", "managed_notional_source", "streams", "questions", "unsupported_mechanics"}
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
                          "coefficient_period", "coefficient_trajectory", "flat_amount_trajectory",
                          "rate_behavior", "cost_kind"}
        extra_stream = set(raw) - allowed_stream
        if extra_stream:
            raise ValueError(f"Guide Me returned unsupported stream fields: {sorted(extra_stream)}")
        def _transport_optional(value):
            return None if value in (None, "not_applicable") else value

        item = {
            "name": str(raw.get("name") or "Fee stream")[:120],
            "basis": str(raw.get("basis") or ""),
            "driver_source": str(raw.get("driver_source") or ""),
            "driver_trajectory": str(raw.get("driver_trajectory") or ""),
            "coefficient_kind": _transport_optional(raw.get("coefficient_kind")),
            "coefficient_period": _transport_optional(raw.get("coefficient_period")),
            "coefficient_trajectory": _transport_optional(raw.get("coefficient_trajectory")),
            "flat_amount_trajectory": _transport_optional(raw.get("flat_amount_trajectory")),
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
            # A natural-period flow coefficient (turns/multiple or pct of source) is, by
            # definition, the derivation of the sourced quantity. The coefficient owns its
            # own flat/growth/explicit path; the upstream AUC/other source remains a stock.
            # Structured Outputs cannot express this cross-field implication without bringing
            # back the large anyOf grammar we deliberately removed. Canonicalize the redundant
            # driver trajectory here rather than rejecting an otherwise valid mapping. This is
            # structural normalization only -- it invents no economic value or path.
            item["driver_trajectory"] = "derived"
        elif any(item[k] is not None for k in ("coefficient_period", "coefficient_trajectory")):
            raise ValueError("Guide Me returned coefficient metadata without a coefficient")
        if item["basis"] == "flat":
            if item["flat_amount_trajectory"] not in {"flat", "growth", "explicit_schedule"}:
                raise ValueError("Guide Me returned unsupported flat amount trajectory")
        elif item["flat_amount_trajectory"] is not None:
            raise ValueError("Guide Me returned flat amount trajectory on a non-flat basis")
        _validate_fee_stream_shape(_dummy_stream(item))
        out_streams.append(item)
    questions = plan.get("questions") or []
    if not isinstance(questions, list):
        raise ValueError("Guide Me questions must be a list")
    unsupported = plan.get("unsupported_mechanics") or []
    if not isinstance(unsupported, list):
        raise ValueError("Guide Me unsupported_mechanics must be a list")
    out_questions = [str(q)[:500] for q in questions[:8]]
    out_unsupported = [str(x)[:500] for x in unsupported[:8]]
    if status == "plan" and (out_questions or out_unsupported):
        raise ValueError("Guide Me plan status cannot contain questions or unsupported mechanics")
    if status == "needs_clarification" and not out_questions:
        raise ValueError("Guide Me clarification status requires at least one question")
    if status == "needs_clarification" and out_unsupported:
        raise ValueError("Guide Me clarification status cannot contain unsupported mechanics")
    if status == "unsupported" and not out_unsupported:
        raise ValueError("Guide Me unsupported status requires at least one unsupported mechanic")
    return {
        "status": status,
        "product_label": str(plan.get("product_label") or "Fee product")[:160],
        "managed_notional_source": mns,
        "streams": out_streams,
        "questions": out_questions,
        "unsupported_mechanics": out_unsupported,
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
        fat = item.get("flat_amount_trajectory") or "flat"
        steps.append(f"Set Amount path to “{fat.replace('_schedule',' schedule').replace('_',' ').title()}”.")
        if fat == "explicit_schedule":
            steps.append("Choose the natural Month / Quarter / Year period, then paste the recurring amount schedule into “Amount schedule ($000s)” and click Load (replace).")
        elif fat == "growth":
            steps.append("Enter the starting recurring amount in “Starting amount ($000s)”, choose its natural period, and enter the stated Amount growth assumption.")
        else:
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


def guide_fee_product(description, api_key=None, model=None, http_open=None, request_timeout=25):
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
        # Sonnet 5 enables adaptive thinking by default. Guide Me is a closed-schema
        # translator, so thinking only adds latency and can push first-use schema
        # compilation beyond reverse-proxy request windows.
        "thinking": {"type": "disabled"},
        "output_config": {
            "format": {
                "type": "json_schema",
                "schema": _guide_output_schema(),
            }
        },
        # Intentionally NO tools, web search, retrieval, URLs, files, or engagement config.
    }
    raw = _anthropic_request(payload, key, timeout=request_timeout, http_open=http_open)
    blocks = raw.get("content") or []
    text = "".join(str(b.get("text") or "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
    try:
        plan = _extract_json(text)
    except (ValueError, json.JSONDecodeError) as e:
        raise RuntimeError(
            "Guide Me could not read Claude's structured response. Please retry the same description; "
            "if it recurs, the configured Claude model may not support structured outputs."
        ) from e
    out = render_guide_plan(plan)
    out["model"] = mdl
    out["grounding"] = "Foundry fee-engine manifest only; no tools/retrieval/engagement data supplied"
    return out
