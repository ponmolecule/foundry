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
import hashlib
import tempfile
from datetime import datetime, timezone
from contextlib import contextmanager

CONFIG_SCHEMA_VERSION = "1"


class SchemaVersionError(ValueError):
    """Raised when a stored engagement's config_schema_version is missing or
    unsupported. Deliberately loud: silent coercion is how the CET1 class of
    bug is born."""


class StructuralGapError(ValueError):
    """Raised when a save is refused because a rate_type / measurement selector points at an
    empty field — the specific structural incompleteness that must never be persisted."""


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


class SaveConflictError(ValueError):
    """The caller did not read the revision it is trying to replace."""


_UNCHECKED = object()  # trusted internal callers; HTTP callers must always pass a revision


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


@contextmanager
def _engagement_lock(slug, user=None):
    directory = os.path.join(_dir(user), '.locks')
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, slugify(slug) + '.lock'), 'a+b') as lock:
        if os.name == 'nt':
            import msvcrt
            lock.seek(0, os.SEEK_END)
            if lock.tell() == 0:
                lock.write(b'0'); lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _atomic_json(path, config):
    directory = os.path.dirname(path)
    fd, temporary = tempfile.mkstemp(prefix='.save-', suffix='.tmp', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(config, out, indent=1)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
        if os.name != 'nt':
            directory_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_engagement(cfg, slug=None, user=None, *, allow_incomplete=False, expected_revision=_UNCHECKED):
    """Stamp the schema version (if absent), persist, return metadata."""
    cfg2 = json.loads(json.dumps(cfg))  # deep copy via the same codec that stores it
    # Authoring endpoints explicitly allow incomplete rate choices so work in
    # progress survives a save/reload. Strict callers retain the completion gate.
    # This never supplies a missing rate or relaxes preview/freeze validation.
    from foundry.v2.validate_q import structural_rate_gaps
    gaps = structural_rate_gaps(cfg2)
    if gaps and not allow_incomplete:
        raise StructuralGapError("cannot save — resolve these rate settings first: "
                                 + "; ".join(gaps))
    cfg2.setdefault("config_schema_version", CONFIG_SCHEMA_VERSION)
    if cfg2["config_schema_version"] != CONFIG_SCHEMA_VERSION:
        raise SchemaVersionError(
            f"config_schema_version {cfg2['config_schema_version']!r} is not "
            f"supported (expected {CONFIG_SCHEMA_VERSION!r}); refusing to save")
    slug = slugify(slug or cfg2.get("client") or cfg2.get("proposed_bank")
                   or cfg2.get("name") or "engagement")
    path = os.path.join(_dir(user), slug + ".json")
    # Compare and replace under one cross-process lock. Missing revision means create-only.
    with _engagement_lock(slug, user):
        previous = None
        if os.path.exists(path):
            with open(path, 'rb') as inp:
                previous = inp.read()
        revision = _digest(previous) if previous is not None else None
        if expected_revision is not _UNCHECKED and expected_revision != revision:
            raise SaveConflictError('The saved engagement changed, or this copy has no verified saved version. Your edits have not been written. Open the latest saved version, or save this work under a new version name.')
        # Back up the version being replaced BEFORE replacing it. A history failure stops the write.
        if previous is not None:
            _record_version(json.loads(previous), slug, user)
        _atomic_json(path, cfg2)
        with open(path, 'rb') as inp:
            revision = _digest(inp.read())
        metadata = {'slug': slug, 'path': path, 'revision': revision,
                    'config_schema_version': cfg2['config_schema_version']}
        try:
            _record_version(cfg2, slug, user)
        except Exception:
            # The new current file is already durable and its predecessor was preserved.
            metadata['history_warning'] = 'Current inputs were saved, but recording their history entry failed. The preceding version was preserved.'
    if allow_incomplete:
        metadata['input_warnings'] = gaps
    return metadata


def load_engagement_with_revision(slug, user=None):
    """Fail-closed load: version must be present and supported."""
    path = os.path.join(_dir(user), slugify(slug) + ".json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"no engagement stored at {path}")
    with open(path, "rb") as f:
        raw = f.read()
    cfg = json.loads(raw)
    v = cfg.get("config_schema_version")
    if v != CONFIG_SCHEMA_VERSION:
        raise SchemaVersionError(
            f"engagement {slug!r} carries config_schema_version {v!r}; this "
            f"build supports {CONFIG_SCHEMA_VERSION!r} and will not coerce")
    return cfg, _digest(raw)


def load_engagement(slug, user=None):
    return load_engagement_with_revision(slug, user)[0]


def load_version(slug, version, user=None):
    if not re.fullmatch(r'\d{8}T\d{12}Z', str(version)):
        raise FileNotFoundError('No such saved version')
    path = os.path.join(_dir(user), '_history', slugify(slug), version + '.json')
    with open(path, encoding='utf-8') as inp:
        return json.load(inp)


def delete_engagement(slug, user=None):
    """Delete a saved engagement file. Returns the slug; raises if absent.

    Uses THIS module's slugify — the same one save_engagement writes filenames with — NOT
    configio.slugify, which caps at 40 chars. The mismatch was the zombie-engagement bug: an
    engagement whose slug exceeded 40 chars was written full-length by save but looked up
    truncated by delete, so it could never be removed. slugify is idempotent, so passing either
    a raw name or an already-slugified value resolves to the same file. As a belt-and-suspenders
    guard, if the direct path is absent but a file with this exact slug exists on disk, remove it.
    """
    fname = slugify(slug) + ".json"
    path = os.path.join(_dir(user), fname)
    if not os.path.exists(path):
        # tolerate a caller passing the on-disk slug verbatim (already the filename stem)
        alt = os.path.join(_dir(user), str(slug) + ".json")
        if os.path.exists(alt):
            path = alt
        else:
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
            # The autosaved working session persists the LIVE config, whose name
            # fields carry the bank being edited — so without this it would display
            # under that bank's name and read as a second saved engagement. It is a
            # draft, not an engagement: label it as such regardless of config fields.
            is_draft = slug.startswith(("working-session", "unsaved-engagement-crash-recovery"))
            display = ("Working session (autosaved)" if is_draft else
                       (cfg.get("scenario_name") or cfg.get("client")
                        or cfg.get("proposed_bank") or slug))
            out.append({"slug": slug,
                        "name": display,
                        "is_draft": is_draft,
                        "updated_at": datetime.fromtimestamp(os.path.getmtime(os.path.join(_dir(user), name)), timezone.utc).isoformat(),
                        "bank": cfg.get("client_legal_name") or cfg.get("proposed_bank") or "",
                        # r293: the bank as the header shows it (proposed name first); versions are grouped by it
                        "bank_display": cfg.get("proposed_bank") or cfg.get("client_legal_name") or "",
                        "config_schema_version": cfg.get("config_schema_version")})
        except Exception:
            out.append({"slug": slug, "name": slug + " (unreadable)",
                        "config_schema_version": None})
    return out


# ---------------------------------------------------------------------------------------------------------
# r248: change history. Each save of a NAMED engagement also keeps a timestamped copy (who, when, the full
# configuration) under <engagements dir>/_history/<slug>/. Unchanged re-saves are not recorded; the newest
# HISTORY_KEEP versions are kept. Working-session autosaves are excluded (they would bury the real saves).
# The engagement file itself is written exactly as before; history is written after it, and any failure is
# swallowed by save_engagement. list_engagements only reads *.json files, so the _history folder never lists.
HISTORY_KEEP = 50


def _history_dir(slug, user=None):
    d = os.path.join(_dir(user), "_history", slugify(slug))
    os.makedirs(d, exist_ok=True)
    return d


def _user_name(user):
    if isinstance(user, dict):
        return str(user.get("user") or user.get("name") or user.get("username") or "")
    return str(user or "")


def _record_version(cfg, slug, user=None):
    if str(slug).startswith("working-session"):
        return None
    import datetime as _dt
    d = _history_dir(slug, user)
    files = sorted(f for f in os.listdir(d) if f.endswith(".json"))
    body = json.dumps(cfg, sort_keys=True)
    if files:
        try:
            with open(os.path.join(d, files[-1]), encoding="utf-8") as f:
                if json.dumps(json.load(f).get("config"), sort_keys=True) == body:
                    return None            # nothing changed since the last recorded save
        except Exception:
            pass
    now = _dt.datetime.now(_dt.timezone.utc)
    vid = now.strftime("%Y%m%dT%H%M%S%fZ")
    _atomic_json(os.path.join(d, vid + '.json'),
                 {'id': vid, 'saved_at': now.isoformat(), 'user': _user_name(user), 'config': cfg})
    files = sorted(f for f in os.listdir(d) if f.endswith(".json"))
    for old in files[:-HISTORY_KEEP]:
        try:
            os.remove(os.path.join(d, old))
        except OSError:
            pass
    return vid


def list_versions(slug, user=None):
    """Recorded versions of an engagement, oldest first: [{id, saved_at, user, config}]."""
    d = os.path.join(_dir(user), "_history", slugify(slug))
    if not os.path.isdir(d):
        return []
    out = []
    for name in sorted(os.listdir(d)):
        if name.endswith(".json"):
            try:
                with open(os.path.join(d, name), encoding="utf-8") as f:
                    out.append(json.load(f))
            except Exception:
                continue
    return out


# r249: change tracking. Started explicitly per engagement; the marker lives beside the versions folder
# (_history/<slug>.tracking.json), never inside it and never in the configuration.
def _tracking_path(slug, user=None):
    d = os.path.join(_dir(user), "_history")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, slugify(slug) + ".tracking.json")


def get_tracking(slug, user=None):
    path = _tracking_path(slug, user)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def start_tracking(slug, user=None):
    import datetime as _dt
    existing = get_tracking(slug, user)
    if existing:
        return existing
    rec = {"started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(), "user": _user_name(user)}
    with open(_tracking_path(slug, user), "w", encoding="utf-8") as f:
        json.dump(rec, f)
    return rec


def is_saved(slug, user=None):
    return os.path.exists(os.path.join(_dir(user), slugify(slug) + ".json"))
