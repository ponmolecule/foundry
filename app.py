"""Foundry web shell. Thin FastAPI wrapper over the pure-Python engine.

Multi-engagement, gated by HTTP Basic auth. Credentials come from
environment variables (FOUNDRY_USER / FOUNDRY_PASS) with demo defaults;
set real values in Railway before sharing the URL.

Basic auth is a demo placeholder, NOT Phase C0-grade authentication.
No real client data behind this gate. Ever.

Deploy: uvicorn app:app --host 0.0.0.0 --port $PORT
"""
import os, secrets, json
from fastapi import Request, FastAPI, HTTPException, Depends, UploadFile, File
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


@app.get("/v3.1")
@app.get("/v31")
def console_v31(_=Depends(gate)):
    """Foundry v3.1 (input-spec rung): the v3 shell plus the input layer -
    Start screen (config-source selector), wizard, FIW. Engine untouched;
    /v2, /v2.1, /v3 are frozen rungs."""
    from fastapi.responses import HTMLResponse
    html = open("web/console_v2.html", encoding="utf-8").read()
    html = html.replace("</head>", "<script>window.V31=true</script>\n</head>")
    return HTMLResponse(html)


@app.get("/api/v31/engagements")
def v31_engagements(_=Depends(gate)):
    from foundry import store
    return JSONResponse({"engagements": store.list_engagements(),
                          "schema_version": store.CONFIG_SCHEMA_VERSION})


@app.get("/api/v31/engagement/{slug}")
def v31_engagement(slug: str, _=Depends(gate)):
    from foundry import store
    try:
        return JSONResponse(store.load_engagement(slug))
    except FileNotFoundError:
        return JSONResponse({"error": "no such engagement"}, status_code=404)
    except store.SchemaVersionError as e:
        return JSONResponse({"error": str(e)}, status_code=409)


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
    return JSONResponse(run_v2(cfg))


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
