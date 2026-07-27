#!/usr/bin/env python3
"""Verify the JS (web/console_v2.html) and Python (foundry/v2/verdict.py) verdict generators produce
identical output. Run manually after editing EITHER generator — they MUST stay in sync so the on-screen
verdict and the exported-workbook verdict never diverge (filed-artifact defensibility).

    python tools/verify_verdict_sync.py

Requires node. Not part of the gate suite (which is node-free by design); run it by hand when touching
verdict logic. Exits non-zero on any mismatch.
"""
import json
import copy
import subprocess
import sys
import re
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

from foundry.v2.run_q import run_v2  # noqa: E402
from foundry.v2 import verdict  # noqa: E402

CONFIGS = [
    ("pf_a_base", "foundry/fixtures/parity/configs/pf_a_base.json"),
    ("pf_b_base", "foundry/fixtures/parity/configs/pf_b_base.json"),
    ("pf_a_warning_heavy", "foundry/fixtures/parity/configs/pf_a_warning_heavy.json"),
    ("pf_a_combined_stress", "foundry/fixtures/parity/configs/pf_a_combined_stress.json"),
    ("pf_b_reserve_build", "foundry/fixtures/parity/configs/pf_b_reserve_build.json"),
]


def _extract_js_module():
    html = open("web/console_v2.html", encoding="utf-8").read()
    script = max(re.findall(r"<script>(.*?)</script>", html, re.S), key=len)
    start = script.find("// The noun for a capital constraint")
    end = script.find("function renderOverview()")
    chunk = script[start:end]
    mod = "let cfg=null; function cfgRef(){return cfg;} function esc(s){return String(s==null?'':s);}\n"
    mod += chunk
    mod += (
        "\nmodule.exports={setCfg:c=>{cfg=c;}, verdictLinesTest:function(r){"
        "var v=_verdictCall(r);var out=[v.call+'.'];if(v.gated)return out;"
        "var b=(r.scenarios||{}).base||{};var ct=(r.constraint_tests||[]);"
        "var commit=(((cfgRef().constraints||[]).find(c=>c.key==='leverage_min')||{}).value)*100;"
        "var scenTotal=new Set(ct.map(t=>t.scenario)).size;"
        "var scenFail=new Set(ct.filter(t=>!t.pass).map(t=>t.scenario)).size;"
        "if(b.min_leverage!=null&&commit){var minPct=b.min_leverage*100;var breaches=scenFail>0||minPct<commit;"
        "if(breaches){var allBreach=scenFail===scenTotal&&scenTotal>0;"
        "out.push('Base leverage bottoms at '+minPct.toFixed(2)+'% in Q'+b.min_leverage_q+"
        "' against the stated '+commit.toFixed(1)+'% threshold'+(allBreach?'; all '+_numWord(scenTotal)+"
        "' modeled scenarios breach it':(scenFail>0?'; '+scenFail+' of '+scenTotal+' modeled scenarios breach it':''))+'.');}"
        "else{out.push('Base leverage holds above the stated '+commit.toFixed(1)+"
        "'% threshold in every modeled scenario (low of '+minPct.toFixed(2)+'% in Q'+b.min_leverage_q+').');}}"
        "var fam=_issueFamilies(r);if(fam.length)out.push('Most material assumption area: '+fam[0].family+' \\u2014 '+fam[0].concern+'.');"
        "var sf=b.capital_shortfall_est;if(sf!=null&&sf>0&&commit)"
        "out.push('Estimated additional opening capital to maintain the '+commit.toFixed(1)+"
        "'% base-case threshold through Q12: '+_money000(sf)+' (estimate).');return out;}};"
    )
    open("/tmp/_js_verdict_sync.js", "w").write(mod)


def main():
    _extract_js_module()
    all_match = True
    for name, path in CONFIGS:
        cfg = json.load(open(path))
        r = run_v2(copy.deepcopy(cfg))
        py_lines = verdict.verdict_lines(cfg, r)
        js = (
            "const m=require('/tmp/_js_verdict_sync.js');"
            f"m.setCfg({json.dumps(cfg)});"
            f"console.log(JSON.stringify(m.verdictLinesTest({json.dumps(r)})));"
        )
        open("/tmp/_runjs_sync.js", "w").write(js)
        out = subprocess.run(["node", "/tmp/_runjs_sync.js"], capture_output=True, text=True)
        try:
            js_lines = json.loads(out.stdout.strip())
        except Exception:
            js_lines = ["JS ERROR: " + out.stderr[:200]]
        match = py_lines == js_lines
        all_match = all_match and match
        print(f"{name}: {'MATCH' if match else 'MISMATCH'}")
        if not match:
            for i in range(max(len(py_lines), len(js_lines))):
                p = py_lines[i] if i < len(py_lines) else "(none)"
                j = js_lines[i] if i < len(js_lines) else "(none)"
                if p != j:
                    print(f"  PY: {p}\n  JS: {j}")
    if all_match:
        print("\nOK — JS and Python verdict generators are in sync across all configs.")
        sys.exit(0)
    print("\nFAIL — verdict generators have drifted. Reconcile web/console_v2.html and foundry/v2/verdict.py.")
    sys.exit(1)


if __name__ == "__main__":
    main()
