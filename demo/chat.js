// Conversation stays in memory. Every health write opens a confirmation review.
let chatHistory=[],chatController=null,chatGeneration=0;
const chatWelcome='สวัสดีครับ ฉันช่วยตอบเรื่องสุขภาพ แนะนำอาหาร บันทึก และจัดตารางได้ พิมพ์ “ถามอะไรได้บ้าง” เพื่อดูตัวอย่าง หรือบอกสิ่งที่อยากให้ช่วยได้เลยครับ';
function chatScroll(){const box=$('#chatMessages');box.scrollTop=box.scrollHeight}
function chatBubble(role,text){
  const row=el('div',undefined,'chat-row '+role),avatar=el('span',role==='user'?'คุณ':'◒','chat-avatar'),bubble=el('div',undefined,'chat-bubble');
  bubble.append(el('div',role==='user'?'คุณ':'Baobuddy','chat-author'),el('div',text,'chat-message-text'));row.append(avatar,bubble);$('#chatMessages').append(row);chatScroll();return bubble;
}
function chatChips(questions){const box=$('#chatSuggestions');box.replaceChildren();for(const q of questions){const b=el('button',q);b.type='button';b.onclick=()=>{$('#chatInput').value=q;$('#chatForm').requestSubmit()};box.append(b)}}
function chatSources(bubble,result){
  for(const excerpt of result.excerpts||[]){const block=el('blockquote',excerpt.text,'chat-excerpt');block.append(el('small',(excerpt.content_type==='editorial_summary'?'สรุปสาระโดยผู้พัฒนา · ':'ข้อความจากแหล่งข้อมูล · ')+excerpt.chunk_id));bubble.append(block)}
  if(result.record_sources?.length){const detail=el('details',undefined,'chat-source-list');detail.append(el('summary','อ้างอิงบันทึกของคุณ '+result.record_sources.length+' รายการ'));for(const r of result.record_sources){const item=el('div',undefined,'chat-source-item');item.append(el('strong',r.label+' · '+r.time),el('p',r.text),el('small','เวอร์ชัน '+r.version+' · '+r.source));detail.append(item)}const button=el('button','เปิดประวัติบันทึก');button.type='button';button.onclick=()=>page('record');detail.append(button);bubble.append(detail)}
  for(const c of result.citations||[]){const detail=el('details',undefined,'chat-source-list');detail.append(el('summary',c.publisher+' · '+c.heading));const link=el('a','เปิดแหล่งข้อมูลต้นฉบับ ↗');try{const url=new URL(c.url);if(url.protocol==='https:'){link.href=url.href;link.target='_blank';link.rel='noopener noreferrer'}}catch{}detail.append(link,el('p',(c.content_type==='editorial_summary'?'สรุปสาระโดยผู้พัฒนา · ':'')+c.location+' · เข้าถึง '+c.accessed_at,'muted'),el('div',c.text,'evidence'));bubble.append(detail)}
}
function resetChat(){chatGeneration++;chatController?.abort();chatController=null;chatHistory=[];$('#chatMessages').replaceChildren();chatBubble('assistant',chatWelcome);chatChips(['แนะนำเมนูมื้อเย็น','วันนี้ทำอะไรไปบ้าง','จัดตารางของฉัน','เป็นเบาหวานจะอ้วนใช่ไหม']);$('#chatSend').disabled=false;$('#chatInput').value='';$('#chatInput').focus()}
$('#chatReset').onclick=resetChat;
$('#chatInput').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();if(!$('#chatSend').disabled)$('#chatForm').requestSubmit()}};
$('#chatForm').onsubmit=async event=>{
  event.preventDefault();const input=$('#chatInput'),question=input.value.trim();if(!question||chatController)return;
  if(!csrf){notice('กำลังเชื่อมเซสชัน กรุณาลองส่งอีกครั้ง');return}
  const generation=chatGeneration;chatController=new AbortController();const controller=chatController;
  chatBubble('user',question);input.value='';$('#chatSend').disabled=true;chatChips([]);
  const loading=chatBubble('assistant','กำลังดูข้อความให้ครับ…');loading.parentElement.classList.add('chat-loading');
  const messages=[...chatHistory,{role:'user',content:question}].slice(-19);
  // Limit prior context without silently truncating the user's current question.
  while(messages.length>1&&messages.reduce((n,m)=>n+m.content.length,0)>15000)messages.shift();
  try{
    const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json','x-csrf-token':csrf},body:JSON.stringify({messages,scope:'auto',captured_at:new Date().toISOString()}),signal:controller.signal});
    if(response.status===404)throw new Error('เซิร์ฟเวอร์ที่เปิดอยู่ยังไม่มี API แชต กรุณาเปิด http://127.0.0.1:8765 และเริ่มเซิร์ฟเวอร์ใหม่ด้วย .venv/bin/python scripts/run_demo.py');
    const result=await response.json();if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'ยังตอบคำถามนี้ไม่ได้ กรุณาลองใหม่');
    if(generation!==chatGeneration)return;
    loading.parentElement.remove();const bubble=chatBubble('assistant',result.answer);
    chatActions(bubble,result);chatDetails(bubble,result);chatSources(bubble,result);
    chatHistory=[...messages,{role:'assistant',content:result.answer.slice(0,4000)}].slice(-18);chatChips(result.suggestions||[]);chatScroll();
  }catch(error){
    if(generation!==chatGeneration||error.name==='AbortError')return;
    loading.parentElement.remove();chatBubble('assistant','ยังตอบไม่ได้ครับ: '+error.message);input.value=question;
  }finally{if(generation===chatGeneration){chatController=null;$('#chatSend').disabled=false;input.focus()}}
};
$('#delete').addEventListener('click',()=>{if($('#deleteText').value==='ลบข้อมูลของฉัน')resetChat()});
resetChat();

function sendAgentPrompt(text){page('chat');$('#chatInput').value=text;if(!chatController)$('#chatForm').requestSubmit();else notice('กำลังตอบข้อความก่อนหน้า ข้อความใหม่เตรียมไว้ในช่องแล้ว')}
function chatDetails(bubble,result){
  const notes=[...(result.details||[])];
  if(result.model)notes.push('ใช้ AI ในเครื่องเรียบเรียงจากหลักฐานที่แสดง');
  if(result.engine)notes.push(result.engine==='local_ai_validated_selection'?'AI ในเครื่องเลือกจากเมนูที่ผ่านการคัดส่วนผสมแล้ว':'ใช้เมนูจากรายการที่ผ่านการคัดส่วนผสมแล้ว');
  if(!notes.length)return;
  const details=el('details',undefined,'chat-source-list chat-answer-details');details.append(el('summary','ข้อมูลที่ใช้ประกอบคำตอบ'));
  for(const note of notes)details.append(el('p',note));bubble.append(details);
}
$('#globalAssistant')?.addEventListener('click',()=>{page('chat');$('#chatInput').focus()});
$('#homeAgentForm')?.addEventListener('submit',event=>{event.preventDefault();const text=$('#homeAgentInput').value.trim();if(text){sendAgentPrompt(text);$('#homeAgentInput').value=''}});
for(const button of document.querySelectorAll('[data-agent-prompt]'))button.addEventListener('click',()=>sendAgentPrompt(button.dataset.agentPrompt));
function chatActions(bubble,result){
  if(result.menus?.length){
    const list=el('div',undefined,'menu-options');
    for(const menu of result.menus){const card=el('article');card.append(el('h3',menu.name));const details=el('details',undefined,'chat-source-list');details.append(el('summary','ส่วนผสมและรายละเอียด'),el('p',menu.note),el('small',menu.kcal_note,'muted'),el('p','ส่วนผสมตามข้อเสนอ: '+menu.ingredients.join(', '),'muted'));card.append(details);const button=el('button','ใช้เมนูนี้ในแผน');button.type='button';button.onclick=()=>{page('plan');const form=$('#routineForm');form.elements.domain.value='meal';form.elements.label.value=menu.name;form.elements.label.focus();notice('ใส่ชื่อเมนูในแผนแล้ว เลือกวัน เวลา และระยะเวลาที่ต้องการก่อนยืนยัน')};card.append(button);list.append(card)}bubble.append(list);
  }
  if(result.meal_references?.length){
    const details=el('details',undefined,'chat-source-list');details.append(el('summary','ดูพลังงานอ้างอิงของอาหารที่บันทึก'));
    for(const food of result.meal_references){const row=el('div',undefined,'chat-source-item');row.append(el('strong',food.name));if(food.kcal){const [lo,hi]=food.kcal;row.append(el('p','ต่อหน่วยอ้างอิงประมาณ '+lo+(lo===hi?'':'–'+hi)+' กิโลแคลอรี'),el('p',food.basis),el('small',food.note,'muted'));const link=el('a',(food.publisher||'แหล่งอ้างอิง')+' ↗');try{const url=new URL(food.url);if(url.protocol==='https:'){link.href=url.href;link.target='_blank';link.rel='noopener noreferrer'}}catch{}row.append(link);for(const source of food.additional_sources||[]){try{const url=new URL(source.url);if(url.protocol==='https:'){const extra=el('a',(source.publisher||'แหล่งอ้างอิงเพิ่มเติม')+' ↗');extra.href=url.href;extra.target='_blank';extra.rel='noopener noreferrer';row.append(el('br'),extra)}}catch{}}}else row.append(el('p',food.note));details.append(row)}details.append(el('p','ค่ารวมโดยประมาณใช้ปริมาณที่บันทึก หรือหน่วยอ้างอิงเมื่อยังไม่บอกปริมาณ สูตรและขนาดเสิร์ฟจริงอาจต่างกัน','muted'));bubble.append(details);
  }
  for(const action of result.actions||[]){
    if(!['navigate','records','journal','plan','export','delete_records'].includes(action.type))continue;
    const button=el('button',action.label||'ตรวจรายการ','agent-action');button.type='button';
    button.onclick=async()=>{button.disabled=true;try{
      if(action.type==='navigate'){if(['overview','profile','record','plan','chat','knowledge'].includes(action.page))page(action.page)}
      else if(action.type==='records'){if(action.inline)await chatChangeReview(bubble,action);else await reviewBatch(action.records,!!action.compact)}
      else if(action.type==='delete_records')await chatChangeReview(bubble,action);
      else if(action.type==='journal'){page('record');$('#journalText').value=action.text;$('#journalText').dispatchEvent(new Event('input',{bubbles:true}));if(action.captured_at){journalCapturedAt=action.captured_at;updateCaptureNote()}$('#prepareJournal').click()}
      else if(action.type==='export')$('#export').click();
      else if(action.type==='plan'){const r=await api('plans/preview',{start_date:action.start_date,general_time_only:true});renderPlan(r.plan,$('#reviewBody'));$('#confirmReview').disabled=!r.can_confirm;pending={draft_id:r.draft_id,idempotency_key:crypto.randomUUID(),confirmed:true};$('#review').showModal()}
    }catch(error){notice(error.message)}finally{button.disabled=false}};bubble.append(button);
  }
}

async function chatChangeReview(bubble,action){
  const generation=chatGeneration,deleting=action.type==='delete_records';
  const path=deleting?'records/delete-preview':'records/batch-preview';
  const payload=deleting?{scope:action.scope,record_ids:action.record_ids}:{records:action.records,compact:!!action.compact};
  let draft=await api(path,payload);if(generation!==chatGeneration)return;
  bubble.querySelector('.chat-change-review')?.remove();
  const card=el('div',undefined,'chat-change-review');bubble.append(card);
  card.append(el('strong',deleting?(action.scope==='all'?'ลบข้อมูลทั้งหมดของคุณ':'ตรวจรายการที่จะลบ'):'ตรวจการแก้ไข'));
  if(deleting){
    card.append(el('p',draft.count+' รายการ · รวมประวัติ '+draft.history_count+' เวอร์ชัน'));
    for(const label of draft.labels.slice(0,30))card.append(el('p','• '+label));
    if(draft.labels.length>30)card.append(el('p','และอีก '+(draft.labels.length-30)+' รายการ'));
    if(draft.plan_count)card.append(el('p','แผนที่อ้างอิงข้อมูลนี้จะถูกลบด้วย '+draft.plan_count+' แผน ต้องสร้างใหม่จากข้อมูลที่เหลือ'));
    card.append(el('p','ลบแล้วเรียกคืนในเว็บไม่ได้'+(action.scope==='all'?' ไฟล์ที่เคยดาวน์โหลดต้องลบแยก':''),'muted'));
  }else{
    for(const [i,record] of draft.records.entries()){
      const before=action.before?.[i];
      const keys=Object.keys(record.data).filter(k=>!before||JSON.stringify(before.data[k])!==JSON.stringify(record.data[k]));
      if(before){card.append(el('p','ก่อนแก้ไข'),fieldsView(Object.fromEntries(keys.map(k=>[k,before.data[k]??null]))))}
      card.append(el('p','หลังแก้ไข'),fieldsView(Object.fromEntries(keys.map(k=>[k,record.data[k]]))));
      if(record.kind==='meal'&&draft.checks[i]?.calculated?.energy){const energyBox=el('div');renderEnergy(energyBox,draft.checks[i].calculated.energy);card.append(energyBox)}
      if(record.journal){const periods={morning:'ตอนเช้า',noon:'ตอนเที่ยง',afternoon:'ตอนบ่าย',evening:'ตอนเย็น',night:'ตอนกลางคืน'};card.append(el('p',[record.journal.date,periods[record.journal.period],record.journal.clock?.slice(0,5)].filter(Boolean).join(' · ')))}
      for(const error of draft.checks[i].errors||[])card.append(el('p',error,'fail'));
    }
  }
  const confirm=el('button',deleting?'ยืนยันลบ':'ยืนยันแก้ไข','primary'),cancel=el('button','ยกเลิก'),status=el('p',undefined,'muted');
  confirm.type=cancel.type='button';confirm.disabled=!draft.can_confirm||!!draft.requires_consent;
  let cancelled=false,attempt=0;
  if(draft.requires_consent){
    const label=el('label','ฉันยินยอมให้เก็บข้อมูลที่ยืนยันในเครื่องนี้','check'),checkbox=el('input');checkbox.type='checkbox';label.prepend(checkbox);card.append(label);
    checkbox.onchange=async()=>{const token=++attempt;confirm.disabled=true;if(!checkbox.checked)return;try{
      const next=await api(path,{...payload,records:[{kind:'consent',data:{local_storage:true},source:'ผู้ใช้ยินยอมเก็บข้อมูลก่อนยืนยันในแชต'},...payload.records]});
      if(!cancelled&&generation===chatGeneration&&token===attempt&&checkbox.checked){draft=next;confirm.disabled=!next.can_confirm||!!next.requires_consent}
    }catch(error){status.textContent=error.message}};
  }
  cancel.onclick=()=>{cancelled=true;confirm.disabled=true;cancel.disabled=true;status.textContent='ยกเลิกแล้ว ยังไม่ได้เปลี่ยนข้อมูลครับ'};
  const key=crypto.randomUUID();
  confirm.onclick=async()=>{
    if(cancelled||generation!==chatGeneration)return;
    confirm.disabled=cancel.disabled=true;
    try{
      const result=await api('confirm',{draft_id:draft.draft_id,idempotency_key:key,confirmed:true});
      if(deleting){
        // Remove previous health snippets/actions from this browser's chat too.
        resetChat();chatBubble('assistant','ลบข้อมูลที่ยืนยันแล้ว '+result.count+' รายการครับ');
        $('#journalText').value='';$('#journalResults').replaceChildren();pending=null;editRecord=null;window.dispatchEvent(new Event('records-deleted'));
      }else{status.textContent='แก้ไขข้อมูลแล้วครับ';chatHistory=[];window.dispatchEvent(new CustomEvent('records-confirmed',{detail:{draftId:draft.draft_id}}))}
      await refresh();
    }catch(error){status.textContent=error.message;confirm.disabled=false;cancel.disabled=false}
  };
  card.append(confirm,cancel,status);chatScroll();
}
