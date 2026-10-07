"""r310: Guide Me "Apply plan". A validated plan becomes real fee streams with every assumption left at zero.

Covers the server materialiser (shapes, links, the list of values still to enter), the engine at zero and with
values, the endpoint, and the console hooks (review panel, chips, banner, guard itemisation).
"""
import json
import sys
from copy import deepcopy
from pathlib import Path

NA = "not_applicable"
FIXTURE = "foundry/fixtures/universal_template_bank.json"


def item(**kw):
    base = dict(name="Fee stream", basis="flat", driver_source="constant", driver_reference=NA, entered_driver_kind=NA,
                driver_trajectory="flat", driver_period=NA, driver_resolution=NA, customer_count_measure=NA,
                stock_multiplier_trajectory=NA, stock_multiplier_period=NA, stock_multiplier_resolution=NA,
                pricing_trajectory=NA, pricing_period=NA, pricing_resolution=NA, transaction_pricing_basis=NA,
                coefficient_kind=NA, coefficient_semantics=NA, coefficient_period=NA, coefficient_trajectory=NA,
                flat_amount_trajectory=NA, rate_behavior="flat", cost_kind="none", revenue_presentation="revenue")
    base.update(kw)
    return base


PLAN = [
    item(name="Account fee", basis="account", driver_source="customer_acquisition_count", customer_count_measure="period_end",
         pricing_trajectory="flat", pricing_period="month"),
    item(name="Card-processing fee", basis="transaction", entered_driver_kind="money_flow", driver_trajectory="proportional",
         driver_period="month", transaction_pricing_basis="pct_of_throughput"),
    item(name="Platform subscription", basis="flat", flat_amount_trajectory="growth"),
]
PLAN2 = [
    item(name="Advisory fee", basis="balance", driver_source="managed_notional", rate_behavior="annual_change",
         pricing_trajectory="flat", pricing_period="year", pricing_resolution="step"),
    item(name="Event fee", basis="event"),
]


def _get(o, path):
    for k in path.split("."):
        if not isinstance(o, dict) or k not in o:
            return KeyError
        o = o[k]
    return o


def _nonzero(v):
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, dict):
        return any(_nonzero(x) for x in v.values())
    if isinstance(v, list):
        return any(_nonzero(x) for x in v)
    return False


def main():
    from foundry.v2 import run_q
    from foundry.v2.fee_guide import materialize_guide_streams
    from foundry.v2.validate_q import validate_errors_v2
    p = f = 0

    def ck(name, cond, detail=""):
        nonlocal p, f
        if cond:
            p += 1; print("  PASS ", name)
        else:
            f += 1; print("  FAIL ", name, detail)

    # --- materialiser ---
    r0 = materialize_guide_streams(PLAN)["streams"]
    ck("three plan items give three rows, in order", [x["name"] for x in r0] == [i["name"] for i in PLAN])
    ck("a customer-count stream waits for its feed instead of guessing one",
       r0[0].get("link_kind") == "customer_count" and "stream" not in r0[0] and r0[0].get("missing"))
    ck("streams with no link are built straight away", all("stream" in x and not x.get("error") for x in r0[1:]))
    r = materialize_guide_streams(PLAN, {"0": "cac-count-universal"})["streams"]
    ck("with the feed chosen every stream is built", all("stream" in x for x in r), str([x.get("error") or x.get("missing") for x in r]))
    ck("the chosen feed is written to the driver", r[0]["stream"]["driver"].get("ref") == "cac-count-universal")
    ck("names can be overridden at apply time",
       materialize_guide_streams(PLAN, {"0": "cac-count-universal"}, {"1": "Card fee"})["streams"][1]["stream"]["name"] == "Card fee")
    allrows = r + materialize_guide_streams(PLAN2)["streams"]
    ck("balance annual-change and event streams are built too", all("stream" in x for x in allrows))
    needs_ok = all(_get(x["stream"], n["path"]) is not KeyError for x in allrows for n in x["needs"])
    ck("every value-to-enter path exists in the built stream", needs_ok)
    ck("every stream has at least one required value to enter", all(any(not n.get("optional") for n in x["needs"]) for x in allrows))
    ck("Guide Me picks no assumptions: every value to enter starts at zero",
       not any(_nonzero(_get(x["stream"], n["path"])) for x in allrows for n in x["needs"]))
    ck("a fixed fee asks for an amount, not a driver",
       [n["label"] for n in r[2]["needs"] if not n.get("optional")] == ["Flat fee (per year)"], str(r[2]["needs"]))
    ck("growth rates are marked optional", all(n.get("optional") for x in allrows for n in x["needs"] if "growth" in n["label"].lower()))
    try:
        materialize_guide_streams([dict(PLAN[0], basis="nonsense")]); bad = False
    except ValueError:
        bad = True
    ck("an invalid plan is refused", bad)

    # --- engine: zero until filled, then revenue ---
    cfg = json.loads(Path(FIXTURE).read_text(encoding="utf-8"))
    prod = next(x for x in cfg["assumptions"]["obs_exposures"] if x.get("fee_streams"))

    def fee_total(c):
        return float(sum(run_q.run_v2(deepcopy(c))["financials"]["is"]["fees"]))

    base_errs = len(validate_errors_v2(deepcopy(cfg)))
    base_total = fee_total(cfg)
    c1 = deepcopy(cfg)
    p1 = next(x for x in c1["assumptions"]["obs_exposures"] if x.get("name") == prod["name"])
    built = [deepcopy(x["stream"]) for x in r]
    for i, st in enumerate(built):
        if st["basis"] in ("account", "transaction", "balance"):
            st["quantity_series_id"] = f"fee-qty-r310-{i}"
    p1["fee_streams"].extend(built)
    ck("the configuration still validates with the new streams at zero", len(validate_errors_v2(deepcopy(c1))) == base_errs)
    z = fee_total(c1)
    ck("streams at zero add nothing to fee income", abs(z - base_total) < 1e-6, f"{z} vs {base_total}")
    c2 = deepcopy(c1)
    p2 = next(x for x in c2["assumptions"]["obs_exposures"] if x.get("name") == prod["name"])
    flat = next(s for s in p2["fee_streams"] if s["name"] == "Platform subscription")
    path = next(n["path"] for n in r[2]["needs"] if not n.get("optional"))
    o = flat
    ks = path.split(".")
    for k in ks[:-1]: o = o[k]
    if isinstance(o[ks[-1]], dict): o[ks[-1]]["value"] = 120000
    else: o[ks[-1]] = 120000
    ck("entering a value turns the stream on", fee_total(c2) > z + 1)

    # --- endpoint ---
    app_src = Path("app.py").read_text(encoding="utf-8")
    ck("materialise endpoint is gated and returns 422 on an invalid plan",
       '@app.post("/api/v31/fee-guide/materialize")' in app_src and "def v31_fee_guide_materialize(body: dict, _=Depends(gate))" in app_src
       and "status_code=422" in app_src[app_src.index("def v31_fee_guide_materialize"):app_src.index("def v31_fee_guide_materialize") + 1200])

    # --- console ---
    html = Path("web/console_v2.html").read_text(encoding="utf-8")
    ck("the plan result offers Review & apply", "function _feeGuideApplyCtaHtml(" in html and "if(_guides.length)h += _feeGuideApplyCtaHtml(j);" in html)
    ck("review panel: nothing changes until Apply; a required link blocks it",
       "window.feeGuideApplyReview=async function(){" in html and "window.feeGuideApplyConfirm=async function(){" in html
       and "const unchosen=S.rows.map(" in html and "Keep checklist only" in html)
    ck("add alongside or replace existing streams", "feeGuideApplyMode('add')" in html and "feeGuideApplyMode('replace')" in html
       and "if(S.mode==='replace'){ if(typeof feeConfirmDeletion==='function'&&!feeConfirmDeletion(p,(p.fee_streams||[]).slice())) return; p.fee_streams=[]; }" in html)
    ck("Replace warns when other items read the streams it removes, and does not offer them as sources",
       "Replacing removes streams that other items read:" in html and "return _fgaAllStreams((S.rows[k]||{}).basis).filter(o=>!own.has(o.value));" in html)
    ck("the deletion warning also names expense lines that read a removed stream", "nie_detail:'Operating expenses'" in html and "!/^Operating expenses/.test(label)" in html)
    ck("applied streams get quantity ids and land on the Fee streams tab",
       "st.quantity_series_id=_seriesId('fee-qty')" in html and "window._prdTab='streams';" in html)
    ck("new streams carry a NEW chip and a count of values still to enter",
       "function _fgChipHtml(st){" in html and "${esc(z.name)}${typeof _fgChipHtml==='function'?_fgChipHtml((p.fee_streams||[])[k]):''}" in html)
    ck("banner counts the values to enter and links to the first", "function _fgBannerHtml(p,fi){" in html and "if(typeof _fgBannerHtml==='function') h += _fgBannerHtml(p,_fi);" in html
       and "They contribute $0 until you fill them in." in html)
    ck("the unsaved-changes list itemises fee streams", 'if(k==="fee_streams") namedList(`${prefix}Fee stream`, v0, v1, "name");' in html)
    ck("opening a fee product is not itself listed as a change", 'if(k==="managed_notional" && v0==null && isObj(v1)' in html)
    ck("build stamp", Path("BUILD_STAMP").read_text().strip() == "foundry-r310-guide-me-apply")
    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
