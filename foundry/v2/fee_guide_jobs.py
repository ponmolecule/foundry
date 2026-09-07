"""Persistent async job wrapper for Fee Product Guide Me.

Browser requests must not remain open while Anthropic generates a structured plan.
Each submission returns a job id immediately; a daemon worker performs the model call
and writes only status/result metadata to Foundry's persistent data directory. Polling
requests are fast and may be served by any web worker sharing FOUNDRY_DATA_DIR.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
import uuid

from .fee_guide import guide_fee_product

_JOB_TTL_SECONDS = 60 * 60


def _data_dir():
    return os.environ.get("FOUNDRY_DATA_DIR") or os.path.join(os.getcwd(), "data")


def _jobs_dir():
    path = os.path.join(_data_dir(), "fee_guide_jobs")
    os.makedirs(path, exist_ok=True)
    return path


def _safe_owner(user):
    return re.sub(r"[^a-zA-Z0-9_.@+-]", "_", str(user or ""))[:160] or "anonymous"


def _job_path(job_id):
    jid = str(job_id or "")
    if not re.fullmatch(r"[0-9a-f]{32}", jid):
        raise KeyError("unknown Guide Me job")
    return os.path.join(_jobs_dir(), jid + ".json")


def _atomic_write(path, payload):
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".fee-guide-job.", dir=parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, separators=(",", ":"), ensure_ascii=False)
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


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _cleanup_jobs(now=None):
    now = time.time() if now is None else float(now)
    try:
        names = os.listdir(_jobs_dir())
    except OSError:
        return
    for name in names:
        if not re.fullmatch(r"[0-9a-f]{32}\.json", name):
            continue
        path = os.path.join(_jobs_dir(), name)
        try:
            st = os.stat(path)
            if now - st.st_mtime > _JOB_TTL_SECONDS:
                os.unlink(path)
        except OSError:
            pass


def _classify_error(exc):
    msg = str(exc or "")
    low = msg.lower()
    if isinstance(exc, ValueError):
        return "validation", msg
    if "credentials are not configured" in low:
        return "not_configured", "Guide Me is not configured for this Foundry service."
    if "claude api error 401" in low or "claude api error 403" in low:
        return "credential_rejected", "Anthropic rejected the configured Guide Me credential."
    if "claude api error 429" in low:
        return "rate_limited", "Anthropic rate-limited Guide Me. Please retry shortly."
    if "claude api error 529" in low or "overloaded" in low:
        return "overloaded", "Anthropic is temporarily overloaded. Please retry shortly."
    if "timed out" in low or "timeout" in low:
        return "timeout", "Guide Me timed out waiting for Anthropic. Please retry."
    return "upstream", "Guide Me could not produce a validated Foundry plan. " + msg[:350]


def _run_job(job_id, owner, description, runner=None):
    path = _job_path(job_id)
    started = time.time()
    try:
        current = _read(path)
        current.update({"status": "running", "updated_at": started})
        _atomic_write(path, current)
        fn = runner or guide_fee_product
        if runner is None:
            try:
                timeout = max(30, min(180, int(os.environ.get("FOUNDRY_GUIDE_TIMEOUT_SECONDS", "90"))))
            except Exception:
                timeout = 90
            result = fn(description, request_timeout=timeout)
        else:
            result = fn(description)
        done = {
            "job_id": job_id,
            "owner": owner,
            "status": "done",
            "created_at": current.get("created_at", started),
            "updated_at": time.time(),
            "result": result,
        }
        _atomic_write(path, done)
    except Exception as exc:
        kind, message = _classify_error(exc)
        try:
            created = _read(path).get("created_at", started)
        except Exception:
            created = started
        failed = {
            "job_id": job_id,
            "owner": owner,
            "status": "error",
            "created_at": created,
            "updated_at": time.time(),
            "error_kind": kind,
            "error": message,
        }
        _atomic_write(path, failed)


def submit_fee_guide_job(user, description, runner=None, start_worker=True):
    desc = str(description or "").strip()
    if not desc:
        raise ValueError("Describe the fee product you are trying to model")
    if len(desc) > 6000:
        raise ValueError("Guide Me description is limited to 6,000 characters")
    _cleanup_jobs()
    owner = _safe_owner(user)
    job_id = uuid.uuid4().hex
    payload = {
        "job_id": job_id,
        "owner": owner,
        "status": "pending",
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    _atomic_write(_job_path(job_id), payload)
    if start_worker:
        thread = threading.Thread(
            target=_run_job,
            args=(job_id, owner, desc, runner),
            name=f"foundry-fee-guide-{job_id[:8]}",
            daemon=True,
        )
        thread.start()
    return {"job_id": job_id, "status": "pending"}


def get_fee_guide_job(user, job_id):
    _cleanup_jobs()
    try:
        payload = _read(_job_path(job_id))
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        raise KeyError("unknown Guide Me job")
    if payload.get("owner") != _safe_owner(user):
        raise KeyError("unknown Guide Me job")
    out = {k: v for k, v in payload.items() if k != "owner"}
    return out
