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
       and '<th class="num">Driver \\u00b7 \'+_stProvP(_stMeta)+\'</th>' in html
       and 'event.stopPropagation();stSelect(' in html and 'Quantity, last period' not in html)
    ck("One 'About these settings' box per stream tab",
       "const tabs=['activity','pricing','timing','costs'], last={};" in html)
    # r220: source rows (AUC, customers) and exact working for feed-driven streams.
    ck("Fee-stream grid shows the AUC and customer sources the engine used, and feed-driven working in authored terms",
       'function _stSrcRows(metas,fi)' in html and 'managedNotionalAvg' in html and "period_average:'customerAverageByPeriod'" in html
       and 'function _stFeedName(ref)' in html and "'fixed amount \\u00b7 no volume driver'" in html
       and 'function _stSchedLbl(per,n)' in html and "+_stSrcRows(_stMeta,_fi)+_stSetupFeeRow(_fi);" in html and 'const _srcChip=_stSrcChip(' in html)

    # r222: calculation cards declutter the stream grid; path row carries no default labels.
    ck("Stream grid shows one line per figure; the working opens in a click card built from the same steps as the editor",
       'function _ipStepsHtml(steps,note)' in html and "data-ip=\"'+key+'\"" in html and 'window.ipHide=hide;' in html
       and 'Click \\u24D8 to see how a figure is calculated' in html and "'<span class=\"st-w\">'" not in html)
    ck("Source rows explain average vs month-end AUC in a card instead of inline",
       'function _ipSrcHtml(fi,kind,ref)' in html and 'Month-end AUC' in html and 'Rates and turns are applied to the <b>average</b> AUC' in html)    # r224: attrition within the period is one control inside the attrition box.
    ck("Attrition within the period is a single dropdown inside the Existing-book attrition box",
       "+_cacAttrWithinHtml(fn,fd,asp,am)+" in html and 'window.cacFeedWithinSet=function' in html
       and 'Straight line between year-ends' in html and 'Straight line between quarter-ends' in html
       and '_cacPathRowHtml' not in html and 'cacFeedPathSet' not in html and 'Intra-period path' not in html
       and '/api/v31/cac/path-options' not in html)
    # r225: attrition Path and Timing are two visible controls; cards open on click only.
    ck("Attrition box shows Path and Timing as separate controls; timing hidden only for straight-line paths",
       "sel('path',path," in html and "sel('timing',timing," in html and 'Attrition is monthly, so timing has no effect.' in html)
    ck("Calculation cards open on click or Enter only (no hover, no show-on-focus)",
       "document.addEventListener('mouseover',e=>{ if(pinned) return;" not in html and "document.addEventListener('focusin',e=>{ const t=e.target.closest" not in html
       and "if(e.key==='Escape') hide();" in html)
    # r226: measured widths across Configuration and notices.
    ck("Forms, master-detail layouts and notices are sized to their content without truncating (r226/r227)",
       '.cfg-stage select{max-width:100%}' in html and 'function fitControls(root)' in html and 'function fitInput(el)' in html
       and '@container stage (min-width:1000px) and (max-width:1399px){.cfg-md:not(.cfg-md-stack){grid-template-columns:minmax(0,1fr)!important}' in html
       and 'minmax(min(640px,calc(100% - 494px)),640px) minmax(480px,880px)' in html and 'max-width:880px}' in html
       and '.warnitem,.ovflag{width:fit-content;max-width:880px}' in html)
    # r228: no duplicate working in the editor; figures refresh in place after each run; only the ⓘ opens a card.
    ck("Stream editor carries no duplicate working block; grid figures refresh after each run; only the info icon opens a card",
       'class="fld wide st-calc"' not in html and 'function refreshStreamFigures()' in html and "if(typeof refreshStreamFigures==='function') refreshStreamFigures(); }" in html
       and '${_stCellHtml(_stMeta,k,_fi)}' in html and '.st-list .st-v[data-ip]' not in html and "data-ip=\"src:'+fi+':auc\" tabindex" not in html)
    # r229: controls are fitted before paint (no shrink-then-grow flicker on redraw).
    ck("Control fitting runs synchronously on redraw, not on a timer",
       "const run=()=>{ if(typeof prdGroupSetup==='function') prdGroupSetup(); fitControls(); };" in html and "t=setTimeout(()=>fitControls(),40)" not in html)
    # r230: workforce role card sized to content; fitting has priority and also runs on module select / section open.
    ck("Workforce role card: compensation amount 140px with fitted dropdowns; columns capped and left-aligned",
       '.wf-role-card .wf-comp-value{grid-template-columns:140px max-content max-content!important;justify-content:start}' in html
       and '.wf-role-card .wf-role-grid{grid-template-columns:minmax(0,340px) minmax(0,300px)!important;justify-content:start}' in html)
    ck("Control fitting applies with priority and also runs when a module is selected or a section is opened",
       "el.style.setProperty('min-width',target+'px','important')" in html and "e.target.tagName==='DETAILS'&&e.target.open) fitControls(e.target)" in html
       and "['cfgSelectModule','nieTabSet','prdTabSet'].forEach(nm=>{ const o=window[nm];" in html and 'w._fit=true; window[nm]=w;' in html)
    # r231b: deposit pools: fee basis control; honest opening-balance label in level / pool modes.
    ck("Deposit pools offer the swept-balance fee basis; level and pool modes label the opening balance for what it is",
       "sweep_fee_balance_measure" in html and 'Fee balance measure' in html and 'Opening balance before period 1 ($000s)' in html)
    # r232: the product tab line (a stray comment once dropped Per-month overrides for every product).
    ck("Product tabs: Setup, Fee streams for fee products, loans and deposits, and Per-month overrides",
       "if(fee||x.fam==='lending'||x.fam==='deposit') tabs.push(['streams','Fee streams',ns]); if(V21) tabs.push(['overrides','Per-month overrides',null]);" in html)
    # r233: loan and deposit Setup grouped by concern, classified by configuration path, before paint.
    ck("Loan and deposit Setup are grouped into Balance / Pricing / Timing / Credit / Costs by configuration path",
       'function prdGroupSetup()' in html and 'const _PRD_GRP_RULES={' in html and "if(fam==='lending'&&typeof _loanBalanceMode==='function'&&_loanBalanceMode(p)==='funded_flow_level') return;" in html
       and "w.style.display=(g===cur)?'contents':'none'" in html and "const run=()=>{ if(typeof prdGroupSetup==='function') prdGroupSetup(); fitControls(); };" in html
       and 'data-fam="${x.fam}" data-i="${x.i}"' in html and 'function prdRefreshSetupSummaries()' in html)
    ck("Setup fields that cannot be classified stay visible below the tabs (never hidden)",
       "if(other.length){ const w=document.createElement('div'); w.className='prd-grp-other'; w.style.display='contents';" in html)
    # r234: workforce role entry fields in two clean rows; run summary sized to its content.
    ck("Workforce role card: two rows of uniform fields with units in the labels; run summary sized to content",
       '.wf-role-card .wf-role-grid::after{content:"";flex-basis:100%;height:0;order:4}' in html
       and 'Escalation %</span>' in html and 'Benefits / payroll %</span>' in html and 'placeholder="Open"' in html
       and 'function _wfUnitWord()' in html and '<table class="ovt ovt-grid wf-run-sum"' in html
       and 'table.ovt-grid.wf-run-sum{width:auto!important;max-width:100%}' in html
       and 'background-color:#FFFFFF;font-size:13.5px;padding:0 10px;margin:0}' in html)
    # r235: controls are fitted by measuring rendered text (not canvas + the computed font shorthand, which is ""
    # when font features are set), re-fitted when web fonts load, and fields that cannot fit span their grid row.
    ck("Control fitting measures rendered text, refits after web fonts load, and lets an over-long field span its row",
       'function _fitMeasure(el,text)' in html and 'cv.font=cs.font' not in html
       and "document.fonts.addEventListener('loadingdone',()=>fitControls())" in html and 'document.fonts.ready.then(()=>fitControls())' in html
       and "row.style.gridColumn='1 / -1'" in html and "input[type=text],input:not([type]),input[type=number]" in html)
    ck("Workforce activation trigger sits directly under the Start row, before Advanced trajectories",
       html.index('// r235: the activation trigger sits directly under the Start row') < html.index('const _advKey=_nieWorkforceAdvancedKey(wr,wi)')
       and html.count('<div class="wf-trigger-row">')==1)
    # r236: selected toggle filled; Add before Paste; slim component buttons; inline disclosure summaries; role drag.
    ck("Segmented toggles fill the selected option (not white on grey)",
       '.cfg-stage .nie-mode button.on{background:#2C2C2C!important;color:#FFFFFF!important;box-shadow:none!important}' in html)
    ck("Add comes before Paste for roles, categories, fixed assets and pre-opening expenses",
       all(0 < html.find(a) < html.find(p) and html.find(p)-html.find(a) < 700 for a,p in
           (('+ Add role','⎘ Paste roles'),('+ Add category','⎘ Paste categories'),('+ Add asset','⎘ Paste assets'),('+ Add one manually','⎘ Paste from spreadsheet'))))
    ck("Additive components are slim buttons with descriptions in tooltips; disclosure summaries are inline text",
       '<span>+ Formula</span></a>' in html and '<span>+ Tiered bands</span></a>' in html and '<span>+ Cost pool</span></a>' in html
       and 'title="A balance evaluated against a band schedule."' in html and '.cfg-disc-val{height:auto!important;padding:0 0 0 12px!important' in html)
    ck("Workforce roles reorder by drag, like operating-expense categories",
       'window.nieWorkforceDrop=function(ev,target)' in html and 'ondragstart="nieWorkforceDragStart(event,${wi})"' in html
       and 'Drag the handle to reorder; select a row to edit its assumptions.' in html)
    # r237: the Operating expense scope card reads "N workforce populations · N expense categories".
    ck("Operating expense scope card reads 'N workforce populations · N expense categories' with correct singulars",
       "workforce population${_r.length===1?'':'s'}" in html and "expense categor${_c.length===1?'y':'ies'}" in html
       and 'Populations / categories' not in html and '.cfg-kpis[data-engine-preview="nie-kpis"]{grid-template-columns:minmax(0,1fr) minmax(0,1fr) minmax(0,1.45fr) minmax(0,1fr)}' in html)
    # r238: list columns grow to their table's width when there is room (no needless horizontal scroll).
    ck("List-and-detail screens size the list to its table when there is room, and re-fit on sub-tab and product-tab switches",
       'function fitMasterDetail()' in html and 'minmax(min(${need}px, calc(100% - 494px)), ${need}px) minmax(480px, 880px)' in html
       and "['cfgSelectModule','nieTabSet','prdTabSet'].forEach(" in html)
    # r240: Peer Cohort: one cached batch request; redesigned corridor with stacked Min..Max; Excel export.
    ck("Peer corridor uses one cached batch request and the redesigned rows with stacked Min..Max",
       '/api/v31/peer-bands/batch?metrics=' in html and 'window._pbCache = window._pbCache || {};' in html
       and 'function _pbDesignHtml(items, ctx)' in html and "stat('min','Min')" in html and "stat('max','Max')" in html
       and 'window.pbExport=async function()' in html and 'const results = await Promise.all(metrics.map(fetchBand));' not in html)
    ck("Vintage corridor tables include Min and Max rows",
       '["max","p90","p75","p50","p25","min"].forEach(p=>{' in html)
    # r241: vintage follows the cohort; graphite headings; plots beside tables; bounded, delineated corridor.
    ck("Vintage corridor follows the peer cohort, with graphite headings and a plot beside each table",
       'function _vinSync()' in html and 'if(typeof _vinSync==="function") _vinSync();' in html and '{asset_band:_mode}' in html
       and '<div class="vin-h"><span class="vin-name">' in html and '_vinChartHtml(M, modeled)' in html
       and '.vin-h{display:flex;align-items:baseline;gap:12px;width:fit-content;min-width:33%;' in html)
    ck("Peer corridor is bounded in width and its percentiles are delineated",
       '.pc-cards,.pc-panel,.pc-note{max-width:calc((100% + 1076px) / 2)}' in html and '.pc-st{padding:0 9px;border-left:1px solid #ECECE8}' in html)
    # r242: vintage follows cohort switches without races; label fixed; plot sized to its table and framed.
    ck("Vintage builds are bound to their cohort (late results discarded) and any switch rebuilds; label renders",
       'const _reqKey = _vinKey(); window._vinWanted = true; window._vinStale = false;' in html
       and 'if(_reqKey === _vinKey()){ window.vintage = j; window.vintageKey = _reqKey; }' in html
       and "if(window._vinWanted && window.vintageKey!==_vinKey()" in html
       and "Build corridor \\u2014 ' + esc(_vinCohortLabel()) + '</button>'" in html and 'Build corridor \\u2014 ${_vinCohortLabel()}' not in html)
    ck("Vintage plot is fitted to its table's height, ends with the peer corridor, as a soft card",
       'function fitVintageCharts()' in html and "if(typeof fitVintageCharts==='function') fitVintageCharts();" in html
       and '.vin-body{flex-wrap:wrap;align-items:flex-start;gap:24px 32px;max-width:calc((100% + 1076px) / 2)}' in html
       and 'box-shadow:0 1px 2px rgba(0,0,0,.06),0 4px 14px rgba(0,0,0,.07)' in html and 'border:0.5in solid' not in html)
    # r244: leverage has a modeled vintage series; plots sized from the table element (no stretch feedback loop).
    ck("Vintage leverage ratio has its modeled series (same quarterly filing view as tier 1)",
       'leverage_ratio:"__lev"' in html and 'mk==="__lev"?"leverage_ratio"' in html)
    ck("Vintage plot is sized from the table element itself, never its stretchable wrapper, and re-fits on resize",
       "const tbl=wrap.querySelector('table')||wrap;" in html and "window.addEventListener('resize',()=>{ clearTimeout(window._vinRz);" in html)
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
