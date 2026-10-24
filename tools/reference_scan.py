"""Reference coverage scan (r394).

Reads web/console_v2.html statically, lists every option label written into the console, and classifies each
against the Reference: explained (an option or title of a Reference entry), mentioned (the text appears in an
entry), or absent. The console embeds the result as REF_COVERAGE; tests fail when the embedded copy is stale.

  python3 tools/reference_scan.py            # print the summary
  python3 tools/reference_scan.py --write    # refresh REF_COVERAGE inside web/console_v2.html
"""
import html, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / 'web' / 'console_v2.html'
BEGIN, END = '/*REF_COVERAGE_BEGIN*/', '/*REF_COVERAGE_END*/'
AREAS = [('dep', 'Deposits'), ('loan', 'Lending'), ('lfx', 'Lending'), ('lnv', 'Lending'), ('fee', 'Fee products & exposures'),
         ('stream', 'Fee products & exposures'), ('obs', 'Fee products & exposures'), ('cac', 'Customer acquisition'),
         ('acq', 'Customer acquisition'), ('account', 'Customer acquisition'), ('nie', 'Operating expenses'), ('opex', 'Operating expenses'),
         ('workforce', 'Workforce & compensation'), ('wf', 'Workforce & compensation'), ('comp', 'Workforce & compensation'),
         ('secur', 'Securities'), ('_sec', 'Securities'), ('secbook', 'Securities'), ('_fa', 'Fixed assets'), ('fixed', 'Fixed assets'), ('_ol', 'Other liabilities'), ('_oa', 'Other assets'),
         ('_bc', 'Interest-bearing balances'), ('tax', 'Taxes'), ('rate', 'Rates & curves'), ('curve', 'Rates & curves'),
         ('cap', 'Capital & funding'), ('borrow', 'Capital & funding'), ('lab', 'Bank Design Lab'), ('formula', 'Shared authoring controls'),
         ('series', 'Shared authoring controls'), ('growth', 'Shared authoring controls'), ('income', 'Other income'), ('fieldsfor', 'Product fields (all families)'), ('prodcard', 'Product fields (all families)'), ('_shared', 'Shared authoring controls')]
NOISE = re.compile(r'^(select|choose|missing|no |none$|—|enter$|link$|qtr$|month$|quarter$|year$|yes$|no$)|^[a-z0-9_]+$|\\u|=|^\W', re.I)
SKIP_FN = {'(top)'}


def norm(t):
    return re.sub(r'[^a-z0-9%$]+', ' ', t.lower()).strip()


def clean(t):
    t = html.unescape(re.sub(r'<[^>]+>', '', t))
    for a, b in (('\\u00b7', '·'), ('\\u2014', '—'), ('\\u2192', '→'), ('\\u00d7', '×'), ('\\u2013', '–'), ('\\u00f7', '÷')):
        t = t.replace(a, b)
    return t.strip()


def options(src):
    """(label, function, line) for every literal option label, skipping the Reference data itself."""
    owner, cur, out, seen = [], '(top)', [], set()
    fre = re.compile(r'^\s*(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(|^\s*window\.([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?function')
    for i, ln in enumerate(src.split('\n')):
        m = fre.match(ln)
        if m:
            cur = m.group(1) or m.group(2)
        if len(ln) > 20000 or 'REF_ENTRIES' in ln or 'FOUNDRY_INDEX = ' in ln or BEGIN in ln:
            continue
        found = [m.group(1) for m in re.finditer(r'<option\b[^>]*>([^<`$]{2,90})</option>', ln)]
        found += [m.group(2) for m in re.finditer(r"\[\s*['\"]([a-z0-9_:\-\.]{1,40})['\"]\s*,\s*['\"]([^'\"]{2,90})['\"]\s*\]", ln)]
        for lab in found:
            lab = clean(lab)
            n = norm(lab)
            if len(n) < 3 or '${' in lab or NOISE.search(lab) or n in seen or not re.search(r'[A-Za-z]', lab):
                continue
            seen.add(n)
            out.append((lab, cur, i + 1))
    return out


def reference_text(src):
    def grab(name):
        k = src.find(name)
        return json.JSONDecoder().raw_decode(src[k + len(name):])[0] if k >= 0 else None
    legacy = grab('const FOUNDRY_INDEX = ') or {'entries': []}
    full = grab('const REF_ENTRIES = ') or []
    explained = {norm(o['label']) for e in legacy['entries'] for o in e['options']} | {norm(e['title']) for e in legacy['entries']}
    explained |= {norm(o['label']) for e in full for o in e.get('options', [])} | {norm(e['title']) for e in full}
    corpus = norm(json.dumps(legacy, ensure_ascii=False) + json.dumps(full, ensure_ascii=False))
    return explained, corpus


def area(fn):
    f = fn.lower()
    for k, a in AREAS:
        if k in f:
            return a
    return 'Other screens & shared controls'


def scan(src):
    explained, corpus = reference_text(src)
    rows, absent = {}, []
    for lab, fn, line in options(src):
        a = area(fn)
        r = rows.setdefault(a, [0, 0, 0])
        n = norm(lab)
        st = 0 if n in explained else 1 if n in corpus else 2
        r[st] += 1
        if st == 2:
            absent.append([lab, a, fn])
    tot = [sum(r[i] for r in rows.values()) for i in range(3)]
    areas = sorted(([a] + r for a, r in rows.items()), key=lambda x: -sum(x[1:]))
    return {'total': sum(tot), 'explained': tot[0], 'mentioned': tot[1], 'absent': tot[2], 'areas': areas, 'absent_examples': absent[:40]}


def embedded(src):
    i, j = src.find(BEGIN), src.find(END)
    return json.loads(src[i + len(BEGIN):j].split('=', 1)[1].strip().rstrip(';')) if i >= 0 and j > i else None


def write(src, data):
    i, j = src.find(BEGIN), src.find(END)
    return src[:i + len(BEGIN)] + 'const REF_COVERAGE=' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';' + src[j:]


if __name__ == '__main__':
    src = CONSOLE.read_text(encoding='utf-8')
    d = scan(src)
    if '--write' in sys.argv:
        CONSOLE.write_text(write(src, d), encoding='utf-8')
    print(f"options {d['total']} · explained {d['explained']} · mentioned {d['mentioned']} · absent {d['absent']}")
    for a, *r in d['areas']:
        print(f"  {a:34s} {r[0]:4d} / {sum(r):4d}")
