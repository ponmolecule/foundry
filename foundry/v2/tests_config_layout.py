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
    ck("Palette is graphite bars on the Klaros theme (white page, #343434 ink, #DFB367 gold), with a graphite tab row",
       '--k-graph:#2C2C2C' in html and '--k-gold:#DFB367' in html and '--k-canvas:#FFFFFF' in html and '--k-tx1:#343434' in html and '--paper:#FFFFFF' in html
       and '.ab-nav{height:40px;background:var(--k-graph)' in html and '.tab.active{background:transparent;color:#FFFFFF' in html)
    ck("Ledger geometry: design-layer radii are 3px or less, with column rules in data grids",
       'border-radius:10px' not in html[html.index('<style id="klaros-graphite">'):html.index('</style>',html.index('<style id="klaros-graphite">'))]
       and 'table.cfg-grid td,table.cfg-grid th{border-right:1px solid var(--k-line)}' in html)
    ck("Products tab is a navigator plus one workspace, with Portfolio and Compare views",
       'class="prd-shell' in html and 'window.prdSelect=function' in html and "view==='compare'" in html
       and 'class="prd-card" data-pp-tab=' in html and 'prodCardHtml(x.fam,x.i)' in html)
    ck("Product card and fee-stream editor are split into tabs by markup only",
       html.count('data-pp="setup"') >= 3 and 'data-pp="streams"' in html and 'data-pp="overrides"' in html
       and all(f'data-st="{k}"' in html for k in ("activity","pricing","timing","costs"))
       and "window._ppMark=true; h += fieldsFor(fam, p, base); window._ppMark=false;" in html)
    ck("Fee streams are master-detail with a driver chain",
       "_mdPick(p.fee_streams,'_stSelObj','_stSeen')" in html and 'window.stSelect=function' in html and 'class="st-chain"' in html)
    # r205: stream workspace follows the approved mockup; editor restyled; schedule strip.
    ck("Stream workspace: product-level chain, grid beside editor, role and engine quantity",
       "'<div class=\"fld wide st-md\">'+chainH" in html and 'outside this chain' in html
       and '.prd-stage .st-md{display:grid;grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr)' in html
       and 'fee_stream_quantities' in html and "role:(()=>{" in html)
    ck("Editor restyle: sentence-case labels, one-line growth rows, memos folded into a note",
       '.prd-card .fld label{text-transform:none!important' in html and '.prd-card .fld:has(> .cu){flex-direction:row' in html
       and 'window.prdAfterRender=function' in html and "d.className='st-about'" in html)
    ck("Explicit schedules show a six-cell strip with display-only rounding",
       'explicit-preview-strip' in html and 'function _prdNum(x)' in html and "_si=n<=6?" in html)
    ck("Product header carries a breadcrumb back to the portfolio",
       'class="prd-crumb"' in html)
    # r206: one side-column pattern for Configuration and Products.
    ck("Configuration side column is full height with the page title and an elevated module card",
       '<div class="cfg-nav-head">Configuration</div><div class="cfg-nav-card">' in html
       and '.cfg-nav{position:sticky;top:var(--appbar-h);height:calc(100vh - var(--appbar-h))' in html
       and 'window.cfgArrangeShell=function' in html)
    ck("Products navigator uses the elevated card rows (icon tile, name, sub-line, revenue)",
       '<div class="prd-nav-card">' in html and 'class="prd-row-t"' in html and ".prd-nav .product-card.prd-row.sel::before" in html)
    # r207: fail-closed display, option-card stream tiles, controls sized to content.
    ck("Products keep the last complete run on screen, muted, while inputs are incomplete",
       'window._prdLastGood={cfg:cfg,rows:(lastRes.ftp.rows||[])}' in html and "window._prdLastGood.cfg===cfg" in html
       and 'class="prd-banner"' in html and "'Needs inputs'" in html)
    ck("Add-stream tiles are option cards and keep the canonical help popover",
       'class="btn-plain fee-add"' in html and 'class="fa-ic"' in html and 'class="fee-basis-popover"' in html)
    ck("Form controls are sized to their content rather than the column",
       '#content input[inputmode="decimal"],#content input[type=number]{max-width:180px}' in html
       and '#content .prd-card .fields{grid-template-columns:repeat(auto-fill,minmax(280px,1fr))!important' in html)
    # r208: checkboxes and radios are never stretched by the legacy text-box width rule.
    ck("Checkboxes and radios keep their natural size inside fields",
       '#content .fld input[type=checkbox],#content .fld input[type=radio]' in html and 'width:auto!important;min-width:0!important' in html)
    # r209: uniform page header on every tab.
    ck("Every tab opens with a breadcrumb and a graphite title band",
       'window.pageChrome=function' in html and 'window.cfgCrumb=function' in html and "GROUPS=['Workspace','Statements','Analysis','Record']" in html
       and '#content .h2.pg-band,#content .pg-band-row,#content .prd-h1.pg-band{' in html)
    # r210: solid Klaros-gold strip under the menu, part of the bar's own height.
    ck("Menu bar carries a 6px solid Klaros-gold strip and sticky offsets match its height",
       '#appbar{border-bottom:6px solid #DFB367;box-shadow:none}' in html and '--appbar-h:96px;' in html and '#appbar::after{content:none}' in html)
    # r211: Welcome on the Klaros cover image.
    ck("Welcome uses the Klaros cover image's parts with sign-in on the gold strip and the exhibit index ribbon",
       'class="wel wel-photo"' in html and 'class="wel-signin"' in html and '.wel-rail{position:absolute;z-index:1;left:25cqw;' in html
       and 'Peer and vintage analysis' in html and 'class="wel-logo" alt="Klaros Group"' in html and '@media (max-width:999px){' in html)
    ck("Narrow Welcome keeps the building behind translucent sections",
       '.wb-b{left:0;top:0;width:100%;height:100%}' in html and 'rgba(234,216,188,.84)' in html)
    # r215: graphite block 50% x 40%; headline semibold, one line, ending where the subtitle ends.
    ck("Welcome graphite block is 50% wide by 40% tall, with sky, gold strip and building as separate parts",
       '.wb-g{left:0;top:0;width:50%;height:40%;' in html and '.wb-s{left:50%;right:0;top:0;height:40%;' in html
       and '.wb-o{left:0;width:25%;top:40%;bottom:0;' in html and '.wb-b{left:25%;right:0;top:40%;bottom:0;' in html)
    ck("Welcome headline is semibold, one line, and fitted to the subtitle's length",
       'font-weight:600;letter-spacing:-.02em;color:#FFFFFF}' in html and 'window.welFit=function' in html
       and 'requestAnimationFrame(welFit)' in html and '.wel-sub{margin:var(--wel-sub-gap,calc(1.883cqw - 10px)) 0 0;' in html)
    ck("Sign-in fields match the Enter platform button: same 162px width at every size",
       '.wel-login input{display:block;box-sizing:border-box;width:162px;max-width:100%;' in html
       and '#enterBtn{width:162px;box-sizing:border-box;justify-content:center;' in html)
    # r216: customer-acquisition audit view is a ruled table sized to its content, headers aligned with figures.
    ck("Customer-acquisition audit table is fully ruled, content-width, with right-aligned year headers and bold ending balances",
       '.cfg-stage table.cac-audit-grid.cac-audit-grid{width:auto!important;min-width:0!important;' in html
       and 'border:1px solid #D8D8D8!important' in html and "String(key).indexOf('end_')===0?' class=\"end\"'" in html
       and '.cfg-stage table.cac-audit-grid.cac-audit-grid th:first-child{text-align:left;white-space:normal;max-width:190px}' in html)
    # r217: sign-in fields are underlined with floating labels; show/hide and Caps Lock; zone labelled "User access".
    ck("Sign-in uses underlined fields with floating labels, a show/hide eye, a Caps Lock warning and a 'User access' label",
       '<div class="wel-signin-t">User access</div>' in html and '<label for="loginUser">Username</label>' in html
       and '<label for="loginPass">Password</label>' in html and 'onclick="welEye(this)"' in html and 'window.welCaps=function' in html
       and 'aria-label="Sign in"' in html and "'Welcome back':'Sign in'" not in html)
    # r218: product list reorder: whole row draggable, row is the drag image, drop line by top/bottom half.
    ck("Product rows drag by the whole row, show the row while dragging, and drop by top or bottom half",
       'draggable="true" title="Drag to reorder" ondragstart="productDragStart(event,' in html and 'prdDragImage(event)' in html
       and 'window.prdRowDragOver=function' in html and 'class="prd-row-t" draggable="false"' in html
       and '.prd-nav .product-card.prd-row.drop-after{box-shadow:0 3px 0 0 var(--k-gold)}' in html)
    # r219: fee-stream driver figures in the editor's units, with their working shown in grid and editor.
    ck("Fee-stream driver column shows the final-period figure in the editor's units with a working line",
       'function _stProv(metas,i,fi)' in html and 'function _stKinds(metas)' in html and "'money_flow'" in html
       and '<th class="num">Driver \\u00b7 \'+_stProvP(_stMeta)+\'</th>' in html and 'class="fld wide st-calc"' in html
       and 'event.stopPropagation();stSelect(' in html and 'Quantity, last period' not in html)
    ck("One 'About these settings' box per stream tab",
       "const tabs=['activity','pricing','timing','costs'], last={};" in html)
    # r220: source rows (AUC, customers) and exact working for feed-driven streams.
    ck("Fee-stream grid shows the AUC and customer sources the engine used, and feed-driven working in authored terms",
       'function _stSrcRows(metas,fi)' in html and 'managedNotionalAvg' in html and "period_average:'customerAverageByPeriod'" in html
       and 'function _stFeedName(ref)' in html and "'fixed amount \\u00b7 no volume driver'" in html
       and 'function _stSchedLbl(per,n)' in html and "+_stSrcRows(_stMeta,_fi);" in html and 'const _srcChip=_stSrcChip(' in html)
    # r221: intra-period path row on customer-acquisition feeds.
    ck("Acquisition feeds offer an Intra-period path row (path, anchor points, attrition timing) under attrition",
       'h+=_cacPathRowHtml(fn,fd,asp,am);' in html and 'window.cacFeedPathSet=function' in html
       and '<option value="straight_line"' in html and "Month-ends aren" in html
       and 'refreshCacPathEffects()' in html)
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
