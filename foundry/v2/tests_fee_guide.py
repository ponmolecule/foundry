"""Grounding/fail-closed gate for Fee Product Guide Me."""
import io, json, os, sys, types, tempfile, stat
sys.path.insert(0, ".")
from foundry.v2.fee_guide import _guide_output_schema, anthropic_config_status, anthropic_key_file_path, fee_guide_manifest, guide_fee_product, render_guide_plan, resolve_anthropic_api_key, store_anthropic_api_key, validate_guide_plan
from foundry.v2.fee_guide_jobs import submit_fee_guide_job, get_fee_guide_job, _run_job

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
    ck("manifest exposes level paths and Step/Smooth resolution", m.get("level_trajectories")==["flat","growth","explicit_schedule"] and set(m.get("level_resolutions",[]))=={"step","smooth"})
    ck("manifest exposes CAC-owned client count as a reusable Account driver",
       any(x.get("id")=="customer_acquisition_count" for x in m.get("driver_sources",[]))
       and any("CAC owns the customer-book path" in x for x in m.get("special_rules",[])))
    ck("manifest distinguishes revenue share from operating cost % of revenue",
       {x["id"] for x in m.get("cost_kinds",[])}=={"none","per_unit","pct_of_revenue","pct_of_revenue_opex"}
       and any("contra-revenue" in x and "noninterest expense" in x for x in m.get("special_rules",[])))

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
            store_anthropic_api_key("anthropic-test-server-key-1234567890")
            keyf,sourcef=resolve_anthropic_api_key()
            ck("Guide Me reads persistent Foundry server secret", keyf=="anthropic-test-server-key-1234567890" and sourcef=="foundry_secret_file")
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
        {"name":"Custody fee","basis":"balance","driver_source":"managed_notional","driver_trajectory":"flat","coefficient_kind":"not_applicable","coefficient_period":"not_applicable","coefficient_trajectory":"not_applicable","flat_amount_trajectory":"not_applicable","rate_behavior":"flat","cost_kind":"none"},
        {"name":"Settlement fee","basis":"transaction","driver_source":"managed_notional","driver_trajectory":"derived","coefficient_kind":"multiple","coefficient_period":"year","coefficient_trajectory":"explicit_schedule","flat_amount_trajectory":"not_applicable","rate_behavior":"flat","cost_kind":"none"}
      ],"questions":[],"unsupported_mechanics":[]}
    def fake_open(req, timeout=0):
        seen["url"]=req.full_url; seen["headers"]={k.lower():v for k,v in req.header_items()}; seen["payload"]=json.loads(req.data.decode())
        return _Resp({"content":[{"type":"text","text":json.dumps(good)}]})
    out=guide_fee_product("Custody on AUC plus settlement turns.",api_key="test-key",model="test-model",http_open=fake_open)
    ck("Guide Me returns validated multi-stream plan", out["status"]=="plan" and len(out["stream_guides"])==2)
    ck("AUC feed ownership is explained without duplicating AUC", "Customer-Acquisition feed" in out["product_setup"])
    ck("transaction flow instructions expose natural-period coefficient", any("Per to “Year”" in s for s in out["stream_guides"][1]["steps"]))
    pl=seen.get("payload") or {}
    ck("Claude request supplies no tools or retrieval", "tools" not in pl and "url" not in pl and "files" not in pl)
    ck("Claude receives only manifest/system + user's description", pl.get("messages")==[{"role":"user","content":"Custody on AUC plus settlement turns."}] and "FOUNDRY_ENGINE_MANIFEST=" in pl.get("system",""))
    ck("Guide Me system contract keeps flow coefficient and fee/spread in one transaction revenue equation",
       "throughput × fee/spread = revenue" in pl.get("system","") and "belong in ONE transaction stream, not two" in pl.get("system",""))
    fmt=((pl.get("output_config") or {}).get("format") or {})
    ck("Claude request uses Anthropic Structured Outputs", fmt.get("type")=="json_schema" and isinstance(fmt.get("schema"),dict))
    sch=_guide_output_schema()
    ck("structured schema requires closed mixed-result fields", sch.get("additionalProperties") is False and "unsupported_mechanics" in sch.get("required",[]))
    ck("structured schema carries Flat amount trajectory", "flat_amount_trajectory" in json.dumps(sch))
    sch_text=json.dumps(sch)
    ck("structured schema avoids high-latency basis anyOf expansion", '"anyOf"' not in sch_text)
    stream_props=sch["properties"]["streams"]["items"]["properties"]
    ck("structured schema carries account-level, stock-multiplier, and pricing paths",
       all(k in stream_props for k in ("driver_period","driver_resolution","stock_multiplier_trajectory","pricing_trajectory","pricing_period")))
    nullable_fields=("driver_period","driver_resolution","stock_multiplier_trajectory","stock_multiplier_period","stock_multiplier_resolution","pricing_trajectory","pricing_period","pricing_resolution","coefficient_kind","coefficient_period","coefficient_trajectory","flat_amount_trajectory")
    ck("structured schema uses string sentinel instead of nullable enum type arrays", all(stream_props[k].get("type")=="string" and "not_applicable" in stream_props[k].get("enum",[]) for k in nullable_fields))
    ck("structured schema contains no union type arrays", not any(isinstance(v.get("type"),list) for v in stream_props.values()))
    ck("Guide Me disables Sonnet adaptive thinking for low-latency translation", pl.get("thinking")=={"type":"disabled"})

    mixed={
      "status":"needs_clarification","product_label":"Settlement escrow","managed_notional_source":"ask",
      "streams":[
        {"name":"Settlement","basis":"transaction","driver_source":"managed_notional","driver_trajectory":"derived","coefficient_kind":"multiple","coefficient_period":"year","coefficient_trajectory":"explicit_schedule","flat_amount_trajectory":"not_applicable","rate_behavior":"flat","cost_kind":"none"},
        {"name":"Escrow fee","basis":"flat","driver_source":"constant","driver_trajectory":"flat","coefficient_kind":None,"coefficient_period":None,"coefficient_trajectory":None,"flat_amount_trajectory":"explicit_schedule","rate_behavior":"flat","cost_kind":"none"}
      ],
      "questions":["What annual settlement-turn values should be used through Y3 and after normalization?","Should AUC come from Manual assumptions or a Customer-Acquisition feed?"],
      "unsupported_mechanics":[]
    }
    mout=render_guide_plan(mixed)
    ck("mixed settlement + escalating escrow maps both supported streams", mout["status"]=="needs_clarification" and len(mout["stream_guides"])==2 and not mout["unsupported_mechanics"])
    ck("escalating escrow maps to one Flat explicit amount trajectory", any("Amount path to “Explicit Schedule”" in step for step in mout["stream_guides"][1]["steps"]))
    escrow_steps=mout["stream_guides"][1]["steps"]
    ck("Flat periodic Guide Me omits dormant driver/rate axes",
       not any("Driver source" in x or x.startswith("Set Trajectory") or "Rate behavior" in x for x in escrow_steps))

    conversion={
      "status":"plan","product_label":"Conversion service","managed_notional_source":"customer_acquisition_feed",
      "streams":[
        {"name":"Conversion Service Fee","basis":"transaction","driver_source":"managed_notional","driver_trajectory":"derived",
         "coefficient_kind":"pct","coefficient_period":"year","coefficient_trajectory":"explicit_schedule",
         "flat_amount_trajectory":"not_applicable","rate_behavior":"flat","cost_kind":"none"}
      ],"questions":[],"unsupported_mechanics":[]
    }
    cv=render_guide_plan(conversion); cvsteps=cv["stream_guides"][0]["steps"]
    ck("conversion volume percentage + spread maps to one transaction stream",
       len(cv["stream_guides"])==1 and any("Volume % trajectory" in x and "Explicit Schedule" in x for x in cvsteps)
       and any("Fee (% of throughput)" in x and "not a separate fee stream" in x for x in cvsteps))
    ck("explicit coefficient Guide Me never tells user to fill inactive single Flow %",
       any("single “Flow %” field is not used" in x for x in cvsteps)
       and not any(x.endswith("“Flow %”.") for x in cvsteps))
    trustee_plan={
      "status":"plan","product_label":"Reserve & Collateral Trustee Fees","managed_notional_source":"customer_acquisition_feed",
      "streams":[
        {"name":"Annual Retainer per Mandate","basis":"account","driver_source":"constant","driver_trajectory":"explicit_schedule",
         "driver_period":"year","driver_resolution":"smooth",
         "stock_multiplier_trajectory":"not_applicable","stock_multiplier_period":"not_applicable","stock_multiplier_resolution":"not_applicable",
         "pricing_trajectory":"flat","pricing_period":"year","pricing_resolution":"not_applicable",
         "coefficient_kind":"not_applicable","coefficient_period":"not_applicable","coefficient_trajectory":"not_applicable",
         "flat_amount_trajectory":"not_applicable","rate_behavior":"flat","cost_kind":"none"},
        {"name":"Trustee Fee on Reserves","basis":"balance","driver_source":"managed_notional","driver_trajectory":"derived",
         "driver_period":"not_applicable","driver_resolution":"not_applicable",
         "stock_multiplier_trajectory":"flat","stock_multiplier_period":"not_applicable","stock_multiplier_resolution":"not_applicable",
         "pricing_trajectory":"flat","pricing_period":"not_applicable","pricing_resolution":"not_applicable",
         "coefficient_kind":"not_applicable","coefficient_period":"not_applicable","coefficient_trajectory":"not_applicable",
         "flat_amount_trajectory":"not_applicable","rate_behavior":"flat","cost_kind":"none"}
      ],"questions":[],"unsupported_mechanics":[]
    }
    tg=render_guide_plan(trustee_plan); t1=tg["stream_guides"][0]["steps"]; t2=tg["stream_guides"][1]["steps"]
    ck("trustee product maps to Account retainer + Balance reserve fee within five-stream ontology",
       len(tg["stream_guides"])==2 and tg["streams"][0]["basis"]=="account" and tg["streams"][1]["basis"]=="balance")
    ck("Guide Me maps FY-end mandates to Explicit EOP counts with Smooth resolution",
       any("Count path to “Explicit schedule”" in x for x in t1) and any("Resolution to “Smooth”" in x for x in t1)
       and any("does not round" in x for x in t1))
    ck("Guide Me maps reserves as stock % of AUC, not transaction flow",
       any("% of source balance" in x for x in t2) and any("Stock % trajectory to “Flat”" in x for x in t2)
       and not any("Flow coefficient" in x for x in t2))
    ck("Guide Me keeps trustee rate on same Balance stream with Series rate path",
       any("Rate behavior to “Series rate path”" in x for x in t2) and any("Rate path to “Flat”" in x for x in t2))
    ck("Guide Me never misuses Flat amount trajectory for trustee Account/Balance streams",
       not any("Amount path" in x for x in (t1+t2)))

    platform_plan={
      "status":"plan","product_label":"Platform","managed_notional_source":"customer_acquisition_feed",
      "streams":[{
        "name":"Platform Integration & API access","basis":"account",
        "driver_source":"customer_acquisition_count","driver_trajectory":"flat",
        "driver_period":"not_applicable","driver_resolution":"not_applicable",
        "stock_multiplier_trajectory":"not_applicable","stock_multiplier_period":"not_applicable","stock_multiplier_resolution":"not_applicable",
        "pricing_trajectory":"flat","pricing_period":"year","pricing_resolution":"not_applicable",
        "coefficient_kind":"not_applicable","coefficient_period":"not_applicable","coefficient_trajectory":"not_applicable",
        "flat_amount_trajectory":"not_applicable","rate_behavior":"flat","cost_kind":"none"}],
      "questions":[],"unsupported_mechanics":[]}
    pg=render_guide_plan(platform_plan); ps=pg["stream_guides"][0]["steps"]
    ck("Guide Me maps CAC-derived clients directly to Account driver without a second count forecast",
       pg["streams"][0]["driver_source"]=="customer_acquisition_count"
       and any("Client-count source" in x for x in ps)
       and any("do not enter a second count schedule" in x for x in ps)
       and not any("Count schedule period" in x or "Count growth" in x for x in ps))

    platform_redundant=json.loads(json.dumps(platform_plan))
    platform_redundant["streams"][0]["driver_trajectory"]="explicit_schedule"
    platform_redundant["streams"][0]["driver_period"]="year"
    platform_redundant["streams"][0]["driver_resolution"]="step"
    pr=render_guide_plan(platform_redundant)
    ck("CAC-owned count source strips redundant Fee Product count-path metadata",
       pr["streams"][0]["driver_trajectory"]=="flat"
       and pr["streams"][0]["driver_period"] is None
       and pr["streams"][0]["driver_resolution"] is None)

    # r41 live failure shape: Claude could redundantly populate the old Flat-amount
    # trajectory while also returning the correct Account/Balance-native path. That
    # redundancy must not resurrect the old "flat amount trajectory on a non-flat basis"
    # error; the local canonicalizer strips it only when the native path is complete.
    trustee_redundant=json.loads(json.dumps(trustee_plan))
    trustee_redundant["streams"][0]["flat_amount_trajectory"]="explicit_schedule"
    trustee_redundant["streams"][1]["flat_amount_trajectory"]="flat"
    tr=render_guide_plan(trustee_redundant)
    ck("trustee mapping canonicalizes redundant Flat amount metadata on Account/Balance",
       all(x.get("flat_amount_trajectory") is None for x in tr["streams"])
       and not any("Amount path" in step for g in tr["stream_guides"] for step in g["steps"]))

    # r43 live regression: "flat Annual Retainer" can make Claude mark the Account
    # count trajectory flat even while it correctly emits annual EOP count metadata.
    # The retainer's flatness belongs to pricing_trajectory, not driver_trajectory.
    trustee_driver_confused=json.loads(json.dumps(trustee_plan))
    trustee_driver_confused["streams"][0]["driver_trajectory"]="flat"
    # A sourced Balance stock multiplier can also receive redundant driver-level
    # period metadata from the translator; it is non-economic and should be stripped.
    trustee_driver_confused["streams"][1]["driver_period"]="year"
    trustee_driver_confused["streams"][1]["driver_resolution"]="smooth"
    tdc=render_guide_plan(trustee_driver_confused)
    ck("flat retainer cannot overwrite explicit mandate-count trajectory",
       tdc["streams"][0]["driver_trajectory"]=="explicit_schedule"
       and any("Count path to “Explicit schedule”" in x for x in tdc["stream_guides"][0]["steps"]))
    ck("balance stock multiplier strips redundant upstream driver level metadata",
       tdc["streams"][1]["driver_period"] is None and tdc["streams"][1]["driver_resolution"] is None)

    exact_trustee_prompt = """I have another stream to capture: RESERVE & COLLATERAL TRUSTEE FEES, composed of a flat
Annual Retainer per Mandate ($): $20,000 flat for each of the projection horizons (7 years)
Mandates at Period-End (FY end) of 2,4,7,10,13,15,17 for the 7 years, respectively
Flat reserves as % of Avg AUC of 30%
Trustee Fee Rate (% p.a. on reserves) of 0.12% flat across all 7 years
And a Revenue Start Month at Month 13, reflecting a phased rollout approach for stablecoin reserve management, deferred beyond the first operating year."""
    def fake_trustee_driver_confused(req, timeout=0):
        return _Resp({"content":[{"type":"text","text":json.dumps(trustee_driver_confused)}]})
    exact_tdc=guide_fee_product(exact_trustee_prompt,api_key="test-key",model="claude-sonnet-5",http_open=fake_trustee_driver_confused)
    ck("exact trustee prompt survives flat-price vs explicit-count translator confusion",
       exact_tdc["streams"][0]["driver_trajectory"]=="explicit_schedule"
       and exact_tdc["streams"][1]["stock_multiplier_trajectory"]=="flat")

    trustee_wrong=json.loads(json.dumps(trustee_plan))
    trustee_wrong["streams"][0]["driver_trajectory"]="flat"
    trustee_wrong["streams"][0]["driver_period"]="not_applicable"
    trustee_wrong["streams"][0]["driver_resolution"]="not_applicable"
    trustee_wrong["streams"][0]["flat_amount_trajectory"]="explicit_schedule"
    try: validate_guide_plan(trustee_wrong); trustee_wrong_raised=False
    except ValueError: trustee_wrong_raised=True
    ck("Flat amount cannot silently substitute for a missing Account count path", trustee_wrong_raised)
    sys_contract=(seen.get("payload") or {}).get("system","")
    ck("Guide Me system contract distinguishes stock % of AUC from transaction % flow",
       "STOCK multiplier" in sys_contract and "must never be represented as a transaction flow coefficient" in sys_contract)

    opcost_plan={
      "status":"plan","product_label":"Service","managed_notional_source":"not_needed",
      "streams":[{"name":"Service fee","basis":"flat","driver_source":"constant","driver_trajectory":"flat",
                  "coefficient_kind":"not_applicable","coefficient_period":"not_applicable","coefficient_trajectory":"not_applicable",
                  "flat_amount_trajectory":"flat","rate_behavior":"flat","cost_kind":"pct_of_revenue_opex"}],
      "questions":[],"unsupported_mechanics":[]}
    opg=render_guide_plan(opcost_plan)
    ck("Guide Me can map operating cost % of revenue to NIE distinct from revenue share",
       any("Operating cost (% of revenue)" in x for x in opg["stream_guides"][0]["steps"]))
    ck("mixed request keeps targeted clarification questions", len(mout["questions"])==2 and "settlement-turn" in mout["questions"][0])

    # Live r31 regression: Claude can redundantly put the turns schedule on the sourced
    # driver trajectory even though a natural-period flow coefficient necessarily owns
    # that path. Guide Me must canonicalize this structural mismatch to Derived rather
    # than surfacing the engine validator error to the user.
    coefficient_misplaced=json.loads(json.dumps(mixed))
    coefficient_misplaced["streams"][0]["driver_trajectory"]="explicit_schedule"
    user_case = "I have another stream of revenue: Settlement turns multiplied by Average AUC per annum, ramping up to Y3, then normalizing as the book matures. Add a flat settlement rate of 0.03%. Add an escrow fee starting at 150,000, increasing by 50,000 each year through Y7."
    seen_case={}
    def fake_case(req, timeout=0):
        seen_case["payload"]=json.loads(req.data.decode())
        return _Resp({"content":[{"type":"text","text":json.dumps(coefficient_misplaced)}]})
    case_out=guide_fee_product(user_case,api_key="test-key",model="claude-sonnet-5",http_open=fake_case)
    ck("exact settlement + escrow prompt canonicalizes coefficient driver to derived",
       case_out["status"]=="needs_clarification" and len(case_out["stream_guides"])==2
       and case_out["streams"][0]["driver_trajectory"]=="derived" and not case_out["unsupported_mechanics"])
    ck("exact multi-stream regression uses schema-constrained output", (((seen_case.get("payload") or {}).get("output_config") or {}).get("format") or {}).get("type")=="json_schema")
    normalized=render_guide_plan(coefficient_misplaced)
    ck("fee coefficient canonicalizes sourced driver trajectory to derived",
       normalized["streams"][0]["driver_trajectory"]=="derived"
       and any("Trajectory to “Derived (× source)”" in step for step in normalized["stream_guides"][0]["steps"]))

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
    ck("Account Fee UI can consume CAC client count without duplicating count authoring",
       "Customer Acquisition client count" in html and "Client-count source" in html
       and "Follows Customer Acquisition" in html and "do not create a second count forecast here" in html)
    ck("Guide Me is advisory and discloses its grounding boundary", "Nothing in your model was changed" in html and "not your engagement configuration, files, web access, or external tools" in html)
    ck("Guide Me UI renders mixed partial mappings instead of parser failures", "Supported portion Foundry can map now" in html and "Unsupported mechanic" in html and "unsupported_mechanics" in html)
    ck("Guide Me UI submits background jobs instead of holding one Anthropic request open", '/api/v31/fee-guide/jobs' in html and 'Still mapping… Foundry is waiting for Anthropic in the background' in html and 'fetch("/api/v31/fee-guide",' not in html)
    ck("Guide Me modal remains escapable after long clarification output", 'max-height:84vh;overflow-y:auto' in html and 'fee-guide-actions{position:sticky' in html)
    ck("Guide Me exposes always-visible top and footer exits", 'class="modal-close-x"' in html and '>Back to Fee Product</button>' in html and 'onclick="closeFeeGuide();return false"' in html)
    ck("closing Guide Me cancels client polling without mutating the fee product", 'window._feeGuideRunToken=(window._feeGuideRunToken||0)+1' in html and 'runToken!==window._feeGuideRunToken || !window._feeGuideActive' in html)
    ck("Escape key closes an open Guide Me/general modal", 'e.key==="Escape"' in html and 'e.preventDefault(); closeModal();' in html)
    ck("Flat fee UI exposes amount trajectory and explicit pastebox", "Amount path" in html and "feeFlatAmountPaste_" in html and "Amount schedule ($000s per" in html)
    # Async job wrapper: persistent status is shared across web workers, user-bound,
    # and the long Anthropic wait happens outside the browser request.
    saved_job_dir=os.environ.get("FOUNDRY_DATA_DIR")
    try:
        with tempfile.TemporaryDirectory() as td:
            os.environ["FOUNDRY_DATA_DIR"]=td
            job=submit_fee_guide_job("alice","custody fee",runner=lambda d:{"status":"plan","stream_guides":[],"description_seen":d},start_worker=False)
            ck("Guide Me job submission returns immediately with pending id", job.get("status")=="pending" and len(job.get("job_id",''))==32)
            pending=get_fee_guide_job("alice",job["job_id"])
            ck("Guide Me polling reads persistent pending job", pending.get("status")=="pending")
            try:
                get_fee_guide_job("bob",job["job_id"]); isolated=False
            except KeyError:
                isolated=True
            ck("Guide Me jobs are bound to authenticated user", isolated)
            _run_job(job["job_id"],"alice","custody fee",runner=lambda d:{"status":"plan","stream_guides":[],"description_seen":d})
            done=get_fee_guide_job("alice",job["job_id"])
            ck("Guide Me background worker persists completed result", done.get("status")=="done" and (done.get("result") or {}).get("description_seen")=="custody fee")
            job2=submit_fee_guide_job("alice","bad",runner=lambda d: (_ for _ in ()).throw(RuntimeError("Claude API error 429: test")),start_worker=False)
            _run_job(job2["job_id"],"alice","bad",runner=lambda d: (_ for _ in ()).throw(RuntimeError("Claude API error 429: test")))
            err=get_fee_guide_job("alice",job2["job_id"])
            ck("Guide Me background worker preserves actionable upstream category", err.get("status")=="error" and err.get("error_kind")=="rate_limited")
    finally:
        if saved_job_dir is None: os.environ.pop("FOUNDRY_DATA_DIR",None)
        else: os.environ["FOUNDRY_DATA_DIR"]=saved_job_dir

    appsrc=open("app.py",encoding="utf-8").read()
    ck("Guide Me API is authenticated and server-side", '@app.post("/api/v31/fee-guide/jobs")' in appsrc and '@app.get("/api/v31/fee-guide/jobs/{job_id}")' in appsrc and "Depends(gate)" in appsrc)
    ck("Guide Me server classifies upstream auth/rate-limit/timeout failures", "Claude API error 401" in appsrc and "Claude API error 429" in appsrc and "timed out waiting for Anthropic" in appsrc)
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
        denied=appmod.v31_fee_guide_configure({"api_key":"anthropic-test-server-key-1234567890"}, user="ordinary")
        ck("configuration endpoint rejects ordinary account", getattr(denied,"status_code",None)==403)
    finally:
        appmod.USER=saved_user; authmod.load_users=saved_loader
    ck("Guide Me one-time configuration endpoint is privilege-gated", '@app.post("/api/v31/fee-guide/configure")' in appsrc and "_can_manage_fee_guide_secret" in appsrc and "store_anthropic_api_key" in appsrc)
    ck("Guide Me setup UI uses a password field and never renders stored key", 'id="feeGuideApiKey" type="password"' in html and "Save server key" in html and "The key is stored server-side and is not displayed" in html)

    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1
if __name__=="__main__": sys.exit(main())
