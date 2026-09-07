"""Grounding/fail-closed gate for Fee Product Guide Me."""
import io, json, os, sys, types, tempfile, stat
sys.path.insert(0, ".")
from foundry.v2.fee_guide import _guide_output_schema, anthropic_config_status, anthropic_key_file_path, fee_guide_manifest, guide_fee_product, render_guide_plan, resolve_anthropic_api_key, store_anthropic_api_key, validate_guide_plan

class _Resp:
    def __init__(self, obj): self._b=json.dumps(obj).encode()
    def read(self): return self._b
    def __enter__(self): return self
    def __exit__(self,*a): return False

def main():
    p=f=0
    def ck(n,c,d=""):
        nonlocal p,f
        if c: p+=1; print("  PASS ",n)
        else: f+=1; print("  FAIL ",n,d)

    m=fee_guide_manifest()
    ck("manifest is closed over current five fee bases", {x["id"] for x in m["bases"]}=={"balance","transaction","account","flat","event"})
    ck("manifest exposes natural periods but not legacy model_period", set(m["natural_periods"])=={"month","quarter","year"})
    ck("manifest exposes Flat amount trajectories", m.get("flat_amount_trajectories")==["flat","growth","explicit_schedule"])

    # Guide Me credential resolution is server-only and must work even though
    # Foundry is deployed separately from CharterIQ. Environment wins, then a
    # persistent Foundry secret file, then legacy/co-located config.settings.
    saved_env={k:os.environ.get(k) for k in ("ANTHROPIC_API_KEY","FOUNDRY_ANTHROPIC_API_KEY","FOUNDRY_DATA_DIR","FOUNDRY_ANTHROPIC_KEY_FILE")}
    saved_config=sys.modules.get("config")
    saved_settings=sys.modules.get("config.settings")
    for k in ("ANTHROPIC_API_KEY","FOUNDRY_ANTHROPIC_API_KEY","FOUNDRY_ANTHROPIC_KEY_FILE"):
        os.environ.pop(k, None)
    pkg=types.ModuleType("config"); pkg.__path__=[]
    sm=types.ModuleType("config.settings"); sm.ANTHROPIC_API_KEY="settings-key"
    sys.modules["config"]=pkg; sys.modules["config.settings"]=sm
    try:
        with tempfile.TemporaryDirectory() as td:
            os.environ["FOUNDRY_DATA_DIR"]=td
            key,source=resolve_anthropic_api_key()
            ck("Guide Me retains co-located config.settings fallback", key=="settings-key" and source=="config.settings")
            store_anthropic_api_key("sk-ant-test-server-key-1234567890")
            keyf,sourcef=resolve_anthropic_api_key()
            ck("Guide Me reads persistent Foundry server secret", keyf=="sk-ant-test-server-key-1234567890" and sourcef=="foundry_secret_file")
            mode=stat.S_IMODE(os.stat(anthropic_key_file_path()).st_mode)
            ck("Guide Me persistent secret is owner-only", mode==0o600, oct(mode))
            st=anthropic_config_status()
            ck("Guide Me status recognizes persistent secret without exposing it", st.get("configured") is True and st.get("credential_source")=="foundry_secret_file" and "key" not in st)
            os.environ["FOUNDRY_ANTHROPIC_API_KEY"]="foundry-env-key"
            keyfe,sourcefe=resolve_anthropic_api_key()
            ck("Foundry-specific environment secret beats persistent file", keyfe=="foundry-env-key" and sourcefe=="foundry_environment")
            os.environ["ANTHROPIC_API_KEY"]="shared-env-key"
            key2,source2=resolve_anthropic_api_key()
            ck("standard environment secret has highest precedence", key2=="shared-env-key" and source2=="environment")
    finally:
        for k,v in saved_env.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k]=v
        if saved_config is None: sys.modules.pop("config", None)
        else: sys.modules["config"]=saved_config
        if saved_settings is None: sys.modules.pop("config.settings", None)
        else: sys.modules["config.settings"]=saved_settings

    seen={}
    good={
      "status":"plan","product_label":"Custody services","managed_notional_source":"customer_acquisition_feed",
      "streams":[
        {"name":"Custody fee","basis":"balance","driver_source":"managed_notional","driver_trajectory":"flat","coefficient_kind":None,"coefficient_period":None,"coefficient_trajectory":None,"flat_amount_trajectory":None,"rate_behavior":"flat","cost_kind":"none"},
        {"name":"Settlement fee","basis":"transaction","driver_source":"managed_notional","driver_trajectory":"derived","coefficient_kind":"multiple","coefficient_period":"year","coefficient_trajectory":"explicit_schedule","flat_amount_trajectory":None,"rate_behavior":"flat","cost_kind":"none"}
      ],"questions":[],"unsupported_mechanics":[]}
    def fake_open(req, timeout=0):
        seen["url"]=req.full_url; seen["headers"]={k.lower():v for k,v in req.header_items()}; seen["payload"]=json.loads(req.data.decode())
        return _Resp({"content":[{"type":"text","text":json.dumps(good)}]})
    out=guide_fee_product("Custody on AUC plus settlement turns.",api_key="test-key",model="test-model",http_open=fake_open)
    ck("Guide Me returns validated multi-stream plan", out["status"]=="plan" and len(out["stream_guides"])==2)
    ck("AUC feed ownership is explained without duplicating AUC", "Customer-Acquisition feed" in out["product_setup"])
    ck("transaction flow instructions expose natural-period coefficient", any("Per = “Year”" in s for s in out["stream_guides"][1]["steps"]))
    pl=seen.get("payload") or {}
    ck("Claude request supplies no tools or retrieval", "tools" not in pl and "url" not in pl and "files" not in pl)
    ck("Claude receives only manifest/system + user's description", pl.get("messages")==[{"role":"user","content":"Custody on AUC plus settlement turns."}] and "FOUNDRY_ENGINE_MANIFEST=" in pl.get("system",""))
    fmt=((pl.get("output_config") or {}).get("format") or {})
    ck("Claude request uses Anthropic Structured Outputs", fmt.get("type")=="json_schema" and isinstance(fmt.get("schema"),dict))
    sch=_guide_output_schema()
    ck("structured schema requires closed mixed-result fields", sch.get("additionalProperties") is False and "unsupported_mechanics" in sch.get("required",[]))
    ck("structured schema carries Flat amount trajectory", "flat_amount_trajectory" in json.dumps(sch))

    mixed={
      "status":"needs_clarification","product_label":"Settlement escrow","managed_notional_source":"ask",
      "streams":[
        {"name":"Settlement","basis":"transaction","driver_source":"managed_notional","driver_trajectory":"derived","coefficient_kind":"multiple","coefficient_period":"year","coefficient_trajectory":"explicit_schedule","flat_amount_trajectory":None,"rate_behavior":"flat","cost_kind":"none"},
        {"name":"Escrow fee","basis":"flat","driver_source":"constant","driver_trajectory":"flat","coefficient_kind":None,"coefficient_period":None,"coefficient_trajectory":None,"flat_amount_trajectory":"explicit_schedule","rate_behavior":"flat","cost_kind":"none"}
      ],
      "questions":["What annual settlement-turn values should be used through Y3 and after normalization?","Should AUC come from Manual assumptions or a Customer-Acquisition feed?"],
      "unsupported_mechanics":[]
    }
    mout=render_guide_plan(mixed)
    ck("mixed settlement + escalating escrow maps both supported streams", mout["status"]=="needs_clarification" and len(mout["stream_guides"])==2 and not mout["unsupported_mechanics"])
    ck("escalating escrow maps to one Flat explicit amount trajectory", any("Amount path to “Explicit Schedule”" in step for step in mout["stream_guides"][1]["steps"]))
    ck("mixed request keeps targeted clarification questions", len(mout["questions"])==2 and "settlement-turn" in mout["questions"][0])

    user_case = "I have another stream of revenue: Settlement turns multiplied by Average AUC per annum, ramping up to Y3, then normalizing as the book matures. A flat settlement rate of 0.03% and an escrow fee starting at 150,000, which increases by 50,000 every year through Y7. Revenue starts in month 1"
    seen_case={}
    def fake_case(req, timeout=0):
        seen_case["payload"]=json.loads(req.data.decode())
        return _Resp({"content":[{"type":"text","text":json.dumps(mixed)}]})
    case_out=guide_fee_product(user_case,api_key="test-key",model="claude-sonnet-5",http_open=fake_case)
    ck("settlement + escalating escrow prompt maps both streams and asks only needed questions", case_out["status"]=="needs_clarification" and len(case_out["stream_guides"])==2 and not case_out["unsupported_mechanics"])
    ck("exact multi-stream regression uses schema-constrained output", (((seen_case.get("payload") or {}).get("output_config") or {}).get("format") or {}).get("type")=="json_schema")

    bad=json.loads(json.dumps(good)); bad["streams"][0]["basis"]="royalty_magic"
    try: validate_guide_plan(bad); raised=False
    except ValueError: raised=True
    ck("hallucinated basis fails closed", raised)
    bad2=json.loads(json.dumps(good)); bad2["streams"][1]["basis"]="balance"
    try: validate_guide_plan(bad2); raised2=False
    except ValueError: raised2=True
    ck("double-periodization shape fails closed through engine validator", raised2)
    bad3=json.loads(json.dumps(good)); bad3["streams"][0]["rate_behavior"]="durbin_capped"
    try: validate_guide_plan(bad3); raised3=False
    except ValueError: raised3=True
    ck("basis/rate incompatibility fails closed", raised3)
    bad4=json.loads(json.dumps(good)); bad4["assumptions"]={"rate":0.002}
    try: validate_guide_plan(bad4); raised4=False
    except ValueError: raised4=True
    ck("invented top-level assumptions fail closed", raised4)
    bad5=json.loads(json.dumps(good)); bad5["streams"][0]["assumed_rate"]=0.002
    try: validate_guide_plan(bad5); raised5=False
    except ValueError: raised5=True
    ck("invented stream fields fail closed", raised5)

    try: guide_fee_product("x",api_key="",http_open=fake_open); nokey=False
    except RuntimeError: nokey=True
    ck("missing Claude API key fails closed", nokey)

    html=open("web/console_v2.html",encoding="utf-8").read()
    ck("Fee Product UI exposes Guide Me beside fee streams", "openFeeGuide(${_fi})" in html and ">Guide Me</button>" in html)
    ck("Guide Me is advisory and discloses its grounding boundary", "Nothing in your model was changed" in html and "not your engagement configuration, files, web access, or external tools" in html)
    ck("Guide Me UI renders mixed partial mappings instead of parser failures", "Supported portion Foundry can map now" in html and "Unsupported mechanic" in html and "unsupported_mechanics" in html)
    ck("Flat fee UI exposes amount trajectory and explicit pastebox", "Amount path" in html and "feeFlatAmountPaste_" in html and "Amount schedule ($000s per" in html)
    appsrc=open("app.py",encoding="utf-8").read()
    ck("Guide Me API is authenticated and server-side", '@app.post("/api/v31/fee-guide")' in appsrc and "Depends(gate)" in appsrc and "ANTHROPIC_API_KEY" in appsrc)
    import app as appmod
    from foundry import auth as authmod
    saved_user=appmod.USER; saved_loader=authmod.load_users
    try:
        appmod.USER="legacy-operator"
        ck("legacy server operator may configure Guide Me", appmod._can_manage_fee_guide_secret("legacy-operator"))
        appmod.USER=""
        authmod.load_users=lambda: {"admin":{"admin":True},"deputy":{"deputy":True},"ordinary":{}}
        ck("privileged Foundry accounts may configure Guide Me", appmod._can_manage_fee_guide_secret("admin") and appmod._can_manage_fee_guide_secret("deputy"))
        ck("ordinary authenticated account cannot configure Guide Me", not appmod._can_manage_fee_guide_secret("ordinary"))
        denied=appmod.v31_fee_guide_configure({"api_key":"sk-ant-test-server-key-1234567890"}, user="ordinary")
        ck("configuration endpoint rejects ordinary account", getattr(denied,"status_code",None)==403)
    finally:
        appmod.USER=saved_user; authmod.load_users=saved_loader
    ck("Guide Me one-time configuration endpoint is privilege-gated", '@app.post("/api/v31/fee-guide/configure")' in appsrc and "_can_manage_fee_guide_secret" in appsrc and "store_anthropic_api_key" in appsrc)
    ck("Guide Me setup UI uses a password field and never renders stored key", 'id="feeGuideApiKey" type="password"' in html and "Save server key" in html and "The key is stored server-side and is not displayed" in html)

    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1
if __name__=="__main__": sys.exit(main())
