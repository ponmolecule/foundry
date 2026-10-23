/* r336: rates authoring is a draft -> validated preview -> explicit apply transaction.
   No run or panel-open action fetches data or rewrites a saved curve. */
let rwsDraft=null,rwsOwner=null,rwsStamp=null,rwsResult=null,rwsTicket=0,rwsError='',rwsBusy=false,rwsIndex='effr',rwsView='monthly';
let rwsEditors={},rwsForms={},rwsFormBases={},rwsPanels={};
function rwsCopy(x){return JSON.parse(JSON.stringify(x));}
function rwsSaved(){return cfg.assumptions.rates_workspace||null;}
function rwsReset(){rwsDraft=null;rwsResult=null;rwsStamp=null;rwsTicket++;rwsError='';rwsBusy=false;rwsEditors={};rwsForms={};rwsFormBases={};rwsPanels={};}
function rwsInit(){
  if(rwsOwner!==cfg){rwsOwner=cfg;rwsReset();}
  if(rwsDraft)return;
  const rc=cfg.assumptions.rate_curves||{};
  rwsDraft=rwsCopy(rwsSaved()||{version:1,published:{current_policy:rc.current_policy||{},fomc:rc.fomc||{},retrieved_at:rc.retrieved_at||null,evidence:rc.fomc?.edited?'Legacy edited anchors — original published values unavailable':'Saved snapshot; release date only where recorded'},anchor_overrides:{},basis:rc.offsets||{effr:0,sofr:.0005,prime:.03},policy_interpolation:'linear',policy_tail:'glide',indices:Object.fromEntries(CURVE_ORDER.map(k=>[k,{source:'existing'}]))});
  rwsDraft.indices=rwsDraft.indices||{};CURVE_ORDER.forEach(k=>{rwsDraft.indices[k]=rwsDraft.indices[k]||{source:'existing'};});rwsDraft.anchor_overrides=rwsDraft.anchor_overrides||{};rwsDraft.basis=rwsDraft.basis||{};rwsDraft.policy_interpolation=rwsDraft.policy_interpolation||'linear';rwsDraft.policy_tail=rwsDraft.policy_tail||'glide';rwsInitialKey=rwsKey(rwsDraft);
}
function rwsKey(value){return JSON.stringify(value,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);}
function rwsChanged(){
 const saved=rwsSaved();if(!saved)return CURVE_ORDER.some(k=>rwsDraft?.indices?.[k]?.source!=='existing')||rwsKey(rwsDraft)!==rwsInitialKey;
 const w=rwsCopy(saved);w.indices=w.indices||{};CURVE_ORDER.forEach(k=>{w.indices[k]=w.indices[k]||{source:'existing'};});w.anchor_overrides=w.anchor_overrides||{};w.basis=w.basis||{};w.policy_interpolation=w.policy_interpolation||'linear';w.policy_tail=w.policy_tail||'glide';
 return rwsKey(w)!==rwsKey(rwsDraft);
}
let rwsInitialKey='';
function rwsUnloaded(){return Object.keys(rwsForms).some(k=>rwsKey(rwsForms[k])!==rwsKey(rwsFormBases[k]));}
function rwsStateText(){return rwsUnloaded()?'Schedule edits not loaded — load and preview before applying.':rwsChanged()?'Draft rate changes — not applied to the model.':rwsSaved()?'Applied — no pending rate changes.':'Saved curves active — no pending rate changes.';}
function rwsCanApply(){return !rwsBusy&&!rwsUnloaded()&&rwsChanged()&&!!rwsResult&&rwsStamp===JSON.stringify(rwsCandidate());}
function rwsUpdateStatus(){const root=document.getElementById('rwsWorkspace');if(!root)return;const status=root.querySelector('[data-rws-state]');if(status){status.textContent=rwsStateText();status.classList.toggle('pending',rwsUnloaded()||rwsChanged());}const apply=root.querySelector('[data-rws-apply]');if(apply)apply.disabled=!rwsCanApply();const discard=root.querySelector('[data-rws-discard]');if(discard)discard.disabled=!rwsChanged()&&!rwsUnloaded();const preview=root.querySelector('[data-rws-preview]');if(preview){preview.disabled=rwsBusy||rwsUnloaded();preview.textContent=rwsBusy?'Working…':rwsChanged()?'Preview draft rates':'Preview applied rates';}}
// Find a concise percentage spelling that parses back to the identical stored rate.
function rwsRateText(rate,units){if(units!=='percent')return String(rate);for(let n=1;n<=17;n++){const v=String(Number((rate*100).toPrecision(n)));if(Number(v)/100===rate)return v;}return String(rate*100);}
function rwsFormSeed(k){const s=rwsDraft.indices[k]?.schedule||{};return {rwsLabel:s.label||'',rwsUnits:s.units||'',rwsCadence:s.input_cadence||'monthly',rwsStart:s.points?.[0]?.date||_isoUTC(_openingModelStart()),rwsInterpolation:s.interpolation||'',rwsExtension:s.extension||'',rwsThrough:s.through||'',rwsPaste:(s.points||[]).map(p=>p.date+'\t'+rwsRateText(p.rate,s.units)).join('\n')};}
function rwsEdit(k){rwsInit();if(!rwsForms[k]){rwsForms[k]=rwsFormSeed(k);rwsFormBases[k]=rwsCopy(rwsForms[k]);}rwsEditors[k]=true;rwsPanels['schedule:'+k]=true;rwsRender();}
function rwsEditorInput(k){if(!rwsForms[k]){rwsForms[k]=rwsFormSeed(k);rwsFormBases[k]=rwsCopy(rwsForms[k]);}Object.keys(rwsForms[k]).forEach(id=>{const el=document.getElementById(id);if(el)rwsForms[k][id]=el.value;});rwsTouch();rwsUpdateStatus();}
function rwsCancelEdit(k){delete rwsForms[k];delete rwsFormBases[k];rwsEditors[k]=false;rwsPanels['schedule:'+k]=false;rwsError='';rwsRender();}
function rwsPanel(key,open=false){return `data-rws-panel="${key}"${(key in rwsPanels?rwsPanels[key]:open)?' open':''} ontoggle="if(this.isConnected)rwsPanels['${key}']=this.open"`;}
function rwsTouch(){rwsResult=null;rwsStamp=null;rwsTicket++;rwsError='';rwsBusy=false;}
function rwsChange(path,value){rwsInit();let o=rwsDraft;const p=path.split('.');p.slice(0,-1).forEach(k=>o=o[k]||(o[k]={}));o[p.at(-1)]=value;rwsTouch();rwsRender();}
function rwsRate(path,v,scale=100){if(String(v).trim()===''||!Number.isFinite(Number(v))){rwsError='Enter a finite rate.';rwsRender();return;}rwsChange(path,Number(v)/scale);}
function rwsAnchor(d,v){rwsRate('anchor_overrides.'+d,v);}
function rwsDeleteAnchor(d){delete rwsDraft.anchor_overrides[d];rwsTouch();rwsRender();}
function rwsCandidate(){const c=rwsCopy(cfg);c.assumptions.rates_workspace=rwsCopy(rwsDraft);return c;}
async function rwsPreview(){
  rwsInit();if(rwsUnloaded()){rwsError='Load the schedule edits before previewing or applying.';rwsUpdateStatus();return;}const owner=cfg,candidate=rwsCandidate(),stamp=JSON.stringify(candidate),ticket=++rwsTicket;
  rwsBusy=true;rwsError='';rwsRender();
  try{const response=await fetch('/api/v31/rates/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({config:candidate})});const data=await response.json();
    if(owner!==cfg||ticket!==rwsTicket||JSON.stringify(rwsCandidate())!==stamp)return;
    if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Rate preview failed.');
    rwsResult=data;rwsStamp=stamp;
  }catch(e){if(owner===cfg&&ticket===rwsTicket){rwsError=e.message;rwsResult=null;rwsStamp=null;}}
  finally{if(owner===cfg&&ticket===rwsTicket){rwsBusy=false;rwsRender();}}
}
function rwsApply(){
  rwsInit();
  if(!rwsChanged()&&!rwsUnloaded())return;
  if(!rwsCanApply()){rwsError='Preview the current draft before applying.';rwsRender();return;}
  cfg.assumptions.rates_workspace=rwsCopy(rwsDraft);rwsForms={};rwsFormBases={};rwsEditors={};CURVE_ORDER.forEach(k=>rwsPanels['schedule:'+k]=false);scheduleAutosave();renderGlobals();refresh();rwsRender();
}
function rwsCancel(){rwsReset();rwsInit();rwsRender();}
async function rwsFetch(){
  rwsInit();const owner=cfg,stamp=JSON.stringify(rwsDraft),ticket=++rwsTicket;rwsBusy=true;rwsError='';rwsRender();
  try{const resp=await fetch('/api/curves/refresh',{method:'POST'});const data=await resp.json();
    if(owner!==cfg||ticket!==rwsTicket||JSON.stringify(rwsDraft)!==stamp)return;
    if(!resp.ok||!data.ok||!data.snapshot)throw Error(data.detail||'Refresh failed; saved evidence and adjustments are unchanged.');
    rwsDraft.previous_published=rwsCopy(rwsDraft.published);rwsDraft.published=rwsCopy(data.snapshot);rwsDraft.published.evidence='Fetched from FRED';rwsResult=null;rwsStamp=null;
  }catch(e){if(owner===cfg&&ticket===rwsTicket)rwsError=e.message;}
  finally{if(owner===cfg&&ticket===rwsTicket){rwsBusy=false;rwsRender();}}
}
function rwsSource(k,v){rwsInit();rwsDraft.indices[k]=rwsDraft.indices[k]||{};rwsChange('indices.'+k+'.source',v);if(v==='schedule'&&!rwsDraft.indices[k].schedule?.points?.length)rwsEdit(k);}
function rwsOverride(k){
  const st=document.getElementById('rwsRangeStart').value,en=document.getElementById('rwsRangeEnd').value,raw=document.getElementById('rwsRangeRate').value;
  if(!st||!en||st>en||raw.trim()===''||!Number.isFinite(Number(raw))){rwsError='Enter ordered dates and a finite annual rate.';rwsRender();return;}
  const c=rwsDraft.indices[k];if(c.source==='existing'){rwsError='Select Fed-based projection or Engagement schedule before adding a range override.';rwsRender();return;}
  (c.overrides||(c.overrides=[])).push({start:st,end:en,rate:Number(raw)/100});rwsTouch();rwsRender();
}
function rwsRemoveRange(k,i){rwsDraft.indices[k].overrides.splice(i,1);rwsTouch();rwsRender();}
function rwsParse(text,units,start,cadence,index){
  if(!['percent','decimal'].includes(units))throw Error('Choose Percent or Decimal before loading rates.');
  let lines=text.trim().split(/\r?\n/).map(s=>s.trim()).filter(Boolean);if(!lines.length)throw Error('Paste a rate schedule.');
  const split=s=>s.split(/\t|,|\s+/).filter(Boolean);
  let cells=lines.map(split),header=null;
  if(cells[0].some(x=>/^(date|effr|sofr|prime)$/i.test(x)))header=cells.shift().map(x=>x.toLowerCase());
  const dateCol=header?header.indexOf('date'):0,col=header?header.indexOf(index):1;
  const dated=cells.every(r=>/^\d{4}-\d{2}-\d{2}$/.test(r[Math.max(0,dateCol)]));
  if(header&&col<0)throw Error('No '+index.toUpperCase()+' column found.');
  const annual=x=>{const cleaned=String(x).replace(/%$/,'');if(!cleaned||!Number.isFinite(Number(cleaned)))throw Error('Each rate must be a number.');if(String(x).endsWith('%')&&units!=='percent')throw Error('Percent signs conflict with Decimal units.');return Number(cleaned)/(units==='percent'?100:1);};
  let pts=[];
  if(dated){pts=cells.map(r=>{if(r.length!==(header?header.length:2))throw Error('Use Date + rate, or named EFFR/SOFR/Prime columns.');return {date:r[Math.max(0,dateCol)],rate:annual(r[col])};});}
  else{if(header)throw Error('Dated columns require ISO dates.');if(!/^\d{4}-\d{2}-\d{2}$/.test(start))throw Error('Choose the first effective date for an undated schedule.');const a=cells.flat(),d=new Date(start+'T00:00:00Z');if(!Number.isFinite(+d))throw Error('Invalid start date.');const step={monthly:1,quarterly:3,annual:12}[cadence];if(!step)throw Error('Choose schedule frequency.');pts=a.map((x,i)=>{const m=new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth()+i*step,1));return {date:m.toISOString().slice(0,10),rate:annual(x)};});}
  if(!pts.length||pts.length>4000)throw Error('Supply 1–4000 rates.');
  pts.forEach((p,i)=>{const d=new Date(p.date+'T00:00:00Z');if(!Number.isFinite(+d)||d.toISOString().slice(0,10)!==p.date)throw Error('Invalid date.');if(i&&pts[i-1].date>=p.date)throw Error('Dates must be increasing and unique.');if(Math.abs(p.rate)>2)throw Error('Check rate units: rates exceed 200%.');});return pts;
}
function rwsLoad(k){
  try{const val=id=>document.getElementById(id).value;const units=val('rwsUnits'),pts=rwsParse(val('rwsPaste'),units,val('rwsStart'),val('rwsCadence'),k),label=val('rwsLabel').trim();if(!label)throw Error('Enter a source label.');
    const s={points:pts,label,units,interpolation:val('rwsInterpolation'),extension:val('rwsExtension'),through:val('rwsThrough'),entered_at:new Date().toISOString(),input_cadence:val('rwsCadence')};
    if(!s.interpolation||!s.extension)throw Error('Choose interpolation and after-schedule treatment.');
    rwsDraft.indices[k].schedule=s;rwsDraft.indices[k].source='schedule';delete rwsForms[k];delete rwsFormBases[k];rwsEditors[k]=false;rwsPanels['schedule:'+k]=false;rwsTouch();rwsRender();return rwsPreview();
  }catch(e){const err=document.getElementById('rwsPasteError');if(err)err.textContent=e.message;}
}
function rwsClear(k){delete rwsForms[k];delete rwsFormBases[k];rwsEditors[k]=false;delete rwsDraft.indices[k].schedule;rwsDraft.indices[k].source='existing';rwsTouch();rwsRender();}
function rwsSelect(options,value){return options.map(([v,label])=>`<option value="${esc(v)}" ${v===value?'selected':''}>${esc(label)}</option>`).join('');}
function rwsPlot(rows){
  if(!rows?.length)return '';const comp=rwsResult?.comparison||[],vals=rows.flatMap(r=>CURVE_ORDER.map(k=>r[k].rate)).concat(comp.map(r=>r[rwsIndex])),lo=Math.min(...vals)-.001,hi=Math.max(...vals)+.001;let h='<svg viewBox="0 0 800 155" role="img" aria-label="Effective annualized index rates">';
  for(let i=0;i<4;i++){const y=12+i*40;h+=`<line x1="42" x2="790" y1="${y}" y2="${y}" stroke="#e5e3dd"/><text x="0" y="${y+4}" fill="#777" font-size="10">${((hi-i*(hi-lo)/3)*100).toFixed(2)}%</text>`;}
  CURVE_ORDER.forEach((k,i)=>{const pts=rows.map((r,j)=>`${42+j*748/Math.max(1,rows.length-1)},${12+(hi-r[k].rate)/(hi-lo)*120}`).join(' ');h+=`<polyline points="${pts}" fill="none" stroke="${['#9d783a','#3c847b','#555b62'][i]}" stroke-width="2"/>`;});if(comp.length){const pts=comp.map((r,j)=>`${42+j*748/Math.max(1,comp.length-1)},${12+(hi-r[rwsIndex])/(hi-lo)*120}`).join(' ');h+=`<polyline points="${pts}" fill="none" stroke="#bfae87" stroke-width="1.5" stroke-dasharray="4 4"/>`;}return h+'</svg><div class="rws-legend">Dashed · selected index, Fed-based comparison &nbsp; EFFR · gold &nbsp; SOFR · teal &nbsp; Prime · charcoal</div>';
}
function ratesWorkspaceHtml(){
  rwsInit();const w=rwsDraft,p=w.published||{},f=p.fomc||{},cp=p.current_policy||{},k=rwsIndex,c=w.indices[k]||{source:'existing'},s=c.schedule||{},form=rwsForms[k]||rwsFormSeed(k),editing=!!rwsEditors[k],fmt=v=>v==null?'—':(v*100).toFixed(3)+'%',option=rwsSelect;
  let h=`<div class="rws"><header class="rws-hero"><div><h2>Rates & Curves</h2><p>Published policy anchors. Your assumptions. Effective index paths.</p></div><span>1 Published → 2 Adjustments → 3 Effective</span></header>
  <div data-rws-state class="rws-applied-state${rwsChanged()||rwsUnloaded()?' pending':''}" role="status">${esc(rwsStateText())}</div>
  <div class="rws-status">${CURVE_ORDER.map(i=>`<span>${CURVE_LABEL[i]} · ${esc({existing:'Saved curve',derived:'Fed-based',schedule:'Engagement schedule'}[w.indices[i]?.source||'existing'])}</span>`).join('')}</div>
  <section class="rws-panel"><div class="rws-head"><div><h3><b>1</b> Published Fed projections</h3><p>Read-only evidence. No interpolation in this section.</p></div><button onclick="rwsFetch()" ${rwsBusy?'disabled':''}>↻ Refresh from Fed (FRED)</button></div>
  <div class="rws-source"><div><label>Current target range</label><strong>${fmt(cp.bottom)} – ${fmt(cp.top)}</strong><small>Midpoint ${fmt(cp.mid)} · observation ${esc(cp.observation_date||cp.statement_date||'not recorded')}</small><small>DFEDTARL / DFEDTARU</small></div><div class="rws-scroll"><table><thead><tr><th>Projection target</th><th>Fetched value</th><th>Previous fetch</th></tr></thead><tbody>${Object.entries(f.anchors||{}).sort().map(([d,v])=>`<tr><td>${esc(d)}</td><td>${fmt(v)}</td><td>${fmt(w.previous_published?.fomc?.anchors?.[d])}</td></tr>`).join('')}<tr><td>Longer run</td><td>${fmt(f.lr)}</td><td>${fmt(w.previous_published?.fomc?.lr)}</td></tr></tbody></table></div></div>
  <p class="rws-note">${esc(p.evidence||'Saved evidence')} · SEP release ${esc(f.source_vintage||'not supplied by feed')} · retrieved ${esc(p.retrieved_at||'not recorded')}. FEDTARMD / FEDTARMDLR. Year-end policy target midpoints, not official EFFR/SOFR/Prime forecasts.</p>
  <p class="rws-note">Refresh stages new evidence for preview. Engagement schedules, basis assumptions and overrides are retained. Apply changes explicitly.</p></section>
  <section class="rws-panel"><div class="rws-head"><div><h3><b>2</b> Your adjustments</h3><p>All percentages are annualized. Select one index to author.</p></div><div class="rws-tabs">${CURVE_ORDER.map(i=>`<button class="${i===k?'active':''}" onclick="rwsIndex='${i}';rwsRender()">${CURVE_LABEL[i]}</button>`).join('')}</div></div>
  <div class="rws-fields"><label class="rws-active-source">Active source<select onchange="rwsSource('${k}',this.value)">${option([['existing','Saved curve · preserve current behavior'],['derived','Fed-based projection'],['schedule','Engagement rate schedule']],c.source)}</select></label></div>
  <p class="rws-note">${c.source==='existing'?'Saved r335 curve is authoritative, including its manual edits. Policy adjustments below stay inactive for this index until Fed-based projection is selected.':c.source==='schedule'?'Engagement schedule replaces policy anchors and basis for this index. Month-range overrides, if present, apply last.':'Dated policy anchors → index basis → month-range overrides. Product spreads, deposit betas, floors and product overrides remain on product cards.'}</p>
  <details class="rws-detail" ${rwsPanel('policy:'+k)}><summary>Policy anchors & derivation <span>${Object.keys(w.anchor_overrides||{}).length} overridden · ${esc(w.policy_interpolation)} · ${esc(w.policy_tail)}</span></summary><p class="rws-note">Shared across indices set to Fed-based projection. These do not rewrite the published evidence.</p><table><thead><tr><th>Target date</th><th>Published</th><th>Value used · %</th><th>Status</th></tr></thead><tbody>${Object.entries({...f.anchors,...(cp.mid!=null?{[cp.observation_date||cp.statement_date]:cp.mid}:{})}).sort().map(([d,v])=>`<tr><td>${esc(d)}</td><td>${fmt(v)}</td><td><input aria-label="Policy anchor ${esc(d)} (%)" type="number" step="any" value="${(w.anchor_overrides[d]??v)*100}" onchange="rwsAnchor('${d}',this.value)"></td><td>${d in w.anchor_overrides?`<span class="rws-amber">Overridden</span> <button onclick="rwsDeleteAnchor('${d}')">Reset</button>`:'Source'}</td></tr>`).join('')}<tr><td>Longer run</td><td>${fmt(f.lr)}</td><td><input aria-label="Longer-run policy rate (%)" type="number" step="any" value="${(w.anchor_overrides.longer_run??f.lr??0)*100}" onchange="rwsAnchor('longer_run',this.value)"></td><td>${'longer_run' in w.anchor_overrides?'<button onclick="rwsDeleteAnchor(\'longer_run\')">Reset</button>':'Source'}</td></tr></tbody></table>
  <div class="rws-fields"><label>Between policy anchors<select onchange="rwsChange('policy_interpolation',this.value)">${option([['linear','Linear by calendar day'],['step','Step / hold']],w.policy_interpolation)}</select></label><label>After final policy anchor<select onchange="rwsChange('policy_tail',this.value)">${option([['glide','Glide 5bp/quarter to longer run'],['hold','Hold last value']],w.policy_tail)}</select></label><label>${CURVE_LABEL[k]} basis · bp${k==='prime'?' above range top':''}<input type="number" step="any" value="${(w.basis[k]??CURVE_OFFSET_DEFAULT[k])*10000}" onchange="rwsRate('basis.${k}',this.value,10000)"></label></div><p class="rws-note">Prime year-end range half-width assumption: ${((cfg.assumptions.rate_curves?.half_band??HALF_BAND_DEFAULT)*10000).toFixed(2)} bp. This is a Foundry assumption.</p></details>
  <details class="rws-detail" ${rwsPanel('schedule:'+k,editing)}><summary>Engagement rate schedule <span>${s.points?.length||0} values${s.label?' · '+esc(s.label):''}</span></summary>
  ${s.points?.length?`<p class="rws-note">${esc(s.label)} · ${s.points[0].date}${s.through?' through '+esc(s.through):' onward · final value '+s.points.at(-1).date} · ${esc(s.interpolation)} · extension ${esc(s.extension)}</p><div class="rws-scroll rws-loaded-schedule"><table><thead><tr><th>Effective date</th><th>Annual rate (%)</th></tr></thead><tbody>${s.points.map(p=>`<tr><td>${esc(p.date)}</td><td>${esc(rwsRateText(p.rate,'percent'))}%</td></tr>`).join('')}</tbody></table></div>`:''}
  ${!editing?`<div class="rws-actions"><button onclick="rwsEdit('${k}')">${s.points?.length?'Edit / replace schedule':'Enter schedule'}</button>${s.points?.length?`<button onclick="rwsClear('${k}')">Remove schedule</button>`:''}</div>`:`<div class="rws-schedule-editor" oninput="rwsEditorInput('${k}')" onchange="rwsEditorInput('${k}')">
  <div class="rws-fields"><label class="rws-wide">Source label<input id="rwsLabel" placeholder="Client model · version or date" value="${esc(form.rwsLabel)}"></label><label>Input units<select id="rwsUnits">${option([['','Choose units…'],['percent','Percent · 3.40 means 3.40%'],['decimal','Decimal · 0.034 means 3.40%']],form.rwsUnits)}</select></label><label>Schedule frequency<select id="rwsCadence">${option([['monthly','Monthly'],['quarterly','Quarterly'],['annual','Annual']],form.rwsCadence)}</select></label><label>First effective date · undated input<input id="rwsStart" type="date" value="${esc(form.rwsStart)}"></label><label>Between dated values<select id="rwsInterpolation">${option([['','Choose…'],['step','Step / hold'],['linear','Linear by calendar day']],form.rwsInterpolation)}</select></label><label>After schedule coverage<select id="rwsExtension">${option([['','Choose…'],['hold','Hold last rate'],['derived','Switch to Fed-based projection'],['error','Require coverage · fail if incomplete']],form.rwsExtension)}</select></label><label>Coverage through · inclusive<input id="rwsThrough" type="date" value="${esc(form.rwsThrough)}"></label></div>
  <label class="rws-paste-label">Paste ${CURVE_LABEL[k]} rates, Date + Rate, or Date / EFFR / SOFR / Prime columns<textarea id="rwsPaste" spellcheck="false" placeholder="2028-01-01&#9;3.40&#10;2029-01-01&#9;3.10">${esc(form.rwsPaste)}</textarea></label>
  <p class="rws-note">ISO dates required for dated input. Undated values start at the first effective date and change on month / quarter / year starts. Coverage end states how long the final value applies; extension must be chosen explicitly.</p><div id="rwsPasteError" class="rws-error" role="alert"></div><div class="rws-actions"><button onclick="rwsCancelEdit('${k}')">Cancel edit</button><button onclick="document.getElementById('rwsPaste').value='';rwsEditorInput('${k}')">Clear paste</button><button class="rws-primary" onclick="rwsLoad('${k}')">Load (replace) & preview</button></div></div>`}</details>
  <details class="rws-detail" ${rwsPanel('ranges:'+k)}><summary>Month-range overrides <span>${(c.overrides||[]).length} configured</span></summary>${(c.overrides||[]).map((r,i)=>`<div class="rws-range"><span>${r.start} – ${r.end} · ${fmt(r.rate)}</span><button aria-label="Remove override" onclick="rwsRemoveRange('${k}',${i})">×</button></div>`).join('')}<div class="rws-fields"><label>From<input id="rwsRangeStart" type="date"></label><label>Through<input id="rwsRangeEnd" type="date"></label><label>Annual rate · %<input id="rwsRangeRate" type="number" step="any"></label></div><button onclick="rwsOverride('${k}')">+ Add override</button></details></section>
  <section class="rws-panel"><div class="rws-head"><div><h3><b>3</b> Effective index paths</h3><p>Base case, before product pricing and scenario shifts.</p></div><div class="rws-tabs"><button class="${rwsView==='monthly'?'active':''}" onclick="rwsView='monthly';rwsRender()">Monthly</button><button class="${rwsView==='native'?'active':''}" onclick="rwsView='native';rwsRender()">Engine cadence</button></div></div>`;
  if(rwsResult&&rwsStamp===JSON.stringify(rwsCandidate())&&!rwsUnloaded()){h+=rwsPlot(rwsResult.monthly);const monthly=rwsView==='monthly',rows=monthly?rwsResult.monthly:rwsResult.native;h+=`<p class="rws-note">${esc(rwsResult.sampling)} ${monthly?'Monthly diagnostic grid.':'Native engine rates.'}</p><div class="rws-scroll"><table><thead><tr><th>Index / date</th>${rows.map(r=>`<th>${r.date}</th>`).join('')}</tr></thead><tbody>${CURVE_ORDER.map(i=>`<tr><th>${CURVE_LABEL[i]}</th>${rows.map(r=>{const obj=monthly?r[i]:{rate:r[i],source:'Engine period-end'},v=obj.rate;return `<td title="${esc(obj.source+' · '+(obj.label||''))}" class="${obj.source==='Engagement schedule'?'rws-teal':obj.source==='Month-range override'?'rws-amber':''}">${fmt(v)}</td>`;}).join('')}</tr>`).join('')}</tbody></table></div><p class="rws-note">Audit records published anchors, engagement inputs, source labels, interpolation, extensions and monthly/native effective rates. No rate is summed across months.</p>`;}
  else h+=`<p class="rws-note">${rwsChanged()||rwsUnloaded()?'Applied rates remain active while you edit. Load schedule edits, preview, then Apply changes.':'Applied rates are active. Preview applied rates to display the complete index paths; no reloading or reapplying is needed.'}</p>`;
  h+=`<div class="rws-error" role="alert">${esc(rwsError)}</div><div class="rws-actions"><button data-rws-discard onclick="rwsCancel()" ${!rwsChanged()&&!rwsUnloaded()?'disabled':''}>Discard draft</button><button data-rws-preview onclick="rwsPreview()" ${rwsBusy||rwsUnloaded()?'disabled':''}>${rwsBusy?'Working…':rwsChanged()?'Preview draft rates':'Preview applied rates'}</button><button data-rws-apply class="rws-primary" onclick="rwsApply()" ${!rwsCanApply()?'disabled':''}>Apply changes</button></div></section></div>`;return h;
}
function rwsRender(){const el=document.getElementById('rwsWorkspace');if(el)el.innerHTML=ratesWorkspaceHtml();}
function rwsOpen(){setTab('config');cfgSelectModule('rates');}
