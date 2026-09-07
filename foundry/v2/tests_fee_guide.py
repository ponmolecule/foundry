"""Grounding/fail-closed gate for Fee Product Guide Me."""
import io, json, sys
sys.path.insert(0, ".")
from foundry.v2.fee_guide import fee_guide_manifest, guide_fee_product, validate_guide_plan

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

    seen={}
    good={
      "status":"plan","product_label":"Custody services","managed_notional_source":"customer_acquisition_feed",
      "streams":[
        {"name":"Custody fee","basis":"balance","driver_source":"managed_notional","driver_trajectory":"flat","coefficient_kind":None,"coefficient_period":None,"coefficient_trajectory":None,"rate_behavior":"flat","cost_kind":"none"},
        {"name":"Settlement fee","basis":"transaction","driver_source":"managed_notional","driver_trajectory":"derived","coefficient_kind":"multiple","coefficient_period":"year","coefficient_trajectory":"explicit_schedule","rate_behavior":"flat","cost_kind":"none"}
      ],"questions":[]}
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
    appsrc=open("app.py",encoding="utf-8").read()
    ck("Guide Me API is authenticated and server-side", '@app.post("/api/v31/fee-guide")' in appsrc and "Depends(gate)" in appsrc and "ANTHROPIC_API_KEY" in appsrc)

    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1
if __name__=="__main__": sys.exit(main())
