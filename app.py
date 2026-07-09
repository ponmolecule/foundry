"""Foundry web shell. Thin FastAPI wrapper over the pure-Python engine.

Multi-engagement, gated by HTTP Basic auth. Credentials come from
environment variables (FOUNDRY_USER / FOUNDRY_PASS) with demo defaults;
set real values in Railway before sharing the URL.

Basic auth is a demo placeholder, NOT Phase C0-grade authentication.
No real client data behind this gate. Ever.

Deploy: uvicorn app:app --host 0.0.0.0 --port $PORT
"""
import os, secrets, json
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from foundry.run import run
from foundry.registry import ENGAGEMENTS, register_config
from foundry.configio import ConfigError

USER = os.environ.get("FOUNDRY_USER", "klaros")
PASS = os.environ.get("FOUNDRY_PASS", "solstice-2026")

app = FastAPI(title="Foundry", version="0.2.1")
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


@app.get("/api/v2/template")
def v2_template(_=Depends(gate)):
    import json as _json
    t = _json.load(open("foundry/fixtures/parity/configs/pf_a_base.json"))
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
    _json.dump(cfg, open(f"clients_v2/{slug}.json", "w"), indent=1)
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
