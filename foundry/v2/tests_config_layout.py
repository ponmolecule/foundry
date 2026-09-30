"""Focused configuration layout regression gate."""
from __future__ import annotations
import re, sys
from pathlib import Path


def main():
    p=f=0
    def ck(name, cond, detail=""):
        nonlocal p,f
        if cond:
            p+=1; print("  PASS ", name + (f" — {detail}" if detail else ""))
        else:
            f+=1; print("  FAIL ", name + (f" — {detail}" if detail else ""))

    html=Path("web/console_v2.html").read_text(encoding="utf-8")
    m=re.search(r"\.cfggrid\{[^}]*grid-template-columns:([0-9.]+)fr\s+([0-9.]+)fr\s+([0-9.]+)fr", html)
    vals=tuple(map(float,m.groups())) if m else ()
    # r199: the three-column grid is superseded. One module is staged at a time beside a module
    # navigator; the legacy proportions rule stays in the stylesheet only as an inert baseline.
    ck("Legacy three-column proportions remain parseable as an inert baseline", bool(vals) and abs(sum(vals)-3.0) < 1e-9, str(vals))
    ck("Configuration stages one module at a time",
       '.cfggrid{display:block}' in html and '.cfggrid>.cfgcard{display:none' in html
       and all(f'.cfggrid[data-cfg-selected="{k}"]>#card-{k}' in html for k in ("cap","sec","nie","cac","tax","cecl")))
    ck("Configuration has a module navigator with per-module switches and a full-width stage",
       'class="cfg-shell"' in html and 'class="modpanel cfg-nav"' in html and 'class="cfg-stage"' in html
       and 'window.cfgSelectModule=function' in html and 'data-cfg-mod="${key}"' in html
       and 'class="modcard${on?" sel":""}" data-act="${act}" role="switch"' in html)
    ck("Navigator lists the staged module's sections and summarises each module's state",
       'function cfgBuildSubnav()' in html and "if(typeof cfgAfterRender==='function')cfgAfterRender();" in html
       and 'class="cfg-mod-sum"' in html and 'const _cfgSum={' in html)
    ck("Global assumptions dock as a right-hand inspector that persists across tabs",
       'id="inspBtn"' in html and 'window.toggleInspector=function' in html
       and 'body.insp-closed main>aside{display:none}' in html and "localStorage.setItem('foundry.inspector'" in html)
    ck("Application chrome is one compact bar with a single-row, grouped tab strip",
       '<div id="appbar">' in html and '<div id="ribbon">' not in html and '<header class="cover">' not in html
       and 'class="tabsep"' in html)
    ck("Opex components are authored without an Advanced click; only timing sits behind a summarised disclosure",
       "if(_adv){\n        if(!_legacyCostPool){" not in html and 'Advanced timing<span class="cfg-disc-val">' in html
       and "if(_hasEnteredRecurring&&_adv){" in html)
    ck("Loaded explicit schedules stay visible: sparkline preview in open, closed and collapsed states",
       'function _sparkHtml(vals)' in html and 'class="paste-closed-preview"' in html
       and "const head=(typeof _sparkHtml==='function'?_sparkHtml(vals):'')" in html
       and '<summary>Advanced trajectories<span class="cfg-disc-val"><i>Count</i>' in html)
    # r200: light work surface; graphite and gold as accents only.
    ck("Configuration renders on a light surface, not the dark cover theme",
       'const DARKTABS = new Set([]);' in html
       and '<style id="klaros-graphite">' in html and '--k-surface:#FFFFFF' in html)
    ck("Operating expense has sub-tabs and a KPI strip fed by the latest run",
       'class="cfg-subtabs"' in html and 'window.nieTabSet=function' in html and 'data-nie-pane="workforce"' in html
       and 'data-nie-pane="categories"' in html and 'data-nie-pane="assessments"' in html
       and 'data-engine-preview="nie-kpis"' in html and '(lastRes||{}).nie_detail_series' in html)
    ck("Workforce and expense categories are master-detail: dense table plus one selected record",
       "_mdPick(wf.roles,'_wfSelObj','_wfSeen')" in html and "_mdPick(nd.categories,'_nieCatSelObj','_nieCatSeen')" in html
       and 'window.wfSelect=function' in html and 'window.nieCatSelect=function' in html and 'class="cfg-md-detail"' in html)
    ck("Category rows keep drag-to-reorder in the table",
       'ondragstart="nieCatDragStart(event,${i})"' in html and 'tr.opex-item-card.drop-before td' in html)
    ck("Expense component tools act inside the selected category",
       'class="cfg-tool" onclick="nieCatAddFormulaDriver(${i})' in html and 'onclick="nieCatAddPiecewise(${i})' in html
       and 'onclick="nieCatAddCostPoolCharge(${i})' in html)
    ck("Module activation switch sits in the module band; the rail shows status",
       'function cfgMountSwitch()' in html and 'class="cfg-mod-dot"' in html and '.cfg-nav .cfg-mod>.modcard{display:none}' in html)
    # r201: analysis and record tabs join the light surface.
    ck("Every page, Welcome included, renders on the light surface",
       'const DARKTABS = new Set([]);' in html and 'c.classList.toggle("cover", V3 && DARKTABS.has(currentTab));' in html)
    ck("Welcome keeps its sign-in wiring and hides engagement controls",
       all(f'id="{i}"' in html for i in ("loginUser","loginPass","loginErr","loginBlock","whoBlock","whoName","enterBtn"))
       and 'onclick="enterPlatform()"' in html and 'document.body.classList.toggle("on-welcome", !!_wel);' in html
       and 'body.on-welcome #chevBox' in html and 'class="welcome-main"' in html)
    ck("Section headers on analysis tabs are graphite bands; KPI tiles and flags are white",
       '.ovh2{background:var(--k-graph)!important' in html and '.ovcard,.ovflag{border-radius:3px;background:var(--k-surface)!important' in html)
    ck("Analysis data tables use proportional tabular figures",
       'section#content table.ovt td,section#content table.dtab td' in html and 'font-variant-numeric:tabular-nums lining-nums' in html)
    ck("Lab heatmaps use the champagne-to-gold ramp",
       html.count('Math.round(238-t*48)') == 2 and 'Math.round(40+t*40)' not in html)
    # r202: remaining list editors are master-detail.
    ck("Managed-portfolio securities are a grid with one selected editor",
       "_mdPick(_slArr,'_secSlSel'+mi,'_secSlSeen'+mi)" in html and 'window.secSleeveSelect=function' in html and 'class="cfg-md cfg-md-stack"' in html)
    ck("Acquisition channels are a grid with drag reorder and one selected editor",
       "_mdPick(fd.channels,'_cacChSel_'+fn,'_cacChSeen_'+fn)" in html and 'window.cacChannelSelect=function' in html
       and 'ondragstart="cacChannelDragStart(event,' in html and 'tr.cac-channel-card.drop-before td' in html)
    # r204: Klaros palette (graphite, yellow gold, neutral surfaces), ledger geometry, Products workspace.
    ck("Palette is graphite and yellow-gold on neutral surfaces, with a graphite tab row",
       '--k-graph:#2C2C2C' in html and '--k-gold:#DBAB5D' in html and '--k-canvas:#F2F2F0' in html
       and '.ab-nav{height:40px;background:var(--k-graph)' in html and '.tab.active{background:transparent;color:#FFFFFF' in html)
    ck("Ledger geometry: design-layer radii are 3px or less, with column rules in data grids",
       'border-radius:10px' not in html[html.index('<style id="klaros-graphite">'):html.index('</style>',html.index('<style id="klaros-graphite">'))]
       and 'table.cfg-grid td,table.cfg-grid th{border-right:1px solid var(--k-line)}' in html)
    ck("Products tab is a navigator plus one workspace, with Portfolio and Compare views",
       'class="prd-shell"' in html and 'window.prdSelect=function' in html and "view==='compare'" in html
       and 'class="prd-card" data-pp-tab=' in html and 'prodCardHtml(x.fam,x.i)' in html)
    ck("Product card and fee-stream editor are split into tabs by markup only",
       html.count('data-pp="setup"') >= 3 and 'data-pp="streams"' in html and 'data-pp="overrides"' in html
       and all(f'data-st="{k}"' in html for k in ("activity","pricing","timing","costs"))
       and "window._ppMark=true; h += fieldsFor(fam, p, base); window._ppMark=false;" in html)
    ck("Fee streams are master-detail with a driver chain",
       "_mdPick(p.fee_streams,'_stSelObj','_stSeen')" in html and 'window.stSelect=function' in html and 'class="st-chain"' in html)
    ck("Securities books use a two-tier field editor",
       '.sec-book-line-top{' in html and '.sec-book-line-bottom{' in html
       and html.count('class="sec-book-line sec-book-line-top"') == 2
       and html.count('class="sec-book-line sec-book-line-bottom"') == 2)
    ck("Both AFS and HTM use the two-tier editor",
       html.count('class="sec-book-editor" data-book-kind="AFS"') == 1
       and html.count('class="sec-book-editor" data-book-kind="HTM"') == 1)
    ck("Securities editor restores full Growth and Purchases labels",
       html.count('<span class="sec-book-label">Growth</span>') == 2
       and html.count('<span class="sec-book-label">Purchases</span>') == 2)
    ck("Securities book name is responsive rather than hard-wired to 48px",
       '.sec-book-name{width:100% !important;min-width:0 !important;max-width:none !important}' in html
       and '.sec-book-name{flex:0 0 48px' not in html)
    ck("Securities Name and Opening balance fields are compact but not squeezed",
       '.sec-book-line-top{grid-template-columns:minmax(70px,90px) minmax(108px,126px);justify-content:start}' in html)
    ck("Workforce and Opex authoring sections have explicit compact Expand/Collapse controls",
       "nieSectionSetOpen('workforce'" in html and "nieSectionSetOpen('opex'" in html
       and 'class="nie-section-toggle"' in html and 'expand to inspect or edit' in html)
    ck("Workforce/Opex sections open by default in the staged layout; dense collapse-when-loaded stays available",
       'function _nieSectionIsOpen(key,hasRows)' in html and ': !hasRows;' in html and 'window._cfgDenseDefaults' in html
       and "!!window._nieSectionOpen[key] : true;" in html
       and 'window._nieSectionOpen.workforce=true' in html and 'window._nieSectionOpen.opex=true' in html)
    ck("Pre-opening expense and Fixed Assets/CAPEX have compact Expand/Collapse controls",
       "cfgSectionSetOpen('preopening'" in html and "cfgSectionSetOpen('fixedassets'" in html
       and '>Pre-opening expenses</span><button class="nie-section-toggle"' in html
       and '>Fixed assets / CAPEX</span><button class="nie-section-toggle"' in html)
    ck("Pre-opening/fixed-asset sections open by default in the staged layout and authoring actions reopen them",
       'function _cfgSectionIsOpen(key,hasContent)' in html and ': !hasContent;' in html
       and "!!window._cfgSectionOpen[key] : true;" in html
       and 'window._cfgSectionOpen.preopening=true' in html and 'window._cfgSectionOpen.fixedassets=true' in html)

    print(f"\n{p} passed, {f} failed")
    return 0 if f==0 else 1

if __name__ == "__main__":
    sys.exit(main())
