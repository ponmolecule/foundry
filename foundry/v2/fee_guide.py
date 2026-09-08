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

GUIDE_SCHEMA_VERSION = 6
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
    "pct_of_revenue": "Revenue share (% of revenue)",
    "pct_of_revenue_opex": "Operating cost (% of revenue)",
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
        "level_trajectories": ["flat", "growth", "explicit_schedule"],
        "level_resolutions": ["step", "smooth"],
        "rate_behavior_by_basis": {k: sorted(v) for k, v in _ALLOWED_RATE_BY_BASIS.items()},
        "special_rules": [
            "Natural-period flow coefficients are valid only on transaction basis with driver trajectory derived.",
            "A derived flow coefficient kind is multiple (turns × source) or pct (% of source).",
            "One transaction stream can contain source × flow coefficient × fee/spread; the flow coefficient creates throughput and the fee/spread monetizes that same throughput.",
            "Do not split a flow coefficient and its fee/spread into separate streams when they are factors in the same revenue equation.",
            "Account count levels may use flat, growth, or explicit_schedule. Explicit account counts are natural-period END-OF-PERIOD levels with step or smooth resolution.",
            "Account fees may be stated per month, quarter, or year and may use flat, growth, or explicit_schedule pricing trajectories.",
            "A balance stream may derive a stock as a percentage of another sourced stock (for example reserves = % of AUC). This is a stock multiplier, not a transaction flow coefficient, and may use flat, growth, or explicit_schedule.",
            "Balance annual fee rates may use flat, growth, or explicit_schedule pricing trajectories.",
            "Flat amounts may be stated per month, quarter, or year and may use flat, growth, or explicit_schedule amount trajectories.",
            "pct_of_revenue is contra-revenue: it reduces fee income. pct_of_revenue_opex preserves gross fee income and routes the calculated cost to noninterest expense.",
            "Use pct_of_revenue_opex when the user describes an operating/service/delivery cost as a percentage of fee revenue; use pct_of_revenue only for an actual revenue share or amount owed away from revenue.",
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
            "driver_period": {"type": "string", "enum": ["month", "quarter", "year", "not_applicable"]},
            "driver_resolution": {"type": "string", "enum": ["step", "smooth", "not_applicable"]},
            "stock_multiplier_trajectory": {"type": "string", "enum": ["flat", "growth", "explicit_schedule", "not_applicable"]},
            "stock_multiplier_period": {"type": "string", "enum": ["month", "quarter", "year", "not_applicable"]},
            "stock_multiplier_resolution": {"type": "string", "enum": ["step", "smooth", "not_applicable"]},
            "pricing_trajectory": {"type": "string", "enum": ["flat", "growth", "explicit_schedule", "not_applicable"]},
            "pricing_period": {"type": "string", "enum": ["month", "quarter", "year", "not_applicable"]},
            "pricing_resolution": {"type": "string", "enum": ["step", "smooth", "not_applicable"]},
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
            "driver_period", "driver_resolution",
            "stock_multiplier_trajectory", "stock_multiplier_period", "stock_multiplier_resolution",
            "pricing_trajectory", "pricing_period", "pricing_resolution",
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
- Treat separate REVENUE EQUATIONS as separate streams, but do not mistake separate factors in ONE
  revenue equation for separate streams. A transaction stream natively represents:
  sourced quantity × flow coefficient = throughput; throughput × fee/spread = revenue.
  Therefore a user's volume/AUC percentage (or turns) and the spread charged on that resulting
  throughput belong in ONE transaction stream, not two.
- Do not output numeric values from your own knowledge. Numbers explicitly supplied by the user are
  not needed in the mapping object; the local Foundry UI tells the user where to enter them.
- If the user describes a ramp/normalization/path but does not give enough values or a growth rule to
  author that path, ask for those values/rule rather than inventing them.
- If a transaction mechanic requires a fee/spread to monetize throughput and the user has not supplied
  that fee/spread, ask for it rather than creating a second stream or inventing a value. If the user
  says revenue begins in a specified month/period but omits the actual start period, ask for it.
- For fee/spread on annualized throughput derived from AUC/AUM, use transaction + managed_notional +
  driver_trajectory=derived with an explicit coefficient kind/period. The turns/multiple path belongs
  in coefficient_trajectory; never place that path in driver_trajectory.
- For a fee charged on a stock such as AUC/AUM itself, use balance + managed_notional.
- Use account only when the user's mechanic is count × fee per account/mandate/relationship.
  Account has TWO INDEPENDENT trajectories: driver_trajectory controls the COUNT path, while
  pricing_trajectory controls the FEE PER ACCOUNT/MANDATE. Words such as "flat annual retainer"
  describe pricing_trajectory=flat; they MUST NOT overwrite an explicit count path.
  Account count paths use driver_trajectory: flat, proportional (for Growth), or explicit_schedule.
  When the user supplies END-OF-PERIOD account/mandate counts, ALWAYS use
  driver_trajectory=explicit_schedule, set driver_period to the source cadence, and set
  driver_resolution to step or smooth only when the user's description specifies that resolution.
  A flat retainer plus changing EOP counts therefore means pricing_trajectory=flat AND
  driver_trajectory=explicit_schedule. If the resolution is economically required but omitted, ask
  whether the EOP levels should Step or Smooth; never invent rounding.
- If a balance is described as a percentage of another stock (for example reserves as % of Avg AUC),
  use balance + the sourced stock + driver_trajectory=derived + stock_multiplier_trajectory. This is a
  STOCK multiplier and must never be represented as a transaction flow coefficient. Stock multiplier
  paths may be flat, growth, or explicit_schedule; explicit paths also name source period and resolution.
- For balance annual rates and account per-unit fees, pricing_trajectory may be flat, growth, or
  explicit_schedule. pricing_period is the account fee's natural billing period; for an explicit balance
  rate path it is the source schedule cadence. Never use Flat amount trajectory for account or balance.
- Use flat for a recurring fixed-dollar amount and set flat_amount_trajectory to flat, growth, or
  explicit_schedule according to the user's stated amount path. A changing Flat amount is supported
  through Amount path; do not confuse that with Rate behavior, which remains flat for the Flat basis.
- Use event only for a one-time amount. Obey rate_behavior_by_basis exactly.
- Distinguish revenue share from operating cost: revenue share is contra-revenue (pct_of_revenue); an operating cost stated as a percent of fee revenue is NIE (pct_of_revenue_opex). Never substitute one for the other.
- For driver_period, driver_resolution, stock_multiplier_trajectory, stock_multiplier_period,
  stock_multiplier_resolution, pricing_trajectory, pricing_period, pricing_resolution, coefficient_kind,
  coefficient_period, coefficient_trajectory, and flat_amount_trajectory, use the string "not_applicable"
  when that field does not apply to the stream.
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


def _dummy_growth_spec():
    return {"rate": 0, "period": "year", "method": "smooth", "anchor": "model_year"}


def _dummy_level_path(trajectory, period=None, resolution=None):
    spec = {"value": 0, "trajectory": trajectory or "flat"}
    if trajectory == "growth":
        spec["growth_spec"] = _dummy_growth_spec()
    elif trajectory == "explicit_schedule":
        spec.update({
            "period": period or "year",
            "resolution": resolution or "step",
            "schedule": {"1": 0},
        })
    return spec


def _dummy_stream(item):
    basis = item["basis"]
    traj = item["driver_trajectory"]
    driver = {"source": item["driver_source"], "trajectory": traj, "params": {}}

    if basis == "account" and traj == "explicit_schedule":
        driver["params"]["level_schedule"] = {
            "period": item["driver_period"],
            "resolution": item["driver_resolution"],
            "schedule": {"1": 0},
        }
    if item.get("stock_multiplier_trajectory") is not None:
        sm = _dummy_level_path(
            item["stock_multiplier_trajectory"],
            item.get("stock_multiplier_period"),
            item.get("stock_multiplier_resolution"),
        )
        sm["kind"] = "pct"
        driver["params"]["stock_multiplier"] = sm
    if item.get("coefficient_kind") is not None:
        driver["params"]["coefficient"] = {
            "kind": item["coefficient_kind"],
            "value": 0,
            "period": item["coefficient_period"],
            "trajectory": item["coefficient_trajectory"] or "flat",
        }
        if item.get("coefficient_trajectory") == "growth":
            driver["params"]["coefficient"]["growth_spec"] = _dummy_growth_spec()
        elif item.get("coefficient_trajectory") == "explicit_schedule":
            driver["params"]["coefficient"]["schedule"] = {"1": 0}

    rate = {"behavior": item["rate_behavior"], "params": {}}
    if basis == "balance":
        pt = item.get("pricing_trajectory") or "flat"
        rate["behavior"] = "flat"
        rate["params"]["rate"] = 0
        rate["params"]["rate_path"] = _dummy_level_path(
            pt, item.get("pricing_period"), item.get("pricing_resolution")
        )
    elif basis == "transaction":
        rate["params"]["per_unit"] = 0
    elif basis == "account":
        pt = item.get("pricing_trajectory") or "flat"
        uf = _dummy_level_path(pt, item.get("pricing_period"), item.get("pricing_resolution"))
        uf["period"] = item.get("pricing_period") or "year"
        if pt == "explicit_schedule":
            # Billing period and path cadence are the same in Guide Me's compact contract.
            uf["path_period"] = item.get("pricing_period") or "year"
        rate["params"]["unit_fee"] = uf
    elif basis == "flat":
        fat = item.get("flat_amount_trajectory") or "flat"
        rate["params"]["flat_amount"] = {"value": 0, "period": "year", "trajectory": fat}
        if fat == "growth":
            rate["params"]["flat_amount"]["growth_spec"] = _dummy_growth_spec()
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
        allowed_stream = {"name", "basis", "driver_source", "driver_trajectory", "driver_period",
                          "driver_resolution", "stock_multiplier_trajectory", "stock_multiplier_period",
                          "stock_multiplier_resolution", "pricing_trajectory", "pricing_period",
                          "pricing_resolution", "coefficient_kind", "coefficient_period",
                          "coefficient_trajectory", "flat_amount_trajectory", "rate_behavior", "cost_kind"}
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
            "driver_period": _transport_optional(raw.get("driver_period")),
            "driver_resolution": _transport_optional(raw.get("driver_resolution")),
            "stock_multiplier_trajectory": _transport_optional(raw.get("stock_multiplier_trajectory")),
            "stock_multiplier_period": _transport_optional(raw.get("stock_multiplier_period")),
            "stock_multiplier_resolution": _transport_optional(raw.get("stock_multiplier_resolution")),
            "pricing_trajectory": _transport_optional(raw.get("pricing_trajectory")),
            "pricing_period": _transport_optional(raw.get("pricing_period")),
            "pricing_resolution": _transport_optional(raw.get("pricing_resolution")),
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
        if item["rate_behavior"] not in _ALLOWED_RATE_BY_BASIS.get(item["basis"], set()):
            raise ValueError(f"Guide Me returned rate behavior {item['rate_behavior']!r} incompatible with basis {item['basis']!r}")
        if item["cost_kind"] not in _FEE_COST_KINDS:
            raise ValueError(f"Guide Me invented unsupported cost kind {item['cost_kind']!r}")
        # Account count-level metadata belongs only to an Explicit EOP count path. Structured
        # translators can confuse a *flat retainer price* with a flat *count* trajectory even
        # while correctly supplying the annual count period/resolution. Because driver_period +
        # driver_resolution have no other Account meaning, a complete valid pair is structural
        # evidence of the Explicit count path and can be canonicalized without inventing values.
        if item["basis"] == "account":
            has_driver_meta = item["driver_period"] is not None or item["driver_resolution"] is not None
            if has_driver_meta:
                if item["driver_period"] not in {"month", "quarter", "year"}:
                    raise ValueError("Guide Me account explicit count path requires driver_period")
                if item["driver_resolution"] not in {"step", "smooth"}:
                    raise ValueError("Guide Me account explicit count path requires step or smooth resolution")
                if item["driver_source"] == "constant" and item["driver_trajectory"] in {"flat", "proportional", "explicit_schedule"}:
                    item["driver_trajectory"] = "explicit_schedule"
                elif item["driver_trajectory"] != "explicit_schedule":
                    raise ValueError("Guide Me returned account count metadata on an incompatible driver")
            elif item["driver_trajectory"] == "explicit_schedule":
                raise ValueError("Guide Me account explicit count path requires driver_period and step or smooth resolution")
        elif item["driver_period"] is not None or item["driver_resolution"] is not None:
            # A sourced Balance stream with a first-class stock multiplier owns its path on the
            # stock-multiplier axis. Claude can redundantly attach the same source-period metadata
            # to the upstream managed-notional driver; it carries no economics there, so strip it.
            if (item["basis"] == "balance" and item["driver_trajectory"] == "derived"
                    and item["driver_source"] != "constant" and item["stock_multiplier_trajectory"] is not None):
                item["driver_period"] = None
                item["driver_resolution"] = None
            else:
                raise ValueError("Guide Me returned driver level metadata outside an explicit account count path")

        smt = item["stock_multiplier_trajectory"]
        if smt is not None:
            if item["basis"] != "balance" or item["driver_trajectory"] != "derived" or item["driver_source"] == "constant":
                raise ValueError("Guide Me stock multiplier requires a sourced derived balance stream")
            if smt not in {"flat", "growth", "explicit_schedule"}:
                raise ValueError("Guide Me returned unsupported stock multiplier trajectory")
            if smt == "explicit_schedule":
                if item["stock_multiplier_period"] not in {"month", "quarter", "year"}:
                    raise ValueError("Guide Me explicit stock multiplier requires a source period")
                if item["stock_multiplier_resolution"] not in {"step", "smooth"}:
                    raise ValueError("Guide Me explicit stock multiplier requires step or smooth resolution")
            else:
                item["stock_multiplier_period"] = None
                item["stock_multiplier_resolution"] = None
        elif item["stock_multiplier_period"] is not None or item["stock_multiplier_resolution"] is not None:
            raise ValueError("Guide Me returned stock multiplier metadata without a stock multiplier")

        pt = item["pricing_trajectory"]
        if item["basis"] in {"balance", "account"}:
            # Backward compatibility: pre-r42 Guide Me plans had no pricing_trajectory field;
            # their balance/account pricing was necessarily Flat. Structured Outputs in r42+
            # carry the field explicitly, but old stored/fake plans remain valid.
            if pt is None:
                pt = item["pricing_trajectory"] = "flat"
            if pt not in {"flat", "growth", "explicit_schedule"}:
                raise ValueError("Guide Me balance/account stream requires a pricing trajectory")
            if item["basis"] == "account":
                # Account fee period is a real economic unit. New Guide Me should provide it
                # when the user's description does; legacy plans may leave it for the user.
                if item["pricing_period"] is not None and item["pricing_period"] not in {"month", "quarter", "year"}:
                    raise ValueError("Guide Me account pricing returned an unsupported natural billing period")
                if pt == "explicit_schedule":
                    if item["pricing_period"] not in {"month", "quarter", "year"}:
                        raise ValueError("Guide Me explicit account pricing requires a natural period")
                    if item["pricing_resolution"] not in {"step", "smooth"}:
                        raise ValueError("Guide Me explicit account pricing requires step or smooth resolution")
                else:
                    item["pricing_resolution"] = None
            else:
                if pt == "explicit_schedule":
                    if item["pricing_period"] not in {"month", "quarter", "year"}:
                        raise ValueError("Guide Me explicit balance-rate pricing requires a source period")
                    if item["pricing_resolution"] not in {"step", "smooth"}:
                        raise ValueError("Guide Me explicit balance-rate pricing requires step or smooth resolution")
                else:
                    # Schedule cadence/resolution are redundant for a flat/growth annualized rate.
                    item["pricing_period"] = None
                    item["pricing_resolution"] = None
        elif any(item[k] is not None for k in ("pricing_trajectory", "pricing_period", "pricing_resolution")):
            raise ValueError("Guide Me returned pricing-path metadata on an unsupported basis")

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
            # Structured-output translators can redundantly populate the legacy Flat-amount
            # axis even when the stream is correctly represented by the richer Account/Balance
            # path fields. Normalize only when those basis-native fields already prove the
            # intended mechanic; otherwise fail closed so a Flat schedule cannot silently stand
            # in for a missing count/stock/rate path.
            account_native = (
                item["basis"] == "account"
                and (
                    item["driver_trajectory"] in {"explicit_schedule", "proportional"}
                    or item.get("pricing_trajectory") in {"growth", "explicit_schedule"}
                )
            )
            balance_native = (
                item["basis"] == "balance"
                and (
                    item.get("stock_multiplier_trajectory") is not None
                    or item.get("pricing_trajectory") in {"growth", "explicit_schedule"}
                )
            )
            if account_native or balance_native:
                item["flat_amount_trajectory"] = None
            else:
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
    basis = item["basis"]
    steps = [
        f"Add a {basis} stream and name it “{item['name']}”.",
        f"Set Basis to “{_BASIS_LABELS[basis]}”.",
    ]

    # Flat periodic amounts are self-contained. Other bases expose their causal driver.
    if basis != "flat":
        steps.append(f"Set Driver source to “{_SOURCE_LABELS[item['driver_source']]}”.")

    if basis == "account" and item["driver_source"] == "constant":
        traj = item["driver_trajectory"]
        if traj == "explicit_schedule":
            steps.append("Set Count path to “Explicit schedule”.")
            steps.append(
                f"Set Count schedule period to “{item['driver_period'].title()}” and Resolution to “{item['driver_resolution'].title()}”."
            )
            steps.append(
                f"Paste the period-end account/mandate counts into “Period-end count schedule by {item['driver_period']}” and click Load (replace). "
                "Foundry treats them as level endpoints; Smooth linearly interpolates between endpoints and Step holds the prior endpoint until the next one. Foundry does not round the interpolated counts."
            )
        elif traj == "proportional":
            steps.append("Set Count path to “Growth”, enter the Starting count, and enter the stated Count growth assumption.")
        else:
            steps.append("Set Count path to “Flat” and enter the account/mandate count in “Count / mandates”.")
    elif basis != "flat":
        steps.append(f"Set Trajectory to “{_TRAJECTORY_LABELS[item['driver_trajectory']]}”.")

    smt = item.get("stock_multiplier_trajectory")
    if smt is not None:
        label = smt.replace("_schedule", " schedule").replace("_", " ").title()
        steps.append("Under Stock derivation, use “% of source balance”.")
        steps.append(f"Set Stock % trajectory to “{label}”.")
        if smt == "explicit_schedule":
            steps.append(
                f"Set Schedule period to “{item['stock_multiplier_period'].title()}” and Resolution to “{item['stock_multiplier_resolution'].title()}”, then paste the stock-percent schedule into “Stock % schedule by {item['stock_multiplier_period']}” and click Load (replace)."
            )
        elif smt == "growth":
            steps.append("Enter the Starting Stock % of source and the stated Stock % growth assumption.")
        else:
            steps.append("Enter the stock percentage in “Stock % of source”.")

    if item.get("coefficient_kind"):
        is_pct = item["coefficient_kind"] == "pct"
        noun = "Volume %" if is_pct else "Turns"
        field = "Flow %" if is_pct else "Turns / multiple"
        selector = "% of source" if is_pct else "× source"
        period = item["coefficient_period"].title()
        traj = item["coefficient_trajectory"]
        traj_label = traj.replace("_", " ").title()
        steps.append(f"Set Flow coefficient to “{selector}” and Per to “{period}”.")
        steps.append(f"Set {noun} trajectory to “{traj_label}”.")
        if traj == "explicit_schedule":
            steps.append(
                f"Paste the source-model {noun.lower()} schedule into “{noun} schedule by {item['coefficient_period']}” and click Load (replace). "
                f"The single “{field}” field is not used for Explicit Schedule."
            )
        elif traj == "growth":
            steps.append(f"Enter the starting assumption in “Starting {field}”, then enter the stated {noun.lower()} growth assumption.")
        else:
            steps.append(f"Enter the assumption in “{field}”.")
        steps.append("Foundry interprets the coefficient in the selected natural period and converts it to the model cadence.")

    if basis == "balance":
        pt = item.get("pricing_trajectory") or "flat"
        steps.append("Set Rate behavior to “Series rate path”.")
        steps.append(f"Set Rate path to “{pt.replace('_schedule',' schedule').replace('_',' ').title()}”.")
        if pt == "explicit_schedule":
            steps.append(
                f"Set Schedule period to “{item['pricing_period'].title()}” and Resolution to “{item['pricing_resolution'].title()}”, then paste the annualized fee-rate schedule into “Rate schedule (bp/yr) by {item['pricing_period']}” and click Load (replace)."
            )
        elif pt == "growth":
            steps.append("Enter the Starting Rate (bp/yr on balance) and the stated Rate growth assumption.")
        else:
            steps.append("Enter the annual fee in “Rate (bp/yr on balance)”.")
    elif basis == "transaction":
        if item.get("coefficient_kind"):
            steps.append("Enter the fee/spread in “Fee (% of throughput)”. This monetizes the throughput produced by the flow coefficient; it is not a separate fee stream.")
        else:
            steps.append("Enter the fee in “Fee ($/unit)”.")
        steps.append(f"Set Rate behavior to “{_RATE_LABELS[item['rate_behavior']]}”.")
    elif basis == "account":
        pt = item.get("pricing_trajectory") or "flat"
        if item.get("pricing_period"):
            steps.append(f"Set Fee is per to “{item['pricing_period'].title()}”.")
        else:
            steps.append("Choose Fee is per = Month / Quarter / Year to match the source-model fee unit.")
        steps.append(f"Set Fee path to “{pt.replace('_schedule',' schedule').replace('_',' ').title()}”.")
        if pt == "explicit_schedule":
            steps.append(
                f"Paste the per-account fee schedule into “Fee schedule ($000s/account) by {item['pricing_period']}” and click Load (replace); use the stated Step/Smooth resolution."
            )
        elif pt == "growth":
            steps.append("Enter the Starting Fee ($000s/account) and the stated Fee growth assumption.")
        else:
            steps.append("Enter the fee in “Fee ($000s/account)”.")
        steps.append("Leave Rate behavior at “Flat”; the Fee path owns Flat / Growth / Explicit pricing changes.")
    elif basis == "flat":
        fat = item.get("flat_amount_trajectory") or "flat"
        steps.append(f"Set Amount path to “{fat.replace('_schedule',' schedule').replace('_',' ').title()}”.")
        if fat == "explicit_schedule":
            steps.append("Choose the natural Month / Quarter / Year period, then paste the recurring amount schedule into “Amount schedule ($000s)” and click Load (replace).")
        elif fat == "growth":
            steps.append("Enter the starting recurring amount in “Starting amount ($000s)”, choose its natural period, and enter the stated Amount growth assumption.")
        else:
            steps.append("Enter the recurring amount in “Amount ($000s)” and choose its natural Month / Quarter / Year period.")
    elif basis == "event":
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
