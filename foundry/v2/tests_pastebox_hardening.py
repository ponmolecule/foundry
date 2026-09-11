"""Exhaustive browser paste-surface hardening gate.

This gate exists because pasteboxes are model-authoring controls, not cosmetic widgets.
A live-validation/state bug can silently prevent an assumption from reaching the model.
The contract is therefore structural:
  * every scalar Explicit Series uses one fail-closed parser/controller;
  * every rendered Load button is scoped to its own textarea id;
  * structured bulk imports keep domain-specific parsers but share per-box activation;
  * state/DOM identifiers are distinct across modules and stable where names can collide.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


def main():
    p = f = 0

    def ck(name, cond, detail=""):
        nonlocal p, f
        if cond:
            p += 1
            print("  PASS ", name + (f" — {detail}" if detail else ""))
        else:
            f += 1
            print("  FAIL ", name + (f" — {detail}" if detail else ""))

    html = Path("web/console_v2.html").read_text(encoding="utf-8")

    # Inventory every actual paste textarea in the shipped console. Guide Me is free text,
    # not a model-schedule pastebox, and is deliberately excluded.
    paste_lines = [ln for ln in html.splitlines() if "<textarea" in ln and "feeGuideDesc" not in ln and "model-free-text" not in ln]
    ck("paste-surface inventory is explicit and complete", len(paste_lines) == 19, str(len(paste_lines)))
    ck("every paste textarea has live per-box activation wiring", all("oninput=" in ln for ln in paste_lines))

    # Fifteen scalar schedule families: eight Fee Product paths (transaction coefficient, Flat amount,
    # Account count, Balance stock %, Balance rate, Account fee, Cost-recovery markup, entered cost base),
    # two Operating Expense cost-pool paths (entered cost base and cost-recovery markup), plus CAC
    # driver/attrition, Workforce Count/Compensation, and individual Operating Expense schedule.
    scalar_markers = [
        "feeCoeffPaste_", "feeFlatAmountPaste_", "feeAccountLevelPaste_", "feeStockPctPaste_",
        "feeBalanceRatePaste_", "feeAccountFeePaste_", "feeCostRecoveryMarkupPaste_", "feeCostBasePaste_",
        "nieCostBasePaste_", "nieCostPoolMarkupPaste_", "cacPaste_", "cacAttritionPaste_",
        "wfCountPaste_", "wfCompPaste_", "nieCatExplicitPaste_",
    ]
    ck("all fifteen scalar Explicit schedule families are present", all(x in html for x in scalar_markers))
    ck("scalar schedules share one fail-closed parser", "function _seriesExplicitValues(text)" in html
       and html.count("raw=_seriesExplicitValues(txt)") >= 5
       and "function _feeParseExplicitValues(text){ return _seriesExplicitValues(text).map" in html)
    ck("scalar schedules share one live Load controller", "function _seriesExplicitPasteInput(id)" in html
       and "function _feeCoeffPasteInput(id){ _seriesExplicitPasteInput(id); }" in html
       and "function _feeFlatAmountPasteInput(id){ _seriesExplicitPasteInput(id); }" in html)

    # All scalar families must render a disabled Load button that is explicitly tied to textarea_id_load.
    scalar_load_fragments = [
        'id="${_cid}_load" class="pillbtn" disabled',
        'id="${_fid}_load" class="pillbtn" disabled',
        'id="${_lid}_load" class="pillbtn" disabled',
        'id="${_smid}_load" class="pillbtn" disabled',
        'id="${_rid}_load" class="pillbtn" disabled onclick="_feeSetBalanceRateSchedule',
        'id="${_ufid}_load" class="pillbtn" disabled',
        'id="${_mid}_load" class="pillbtn" disabled onclick="_feeSetCostRecoveryMarkupSchedule',
        "id=\"${_eid}_load\" class=\"pillbtn\" disabled onclick='_feeSetCostPoolEnteredSchedule",
        "id=\"${eid}_load\" class=\"pillbtn\" disabled onclick='_feeSetCostPoolEnteredSchedule",
        'id="${mid}_load" class="pillbtn" disabled onclick="${typed?',
        'id="${boxId}_load" class="pillbtn" disabled',
        'id="${_aid}_load" class="pillbtn" disabled',
        'id="${_rid}_load" class="pillbtn" disabled onclick="nieWorkforceCountPaste',
        'id="${_rid}_load" class="pillbtn" disabled onclick="nieWorkforceCompPaste',
        'id="${_rid}_load" class="pillbtn" disabled onclick="nieCatSchedulePaste',
    ]
    ck("every scalar schedule Load button is textarea-scoped and initially disabled",
       all(x in html for x in scalar_load_fragments)
       and "nieCatCostPoolComponentSetMarkupSchedule" in html
       and "nieCatCostPoolSetMarkupSchedule" in html)

    clear_markers = [
        "_feeClearCoeffSchedule", "_feeClearFlatAmountSchedule", "_feeClearAccountLevelSchedule",
        "_feeClearStockMultiplierSchedule", "_feeClearBalanceRateSchedule", "_feeClearAccountFeeSchedule",
        "_feeClearCostRecoveryMarkupSchedule", "_feeClearCostPoolEnteredSchedule",
        "nieCatCostPoolClearMarkupSchedule", "cacScheduleClear", "cacFeedExplicitClear", "nieWorkforceCountClear", "nieWorkforceCompClear",
        "nieCatScheduleClear",
    ]
    ck("every scalar Explicit schedule family has an isolated Clear action", all(x in html for x in clear_markers))

    # CAC used to derive DOM ids from sanitized user-facing feed names. A-B and A_B could then
    # collide. Stable Series IDs now own the pastebox identity.
    ck("CAC scalar pasteboxes use stable Series IDs instead of sanitized feed-name identity",
       "String(sp.series_id||fn+'_'+ci+'_'+meta.k)" in html
       and "String(asp.series_id||fn)" in html
       and "boxId=`cacPaste_${fn}_${ci}_${meta.k}`" not in html)

    # Four structured bulk-import boxes retain their own row parsers but use one activation controller.
    structured = ["poPasteBox", "faPasteBox", "nieWorkforcePasteBox", "nieCatPasteBox"]
    ck("all four structured bulk paste surfaces have distinct ids", all(f'id="{x}"' in html for x in structured)
       and len(set(structured)) == 4)
    ck("structured imports share per-box activation without sharing domain parsers",
       "function _structuredPasteInput(id)" in html
       and all(f"_structuredPasteInput(\\x27{x}\\x27)" in html for x in structured))
    ck("structured Load buttons are individually targeted and disabled until input",
       all(f'id="{x}_load" class="pillbtn" disabled' in html for x in structured)
       and 'id="poPasteBox_append" class="pillbtn" disabled' in html
       and 'id="faPasteBox_append" class="pillbtn" disabled' in html)

    # Execute the actual canonical parser/controller from the shipped HTML.
    a = html.index("// Canonical controller for every scalar Series")
    b = html.index("function _feeParseExplicitValues", a)
    helpers = html[a:b]
    js = r'''
const els={};
function mk(id, suffixes=['_load']){
  const ta={value:''}; els[id]=ta;
  suffixes.forEach(s=>els[id+s]={disabled:true,classList:{ready:false,toggle(k,v){this.ready=v;}}});
  return ta;
}
const document={getElementById:(id)=>els[id]||null};
''' + helpers + r'''
const parse={
 comma:_seriesExplicitValues('8,10,12,10,10,10,9').map(x=>x.value),
 tabs:_seriesExplicitValues('1,000\t2,500\t3,000').map(x=>x.value),
 pct:_seriesExplicitValues('12%;10%;8%').map(x=>[x.value,x.pct]),
 invalid:_seriesExplicitValues('8,banana,12').length
};
const scalarIds=['feeCoeffPaste_0_0','feeFlatAmountPaste_0_1','feeAccountLevelPaste_0_2','feeStockPctPaste_0_3','feeBalanceRatePaste_0_3','feeAccountFeePaste_0_2','feeCostRecoveryMarkupPaste_0_4','wfCountPaste_0','wfCompPaste_0','opexSchedulePaste_0','cacPaste_series_a','cacAttritionPaste_series_b'];
scalarIds.forEach(id=>mk(id));
els[scalarIds[0]].value='8,10,12'; _seriesExplicitPasteInput(scalarIds[0]);
const firstOnly=scalarIds.map(id=>!els[id+'_load'].disabled);
els[scalarIds[1]].value='150,200,250'; _seriesExplicitPasteInput(scalarIds[1]);
const firstTwo=scalarIds.map(id=>!els[id+'_load'].disabled);
els[scalarIds[2]].value='bad,value'; _seriesExplicitPasteInput(scalarIds[2]);
const invalidDisabled=els[scalarIds[2]+'_load'].disabled;
els[scalarIds[0]].value=''; _seriesExplicitPasteInput(scalarIds[0]);
const clearAOnly=els[scalarIds[0]+'_load'].disabled && !els[scalarIds[1]+'_load'].disabled;

const po=mk('poPasteBox',['_load','_append']), fa=mk('faPasteBox',['_load','_append']), wf=mk('nieWorkforcePasteBox'), op=mk('nieCatPasteBox');
fa.value='Asset\tCost\nServers\t250'; _structuredPasteInput('faPasteBox');
const structuredIsolation={
 faLoad:!els.faPasteBox_load.disabled,faAppend:!els.faPasteBox_append.disabled,
 poLoad:!els.poPasteBox_load.disabled,wfLoad:!els.nieWorkforcePasteBox_load.disabled,opLoad:!els.nieCatPasteBox_load.disabled,
 scalarStill:!els[scalarIds[1]+'_load'].disabled
};
console.log(JSON.stringify({parse,firstOnly,firstTwo,invalidDisabled,clearAOnly,structuredIsolation}));
'''
    r = subprocess.run(["node", "-e", js], text=True, capture_output=True)
    obj = {}
    if r.returncode == 0 and r.stdout.strip():
        try:
            obj = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            pass
    parse = obj.get("parse") or {}
    ck("canonical scalar parser accepts comma schedules exactly", parse.get("comma") == [8,10,12,10,10,10,9], r.stderr.strip())
    ck("canonical scalar parser preserves thousands-formatted spreadsheet cells", parse.get("tabs") == [1000,2500,3000])
    ck("canonical scalar parser preserves percentage-cell semantics", parse.get("pct") == [[12,True],[10,True],[8,True]])
    ck("canonical scalar parser fails closed on any invalid token", parse.get("invalid") == 0)
    ck("typing in one scalar pastebox activates only its own Load button",
       obj.get("firstOnly") == [True,False,False,False,False,False,False,False,False,False,False,False])
    ck("sequential scalar pasteboxes remain independently active",
       obj.get("firstTwo") == [True,True,False,False,False,False,False,False,False,False,False,False])
    ck("invalid scalar input cannot activate Load", obj.get("invalidDisabled") is True)
    ck("clearing one scalar editor does not disable another loaded editor", obj.get("clearAOnly") is True)
    si = obj.get("structuredIsolation") or {}
    ck("structured bulk activation is scoped to the box being edited",
       si == {"faLoad":True,"faAppend":True,"poLoad":False,"wfLoad":False,"opLoad":False,"scalarStill":True}, str(si))

    # Free-text textareas must be explicitly classified so a model schedule cannot silently bypass
    # the pastebox contract. Guide Me and the optional pricing/regulatory memo are narrative text.
    all_textareas = [ln for ln in html.splitlines() if "<textarea" in ln]
    nonpaste = [ln for ln in all_textareas if "oninput=" not in ln]
    ck("no model-authoring textarea silently bypasses the pastebox contract",
       len(nonpaste) == 2
       and any("feeGuideDesc" in ln for ln in nonpaste)
       and any("feePricingMemo_" in ln and "model-free-text" in ln for ln in nonpaste), str(len(nonpaste)))

    print(f"\n{p} passed, {f} failed")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
