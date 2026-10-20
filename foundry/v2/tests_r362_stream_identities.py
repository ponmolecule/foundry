import json
import subprocess
import unittest
from pathlib import Path
from .tests_r360_stream_outputs import fixture
from .run_q import run_v2

class StreamIdentityTests(unittest.TestCase):
    def test_legacy_flat_event_results(self):
        cfg=fixture()
        streams=[{"name":"Escrow","basis":"flat","driver":{"source":"constant","trajectory":"flat","params":{"base":0}},"rate":{"behavior":"flat","params":{"flat_amount":{"trajectory":"explicit_schedule","period":"year","resolution":"step","schedule":{"1":150000}}}},"cost":{"kind":"pct_of_revenue_opex","params":{"pct":.32,"multiplier_path":{"trajectory":"explicit_schedule","period":"year","resolution":"step","schedule":{"1":1.64}}}}},
                 {"name":"Event","basis":"event","driver":{"source":"constant","trajectory":"flat","params":{"at_period":2}},"rate":{"behavior":"flat","params":{"amount":1000}},"cost":{"kind":"none","params":{}}}]
        cfg["assumptions"]["obs_exposures"][0]["fee_streams"]=streams
        js=Path("web/console_v2.html").read_text()
        start=js.index("function _ensureLinkableSeriesIds(){")
        fn=js[start:js.index("// Shared metadata comes",start)]
        code="let n=0;let cfg="+json.dumps(cfg)+";function _seriesId(){return 'test-'+(++n)};"+fn+";_ensureLinkableSeriesIds();const first=JSON.stringify(cfg);_ensureLinkableSeriesIds();if(JSON.stringify(cfg)!==first)throw Error('unstable IDs');console.log(JSON.stringify(cfg));"
        cfg=json.loads(subprocess.check_output(["node","-e",code],text=True))
        r=run_v2(cfg)
        flat,event=cfg["assumptions"]["obs_exposures"][0]["fee_streams"]
        econ=r["fee_stream_economics"]["series"]
        f=econ[flat["quantity_series_id"]]
        self.assertAlmostEqual(sum(f["reported_fee_income"]),150000)
        self.assertAlmostEqual(sum(f["fee_product_cost"]),78720)
        self.assertEqual(econ[event["quantity_series_id"]]["reported_fee_income"][:3],[0,1000,0])
