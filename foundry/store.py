"""Engagement store — INPUT_SPEC §6, build step 1.

One JSON file per engagement at $FOUNDRY_DATA_DIR/engagements/{slug}.json (no
database). The canonical Tier-3 config carries `config_schema_version`; the
LOAD path is fail-closed: a file with a missing or unsupported version refuses
to load rather than being coerced. Save stamps the current version onto
configs that predate the pin (the nine goldens and fixtures), which the run
path has been verified to tolerate hash-neutrally.
"""
import json
import os
import re

CONFIG_SCHEMA_VERSION = "1"


class SchemaVersionError(ValueError):
    """Raised when a stored engagement's config_schema_version is missing or
    unsupported. Deliberately loud: silent coercion is how the CET1 class of
    bug is born."""


def _dir(user=None):
    base = os.environ.get("FOUNDRY_DATA_DIR", os.path.join(os.getcwd(), "data"))
    d = os.path.join(base, "engagements", _safe_user(user)) if user else os.path.join(base, "engagements")
    os.makedirs(d, exist_ok=True)
    return d


def _safe_user(user):
    return re.sub(r"[^a-z0-9_-]", "", str(user).lower()) or "shared"


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
    return s or "engagement"


def save_engagement(cfg, slug=None, user=None):
    """Stamp the schema version (if absent), persist, return metadata."""
    cfg2 = json.loads(json.dumps(cfg))  # deep copy via the same codec that stores it
    cfg2.setdefault("config_schema_version", CONFIG_SCHEMA_VERSION)
    if cfg2["config_schema_version"] != CONFIG_SCHEMA_VERSION:
        raise SchemaVersionError(
            f"config_schema_version {cfg2['config_schema_version']!r} is not "
            f"supported (expected {CONFIG_SCHEMA_VERSION!r}); refusing to save")
    slug = slugify(slug or cfg2.get("client") or cfg2.get("proposed_bank")
                   or cfg2.get("name") or "engagement")
    path = os.path.join(_dir(user), slug + ".json")
    # Insertion order is preserved verbatim: v1 engine results are sensitive
    # to config mapping order (float accumulation follows dict iteration), so
    # sort-normalizing here would silently change run hashes. Discovered by
    # gate T18; recorded in PROTOCOL_GAPS and ENGINE_SPEC §12.
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg2, f, indent=1)
    return {"slug": slug, "path": path,
            "config_schema_version": cfg2["config_schema_version"]}


def load_engagement(slug, user=None):
    """Fail-closed load: version must be present and supported."""
    path = os.path.join(_dir(user), slugify(slug) + ".json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"no engagement stored at {path}")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    v = cfg.get("config_schema_version")
    if v != CONFIG_SCHEMA_VERSION:
        raise SchemaVersionError(
            f"engagement {slug!r} carries config_schema_version {v!r}; this "
            f"build supports {CONFIG_SCHEMA_VERSION!r} and will not coerce")
    return cfg


def delete_engagement(slug, user=None):
    """Delete a saved engagement file. Returns the slug; raises if absent."""
    from .configio import slugify
    path = os.path.join(_dir(user), slugify(slug) + ".json")
    if not os.path.exists(path):
        raise FileNotFoundError(slug)
    os.remove(path)
    return slugify(slug)


def list_engagements(user=None):
    out = []
    for name in sorted(os.listdir(_dir(user))):
        if not name.endswith(".json"):
            continue
        slug = name[:-5]
        try:
            with open(os.path.join(_dir(user), name), encoding="utf-8") as f:
                cfg = json.load(f)
            out.append({"slug": slug,
                        "name": cfg.get("scenario_name") or cfg.get("client")
                                 or cfg.get("proposed_bank") or slug,
                        "bank": cfg.get("client_legal_name") or cfg.get("proposed_bank") or "",
                        "config_schema_version": cfg.get("config_schema_version")})
        except Exception:
            out.append({"slug": slug, "name": slug + " (unreadable)",
                        "config_schema_version": None})
    return out
