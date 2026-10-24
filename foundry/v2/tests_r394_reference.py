"""r394: Reference registry checks.

Fails the build when a documented control's options change without its Reference entry changing, when an
entry is malformed, or when the embedded coverage scan is stale (refresh with: python3 tools/reference_scan.py --write).
"""
import html, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import reference_scan  # noqa: E402

H = (ROOT / 'web/console_v2.html').read_text(encoding='utf-8')
ok = fail = 0


def ck(name, cond, detail=''):
    global ok, fail
    print(('  PASS  ' if cond else '  FAIL  ') + name + ('' if cond or not detail else '\n        ' + str(detail)[:600]))
    ok += bool(cond)
    fail += not cond


def grab(name):
    k = H.index(name)
    return json.JSONDecoder().raw_decode(H[k + len(name):])[0]


REF = grab('const REF_ENTRIES = ')
IDX = grab('const FOUNDRY_INDEX = ')
BY = {e['id']: e for e in REF}
SUBJECTS = {'Lending', 'Deposits', 'Fee products & exposures', 'Operating expenses', 'Shared authoring controls', 'Customer acquisition'}
TOPICS = {'Balance authoring', 'Source selection', 'Pricing & costs', 'Formulas & timing'}

# 1. Entries are well formed.
ck('entry ids are unique', len(BY) == len(REF))
bad = [e['id'] for e in REF if e.get('subject') not in SUBJECTS or e.get('topic') not in TOPICS or not e.get('options') or not e.get('summary') or not e.get('path') or not e.get('control_label')]
ck('every entry has subject, topic, label, path, summary and options', not bad, bad)
ids = set(BY) | {e['id'] for e in IDX['entries']}
dangling = [(e['id'], r) for e in REF for r in e.get('related', []) if r not in ids]
ck('related links resolve', not dangling, dangling)
thin = [(e['id'], o['label']) for e in REF for o in e['options'] if not o.get('what') or not o.get('when')]
ck('every option says what it calculates and when to choose it', not thin, thin)
dash = [(e['id'], k) for e in REF for o in [e] + e['options'] for k in ('summary', 'what', 'when', 'differs') if '—' in str(o.get(k, ''))]
ck('prose uses no em dashes', not dash, dash)
nav = [e['id'] for e in REF if (e.get('nav') or {}).get('tab') not in ('products', 'config')]
ck('every entry can open its screen', not nav, nav)

# 2. Every documented option label exists on screen (verbatim), except labels built from the user's data.
code = '\n'.join(l for l in H.split('\n') if 'const REF_ENTRIES = ' not in l and 'const FOUNDRY_INDEX = ' not in l and 'REF_COVERAGE' not in l)
code += json.dumps(IDX['loan'] + IDX['deposit'], ensure_ascii=False)   # the balance-authoring selects render these lists


def on_screen(label):
    forms = {label, html.escape(label, quote=False), label.replace('&', '&amp;')}
    for a, b in (('·', '\\u00b7'), ('×', '\\u00d7'), ('÷', '\\u00f7'), ('—', '\\u2014'), ('–', '\\u2013')):
        forms |= {f.replace(a, b) for f in list(forms)}
    return any(f in code for f in forms)


missing = [(e['id'], o['label']) for e in REF for o in e['options'] if not o.get('dynamic') and not on_screen(o['label'])]
ck('documented option labels exist in the console', not missing, missing)


# 3. Controls whose option list is defined in one place: the entry lists exactly those options, in that order.
def pairs(src):
    return [(v, l) for v, l in re.findall(r"\[\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\]", src)]


def between(a, b):
    i = H.index(a)
    return H[i:H.index(b, i) + len(b)]


REGISTRY = {
    'loan-balance-authoring': [tuple(x) for x in IDX['loan']],
    'deposit-balance-method': [tuple(x) for x in IDX['deposit']],
    'cac-channel-method': pairs(between('var CAC_METHODS = ', ';')),
    'cac-attrition-path': pairs(between("[['flows','Monthly flows']", "]]")),
    'cac-attrition-timing': pairs(between("[['end','At the end of each attrition period']", "]]")),
    'loan-production-method': re.findall(r'<option value="(legacy|contract)"\$\{[^}]*\}>([^<]+)</option>', H)[:2],
}
for cid, opts in REGISTRY.items():
    e = BY.get(cid)
    got = [o['label'] for o in (e or {}).get('options', [])]
    want = [l for _, l in opts]
    ck(f'{cid}: entry lists every option of the control, in order', e is not None and got == want and len(want) >= 2,
       f'control {want} · entry {got}' if e else 'entry missing')

# 4. The coverage figures embedded in the console match a fresh scan.
emb, fresh = reference_scan.embedded(H), reference_scan.scan(H)
ck('embedded coverage matches the console (run tools/reference_scan.py --write)', emb == fresh,
   {k: (emb or {}).get(k) for k in ('total', 'explained', 'mentioned', 'absent')} if emb != fresh else '')

# 5. Placement and wiring.
ck('the Index tab is now Reference', '["index","Reference"]' in H and '["index","Index"]' not in H)
ck('the tab renders the new Reference', 'refRender();return;}   // r394: Reference' in H)
ck('contextual help runs with the layout hooks', "if(typeof refHelpDecorate==='function') refHelpDecorate();" in H)
ck('attrition timing "start" stores the value the engine accepts', "else if(v==='start') fd.attrition_timing='period_start';" in H and "attrition_timing='monthly_bucket'" not in H)

# 6. The engine accepts the value the "start of period" timing now stores.
try:
    import copy
    from foundry.v2.tests_r376_deferred import config
    from foundry.v2.run_q import run_v2
    c = config()
    for fd in c['assumptions']['cac_feeds'].values():
        fd['attrition_timing'] = 'period_start'
    run_v2(c)
    ck('engine runs with attrition timing at the start of the period', True)
except Exception as ex:  # noqa: BLE001
    ck('engine runs with attrition timing at the start of the period', False, ex)

r = subprocess.run(['node', str(ROOT / 'web/tests_r394_reference.cjs')], capture_output=True, text=True, cwd=str(ROOT), timeout=280)
ck('browser behaviour (node)', r.returncode == 0, (r.stdout[-1500:] + r.stderr[-1500:]) if r.returncode else '')
print(f"\n{ok} passed, {fail} failed")
raise SystemExit(1 if fail else 0)
