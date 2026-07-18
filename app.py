"""Foundry web shell. Thin FastAPI wrapper over the pure-Python engine.

Multi-engagement, gated by HTTP Basic auth. Credentials come from
environment variables (FOUNDRY_USER / FOUNDRY_PASS) with demo defaults;
set real values in Railway before sharing the URL.

Basic auth is a demo placeholder, NOT Phase C0-grade authentication.
No real client data behind this gate. Ever.

Deploy: uvicorn app:app --host 0.0.0.0 --port $PORT
"""
import os, secrets, json
from fastapi import Request, FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from foundry.run import run
from foundry.registry import ENGAGEMENTS, register_config
from foundry.configio import ConfigError

USER = os.environ.get("FOUNDRY_USER", "klaros")
PASS = os.environ.get("FOUNDRY_PASS", "solstice-2026")

app = FastAPI(title="Foundry", version="0.2.2", docs_url=None, redoc_url=None, openapi_url=None)
security = HTTPBasic()
_cache = {}


def gate(creds: HTTPBasicCredentials = Depends(security)):
    ok = (secrets.compare_digest(creds.username, USER)
          and secrets.compare_digest(creds.password, PASS))
    if not ok:
        raise HTTPException(401, "Unauthorized",
                            headers={"WWW-Authenticate": "Basic realm=Foundry"})


@app.get("/api/engagements")
def engagements(_=Depends(gate)):
    return [{"slug": k, "label": v["label"]} for k, v in ENGAGEMENTS.items()]


@app.post("/api/engagements")
async def upload_engagement(cfg: dict, _=Depends(gate)):
    try:
        slug = register_config(cfg)
    except ConfigError as e:
        raise HTTPException(422, str(e))
    _cache.pop(slug, None)
    return {"slug": slug, "label": ENGAGEMENTS[slug]["label"]}


@app.post("/api/engagements/upload")
async def upload_engagement_file(file: UploadFile = File(...), _=Depends(gate)):
    """File upload door: .xlsx (banker-native) or .json. Both funnel into
    the same validate -> register -> run pipeline."""
    name = (file.filename or "").lower()
    data = await file.read()
    try:
        if name.endswith(".xlsx"):
            from foundry.excelio import parse_workbook
            cfg = parse_workbook(data)
        elif name.endswith(".json"):
            cfg = json.loads(data)
        else:
            raise HTTPException(415, "upload a .xlsx or .json engagement configuration")
        slug = register_config(cfg)
    except ConfigError as e:
        raise HTTPException(422, str(e))
    except json.JSONDecodeError as e:
        raise HTTPException(422, f"invalid JSON: {e}")
    _cache.pop(slug, None)
    return {"slug": slug, "label": ENGAGEMENTS[slug]["label"]}


@app.get("/api/results")
def results(engagement: str, _=Depends(gate)):
    if engagement not in ENGAGEMENTS:
        raise HTTPException(404, f"unknown engagement '{engagement}'")
    if engagement not in _cache:
        _cache[engagement] = run(ENGAGEMENTS[engagement]["config"])
    return JSONResponse(_cache[engagement])


@app.get("/api/health")
def health():   # unauthenticated on purpose: deploy probes need it
    return {"ok": True, "engagements": list(ENGAGEMENTS)}


@app.get("/")
def index(_=Depends(gate)):
    return FileResponse("web/index.html")


@app.get("/sandbox")
def sandbox(_=Depends(gate)):
    # retired at PC — the modeling workspace is the thin client at /v2
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/v2", status_code=307)


@app.get("/v2")
def console_v2(_=Depends(gate)):
    """Modeling Workspace: thin client over /api/v2/preview. No arithmetic in
    the browser; the engine is the only engine (ledger G2)."""
    return FileResponse("web/console_v2.html")


@app.get("/docs", include_in_schema=False)
def gated_docs(_=Depends(gate)):
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(openapi_url="/openapi.json", title="Foundry API")


@app.get("/openapi.json", include_in_schema=False)
def gated_openapi(_=Depends(gate)):
    return JSONResponse(app.openapi())


def _build_stamp():
    import subprocess
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                               capture_output=True, text=True, timeout=3).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


@app.get("/v3.1")
@app.get("/v31")
def console_v31(_=Depends(gate)):
    """Foundry v3.1 (input-spec rung): the v3 shell plus the input layer -
    Start screen (config-source selector), wizard, FIW. Engine untouched;
    /v2, /v2.1, /v3 are frozen rungs."""
    from fastapi.responses import HTMLResponse
    html = open("web/console_v2.html", encoding="utf-8").read()
    html = html.replace("</head>", "<script>window.V31=true</script>\n</head>")
    html = html.replace("one engine — the browser does no arithmetic",
                         "one engine — build " + _build_stamp())
    return HTMLResponse(html)


@app.get("/api/v31/engagements")
def v31_engagements(_=Depends(gate)):
    from foundry import store
    return JSONResponse({"engagements": store.list_engagements(),
                          "schema_version": store.CONFIG_SCHEMA_VERSION})


@app.delete("/api/v31/engagement/{slug}")
def v31_engagement_delete(slug: str, _=Depends(gate)):
    from foundry import store
    try:
        return JSONResponse({"deleted": store.delete_engagement(slug)})
    except FileNotFoundError:
        return JSONResponse({"error": "no such engagement"}, status_code=404)


@app.post("/api/v31/engagement/save-current")
def v31_engagement_save_current(body: dict, _=Depends(gate)):
    """Promote the live configuration to a saved engagement — no wizard required."""
    from foundry import store
    cfg = body.get("config")
    name = (body.get("name") or "").strip()
    if not cfg or not name:
        return JSONResponse({"error": "config and name required"}, status_code=422)
    cfg.setdefault("proposed_bank", name)
    cfg.setdefault("client", name)
    try:
        return JSONResponse(store.save_engagement(cfg, slug=name))
    except store.SchemaVersionError as e:
        return JSONResponse({"error": str(e)}, status_code=422)


@app.get("/api/v31/engagement/{slug}")
def v31_engagement(slug: str, _=Depends(gate)):
    from foundry import store
    try:
        return JSONResponse(store.load_engagement(slug))
    except FileNotFoundError:
        return JSONResponse({"error": "no such engagement"}, status_code=404)
    except store.SchemaVersionError as e:
        return JSONResponse({"error": str(e)}, status_code=409)


@app.get("/api/v31/template")
def v31_template(_=Depends(gate)):
    import json as _json
    import os as _os
    p = "foundry/fixtures/patrick_default_v31.json"
    if not _os.path.exists(p):
        return JSONResponse({"error": "v3.1 default configuration missing"}, status_code=500)
    return JSONResponse(_json.load(open(p, encoding="utf-8")))


@app.get("/api/v31/persistence")
def v31_persistence(_=Depends(gate)):
    """Workspace persistence honesty: is FOUNDRY_DATA_DIR a mounted volume, or
    ephemeral container disk that a redeploy will clear? Verifiable, not asserted."""
    import os
    base = os.environ.get("FOUNDRY_DATA_DIR", os.path.join(os.getcwd(), "data"))
    os.makedirs(base, exist_ok=True)
    explicit = "FOUNDRY_DATA_DIR" in os.environ
    try:
        parent = os.path.dirname(os.path.abspath(base)) or "/"
        is_mount = os.stat(base).st_dev != os.stat(parent).st_dev or os.path.ismount(base)
    except OSError:
        is_mount = False
    try:
        probe = os.path.join(base, ".persistence_probe")
        with open(probe, "w") as fh: fh.write("ok")
        os.remove(probe); writable = True
    except OSError:
        writable = False
    def _count(sub):
        p = os.path.join(base, sub)
        try: return len([f for f in os.listdir(p) if not f.startswith(".")])
        except OSError: return 0
    return {"data_dir": os.path.abspath(base), "explicit_env": explicit,
            "is_mounted_volume": bool(is_mount), "writable": writable,
            "counts": {"fiw_snapshots": _count("fiw"),
                        "engagements": _count("engagements"),
                        "freezes": _count("registry"),
                        "forecast_inventories": _count("modet")},
            "outside_deploy_tree": not os.path.abspath(base).startswith(os.getcwd() + os.sep),
            "verdict": ("durable — mounted volume, writable" if is_mount and writable else
                         ("durable by location on a host machine — explicit path outside the deploy tree; "
                          "on a container platform this is STILL EPHEMERAL unless a volume is mounted here")
                          if writable and explicit and not os.path.abspath(base).startswith(os.getcwd() + os.sep) else
                         "EPHEMERAL — inside the deploy tree; a redeploy (or the deploy script replacing "
                          "this folder) clears it; set FOUNDRY_DATA_DIR outside the tree or mount a volume" if writable else
                         "NOT WRITABLE — nothing persists at all")}

@app.post("/api/v31/fiw")
def v31_fiw(body: dict, _=Depends(gate)):
    """Per-engagement Foundry Input Workbook (INPUT_SPEC section 7)."""
    from fastapi.responses import Response
    from foundry.v2.fiw import build_fiw, persist_snapshot
    cfg = body.get("cfg") or body
    data, gh = build_fiw(cfg)
    persist_snapshot(cfg, gh)
    name = (cfg.get("proposed_bank") or "engagement").lower().replace(" ", "_")[:40]
    return Response(content=data,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="fiw_{name}_{gh}.xlsx"'})


@app.post("/api/v31/fiw/import")
async def v31_fiw_import(file: UploadFile = File(...), current: str = Form("{}"), _=Depends(gate)):
    """Diff-import of a filled FIW: only human edits apply; fail-closed."""
    from foundry.v2.fiw import diff_import
    from foundry.v2.validate_q import validate_config_v2, ConfigErrorV2
    data = await file.read()
    try:
        merged, report = diff_import(data, json.loads(current))
        validate_config_v2(merged)
    except (ValueError, ConfigErrorV2) as e:
        return JSONResponse({"error": str(e)}, status_code=422)
    except Exception as e:   # BadZipFile, KeyError from old-format workbooks, etc. — fail closed, never 500
        return JSONResponse({"error": f"could not read this workbook ({type(e).__name__}: {e}). "
                                        "If it was generated by an earlier Foundry build or re-saved "
                                        "in another tool, regenerate the input workbook from the "
                                        "current configuration and reapply your edits."},
                             status_code=422)
    from foundry.entry_screen import entry_screen
    screen = entry_screen(merged)
    if screen["blockers"]:
        return JSONResponse({"error": "entry screen refused the workbook:\n- "
                              + "\n- ".join(screen["blockers"])}, status_code=422)
    report["warnings"] = screen["warnings"]
    return JSONResponse({"cfg": merged, "report": report})


@app.post("/api/v31/modet/recon")
async def v31_modet_recon(file: UploadFile = File(...), _=Depends(gate)):
    """Mode T stage T-1: what does this file contain? (No interpretation.)"""
    from foundry.modet import ingest, recon, persist_inventory
    data = await file.read()
    try:
        inv = ingest(data, file.filename or "")
        rep = recon(inv)
        persist_inventory(inv, rep["report_hash"])
        return JSONResponse(rep)
    except Exception as e:
        return JSONResponse({"error": f"could not read file: {e}"}, status_code=422)


@app.post("/api/v31/modet/finalize")
def v31_modet_finalize(body: dict, _=Depends(gate)):
    """Stage T-5 over the wire: session + current cfg -> merged cfg,
    translation log, gap questions. Fail-closed on unknown inventory."""
    from foundry.modet import load_inventory
    from foundry.modet_map import finalize
    sess, cur = body.get("session") or {}, body.get("cfg") or {}
    inv = load_inventory(str(sess.get("source_hash", "")))
    if inv is None:
        return JSONResponse({"error": "source inventory not found on this workspace — "
                              "re-upload the file through the recon step"}, status_code=422)
    try:
        out = finalize(sess, inv, cur)
    except (ValueError, KeyError) as e:
        return JSONResponse({"error": str(e)}, status_code=422)
    from foundry.entry_screen import entry_screen
    screen = entry_screen(out["cfg"])
    if screen["blockers"]:
        return JSONResponse({"error": "entry screen refused the translation:\n- "
                              + "\n- ".join(screen["blockers"])}, status_code=422)
    out["warnings"] = screen["warnings"]
    return JSONResponse(out)


@app.post("/api/v31/retro")
async def v31_retro(file: UploadFile = File(...), cfg: str = Form("{}"), _=Depends(gate)):
    """Retrodiction: projection under the posted config vs uploaded actuals."""
    from foundry.retro import load_actuals, compare
    from foundry.v2.run_q import run_v2
    from foundry.v2.validate_q import validate_errors_v2
    data = await file.read()
    try:
        actuals = load_actuals(data, file.filename or "")
        c = json.loads(cfg)
        errs = validate_errors_v2(c)
        if errs:
            return JSONResponse({"error": "config invalid: " + "; ".join(errs[:3])}, status_code=422)
        return JSONResponse(compare(run_v2(c), actuals))
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=422)


@app.get("/api/v31/substrate/status")
def v31_substrate_status(_=Depends(gate)):
    """Is the CharterIQ substrate configured and reachable? Honest either way."""
    from foundry.charteriq_client import CharterIQClient
    cl = CharterIQClient()
    if not cl.configured():
        return JSONResponse({"configured": False,
                              "note": "set CHARTERIQ_DATABASE_URL on this instance"})
    try:
        n = len(cl.list_available_metrics())
        return JSONResponse({"configured": True, "reachable": True, "metrics_catalogued": n})
    except Exception as e:
        return JSONResponse({"configured": True, "reachable": False, "error": str(e)[:200]})


@app.get("/api/v31/substrate/peers")
def v31_substrate_peers(metric: str, band: str, year: int, quarter: int, _=Depends(gate)):
    from foundry.charteriq_client import CharterIQClient, PEER_BANDS
    if band not in PEER_BANDS:
        return JSONResponse({"error": f"unknown band {band}; known: {PEER_BANDS}"}, status_code=422)
    cl = CharterIQClient()
    try:
        row = cl.get_peer_percentiles(metric, band, year, quarter)
    except Exception as e:
        return JSONResponse({"error": str(e)[:300]}, status_code=422)
    if row is None:
        return JSONResponse({"error": f"no percentile row for {metric}/{band}/{year}Q{quarter}"}, status_code=404)
    return JSONResponse(row)


@app.post("/api/v31/retro/substrate")
def v31_retro_substrate(body: dict, _=Depends(gate)):
    """Retrodiction against the substrate: cert + config -> scored overlay.
    Fails closed until CHARTERIQ_RETRO_MAP names the series' metric names."""
    from foundry.charteriq_client import CharterIQClient
    from foundry.retro import compare
    from foundry.v2.run_q import run_v2
    from foundry.v2.validate_q import validate_errors_v2
    cl = CharterIQClient()
    try:
        cert = int(body.get("cert"))
        actuals = cl.get_retro_actuals(cert, since_year=body.get("since_year"))
        inst = cl.get_institution(cert)
        cfg = body.get("cfg") or {}
        errs = validate_errors_v2(cfg)
        if errs:
            return JSONResponse({"error": "config invalid: " + "; ".join(errs[:3])}, status_code=422)
        rep = compare(run_v2(cfg), actuals)
        rep["institution"] = inst
        rep["accuracy"] = actuals.get("accuracy")
        return JSONResponse(rep)
    except (ValueError, TypeError) as e:
        return JSONResponse({"error": str(e)[:600]}, status_code=422)
    except Exception as e:
        return JSONResponse({"error": f"substrate error: {str(e)[:300]}"}, status_code=502)


@app.post("/api/v31/substrate/placement")
def v31_substrate_placement(body: dict, _=Depends(gate)):
    """Modeled capital ratios placed against real peer percentiles (capital
    family only, per the substrate accuracy caveat). Latest covered quarter."""
    from foundry.charteriq_client import CharterIQClient, band_for_assets_mm, placement
    cl = CharterIQClient()
    if not cl.configured():
        return JSONResponse({"error": "substrate not configured"}, status_code=422)
    try:
        assets_k = float(body["q12_total_assets_k"])
        lev = float(body["leverage_pct"])
        band = band_for_assets_mm(assets_k / 1000.0)
        rows, year, quarter = [], 2025, 4
        for metric, modeled, note in (
                ("tier1_ratio", lev, "modeled leverage vs peer tier 1 ratio — "
                  "related but not identical measures; a placement anchor, not a filing figure"),
                ("cet1_ratio", lev, "modeled bank is all-CET1 at this stage, so the "
                  "leverage proxy doubles as the CET1 comparison")):
            p = cl.get_peer_percentiles(metric, band, year, quarter)
            if p:
                p["modeled_value"] = modeled
                p["placement"] = placement(modeled, p)
                p["comparison_note"] = note
                rows.append(p)
        if not rows:
            try:
                groups = cl.available_peer_groups(year, quarter)
            except Exception:
                groups = []
            return JSONResponse({"error": f"no percentile rows for band '{band}' at "
                                  f"{year}Q{quarter}. Groups actually present: "
                                  f"{groups[:40]}"}, status_code=404)
        return JSONResponse({"band": band, "year": year, "quarter": quarter, "rows": rows,
                              "band_note": "band derived from the MODELED Q12 total assets; "
                                            "UBPR peer codes arrive via Deliverable D"})
    except Exception as e:
        return JSONResponse({"error": str(e)[:300]}, status_code=502)


@app.post("/api/v2/sens")
def v2_sens(body: dict, _=Depends(gate)):
    """SENS (FLOOR F-112): one-variable low/base/high sensitivity, three full runs."""
    from foundry.v2.run_q import run_v2
    from foundry.v2.validate_q import validate_errors_v2
    import copy as _copy
    cfg = body.get("config")
    var = body.get("variable")
    lo, hi = body.get("low"), body.get("high")
    if not cfg or not var or lo is None or hi is None:
        return JSONResponse({"error": "config, variable, low, high required"}, status_code=422)
    def _set(c, path, val):
        parts = path.split(".")
        o = c
        for p in parts[:-1]:
            o = o[int(p)] if p.isdigit() else o[p]
        o[parts[-1]] = val
    out = {}
    try:
        for name, val in (("low", lo), ("base", None), ("high", hi)):
            c2 = _copy.deepcopy(cfg)
            if val is not None:
                _set(c2, var, val)
            errs = validate_errors_v2(c2)
            if errs:
                return JSONResponse({"error": f"{name} case invalid",
                                       "errors": errs[:3]}, status_code=422)
            r = run_v2(c2)
            rt = r["financials"]["ratios"]
            def _q12(k):
                s = rt.get(k) or []
                s = [x for x in s if x is not None]
                return s[-1] if s else None
            out[name] = {"value": val, "nim_q12": _q12("nim"), "roa_q12": _q12("roa"),
                          "lev_q12": _q12("lev"),
                          "ni_cum": round(sum(r["financials"]["is"]["ni"][:12]), 1)}
        out["variable"] = var
        out["note"] = ("Patrick's SENS intent: one variable, three full engine runs \u2014 "
                        "distinct from scenario stress, which moves many things at once")
        return JSONResponse(out)
    except (KeyError, IndexError, TypeError) as e:
        return JSONResponse({"error": f"variable path not found: {var} ({e})"},
                             status_code=422)


@app.post("/api/v31/substrate/vintage")
def v31_substrate_vintage(body: dict, _=Depends(gate)):
    """Vintage corridor: age-aligned de novo trajectories from the substrate."""
    from foundry.charteriq_client import CharterIQClient, build_vintage_corridor
    cl = CharterIQClient()
    if not cl.configured():
        return JSONResponse({"error": "substrate not configured"}, status_code=422)
    try:
        est_from = int(body.get("est_from", 2018))
        est_to = int(body.get("est_to", 2023))
        return JSONResponse(build_vintage_corridor(cl, est_from, est_to))
    except ValueError as e:
        return JSONResponse({"error": str(e)[:300]}, status_code=422)
    except Exception as e:
        return JSONResponse({"error": f"substrate error: {str(e)[:300]}"}, status_code=502)


@app.get("/api/v31/fieldlib")
def v31_fieldlib(_=Depends(gate)):
    from foundry import fieldlib as fl
    return JSONResponse({
        "archetypes": {k: {"label": v["label"], "drivers": v["drivers"],
                            "defaults": v["defaults"]}
                        for k, v in fl.ARCHETYPES.items()},
        "tier_a": fl.TIER_A, "tier_b": fl.TIER_B,
        "derived": fl.DERIVED, "phase2": fl.PHASE2})


@app.get("/api/v31/fields")
def v31_fields(activations: str = "", _=Depends(gate)):
    from foundry import fieldlib as fl
    acts = [x for x in activations.split(",") if x]
    try:
        out = fl.fields_for(acts)
        out["typed_count"] = len(out["typed"])
        return JSONResponse(out)
    except KeyError as e:
        return JSONResponse({"error": str(e)}, status_code=422)


@app.post("/api/v31/engagement")
def v31_save_engagement(body: dict, _=Depends(gate)):
    from foundry import store
    try:
        return JSONResponse(store.save_engagement(body.get("cfg") or body,
                                                   slug=body.get("slug")))
    except store.SchemaVersionError as e:
        return JSONResponse({"error": str(e)}, status_code=409)


@app.get("/v3")
@app.get("/v2.2")
@app.get("/v22")
def console_v3(_=Depends(gate)):
    """Foundry v3: the full lineage on one engine — faithful HTML replication
    (v2) + approved JSX enhancements (v2.1) + the Foundry-native layer
    (configuration front door, governance registry, and the Overview/flags
    work to come). Flag-gated and additive; /v2 and /v2.1 are untouched
    rungs. /v2.2 is kept as an alias of /v3."""
    from fastapi.responses import HTMLResponse
    html = open("web/console_v2.html", encoding="utf-8").read()
    html = html.replace("</head>", "<script>window.V3=true</script>\n</head>")
    return HTMLResponse(html)


@app.post("/api/v2/freeze")
def v2_freeze(body: dict, _=Depends(gate)):
    """Notarize the posted configuration: run it and record config+hashes."""
    from foundry.v2 import registry_q
    from foundry.v2.validate_q import validate_errors_v2
    cfg = body.get("cfg") or body
    errs = validate_errors_v2(cfg)
    if errs:
        return JSONResponse({"valid": False, "errors": errs}, status_code=422)
    return JSONResponse(registry_q.freeze(cfg, body.get("label")))


@app.get("/api/v2/registry")
def v2_registry(_=Depends(gate)):
    from foundry.v2 import registry_q
    return JSONResponse({"status": registry_q.status(), "entries": registry_q.list_entries()})


@app.post("/api/v2/verify/{entry_id}")
def v2_verify(entry_id: str, _=Depends(gate)):
    from foundry.v2 import registry_q
    out = registry_q.verify(entry_id)
    if out is None:
        return JSONResponse({"error": "no such frozen run"}, status_code=404)
    return JSONResponse(out)


@app.get("/api/v2/frozen/{entry_id}/config")
def v2_frozen_config(entry_id: str, _=Depends(gate)):
    from foundry.v2 import registry_q
    e = registry_q.get_entry(entry_id)
    if e is None:
        return JSONResponse({"error": "no such frozen run"}, status_code=404)
    return JSONResponse(e["config"])


@app.get("/v2.1")
@app.get("/v21")
def console_v21(_=Depends(gate)):
    """Foundry v2.1: the faithful surface plus approved JSX enhancements
    (Call Report reference column, per-quarter override grids, CBLR cards).
    Same file, same engine; a flag turns the additive layer on so the client
    can choose which surface to deploy."""
    from fastapi.responses import HTMLResponse
    html = open("web/console_v2.html", encoding="utf-8").read()
    html = html.replace("</head>", "<script>window.V21=true</script>\n</head>")
    return HTMLResponse(html)


@app.get("/api/v2/template")
def v2_template(_=Depends(gate)):
    import json as _json
    t = _json.load(open("foundry/fixtures/parity/configs/pf_a_base.json", encoding="utf-8"))
    t["engagement_id"] = "ENG-NEW"; t["parity_expectation"] = None
    t["step_0"]["one_sentence"] = "New applicant scoping template."
    t["step_minus_1"]["alternatives_priced"] = {"de_novo": "Template."}
    t["step_1"]["rationale"] = "Template."
    for c in t["constraints"]:
        c["source"] = "Engagement commitment (edit with citation)"
    t["hq"] = "TBD"; t["prepared_by"] = "Foundry Modeling Workspace"
    return JSONResponse(t)


@app.post("/api/v2/preview")
def v2_preview(cfg: dict, _=Depends(gate)):
    """Preview IS the run (T-PRV): this calls exactly run_v2."""
    from foundry.v2.run_q import run_v2
    from foundry.v2.validate_q import validate_errors_v2
    errs = validate_errors_v2(cfg)
    if errs:
        return JSONResponse({"valid": False, "errors": errs}, status_code=422)
    res = run_v2(cfg)
    try:
        from foundry.v2.callreport import build_call_report
        res["call_report"] = build_call_report(res, cfg)   # presentation only
    except Exception:
        pass   # schedules must never take down the run
    return JSONResponse(res)


@app.post("/api/v2/engagements")
def v2_register(cfg: dict, _=Depends(gate)):
    """Freeze scenario (C.11): save the config, return slug + canonical hashes."""
    import os, re, json as _json
    from foundry.v2.run_q import run_v2
    from foundry.v2.validate_q import validate_errors_v2
    errs = validate_errors_v2(cfg)
    if errs:
        return JSONResponse({"valid": False, "errors": errs}, status_code=422)
    os.makedirs("clients_v2", exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", (cfg.get("proposed_bank") or "engagement").lower()).strip("-")[:40]
    base = slug; i = 1
    while os.path.exists(f"clients_v2/{slug}.json"):
        i += 1; slug = f"{base}-{i}"
    _json.dump(cfg, open(f"clients_v2/{slug}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    r = run_v2(cfg)
    return {"slug": slug, "config_hash": r["config_hash"], "run_hash": r["run_hash"]}


@app.post("/api/v2/exhibit")
def v2_exhibit(cfg: dict, _=Depends(gate)):
    """Results workbook (A.15) for the posted configuration."""
    import io as _io
    from fastapi.responses import StreamingResponse
    from foundry.v2.parity import run_parity
    from foundry.v2.excel_q import results_workbook_v2
    from foundry.v2.validate_q import validate_errors_v2
    errs = validate_errors_v2(cfg)
    if errs:
        return JSONResponse({"valid": False, "errors": errs}, status_code=422)
    buf = _io.BytesIO()
    results_workbook_v2(cfg, run_parity(cfg)).save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=proforma_exhibit.xlsx"})


@app.post("/api/v2/config-workbook")
def v2_config_workbook(cfg: dict, _=Depends(gate)):
    """Banker-native config workbook (A.14) for the posted configuration."""
    import io as _io
    from fastapi.responses import StreamingResponse
    from foundry.v2.excel_q import workbook_from_config_v2
    from foundry.v2.validate_q import validate_errors_v2
    errs = validate_errors_v2(cfg)
    if errs:
        return JSONResponse({"valid": False, "errors": errs}, status_code=422)
    buf = _io.BytesIO()
    workbook_from_config_v2(cfg).save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=foundry_v2_config.xlsx"})


@app.post("/api/v2/parse-workbook")
async def v2_parse_workbook(request: Request, _=Depends(gate)):
    """Upload the config workbook; returns the canonical Tier-3 JSON (A.14).
    Fail-closed: the parsed config is validated before it is returned."""
    from foundry.v2.excel_q import parse_workbook_v2
    from foundry.v2.validate_q import validate_errors_v2
    data = await request.body()
    try:
        cfg = parse_workbook_v2(data)
    except Exception as e:
        return JSONResponse({"valid": False, "errors": [{"message": f"workbook did not parse: {e}"}]}, status_code=422)
    errs = validate_errors_v2(cfg)
    if errs:
        return JSONResponse({"valid": False, "errors": errs}, status_code=422)
    return JSONResponse(cfg)
