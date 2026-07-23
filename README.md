# Foundry — pilot engagement build

Deterministic bank-model engine (pure Python, zero web dependencies) plus a
thin FastAPI/HTML shell. Fictitious client: Solstice Bank (in organization).

## Run locally
    pip install -r requirements.txt
    python -m foundry.run          # engine only -> results.json
    uvicorn app:app --port 8000    # console at http://localhost:8000

## Deploy (Railway, domain foundry.charteriq.app)
    start command: uvicorn app:app --host 0.0.0.0 --port $PORT

## Access (HTTP Basic auth)
    demo defaults (baked in, FICTITIOUS DATA ONLY):
        username: klaros
        password: (set via FOUNDRY_PASS env var)
    Override in Railway -> service -> Variables before sharing any URL:
        FOUNDRY_USER, FOUNDRY_PASS
    /api/health stays unauthenticated for deploy probes.
    Basic auth is a demo placeholder; it does not satisfy the Phase C0
    real-data gate. No real client data behind this gate, ever.

## Layout
    foundry/client_solstice.py  Tier 3 configuration (steps -1..3, constraints, assumptions)
    foundry/peers.py            Step 4: bounded-radius cohort, kernel priors (fixture reference data)
    foundry/chassis.py          Steps 3/6/7: volume engine, monthly loop w/ identity enforcement,
                                scenarios, reverse stress
    foundry/challenge.py        Step 6 flags + step 8 examiner book (deterministic templating)
    foundry/run.py              Orchestrator -> results dict
    app.py, web/index.html      The shell

## Status (v0.2.1)
- Tier 2 module dispatch live: two clients (Solstice digital consumer, Blackland CRE community) run
  through one chassis from configuration alone. Protocol harness: python -m foundry.tests_protocol (22/23).
- Reference peers remain a synthetic fixture (fixture-v2, stable under extension); swap point at
  foundry/peers.py REFERENCE.
- Known open items: config-schema validation (T14 red check), journal-entry engine, prior-metric
  definition parity with the production reference warehouse. All client facts fictitious.
