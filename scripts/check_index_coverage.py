"""Check declared UI-surface coverage and reference integrity; no server/model writes.

This guards the screen/module inventory and documented option lists. It is not
an automatic proof that every conditional field's prose is semantically complete.
"""
from pathlib import Path
import json,re
root=Path(__file__).resolve().parents[1]
s=(root/'web/console_v2.html').read_text()
data=json.JSONDecoder().raw_decode(s.split('const FOUNDRY_INDEX = ',1)[1])[0]
entries={e['id']:e for e in data['entries']}
assert len(entries)==len(data['entries']), 'Duplicate topic ID'
sections={x[0] for x in data['sections']}
assert set(e['section'] for e in entries.values())==sections
assert {x for d in data['domains'] for x in d[3]}==sections
for e in entries.values():
 assert e['path'] and e['summary'] and e['terms'] and e['options'] and e['example']['steps'],e['id']
 assert all(o['label'] and o['text'] and o['when'] for o in e['options']),e['id']
 assert all(x in entries for x in e['related']),e['id']
# Every currently registered application tab has an explained destination.
tabs={'welcome':'setup-workflow','start':'setup-scope','config':'setup-scope','products':'stream-basis','bs':'results-statements','is':'results-statements','ratios':'results-ratios','detail':'results-products','stress':'stress-testing','notes':'overview-reports','overview':'overview-reports','peer':'peer-analysis','examiner':'overview-reports','lab':'lab-goalseek','gov':'governance','index':'source-selection'}
block=s.split('const TAB_DEFS =',1)[1].split('const DARKTABS',1)[0]
registered=set(re.findall(r'\["([a-z]+)","[^"\n]+"\]',block))
assert registered==set(tabs),('Update tab coverage',registered^set(tabs))
mods={'rates':'rates-indices','cap':'capital-raises','sec':'cash-securities','income':'other-income','nie':'opex-modes','cac':'acquisition-methods','tax':'tax-modes','cecl':'cecl-presentation'}
mod_ids=set(re.findall(r"'([^']+)'",re.search(r'const _CFG_MODS=\[([^]]+)\]',s).group(1)))
assert mod_ids==set(mods),('Update Configuration coverage',mod_ids^set(mods))
for id in list(tabs.values())+list(mods.values()):assert id in entries,id
for key,id in [('loan','loan-balance'),('deposit','deposit-balance')]:
 assert [x[1] for x in data[key]]==[o['label'] for o in entries[id]['options']]
# Real code option sets independent of the Index metadata.
cac=re.search(r'var CAC_METHODS = (\[.*?\]);',s).group(1)
assert [x[1] for x in json.loads(cac)]==[o['label'] for o in entries['acquisition-methods']['options']]
lab=re.search(r'const modes = (\[.*?\]);',s[s.index('function renderLab()'):]).group(1)
for code,label in json.loads(lab):assert label+' · Bank Design Lab'==entries['lab-'+code]['title']
print(f"PASS: {len(entries)} topics, {len(sections)} subjects, {len(registered)} tabs, {len(mod_ids)} Configuration modules; acquisition/Lab/balance option coverage and cross-references")
