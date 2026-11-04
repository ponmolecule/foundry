import copy,unittest
from .tests_r408_product_formulas import config
from .acquisition_spend import catalog,resolve,value
from .run_q import run_v2


def fixture(ppy=12):
    c=config(ppy);a=c['assumptions'];a['nie_detail']['categories']=[];f=a['cac_feeds']['Accounts']
    f['channels']=[{'name':'Digital','method':'spend_cac','params':{'spend':259488,'cac':1000}}, {'name':'Other','method':'spend_cac','params':{'spend':12000,'cac':1000}}]
    refs=catalog(a);digital=next(x['series_id'] for x in refs if x.get('channel')==0);other=next(x['series_id'] for x in refs if x.get('channel')==1)
    st={'name':'Digital CAC','quantity_series_id':'digital-cost','basis':'flat','driver':{'source':'constant','trajectory':'flat','params':{}},'rate':{'behavior':'flat','params':{'amount_per_period':0}},'cost':{'kind':'periodic_amount_opex','params':{'linked_sources':[{'series_id':digital,'share':1}]}},'timing':{'start_period':1}}
    a['obs_exposures'][-1]['fee_streams']=[st]
    return c,st,digital,other

class SpendLinks(unittest.TestCase):
    def test_live_cost_and_cadence(self):
        for ppy in (12,4):
            c,st,sid,other=fixture(ppy);before=copy.deepcopy(c);r=run_v2(c)
            self.assertEqual(c,before)
            vals=r['fee_stream_economics']['series']['digital-cost']['fee_product_cost']
            self.assertTrue(all(abs(x-21624*12/ppy)<1e-7 for x in vals))
            # Zero revenue, explicit expense, and native cost capture agree.
            self.assertTrue(all(x==0 for x in r['fee_stream_economics']['series']['digital-cost']['reported_fee_income']))
            c['assumptions']['cac_feeds']['Accounts']['channels'][0]['params']['spend']*=2
            doubled=run_v2(c)['fee_stream_economics']['series']['digital-cost']['fee_product_cost']
            self.assertEqual(doubled,[2*x for x in vals])
    def test_add_share_timing_and_identity(self):
        c,st,sid,other=fixture();st['cost']['params']['linked_sources']=[{'series_id':sid,'share':.5},{'series_id':other,'share':.25}]
        st['timing']={'start_period':2,'end_period':3}
        a=c['assumptions'];a['cac_feeds']['Accounts']['channels'].reverse();a['cac_feeds']['Accounts']['channels'][1]['name']='Renamed'
        vals=run_v2(c)['fee_stream_economics']['series']['digital-cost']['fee_product_cost']
        self.assertEqual(vals[:4],[0,11062,11062,0])
    def test_fail_closed(self):
        c,st,sid,other=fixture()
        for links in ([{'series_id':'missing'}],[{'series_id':sid,'share':-1}],[{'series_id':sid,'share':float('nan')}],[{'series_id':sid},{'series_id':sid}]):
            st['cost']['params']['linked_sources']=links
            with self.assertRaises((ValueError,TypeError)):run_v2(c)
    def test_all_product_families_and_spend_methods(self):
        for collection in ('obs_exposures','deposit_products','lending_products'):
            c,st,sid,other=fixture()
            if collection!='obs_exposures':
                from .tests_fee_quantity_links import fixture as base
                c['assumptions'][collection]=copy.deepcopy(base()['assumptions'][collection])
                c['assumptions']['obs_exposures'][-1]['fee_streams']=[]
                c['assumptions'][collection][0]['fee_streams']=[st]
            vals=run_v2(c)['fee_stream_economics']['series']['digital-cost']['fee_product_cost']
            self.assertEqual(vals,[21624]*60)
        for channel in (
            {'method':'pool_conversion','params':{'pool':120,'conversion_rate':.5,'cost_per_customer':50}},
            {'method':'explicit','driver_specs':{'new_customers':{'source':'entered','trajectory':'flat','value':10,'period':'month'}},'params':{'spend':6000}},
            {'method':'fte_productivity','params':{'ftes':2,'comp_per_fte':120000,'per_fte':10}},
        ):
            c,st,sid,other=fixture();f=c['assumptions']['cac_feeds']['Accounts'];ids=f['channels'][0]['derived_series_ids'];f['channels'][0]=dict(channel,name='Replacement',derived_series_ids=ids)
            from .cac_feeder import cac_auc_rollforward
            expected=[x['channels'][0]['spend'] for x in cac_auc_rollforward(f,60,12,assumptions=c['assumptions'])['monthly']]
            actual=run_v2(c)['fee_stream_economics']['series']['digital-cost']['fee_product_cost']
            self.assertGreater(sum(expected),0)
            self.assertEqual(actual,expected)
    def test_variable_spend_posts_once(self):
        c,st,sid,other=fixture();ch=c['assumptions']['cac_feeds']['Accounts']['channels'][0]
        ch['driver_specs']={'spend':{'source':'entered','trajectory':'explicit','cadence':'month','values':[0,1000,2500]*20}}
        from .engine_q_a import run_pf_a
        linked=run_pf_a(c);st['cost']={'kind':'none','params':{}};base=run_pf_a(c)
        lp=next(x for x in linked['products'] if x['name']=='Operating Account');bp=next(x for x in base['products'] if x['name']=='Operating Account')
        self.assertEqual([x-y for x,y in zip(lp['passCost'],bp['passCost'])],[0,1000,2500]*20)
    def test_feed_total_and_overlap(self):
        c,st,sid,other=fixture();total=next(x['series_id'] for x in catalog(c['assumptions']) if 'channel' not in x)
        st['cost']['params']['linked_sources']=[{'series_id':total}]
        self.assertEqual(run_v2(c)['fee_stream_economics']['series']['digital-cost']['fee_product_cost'],[22624]*60)
        st['cost']['params']['linked_sources'].append({'series_id':sid})
        with self.assertRaisesRegex(ValueError,'not both'):run_v2(c)
    def test_unlinked_models_unchanged(self):
        c,st,sid,other=fixture();st['cost']['params']={'factor_path':{'value':21624,'period':'month','trajectory':'flat'}}
        vals=run_v2(c)['fee_stream_economics']['series']['digital-cost']['fee_product_cost']
        self.assertEqual(vals,[21624]*60)

if __name__=='__main__':unittest.main()
