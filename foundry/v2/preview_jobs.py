"""Bounded, account-bound preview jobs. One CPU calculation at a time per service process.

A browser timeout never controls an engine run. Queued updates from the same tab
are replaced by the newest inputs; already running work finishes without spawning
another calculation. Results expire and are not persisted engagement data.
"""
import copy
import hashlib
import json
import logging
import threading
import time
import uuid
from collections import OrderedDict

log = logging.getLogger("uvicorn.error.preview")


def calculate(cfg, scope):
    from .run_q import run_v2
    from .validate_q import validate_errors_v2
    errs = validate_errors_v2(cfg)
    if errs:
        return {"status": "failed", "http_status": 422, "errors": errs}
    result = run_v2(cfg, scope=scope)
    try:
        from .callreport import build_call_report
        result["call_report"] = build_call_report(result, cfg)
    except Exception:
        log.exception("preview call-report presentation failed")
    return {"status": "completed", "result": result}


class PreviewJobs:
    def __init__(self, runner=calculate, *, max_pending=8, ttl=120):
        self.runner, self.max_pending, self.ttl = runner, max_pending, ttl
        self.cv = threading.Condition()
        self.jobs, self.pending = {}, OrderedDict()
        self.worker = None

    def _prune(self):
        now = time.monotonic()
        for jid, job in list(self.jobs.items()):
            if job["status"] not in ("queued", "running") and now - job["finished"] > self.ttl:
                del self.jobs[jid]
        # Tabs that closed while queued must not leave indefinite expensive work.
        for jid in list(self.pending):
            job = self.jobs[jid]
            if now - job["polled"] > 60:
                self.pending.pop(jid)
                job.update(status="superseded", finished=now)
                job.pop("config", None)

    def submit(self, user, session, cfg, scope="base"):
        if scope not in ("base", "full"):
            raise ValueError("Calculation scope must be base or full")
        if not isinstance(session, str) or not session or len(session) > 128:
            raise ValueError("A preview tab identifier is required")
        if not isinstance(cfg, dict):
            raise ValueError("A configuration object is required")
        fingerprint = hashlib.sha256(json.dumps([scope, cfg], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        with self.cv:
            self._prune()
            for job in reversed(list(self.jobs.values())):
                if job["user"] == user and job["session"] == session and job["fingerprint"] == fingerprint and job["status"] in ("queued", "running", "completed"):
                    job["polled"] = time.monotonic()
                    return self._public(job)
            for jid in list(self.pending):
                job = self.jobs[jid]
                if job["user"] == user and job["session"] == session:
                    self.pending.pop(jid)
                    job.update(status="superseded", finished=time.monotonic())
                    job.pop("config", None)
            if len(self.pending) >= self.max_pending:
                raise OverflowError("Calculation queue is busy. Retry shortly; your inputs are unchanged.")
            now, jid = time.monotonic(), uuid.uuid4().hex
            job = dict(job_id=jid, user=user, session=session, fingerprint=fingerprint, scope=scope,
                       config=copy.deepcopy(cfg), status="queued", created=now, polled=now)
            self.jobs[jid] = job
            self.pending[jid] = None
            if self.worker is None or not self.worker.is_alive():
                self.worker = threading.Thread(target=self._work, name="foundry-preview", daemon=True)
                self.worker.start()
            self.cv.notify()
            return self._public(job)

    def get(self, user, jid):
        with self.cv:
            self._prune()
            job = self.jobs.get(jid)
            if not job or job["user"] != user:
                raise KeyError(jid)
            job["polled"] = time.monotonic()
            return self._public(job)

    def _public(self, job):
        out = {k: job[k] for k in ("job_id", "status", "scope")}
        out["elapsed_seconds"] = round(time.monotonic() - job["created"], 3)
        if job["status"] == "queued":
            out["queue_position"] = list(self.pending).index(job["job_id"]) + 1
        for key in ("result", "errors", "message", "http_status", "queue_seconds", "calculation_seconds"):
            if key in job:
                out[key] = job[key]
        return out

    def _work(self):
        while True:
            with self.cv:
                self._prune()
                if not self.pending:
                    self.worker = None
                    return
                jid, _ = self.pending.popitem(last=False)
                job = self.jobs[jid]
                job.update(status="running", queue_seconds=round(time.monotonic() - job["created"], 3))
                cfg = job.pop("config")
            started = time.monotonic()
            log.info("preview_start job=%s scope=%s queue_seconds=%.3f", jid, job["scope"], job["queue_seconds"])
            try:
                outcome = self.runner(cfg, job["scope"])
            except ValueError as exc:
                outcome = dict(status="failed", http_status=422, errors=[{"message": str(exc)}])
            except Exception:
                log.exception("preview_failed job=%s", jid)
                outcome = dict(status="failed", http_status=500, message="Calculation failed on the server. Reference: " + jid)
            with self.cv:
                job.update(outcome, finished=time.monotonic(), calculation_seconds=round(time.monotonic() - started, 3))
                log.info("preview_finish job=%s status=%s calculation_seconds=%.3f", jid, job["status"], job["calculation_seconds"])


jobs = PreviewJobs()
