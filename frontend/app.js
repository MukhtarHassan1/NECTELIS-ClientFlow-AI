/* ClientFlow AI — The Signal Room. Framework-free, accessible, API-backed UI. */
'use strict';
const $ = id => document.getElementById(id);
const scenarios = ['new', 'replay', 'update', 'conflict', 'ratelimit', 'unauthorized', 'noconsent', 'notification'];
const fallbackProfiles = [
  {client_key:'home-services-demo',company_name:'Northline Home Services',industry:'home_services',timezone:'America/New_York',services:['air_conditioner_repair','plumbing','electrical']},
  {client_key:'real-estate-demo',company_name:'Horizon Realty',industry:'real_estate',timezone:'America/New_York',services:['property_viewing','rental_consultation','buying_consultation']}
];
let profiles = fallbackProfiles;
let lastEvent = null;
let lastResult = null;
let recentState = null;
let scenarioSeed = null;
let busy = false;
let suiteActive = false;
const verdicts = {};
function toast(message) {
  const el = $('toast'); el.textContent = message; el.classList.add('visible');
  clearTimeout(toast.timer); toast.timer = setTimeout(() => el.classList.remove('visible'), 3600);
}
function newId(prefix='cf') {
  const id = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID().slice(0,18) : Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,9);
  return prefix+'-'+id;
}
function formatService(s) {return s.replaceAll('_', ' ').replace(/\b\w/g, m => m.toUpperCase());}
function currentProfile() {return profiles.find(p => p.client_key === $('profile').value) || profiles[0];}
function localDateInput(date) {const adjusted = new Date(date.getTime() - date.getTimezoneOffset()*60000);return adjusted.toISOString().slice(0,16);}
function nextSlot(offset=0, profileKey=null) {
  const key=profileKey||$('profile').value;
  const taken = new Set((recentState?.bookings || []).filter(x=>x.client_key===key).map(x=>new Date(x.start_at).getTime()));
  const start=new Date();start.setUTCDate(start.getUTCDate()+3+offset);start.setUTCHours(15,0,0,0);
  for(let i=0;i<42;i++) {
    const day=new Date(start.getTime()+i*86400000);
    if(day.getUTCDay()===0 || day.getUTCDay()===6)continue;
    for(let hour of [15,16,17,18]){
      const slot=new Date(day.getTime());slot.setUTCHours(hour,0,0,0);
      if(!taken.has(slot.getTime()))return slot;
    }
  }
  return start;
}
function refreshSlot() {$('slot').value=localDateInput(nextSlot());}
function updateProfile() {
  const p=currentProfile();
  const services=$('service'); services.replaceChildren();
  p.services.forEach(k => {const o=document.createElement('option');o.value=k;o.textContent=formatService(k);services.append(o);});
  $('active-profile').textContent='PROFILE / '+p.company_name.toUpperCase();
  $('timezone-note').textContent=`Your local time is converted to UTC. Booking is evaluated in ${p.timezone}.`;
  scenarioSeed=null;refreshSlot();
}
function drawProfiles() {
  const container=$('profile-summary');container.replaceChildren();
  profiles.forEach(p=>{
    const row=document.createElement('div');row.className='profile-row';
    const label=document.createElement('span');label.textContent=p.company_name;
    const desc=document.createElement('strong');desc.textContent=`${p.services.length} SERVICES / ${p.timezone}`;
    row.append(label,desc);container.append(row);
  });
}
async function loadProfiles() {
  try {
    const list=await api('/api/v1/profiles');
    if(!Array.isArray(list)||!list.length)throw new Error('No profiles returned');
    profiles=list;
    const chosen=$('profile').value;
    $('profile').replaceChildren();
    profiles.forEach(p=>{const o=document.createElement('option');o.value=p.client_key;o.textContent=p.company_name;$('profile').append(o);});
    if(profiles.some(p=>p.client_key===chosen))$('profile').value=chosen;
  } catch(e) {toast('Using bundled sample profile labels: '+e.message);}
  drawProfiles();updateProfile();
}
async function api(path, options={}) {
  let response;
  try {response=await fetch(path, {headers:{'Accept':'application/json','Content-Type':'application/json'},...options});}
  catch(e) {throw new Error('Cannot reach the local FastAPI server. Start RUN_WINDOWS.bat first.');}
  let data; try{data=await response.json();}catch(e){throw new Error('Server returned an invalid JSON response.');}
  if(!response.ok){const detail=data.detail || data.validation_errors?.join(', ') || response.statusText;
    throw new Error(`HTTP ${response.status}: ${typeof detail==='string'?detail:JSON.stringify(detail)}`);}
  return data;
}
function formPayload() {
  let slot=null;
  if($('slot').value){const date=new Date($('slot').value);if(Number.isNaN(date.getTime()))throw new Error('Please select a valid appointment date/time');slot=date.toISOString();}
  return {event_id:newId('ui'), source:'demo_ui',client_key:$('profile').value,
    lead:{first_name:$('first_name').value.trim(),email:$('email').value.trim()||null,phone:$('phone').value.trim()||null,
      service:$('service').value,message:$('message').value,consent_to_contact:$('consent').checked},requested_slot:slot};
}
function stateClass(status) {return status==='booked'||status==='qualified_no_booking_requested'?'success':status==='needs_review'||status==='connector_failed'||status==='slot_unavailable'?'problem':'';}
function updateFlow(steps) {
  const found=new Set();
  for(const x of steps){
    if(x.step==='receive')found.add('receive');
    if(x.step==='contact_upsert'||x.step==='crm'||x.step==='identity')found.add('contact');
    if(x.step==='qualification'||x.step==='local_ai_advisory')found.add('qualify');
    if(x.step==='booking'||x.step==='calendar'||x.step==='availability')found.add('booking');
    if(x.step==='pipeline'||x.step==='follow_up'||x.step==='notification'||x.step==='external_communication'||x.step==='error_policy')found.add('audit');
  }
  document.querySelectorAll('.flow-node').forEach(node=>node.classList.toggle('activated',found.has(node.dataset.flow)));
}
async function inspectEvent(eventId, clientKey, source='demo_ui') {
  try {
    const audit=await api(`/api/v1/audit/${encodeURIComponent(clientKey)}/${encodeURIComponent(source)}/${encodeURIComponent(eventId)}`);
    const body=$('trace');body.replaceChildren();
    $('trace-count').textContent=String(audit.timeline.length).padStart(2,'0')+' STEPS';
    updateFlow(audit.timeline);
    if(audit.timeline.length===0){body.textContent='No audit steps found.';return;}
    for(const item of audit.timeline){
      const row=document.createElement('div');row.className='trace-item'+(['failed','conflict','isolated','unavailable'].includes(item.outcome)?' negative':'');
      const inner=document.createElement('div');const heading=document.createElement('strong');heading.textContent=item.step.replaceAll('_',' ');
      const stamp=document.createElement('em');stamp.textContent=`${item.outcome.toUpperCase()} / ${item.attempts} ATTEMPT(S)`;
      const detail=document.createElement('p');detail.textContent=item.detail;
      inner.append(heading,stamp,detail);row.append(inner);body.append(row);
    }
    // The selected audit can also be inspected as JSON; results are already free of raw lead messages.
    if(lastEvent?.event_id!==eventId||lastEvent?.client_key!==clientKey||lastEvent?.source!==source){
      lastResult=audit.result||{event_id:eventId,status:audit.status};renderResult(lastResult);lastEvent={event_id:eventId,client_key:clientKey,source};
    }
  } catch(err){$('trace').textContent=err.message;toast('Could not load this trace.');}
}
function renderResult(result){
  lastResult=result;
  $('result-json').textContent=JSON.stringify(result,null,2);
  const state=$('result-state');state.textContent=(result.status||'UNEXPECTED').replaceAll('_',' ').toUpperCase();state.className='execution-badge '+stateClass(result.status);
}
async function refresh() {
  try {
    const state=await api('/api/v1/state');recentState=state;
    for(const k of ['events','contacts','bookings','followups'])$('m-'+k).textContent=(state.stats?.[k]??0).toLocaleString();
    drawLedger();
  }catch(e){toast('State unavailable: '+e.message);}
}
function drawLedger(){
  const tbody=$('event-rows');tbody.replaceChildren();
  const filter=$('ledger-filter').value;
  const events=(recentState?.events||[]).filter(item=>filter==='all'||item.status===filter);
  if(!events.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=4;td.className='empty-row';td.textContent='No events match the selected view.';tr.append(td);tbody.append(tr);return;}
  for(const event of events){
    const row=document.createElement('tr');
    const id=document.createElement('td'),code=document.createElement('code');code.textContent=event.event_id;id.append(code);
    const client=document.createElement('td');client.textContent=(profiles.find(p=>p.client_key===event.client_key)?.company_name||event.client_key);
    const outcome=document.createElement('td'),chip=document.createElement('span');chip.className='status-chip'+(stateClass(event.status)==='problem'?' warn':'');chip.textContent=event.status.replaceAll('_',' ').toUpperCase();outcome.append(chip);
    const inspect=document.createElement('td'),button=document.createElement('button');button.type='button';button.className='inspect-btn';button.textContent='Open trace ↗';button.addEventListener('click',()=>inspectEvent(event.event_id,event.client_key,event.source));inspect.append(button);
    row.append(id,client,outcome,inspect);tbody.append(row);
  }
}
function setBusy(value){
  busy=value;$('submit').disabled=value;$('run-suite').disabled=value;
  document.querySelectorAll('[data-scenario]').forEach(button=>button.disabled=value);
  $('submit').querySelector('span:first-child').textContent=value?'PROCESSING SIGNAL…':'PROCESS THIS INQUIRY';
}
async function execute(data) {
  const response=await api('/api/v1/leads',{method:'POST',body:JSON.stringify(data)});
  renderResult(response);
  lastEvent={event_id:response.event_id, client_key:data.client_key, source:data.source};
  if(response.status!=='dry_run')await inspectEvent(data.event_id,data.client_key,data.source);
  await refresh();
  return response;
}
async function submitLead(data){
  if(busy)return;
  setBusy(true);
  try{const response=await execute(data);toast('Local transaction recorded · '+response.status.replaceAll('_',' '));return response;}
  catch(e){renderResult({status:'request_failed',detail:e.message});toast(e.message);return null;}
  finally{setBusy(false);}
}
function scenarioPayload(kind){
  const data=formPayload();data.event_id=newId('proof-'+kind);
  const short=data.event_id.replace(/[^a-z0-9]/gi,'').slice(-15);
  data.lead.first_name='Taylor';data.lead.email=short+'@example.com';data.lead.phone=null;
  data.lead.consent_to_contact=true;data.lead.message='Synthetic appointment inquiry for reliability verification';
  data.requested_slot=nextSlot(scenarios.indexOf(kind)*2).toISOString();
  return data;
}
function markScenario(kind,mode,message){
  const button=document.querySelector(`[data-scenario="${kind}"]`);
  button.classList.remove('running','passed','failed');button.classList.add(mode);
  $('scenario-state-'+kind).textContent=message;
  if(mode==='passed'||mode==='failed')verdicts[kind]=mode==='passed';
  const total=Object.keys(verdicts).length;
  $('suite-count').textContent=String(Object.values(verdicts).filter(Boolean).length).padStart(2,'0')+' / 08';
  $('suite-message').textContent=total?`${total} SCENARIOS ASSESSED · ${Object.values(verdicts).filter(Boolean).length} VERIFIED`: 'NO SCENARIOS EXECUTED IN THIS SESSION';
}
async function runScenario(kind) {
  markScenario(kind,'running','RUNNING…');
  try {
    let output, base=scenarioPayload(kind);
    if(kind==='new'){scenarioSeed=base;output=await execute(base);}
    else if(kind==='replay'){
      if(!scenarioSeed||scenarioSeed.client_key!==base.client_key){scenarioSeed=base;await execute(base);}
      output=await execute(scenarioSeed);
    }
    else if(kind==='update'){
      if(!scenarioSeed||scenarioSeed.client_key!==base.client_key){scenarioSeed=base;await execute(base);}
      const changed=structuredClone(scenarioSeed);changed.event_id=newId('update');changed.lead.phone='+1555'+String([...scenarioSeed.event_id].reduce((acc,ch)=>(acc*31+ch.charCodeAt(0))%10000000,7)).padStart(7,'0');changed.lead.message='Updated synthetic service inquiry';changed.requested_slot=null;
      output=await execute(changed);
    }
    else if(kind==='conflict'){
      const first=await execute(base);
      if(first.status!=='booked')throw new Error('Setup booking was not confirmed. Try again with a free slot.');
      const second=structuredClone(base);second.event_id=newId('compete');second.lead.email='competitor'+newId().replace(/-/g,'')+'@example.com';output=await execute(second);
    }
    else{
      if(kind==='ratelimit')base.simulate={crm:'429,200'};
      if(kind==='unauthorized')base.simulate={crm:'401'};
      if(kind==='notification')base.simulate={notification:'503'};
      if(kind==='noconsent')base.lead.consent_to_contact=false;
      output=await execute(base);
    }
    const success = kind==='new'?output.status==='booked'&&output.crm_action==='created' :
      kind==='replay'?output.duplicate_event===true :
      kind==='update'?output.crm_action==='updated' :
      kind==='conflict'?output.status==='slot_unavailable' :
      kind==='ratelimit'?output.status==='booked' :
      kind==='unauthorized'?output.status==='connector_failed'&&output.retryable===false :
      kind==='noconsent'?output.status==='needs_review' :
      kind==='notification'?output.status==='booked'&&output.notification_status==='failed_logged' : false;
    markScenario(kind, success?'passed':'failed',success?'VERIFIED ✓':'CHECK RESULT');
    return success;
  }catch(e){markScenario(kind,'failed','ERROR');renderResult({status:'request_failed',detail:e.message});toast(e.message);return false;}
}
async function clickScenario(kind){if(busy)return;setBusy(true);try{await runScenario(kind);}finally{setBusy(false);}}
async function runSuite(){if(busy)return;setBusy(true);suiteActive=true;
  try{for(const kind of scenarios){await runScenario(kind);}
    const count=Object.values(verdicts).filter(Boolean).length;
    toast(count===8?'Eight synthetic scenarios verified in this browser session':`Suite completed: ${count}/8 verified. Inspect failed traces.`);
  }finally{suiteActive=false;setBusy(false);}
}
function openSettings(){const drawer=$('settings-drawer');$('drawer-scrim').hidden=false;drawer.hidden=false;drawer.querySelector('#close-settings').focus();document.addEventListener('keydown',escapeSettings);}
function closeSettings(){$('settings-drawer').hidden=true;$('drawer-scrim').hidden=true;$('open-settings').focus();document.removeEventListener('keydown',escapeSettings);}
function escapeSettings(e){if(e.key==='Escape')closeSettings();}
function applySettings(){
  document.body.classList.toggle('compact',$('compact-setting').checked);
  document.body.classList.toggle('reduced-motion',$('motion-setting').checked);
  try{localStorage.setItem('cf-ui-preferences',JSON.stringify({compact:$('compact-setting').checked,motion:$('motion-setting').checked}));}catch(e){}
}
function initSettings(){try{const p=JSON.parse(localStorage.getItem('cf-ui-preferences')||'{}');$('compact-setting').checked=!!p.compact;$('motion-setting').checked=!!p.motion;}catch(e){}applySettings();}
async function reset(){if(busy)return;
  if(!confirm('Permanently delete all LOCAL SYNTHETIC contacts, bookings, and execution history? This cannot be undone.'))return;
  try{await api('/api/v1/admin/reset',{method:'POST',body:'{}'});lastResult=null;lastEvent=null;scenarioSeed=null;
    $('result-json').textContent='// Local synthetic data cleared. Run a new scenario.';$('result-state').textContent='AWAITING EVENT';$('result-state').className='execution-badge';
    $('trace').replaceChildren();$('trace-count').textContent='00 STEPS';updateFlow([]);
    Object.keys(verdicts).forEach(k=>delete verdicts[k]);scenarios.forEach(k=>markScenario(k,'','READY'));await refresh();refreshSlot();closeSettings();toast('Synthetic data reset completed.');
  }catch(e){toast(e.message);}
}

// Provider evidence panel: actual offline HTTP adapter calls, never a connected claim.
let contractResult=null;
async function runContract(provider, scenario, button){
  document.querySelectorAll('.provider-test').forEach(el=>{el.disabled=true;el.classList.toggle('is-active',el===button);});
  $('contract-title').textContent='Testing '+provider.toUpperCase()+' / '+scenario.replaceAll('_',' ');
  $('contract-verdict').textContent='EXECUTING';$('contract-verdict').className='contract-verdict';
  $('contract-log').replaceChildren();
  try{
    const data=await api(`/api/v1/integration-lab/${encodeURIComponent(provider)}/${encodeURIComponent(scenario)}`,{method:'POST',body:'{}'});
    contractResult=data;
    $('contract-verdict').textContent=data.passed?'CONTRACT PASSED':'CHECK FAILED';
    $('contract-verdict').className='contract-verdict '+(data.passed?'pass':'fail');
    $('contract-mode').textContent=data.mode;
    $('contract-provider').textContent=data.provider;
    $('contract-hint').textContent=data.scope;
    const lines=data.request_trace || data.steps || [];
    for(const [index,line] of lines.entries()){
      const row=document.createElement('div');row.className='contract-entry';
      const no=document.createElement('span');no.className='contract-number';no.textContent=String(index+1).padStart(2,'0');
      const body=document.createElement('div');const name=document.createElement('strong');
      name.textContent=line.path?line.method+' '+line.path:line.operation;
      const summary=document.createElement('p');summary.textContent=line.path?'Operation: '+line.operation+' · Version: '+line.api_version+' · Payload fields: '+line.payload_fields.join(', '):'Payload validation / safe behavior';
      body.append(name,summary);
      const code=document.createElement('span');code.className='http'+(line.status>=400?' warn':'');
      code.textContent=typeof line.status==='number'?'HTTP '+line.status:line.status.toUpperCase();
      row.append(no,body,code);$('contract-log').append(row);
    }
    if(data.event_results){const result=document.createElement('div');result.className='contract-entry';
      const no=document.createElement('span');no.className='contract-number';no.textContent='→';
      const mid=document.createElement('div');const strong=document.createElement('strong');strong.textContent='SAFE OUTCOME';const detail=document.createElement('p');detail.textContent=data.event_results.map(e=>e.outcome).join(' → ')+` · ${data.summary.appointments} simulated appointment(s)`;mid.append(strong,detail);
      const flag=document.createElement('span');flag.className='http';flag.textContent='OFFLINE';result.append(no,mid,flag);$('contract-log').append(result);}
    $('export-contract').disabled=false;
    toast(data.passed?'Offline connector contract verified. No external provider called.':'Contract check failed — see trace.');
  }catch(e){contractResult=null;$('contract-verdict').textContent='CHECK FAILED';$('contract-verdict').className='contract-verdict fail';$('contract-log').textContent=e.message;$('export-contract').disabled=true;toast(e.message);}
  finally{document.querySelectorAll('.provider-test').forEach(el=>el.disabled=false);}
}
function exportContract(){if(!contractResult)return;const blob=new Blob([JSON.stringify({...contractResult,exported_at:new Date().toISOString()},null,2)],{type:'application/json'});
const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=`nectelis-${contractResult.provider.toLowerCase()}-${contractResult.scenario||'inbound'}-offline-evidence.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}

// Reviewer-controlled live local proof. The supplied phrase is not used as a success flag;
// every verdict is derived from HTTP replies and an independent SQLite read-back.
let lastChallengeEvidence=null;
async function executeChallenge(){
  if(busy)return;
  const phrase=$('challenge-phrase').value.trim();
  const name=$('challenge-name').value.trim();
  if(phrase.length<3 || phrase.length>40 || !/^[a-zA-Z0-9 _.-]+$/.test(phrase)){
    toast('Challenge phrase: 3–40 letters, numbers, spaces, dots or hyphens.');return;
  }
  if(!name || name.length>40 || !/^[a-zA-Z ]+$/.test(name)){
    toast('Use a synthetic name with letters/spaces, maximum 40 characters.');return;
  }
  const runId=newId('client-challenge');
  // Fresh email avoids relying on a pre-seeded CRM contact or screenshot fixture.
  const profile=currentProfile();
  const data={event_id:runId,source:'demo_ui',client_key:profile.client_key,
    lead:{first_name:name,email:`review.${runId.replace(/[^a-z0-9]/gi,'')}@example.com`,phone:null,
      service:profile.services[0],message:'Reviewer supplied challenge phrase: '+phrase,consent_to_contact:true},
    requested_slot:nextSlot(0,profile.client_key).toISOString()};
  lastChallengeEvidence=null;$('export-challenge').disabled=true;
  $('run-challenge').disabled=true;
  $('challenge-verdict').textContent='EXECUTING / API';
  $('challenge-verdict').className='';$('challenge-checks').replaceChildren();
  try{
    const before=await api('/api/v1/state');
    const first=await api('/api/v1/leads',{method:'POST',body:JSON.stringify(data)});
    const replay=await api('/api/v1/leads',{method:'POST',body:JSON.stringify(data)});
    const persisted=await api(`/api/v1/proof/verify/${encodeURIComponent(data.client_key)}/${encodeURIComponent(data.source)}/${encodeURIComponent(data.event_id)}`);
    const after=await api('/api/v1/state');
    const mutated=structuredClone(data);mutated.lead.first_name=name+' altered';
    let mutationStatus=null;
    try{
      const res=await fetch('/api/v1/leads',{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify(mutated)});
      mutationStatus=res.status;
    }catch(e){mutationStatus='network_error';}
    const checks={
      'Fresh event creates a booked lead':first.status==='booked' && first.crm_action==='created',
      'Exact replay returns duplicate-event verdict':replay.duplicate_event===true && replay.appointment_id===first.appointment_id,
      'SQLite verifies actual event/contact/booking':persisted.passed===true,
      'Exactly one new event in storage':after.stats.events-before.stats.events===1,
      'Exactly one new contact in storage':after.stats.contacts-before.stats.contacts===1,
      'Exactly one new appointment in storage':after.stats.bookings-before.stats.bookings===1,
      'Mutated replay blocked by HTTP 409':mutationStatus===409
    };
    const allPassed=Object.values(checks).every(Boolean);
    lastChallengeEvidence={title:'NECTELIS reviewer-controlled execution evidence',
      tested_at:new Date().toISOString(),environment:'LOCAL / SYNTHETIC',live_ghl_connected:false,
      reviewer_phrase:phrase,request:{method:'POST',endpoint:'/api/v1/leads',body:data},
      first_response:first,exact_replay_response:replay,mutated_replay_http_status:mutationStatus,
      sqlite_readback:persisted,counter_before:before.stats,counter_after:after.stats,
      checks,passed:allPassed,limit:'Real FastAPI + SQLite, not a live external provider or production GHL test.'};
    const area=$('challenge-checks');
    for(const [name,ok] of Object.entries(checks)){
      const line=document.createElement('div');line.className='challenge-line';
      const label=document.createElement('span');label.textContent=name;
      const result=document.createElement('strong');result.textContent=ok?'PASS':'FAIL';
      if(!ok)result.className='failed';line.append(label,result);area.append(line);
    }
    $('challenge-json').textContent=JSON.stringify(lastChallengeEvidence,null,2);
    $('challenge-verdict').textContent=allPassed?'07/07 BACKEND VERIFIED':'CHECKS FAILED';
    $('challenge-verdict').className=allPassed?'pass':'fail';
    $('export-challenge').disabled=false;
    renderResult(first);lastEvent={event_id:data.event_id,client_key:data.client_key,source:data.source};
    await inspectEvent(data.event_id,data.client_key,data.source);await refresh();
    toast(allPassed?'Real local execution and SQLite read-back verified.':'At least one check failed; inspect the actual evidence.');
  }catch(e){
    $('challenge-verdict').textContent='EXECUTION ERROR';$('challenge-verdict').className='fail';
    $('challenge-checks').textContent=e.message;$('challenge-json').textContent='// Incomplete run: '+e.message;
    toast('Challenge failed: '+e.message);
  }finally{$('run-challenge').disabled=false;}
}
function downloadChallenge(){
  if(!lastChallengeEvidence)return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(lastChallengeEvidence,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download=`nectelis-reviewer-proof-${new Date().toISOString().slice(0,10)}.json`;
  document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function downloadReport(){if(!recentState){toast('No state has been loaded to export.');return;}
  const report={proof:'NECTELIS ClientFlow AI — The Signal Room',mode:'MOCK / SYNTHETIC',not_live_GHL:true,
    exported_at:new Date().toISOString(),statistics:recentState.stats,events:recentState.events,bookings:recentState.bookings,
    contacts_masked:recentState.contacts,notifications:recentState.notifications,followups:recentState.followups,
    session_scenario_verdicts:verdicts,last_result:lastResult};
  const blob=new Blob([JSON.stringify(report,null,2)],{type:'application/json'});
  const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=`clientflow-proof-${new Date().toISOString().slice(0,10)}.json`;
  document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(link.href),1000);toast('Synthetic evidence exported.');
}
function init(){
  $('lead-form').addEventListener('submit',e=>{e.preventDefault();try{submitLead(formPayload());}catch(err){toast(err.message);}});
  $('profile').addEventListener('change',updateProfile);
  $('refresh').addEventListener('click',refresh);
  $('ledger-filter').addEventListener('change',drawLedger);
  $('run-suite').addEventListener('click',runSuite);
  document.querySelectorAll('[data-scenario]').forEach(b=>b.addEventListener('click',()=>clickScenario(b.dataset.scenario)));
  $('copy-result').addEventListener('click',async()=>{if(!lastResult){toast('Run or inspect an event first.');return;}try{await navigator.clipboard.writeText(JSON.stringify(lastResult,null,2));toast('JSON copied to clipboard.');}catch(e){toast('Clipboard unavailable in this browser.');}});
  $('download-report').addEventListener('click',downloadReport);
  $('run-challenge').addEventListener('click',executeChallenge);
  $('export-challenge').addEventListener('click',downloadChallenge);
  document.querySelectorAll('.provider-test').forEach(el=>el.addEventListener('click',()=>runContract(el.dataset.provider,el.dataset.test,el)));
  $('export-contract').addEventListener('click',exportContract);
  $('open-settings').addEventListener('click',openSettings);$('close-settings').addEventListener('click',closeSettings);$('drawer-scrim').addEventListener('click',closeSettings);
  $('compact-setting').addEventListener('change',applySettings);$('motion-setting').addEventListener('change',applySettings);$('reset-demo').addEventListener('click',reset);
  initSettings();loadProfiles();refresh();
  api('/api/v1/health').then(x=>{$('health-engine').textContent=x.ok?'ONLINE':'UNAVAILABLE';$('health-ai').textContent=x.ai_mode==='deterministic_rules_only'?'RULE-BASED':'LOCAL ADVISORY';}).catch(()=>{$('health-engine').textContent='OFFLINE';});
}
if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();

// Provider workbench: server-generated execution receipts from real connector code.
const wbScenarios={
  ghl:[['success','Contact → pipeline → appointment'],['rate_limit','429 → bounded retry'],['unavailable','Calendar conflict → review'],['unauthorized','401 → no writes'],['timeout','Ambiguous booking → reconciliation']],
  vapi:[['success','Voice report → CRM → appointment'],['duplicate','Repeated call → one appointment'],['malformed','Malformed report → rejection']],
  twilio:[['success','Inbound SMS → outbound REST → delivered'],['tamper','Tampered signature → rejected'],['rate_limit','REST 429 → no blind retry'],['delivery_failed','Delivery callback → failure recorded']]
};
let wbLast=null;
function wbUpdateScenarios(){
  const box=$('wb-scenario'), provider=$('wb-provider').value;
  box.replaceChildren();for(const [value,title] of wbScenarios[provider]){const o=document.createElement('option');o.value=value;o.textContent=title;box.appendChild(o);}
}
async function wbExecute(e){
  e.preventDefault();const button=$('wb-run');button.disabled=true;$('wb-verdict').textContent='RUNNING';$('wb-verdict').className='wb-verdict';
  const body={provider:$('wb-provider').value,scenario:$('wb-scenario').value,
    name:$('wb-name').value.trim(),phrase:$('wb-phrase').value.trim(),client_key:'home-services-demo'};
  wbLast=null;$('wb-export').disabled=true;
  try{
    const reply=await api('/api/v1/workbench/run',{method:'POST',body:JSON.stringify(body)});
    wbLast=reply;$('wb-title').textContent=`${reply.provider} / ${reply.scenario}`;
    $('wb-verdict').textContent=reply.passed?'EXECUTED ✓':'CHECK FAILED';$('wb-verdict').className=reply.passed?'wb-verdict pass':'wb-verdict fail';
    $('wb-checks').replaceChildren();for(const [label,pass] of Object.entries(reply.checks)){
      const line=document.createElement('div');line.className='wb-check';const a=document.createElement('span');a.textContent=label;
      const b=document.createElement('b');b.textContent=pass?'PASS':'FAIL';if(!pass)b.className='fail';line.append(a,b);$('wb-checks').append(line);
    }
    $('wb-trace').replaceChildren();const rows=reply.trace||[];$('wb-trace-count').textContent=`${rows.length} STEPS`;
    for(const [i,row] of rows.entries()){
      const el=document.createElement('div');el.className='wb-event';const title=document.createElement('b');title.textContent=String(i+1).padStart(2,'0')+'  '+(row.operation||row.method||row.step||'Provider event');
      const meta=document.createElement('span');meta.textContent=Object.entries(row).filter(([k])=>!['operation','method','step'].includes(k)).map(([k,v])=>`${k}: ${typeof v==='object'?JSON.stringify(v):v}`).join(' · ');
      el.append(title,meta);$('wb-trace').append(el);
    }
    $('wb-json').textContent=JSON.stringify(reply,null,2);$('wb-export').disabled=false;
  }catch(error){$('wb-verdict').textContent='REQUEST FAILED';$('wb-verdict').className='wb-verdict fail';$('wb-title').textContent='Execution stopped';$('wb-checks').textContent=error.message;$('wb-trace').textContent='Inspect the application logs for details.';}
  finally{button.disabled=false;}
}
function wbExport(){if(!wbLast)return;const url=URL.createObjectURL(new Blob([JSON.stringify({...wbLast,exported_at:new Date().toISOString()},null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download=`nectelis-${wbLast.provider.toLowerCase()}-${wbLast.scenario}-receipt.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1200);}
function wbInit(){if(!$('wb-form'))return;wbUpdateScenarios();$('wb-provider').addEventListener('change',wbUpdateScenarios);
  $('wb-form').addEventListener('submit',wbExecute);$('wb-export').addEventListener('click',wbExport);}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',wbInit);else wbInit();
