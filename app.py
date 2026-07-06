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
