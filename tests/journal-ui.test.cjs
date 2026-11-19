// SOFTWARE TEST ONLY: actual app scripts and HTML in jsdom; no user database writes.
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto');
const {execFileSync}=require('node:child_process'),{JSDOM,VirtualConsole}=require('jsdom');
function python(code,input){return JSON.parse(execFileSync('.venv/bin/python',['-c',code],{input:JSON.stringify(input),encoding:'utf8'}))}
const settle=async()=>{for(let i=0;i<6;i++)await new Promise(r=>setImmediate(r))};
async function setup(firstConsent=false){
  const errors=[],requests=[],drafts=new Map();let saved=[],draftCounter=0;
  const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e));
  const dom=new JSDOM(fs.readFileSync('demo/index.html','utf8'),{url:'http://127.0.0.1:8765',runScripts:'dangerously',virtualConsole:vc});
  const w=dom.window;w.structuredClone=structuredClone;w.scrollTo=()=>{};w.HTMLElement.prototype.scrollIntoView=()=>{};
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true};w.HTMLDialogElement.prototype.close=function(){this.open=false};
  Object.defineProperty(w.crypto,'randomUUID',{value:crypto.randomUUID});
  w.fetch=async(url,options={})=>{
    const path=url.replace('/api/',''),body=options.body?JSON.parse(options.body):undefined;requests.push({path,body});let result;
    if(path==='session')result={csrf:'SOFTWARE-TEST',note:'SOFTWARE TEST ONLY'};
    else if(path==='summary')result={counts:Object.fromEntries(['meal','activity','sleep','medication','appointment','measurement','wellbeing'].map(k=>[k,saved.filter(r=>r.kind===k).length])),activity_sleep:[],measurements:[],incomplete_records:saved.length};
    else if(path.startsWith('records?'))result={items:saved,revision:saved.length};
    else if(path==='plans'||path==='food-catalog')result={items:[]};
    else if(path==='chat')result=python('import json,sys; from services.agent import agent_request; from services.journal import capture_time; b=json.load(sys.stdin); print(json.dumps(agent_request(b["messages"][-1]["content"],b["records"],capture_time(b.get("captured_at")))))',{...body,records:saved});
    else if(path==='journal/prepare')result=python('import json,sys; from services.journal import prepare_journal; b=json.load(sys.stdin); print(json.dumps(prepare_journal(b["text"],b["captured_at"])))',body);
    else if(path==='food-energy')result=python('import json,sys; from services.nutrition import estimate_meal; b=json.load(sys.stdin); print(json.dumps(estimate_meal({"kind":"meal","text":b["name"],"data":b})))',body);
    else if(path==='records/batch-preview'){
      const checks=python('import json,sys; from services.schemas import Record,inspect_record; print(json.dumps([inspect_record(Record.model_validate(r)) for r in json.load(sys.stdin)]))',body.records);
      const id='software-draft-'+(++draftCounter);drafts.set(id,body.records);result={draft_id:id,records:body.records,checks,can_confirm:checks.every(c=>c.can_record),requires_consent:firstConsent&&!saved.some(r=>r.kind==='consent')&&!body.records.some(r=>r.kind==='consent')};
    }else if(path==='records/delete-preview'){
      const records=body.scope==='all'?saved:saved.filter(r=>body.record_ids.includes(r.id)),id='software-delete-'+(++draftCounter);
      drafts.set(id,{deleting:true,records});result={draft_id:id,records,labels:records.map(r=>r.text||r.kind),count:records.length,history_count:records.length,plan_count:0,can_confirm:records.length>0};
    }else if(path==='confirm'){
      const draft=drafts.get(body.draft_id);
      if(draft.deleting){saved=saved.filter(r=>!draft.records.some(x=>x.id===r.id));result={deleted:true,count:draft.records.length}}
      else{for(const r of draft){const old=saved.find(x=>x.id===r.previous_id);const row={...r,id:crypto.randomUUID(),version:old?old.version+1:1};saved=saved.filter(x=>x.id!==r.previous_id);saved.push(row)}result={count:draft.length}}
    }else throw new Error('Unexpected API call '+path);
    return {ok:true,json:async()=>result};
  };
  for(const file of ['demo/app.js','demo/journal.js','demo/chat.js']){const s=w.document.createElement('script');s.textContent=fs.readFileSync(file,'utf8');w.document.body.append(s)}
  await settle();assert.deepEqual(errors,[]);
  return {w,requests,errors,saved:()=>saved,close:()=>w.close()};
}
function input(w,selector,value){const e=w.document.querySelector(selector);e.value=value;e.dispatchEvent(new w.Event('input',{bubbles:true}));return e}
test('missing time is visibly defaulted to capture and manual edits preserve original capture',async()=>{
  const ui=await setup(),w=ui.w,d=w.document;
  try{
    input(w,'#journalText','กินข้าว');d.querySelector('#prepareJournal').click();await settle();
    const request=ui.requests.find(r=>r.path==='journal/prepare'),capture=request.body.captured_at;
    const expected=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Bangkok',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(capture));
    const card=d.querySelector('.journal-card'),clock=card.querySelector('input[type=time]');
    assert.equal(clock.value,expected);assert.match(card.textContent,/ไม่ได้ระบุเวลา จึงใช้เวลาที่พิมพ์/);
    assert.equal(ui.saved().length,0);
    clock.value=expected==='10:15'?'10:16':'10:15';
    d.querySelector('#journalResults>button').click();await settle();
    const record=ui.requests.filter(r=>r.path==='records/batch-preview').at(-1).body.records[0];
    assert.equal(record.journal.clock_source,'user_edited');
    assert.equal(new Date(record.journal.captured_at).getTime(),new Date(capture).getTime());
    assert.equal(record.data.occurred_at.slice(11,16),clock.value);
    d.querySelector('#confirmReview').click();await settle();
    assert.equal(ui.saved()[0].journal.clock_source,'user_edited');assert.deepEqual(ui.errors,[]);
  }finally{ui.close()}
});
test('one message, several categories, period-only save, then refine time',async()=>{
  const ui=await setup(),w=ui.w,d=w.document;
  try{
    input(w,'#journalText','ตอนเช้ากินข้าว 1 จาน\nตอนบ่ายเดิน\nรู้สึกเหนื่อย');d.querySelector('#prepareJournal').click();await settle();
    assert.equal(d.querySelectorAll('.journal-card').length,3);assert.equal(ui.saved().length,0);
    const activity=d.querySelectorAll('.journal-card')[1];assert.equal(activity.querySelector('input[type=time]').value,'');
    d.querySelector('#journalResults>button').click();await settle();assert.equal(d.querySelector('#confirmReview').disabled,false);assert.equal(ui.saved().length,0);
    d.querySelector('#confirmReview').click();await settle();assert.equal(ui.saved().length,3);assert.equal(d.querySelector('#journalText').value,'');
    assert.equal(ui.saved().find(r=>r.kind==='activity').journal.period,'afternoon');assert.equal(ui.saved().find(r=>r.kind==='activity').data.start,null);
    const row=[...d.querySelectorAll('#records .row')].find(x=>x.querySelector('strong').textContent==='การเคลื่อนไหว');row.querySelector('button').click();await settle();
    const card=d.querySelector('.journal-card'),times=card.querySelectorAll('input[type=time]');times[0].value='16:00';times[1].value='16:30';
    d.querySelector('#journalResults>button').click();await settle();d.querySelector('#confirmReview').click();await settle();
    const updated=ui.saved().find(r=>r.kind==='activity');assert.equal(updated.version,2);assert.match(updated.data.start,/T16:00:00\+07:00$/);assert.equal(ui.saved().length,3);assert.deepEqual(ui.errors,[]);
  }finally{ui.close()}
});
test('unknown category must be chosen or explicitly excluded; changed text invalidates old cards',async()=>{
  const ui=await setup(),w=ui.w,d=w.document;
  try{
    input(w,'#journalText','ข้อความที่ยังไม่ชัดเจน');d.querySelector('#prepareJournal').click();await settle();
    d.querySelector('#journalResults>button').click();await settle();assert.match(d.querySelector('#notice').textContent,/กรุณาเลือกหมวด/);assert.equal(ui.requests.filter(x=>x.path==='records/batch-preview').length,0);
    input(w,'#journalText','เดิน 16.00');d.querySelector('#journalResults>button').click();await settle();assert.match(d.querySelector('#notice').textContent,/ข้อความเปลี่ยนแล้ว/);assert.equal(ui.saved().length,0);assert.deepEqual(ui.errors,[]);
  }finally{ui.close()}
});

test('home assistant drafts multiple records and requires explicit first consent before saving',async()=>{
  const ui=await setup(true),w=ui.w,d=w.document;
  try{
    input(w,'#homeAgentInput','บันทึกตอนเช้ากินข้าวมันไก่ ตอนบ่ายเดิน');d.querySelector('#homeAgentForm').requestSubmit();await settle();
    assert.equal(d.querySelector('#chat').classList.contains('hidden'),false);assert.equal(ui.saved().length,0);
    assert.match(d.querySelector('#chatMessages').textContent,/ข้าวมันไก่/);
    d.querySelector('.agent-action').click();await settle();assert.equal(d.querySelector('#review').open,true);
    assert.equal(d.querySelector('#confirmReview').disabled,true);assert.equal(ui.saved().length,0);
    const consent=d.querySelector('#reviewBody input[type=checkbox]');assert.ok(consent);consent.checked=true;consent.dispatchEvent(new w.Event('change'));await settle();
    assert.equal(d.querySelector('#confirmReview').disabled,false);assert.equal(ui.saved().length,0);
    d.querySelector('#confirmReview').click();await settle();assert.equal(ui.saved().length,3);
    const meal=ui.saved().find(r=>r.kind==='meal');assert.equal(meal.text,'ข้าวมันไก่');assert.equal(meal.journal.period,'morning');assert.equal(meal.journal.clock,null);
    assert.deepEqual(ui.errors,[]);
  }finally{ui.close()}
});

test('reported Thai meal typo is reviewed as two short names and periods before confirmation',async()=>{
  const ui=await setup(true),w=ui.w,d=w.document;
  try{
    input(w,'#homeAgentInput','วันนี้กินข้าวช้าวเป็นข้าวขาหมู ตอนเที่ยงกินต้มยำกุ้ง');d.querySelector('#homeAgentForm').requestSubmit();await settle();
    const answer=[...d.querySelectorAll('.chat-row.assistant')].at(-1);
    assert.match(answer.querySelector('.chat-message-text').textContent,/ข้าวขาหมู · ตอนเช้า/);
    assert.match(answer.querySelector('.chat-message-text').textContent,/ต้มยำกุ้ง · ตอนเที่ยง/);
    assert.doesNotMatch(answer.querySelector('.chat-message-text').textContent,/ข้าวช้าวเป็น/);
    assert.equal(answer.querySelector('.chat-answer-details').open,false);
    answer.querySelector('.agent-action').click();await settle();assert.equal(ui.saved().length,0);
    const draft=ui.requests.filter(x=>x.path==='records/batch-preview').at(-1).body.records;
    assert.deepEqual(draft.map(r=>r.text),['ข้าวขาหมู','ต้มยำกุ้ง']);
    assert.deepEqual(draft.map(r=>r.journal.period),['morning','noon']);
    assert.ok(draft.every(r=>r.journal.clock===null));
    assert.equal(d.querySelector('#confirmReview').disabled,true);
    const consent=d.querySelector('#reviewBody input[type=checkbox]');consent.checked=true;consent.dispatchEvent(new w.Event('change'));await settle();
    d.querySelector('#confirmReview').click();await settle();
    assert.equal(ui.saved().filter(r=>r.kind==='meal').length,2);assert.deepEqual(ui.errors,[]);
  }finally{ui.close()}
});

test('usage help answers with examples without preparing a write',async()=>{
  const ui=await setup(),w=ui.w,d=w.document;
  try{
    input(w,'#homeAgentInput','แนะนำหน่อยว่าฉันจะถามคุณว่าอะไรได้บ้าง');d.querySelector('#homeAgentForm').requestSubmit();await settle();
    const answer=[...d.querySelectorAll('.chat-row.assistant')].at(-1).querySelector('.chat-message-text').textContent;
    assert.match(answer,/ตอนเย็นกินอะไรดี/);assert.match(answer,/ลบบันทึกล่าสุด/);assert.doesNotMatch(answer,/นอกเรื่องสุขภาพ/);
    assert.equal(ui.saved().length,0);assert.equal(ui.requests.filter(r=>r.path.includes('preview')||r.path==='confirm').length,0);assert.deepEqual(ui.errors,[]);
  }finally{ui.close()}
});

test('edit and delete remain inside chat with before/after review, cancellation and confirmation',async()=>{
  const ui=await setup(true),w=ui.w,d=w.document;
  const ask=async text=>{input(w,'#chatInput',text);d.querySelector('#chatForm').requestSubmit();await settle();return [...d.querySelectorAll('.chat-row.assistant')].at(-1)};
  try{
    input(w,'#homeAgentInput','บันทึกตอนเช้ากินข้าวขาหมู');d.querySelector('#homeAgentForm').requestSubmit();await settle();
    d.querySelector('.agent-action').click();await settle();const consent=d.querySelector('#reviewBody input[type=checkbox]');consent.checked=true;consent.dispatchEvent(new w.Event('change'));await settle();d.querySelector('#confirmReview').click();await settle();
    const before=ui.saved().find(r=>r.kind==='meal');assert.equal(before.text,'ข้าวขาหมู');
    let answer=await ask('แก้ข้าวขาหมูเป็นโจ๊ก');answer.querySelector('.agent-action').click();await settle();
    let card=answer.querySelector('.chat-change-review');assert.ok(card);assert.equal(d.querySelector('#review').open,false);
    assert.match(card.textContent,/ก่อนแก้ไข/);assert.match(card.textContent,/ข้าวขาหมู/);assert.match(card.textContent,/โจ๊ก/);
    assert.equal(ui.saved().find(r=>r.kind==='meal').text,'ข้าวขาหมู');
    [...card.querySelectorAll('button')].find(x=>x.textContent==='ยกเลิก').click();await settle();
    assert.equal(ui.saved().find(r=>r.kind==='meal').text,'ข้าวขาหมู');
    answer.querySelector('.agent-action').click();await settle();card=answer.querySelector('.chat-change-review');[...card.querySelectorAll('button')].find(x=>x.textContent==='ยืนยันแก้ไข').click();await settle();
    const edited=ui.saved().find(r=>r.kind==='meal');assert.equal(edited.text,'โจ๊ก');assert.equal(edited.version,2);assert.deepEqual(edited.journal,before.journal);
    assert.equal(d.querySelector('#chat').classList.contains('hidden'),false);
    answer=await ask('ลบโจ๊ก');answer.querySelector('.agent-action').click();await settle();card=answer.querySelector('.chat-change-review');
    assert.match(card.textContent,/เรียกคืนในเว็บไม่ได้/);assert.equal(ui.saved().filter(r=>r.kind==='meal').length,1);
    [...card.querySelectorAll('button')].find(x=>x.textContent==='ยกเลิก').click();assert.equal(ui.saved().filter(r=>r.kind==='meal').length,1);
    answer.querySelector('.agent-action').click();await settle();card=answer.querySelector('.chat-change-review');[...card.querySelectorAll('button')].find(x=>x.textContent==='ยืนยันลบ').click();await settle();
    assert.equal(ui.saved().filter(r=>r.kind==='meal').length,0);assert.equal(ui.saved().filter(r=>r.kind==='consent').length,1);
    assert.match(d.querySelector('#chatMessages').textContent,/ลบข้อมูลที่ยืนยันแล้ว 1 รายการ/);
    assert.doesNotMatch(d.querySelector('#chatMessages').textContent,/ข้าวขาหมู|โจ๊ก/);
    assert.equal(d.querySelector('#chat').classList.contains('hidden'),false);assert.deepEqual(ui.errors,[]);
  }finally{ui.close()}
});

test('meal review shows calories, recalculates edited amounts and clears stale values without saving',async()=>{
  const ui=await setup(),w=ui.w,d=w.document;
  try{
    input(w,'#journalText','เช้ากินข้าวมันไก่ 1 จาน');d.querySelector('#prepareJournal').click();await settle();
    const card=d.querySelector('.journal-card'),energy=card.querySelector('.meal-energy');
    assert.match(energy.textContent,/558–619 kcal/);
    const quantity=[...card.querySelectorAll('label')].find(l=>l.firstChild.textContent==='ปริมาณ').querySelector('input');
    quantity.value='0.5';quantity.dispatchEvent(new w.Event('input',{bubbles:true}));
    assert.doesNotMatch(energy.textContent,/558–619/);
    await new Promise(r=>setTimeout(r,400));await settle();
    assert.match(energy.textContent,/279–309.5 kcal/);
    const name=[...card.querySelectorAll('label')].find(l=>l.firstChild.textContent==='ชื่อรายการ').querySelector('input');
    name.value='อาหารที่ไม่มีในฐาน';name.dispatchEvent(new w.Event('input',{bubbles:true}));
    await new Promise(r=>setTimeout(r,400));await settle();
    assert.match(energy.textContent,/ยังประเมินแคลอรีไม่ได้/);
    assert.doesNotMatch(energy.textContent,/279–309.5/);
    assert.equal(ui.saved().length,0);assert.ok(!ui.requests.some(r=>r.path==='confirm'));assert.deepEqual(ui.errors,[]);
  }finally{ui.close()}
});

test('rice and side stay in one meal through quantity editing, review, save and later edit',async()=>{
  const ui=await setup(),w=ui.w,d=w.document;
  try{
    input(w,'#journalText','ตอนเที่ยงกินข้าว 2 ทัพพี กับไข่พะโล้ 1 ส่วน');d.querySelector('#prepareJournal').click();await settle();
    assert.equal(d.querySelectorAll('.journal-card').length,1);
    let card=d.querySelector('.journal-card');
    assert.match(card.textContent,/512.9 kcal · รวมมื้อนี้/);
    assert.equal(card.querySelectorAll('[name=component-name]').length,2);
    input(w,'[name=component-quantity]','1');
    assert.doesNotMatch(card.querySelector('.meal-energy').textContent,/512.9/);
    await new Promise(r=>setTimeout(r,400));await settle();
    assert.match(card.textContent,/432.9 kcal · รวมมื้อนี้/);
    d.querySelector('#journalResults>button').click();await settle();
    assert.equal(ui.saved().length,0);assert.match(d.querySelector('#reviewBody').textContent,/432.9 kcal · รวมมื้อนี้/);
    d.querySelector('#confirmReview').click();await settle();
    assert.equal(ui.saved().length,1);
    const meal=ui.saved()[0];assert.equal(meal.data.components[0].quantity,1);assert.equal(meal.data.components[1].quantity,1);
    assert.equal(meal.journal.period,'noon');assert.equal(meal.data.occurred_at,null);
    const row=[...d.querySelectorAll('#records .row')].find(x=>x.querySelector('strong').textContent==='อาหาร');row.querySelector('button').click();await settle();
    card=d.querySelector('.journal-card');assert.equal(card.querySelectorAll('[name=component-name]').length,2);
    input(w,'[name=component-quantity]','0.5');await new Promise(r=>setTimeout(r,400));await settle();
    assert.match(card.textContent,/392.9 kcal · รวมมื้อนี้/);
    d.querySelector('#journalResults>button').click();await settle();d.querySelector('#confirmReview').click();await settle();
    assert.equal(ui.saved().length,1);assert.equal(ui.saved()[0].version,2);
    assert.equal(ui.saved()[0].data.components[0].quantity,0.5);assert.deepEqual(ui.errors,[]);
  }finally{ui.close()}
});
