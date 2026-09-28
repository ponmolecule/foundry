"""Exercise the real browser paste handlers against a copied monthly source row."""
from pathlib import Path
import json
import subprocess


html = (Path(__file__).parents[2] / "web" / "console_v2.html").read_text()


def function(name):
    start = html.index(f"function {name}(")
    opening = html.index("{", start)
    depth = 0
    for pos in range(opening, len(html)):
        if html[pos] == "{":
            depth += 1
        elif html[pos] == "}":
            depth -= 1
            if not depth:
                return html[start : pos + 1]
    raise AssertionError(f"Unclosed function {name}")


js = "\n".join(function(name) for name in (
    "_seriesExplicitValues", "_feeParseExplicitValues", "loanFundedSchedule",
    "loanFundedScheduleClear", "loanFundedPasteClose", "loanFlowSchedule",
))
js += "\n" + r"""
const assert = require('node:assert/strict');
const fp = {period:'month', trajectory:'flat', value:0, schedule:{}};
const cfg = {assumptions:{lending_products:[{funded_flow_driver:{flow_path:fp}}]}};
const _loanFlowDraft = {};
let status = '', alerts = [], renders = 0, refreshes = 0;
function _seriesSourcePeriods(){return 36;}
function appStatus(_,s){status=s;}
function alert(s){alerts.push(s);}
function renderContent(){renders++;}
function refresh(){refreshes++;}
const source = Array.from({length:36}, (_,i)=>String(i+1)).join('\t');
loanFundedSchedule(0,source);
assert.equal(fp.schedule['1'],1000);
assert.equal(fp.schedule['36'],36000);
assert.equal(Object.keys(fp.schedule).length,36);
assert.equal(fp.trajectory,'explicit_schedule');
const feeFlow = {period:'month', trajectory:'flat', value:0, schedule:{}};
cfg.assumptions.lending_products[0].fee_streams = [
  {driver:{trajectory:'flat',params:{flow_path:feeFlow}}}
];
loanFlowSchedule(0,0,source);
assert.equal(feeFlow.schedule['1'],1000);
assert.equal(feeFlow.schedule['36'],36000);
assert.equal(cfg.assumptions.lending_products[0].fee_streams[0].driver.trajectory,'explicit_schedule');
assert.match(status,/36 funded-flow values loaded/);
loanFundedPasteClose(0);
assert.equal(_loanFlowDraft['funded:0'],false);
assert.equal(fp.schedule['36'],36000);
loanFundedSchedule(0,'1\t2');
assert.equal(fp.schedule['36'],36000);
assert.equal(alerts.length,1);
loanFundedScheduleClear(0);
assert.equal(Object.keys(fp.schedule).length,0);
assert.equal(fp.trajectory,'explicit_schedule');
console.log('PASS funded-flow UI paste');
"""
result = subprocess.run(["node", "-e", js], text=True, capture_output=True)
assert result.returncode == 0, result.stdout + result.stderr
print(result.stdout.strip())
