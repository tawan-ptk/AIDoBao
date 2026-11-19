const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const names={meal:'อาหาร',activity:'การเคลื่อนไหว',sleep:'การนอน',medication:'ยา',appointment:'นัดหมาย',measurement:'ค่าตรวจสุขภาพ',wellbeing:'ความเป็นอยู่',profile:'โปรไฟล์',constraint:'เวลาที่ล็อก',routine:'รายการในแผน',consent:'ความยินยอม',feedback:'ผลตอบรับ'};
const labels={name:'ชื่อรายการ',quantity:'ปริมาณ',unit:'หน่วย',occurred_at:'วันและเวลา',food_state:'สถานะอาหาร',start:'เริ่ม',end:'สิ้นสุด',method:'วิธีวัดหรือรายงาน',episode:'การนอนหลักหรืองีบ',dose:'ขนาดตามคำสั่ง',instruction_source:'แหล่งคำสั่งใช้ยา',state:'สถานะ',value:'ค่า',context:'บริบท',note:'ความรู้สึกหรืออุปสรรค',age:'อายุ',timezone:'เขตเวลา',goals:'เป้าหมาย',preferences:'ความชอบ',allergies:'การแพ้อาหาร',mobility_limits:'ข้อจำกัดการเคลื่อนไหว',reported_type2:'รายงานเบาหวานชนิดที่ 2',pregnant:'ตั้งครรภ์',complex_care:'ต้องดูแลเฉพาะ',local_storage:'ยินยอมเก็บในเครื่อง',label:'รายการ',domain:'ด้าน',dates:'วันที่',earliest:'เวลาเริ่มเร็วที่สุด',latest:'เวลาเริ่มช้าที่สุด',duration_minutes:'ระยะเวลา (นาที)',fixed:'ล็อกเวลา',goal:'เป้าหมาย',meal_relation:'เงื่อนไขกับมื้ออาหาร',weight_kg:'น้ำหนัก (กก.)',height_cm:'ส่วนสูง (ซม.)',conditions:'โรคประจำตัว',medications:'ยาที่ใช้',prohibited_catalog_ids:'รายการที่ไม่ต้องการ'};
const specs={meal:{name:'text',quantity:'number',unit:'text',occurred_at:'datetime-local',food_state:['raw|ดิบ','cooked|สุก','packaged|ผลิตภัณฑ์','unknown|ยังไม่ทราบ']},activity:{name:'text',start:'datetime-local',end:'datetime-local',method:['self_report|ผู้ใช้รายงาน','device_estimate|อุปกรณ์ประมาณ']},sleep:{start:'datetime-local',end:'datetime-local',method:['time_in_bed|เวลาบนเตียง','self_report_sleep|เวลาหลับที่รายงาน','device_estimate|อุปกรณ์ประมาณ'],episode:['main|การนอนหลัก','nap|งีบ']},medication:{name:'text',dose:'number',unit:'text',occurred_at:'datetime-local',instruction_source:'text',state:['reported_taken|รายงานว่าใช้แล้ว','reminder_due|ถึงเวลาเตือน','acknowledged|รับทราบการเตือน','unknown|ไม่ทราบ']},measurement:{name:['weight|น้ำหนัก','height|ส่วนสูง','waist|รอบเอว','glucose|น้ำตาล','hba1c|HbA1c','systolic|ความดันตัวบน','diastolic|ความดันตัวล่าง'],value:'number',unit:'text',occurred_at:'datetime-local',context:['unknown|ยังไม่ทราบ','fasting|อดอาหาร','before-meal|ก่อนมื้อ','after-meal|หลังมื้อ','routine|ตรวจทั่วไป'],method:['self_report|ผู้ใช้รายงาน','fingerstick|ปลายนิ้ว','laboratory|ห้องปฏิบัติการ','sensor|เซนเซอร์','scale|เครื่องชั่ง','tape|สายวัด','cuff|เครื่องวัดความดัน']},wellbeing:{note:'text',occurred_at:'datetime-local'},appointment:{name:'text',start:'datetime-local',end:'datetime-local'}};
let csrf='', pending=null, revision=0, currentProfile=null, offset=0, editRecord=null;
window.addEventListener('records-deleted',()=>{currentProfile=null;pending=null;editRecord=null;$('#profileForm').reset();$('#recordForm').reset();$('#review').close();$('#reviewBody').replaceChildren();$('#planResult').replaceChildren();$('#routineForm').reset()});
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e}
function notice(s){$('#notice').textContent=s||''}
async function api(path,body){const r=await fetch('/api/'+path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','x-csrf-token':csrf},body:body===undefined?undefined:JSON.stringify(body)});const x=await r.json();if(!r.ok)throw new Error(typeof x.detail==='string'?x.detail:JSON.stringify(x.detail));return x}
function energyAmount(kcal){return kcal?Number(kcal[0]).toLocaleString('th-TH',{maximumFractionDigits:1})+(kcal[0]===kcal[1]?'':'–'+Number(kcal[1]).toLocaleString('th-TH',{maximumFractionDigits:1}))+' kcal':''}
function renderEnergy(target,energy){
  target.replaceChildren();if(!energy)return;
  target.className='meal-energy';
  target.append(el('strong',energy.kcal?'ประมาณ '+energyAmount(energy.kcal)+' · '+(energy.components?'รวมมื้อนี้':energy.quantity+' '+energy.unit):'ยังประเมินแคลอรีไม่ได้'));
  if(energy.components){
    for(const part of energy.components){const row=el('div');renderEnergy(row,part);row.classList.add('meal-energy-component');const title=row.querySelector('strong');title.textContent=part.name+' · '+title.textContent;target.append(row)}
    target.append(el('p',energy.note,'muted'));return;
  }
  if(energy.assumption)target.append(el('p',energy.assumption,'muted'));
  if(!energy.kcal){target.append(el('p',energy.note,'muted'));if(energy.reference?.serving)target.append(el('p','หน่วยอ้างอิง: '+energy.reference.serving.quantity+' '+energy.reference.serving.unit+' · '+energy.reference.basis,'muted'));else if(energy.status==='unknown_food')target.append(el('p','ลองพิมพ์ชื่ออาหารในช่องชื่อเพื่อดูรายการที่มีข้อมูลอ้างอิง เลือกให้ตรงกับสิ่งที่กินครับ','muted'));return}
  const details=el('details');details.append(el('summary','หน่วยเสิร์ฟและแหล่งอ้างอิง'),el('p',energy.reference.basis),el('p',energy.note,'muted'));
  const link=el('a',(energy.reference.publisher||'แหล่งข้อมูล')+' ↗');
  try{const url=new URL(energy.reference.url);if(url.protocol==='https:'){link.href=url.href;link.target='_blank';link.rel='noopener noreferrer'}}catch{}
  details.append(link);target.append(details);
  for(const source of energy.reference.additional_sources||[]){try{const url=new URL(source.url);if(url.protocol==='https:'){const extra=el('a',(source.publisher||'แหล่งอ้างอิงเพิ่มเติม')+' ↗');extra.href=url.href;extra.target='_blank';extra.rel='noopener noreferrer';details.append(extra)}}catch{}}
}
let foodCatalogRequest=null;
async function attachFoodNames(input){
  if(!input||input.getAttribute('list'))return;
  if(!foodCatalogRequest)foodCatalogRequest=api('food-catalog').catch(()=>{foodCatalogRequest=null;return {items:[]}});
  const result=await foodCatalogRequest;
  if(!input.isConnected)return;
  let list=document.getElementById('food-reference-names');
  if(!list){list=el('datalist');list.id='food-reference-names';for(const food of result.items||[]){const option=el('option');option.value=food.name;option.label=food.basis;list.append(option)}document.body.append(list)}
  input.setAttribute('list',list.id);input.autocomplete='off';
}
function attachMealEnergy(target,read,events,initial){
  let sequence=0,timer;renderEnergy(target,initial);attachFoodNames(events.querySelector('[name="name"]'));
  const update=()=>{
    const current=++sequence;clearTimeout(timer);const record=read();
    if(record.kind!=='meal'||!record.data.name?.trim()){target.replaceChildren();return}
    // Clear stale numbers immediately when the name/amount changes.
    target.replaceChildren(el('p','กำลังตรวจแคลอรีโดยประมาณ…','muted'));
    timer=setTimeout(async()=>{
      if(!target.isConnected)return;
      try{const energy=await api('food-energy',{name:record.data.name.trim(),quantity:record.data.quantity??null,unit:record.data.unit||null,food_state:record.data.food_state||null,...(record.data.components?{components:record.data.components}:{})});if(current===sequence)renderEnergy(target,energy)}
      catch{if(current===sequence)target.replaceChildren(el('p','ยังตรวจแคลอรีไม่ได้ กรุณาตรวจชื่อ ปริมาณ และหน่วย','muted'))}
    },300);
  };
  events.addEventListener('input',update);events.addEventListener('change',update);
  if(!initial&&read().data.name)update();
}
function safely(fn){return async e=>{if(e)e.preventDefault();try{notice('');await fn(e)}catch(err){notice(err.message)}}}
function page(id){$$('.page').forEach(e=>e.classList.toggle('hidden',e.id!==id));$$('nav button').forEach(e=>e.classList.toggle('active',e.dataset.page===id));window.scrollTo(0,0)}
$$('[data-page]').forEach(b=>b.onclick=()=>page(b.dataset.page));
function valText(v){if(v===null||v==='')return 'ยังไม่ทราบ';if(typeof v==='boolean')return v?'ใช่':'ไม่ใช่';if(Array.isArray(v))return v.join('\n')||'ยังไม่ระบุ';return names[v]||String(v)}
function fieldsView(d){const dl=el('dl');Object.entries(d).forEach(([k,v])=>{dl.append(el('dt',k==='components'?'อาหารในมื้อนี้':labels[k]||k),el('dd',k==='components'?v.map(p=>p.name+(p.quantity!=null?' · '+p.quantity+' '+(p.unit||'ยังไม่ระบุหน่วย'):' · ยังไม่ระบุปริมาณ')).join('\n'):valText(v)))});return dl}
function checkView(check){const box=el('div');box.append(el('span',check.status==='pass'?'ข้อมูลครบตามรูปแบบ':check.status==='unknown'?(check.can_record?'เก็บข้อความได้ รายละเอียดเติมภายหลัง':'ต้องเติมข้อมูล'):'พบข้อมูลที่ต้องแก้','tag '+(check.status==='pass'?'':'warn')));for(const k of check.missing||[])box.append(el('p','รายละเอียดที่ยังไม่ทราบ: '+(labels[k]||k)));for(const e of check.errors||[])box.append(el('p',e,'fail'));if(check.calculated?.interval_minutes)box.append(el('p',(check.calculated.label||'ระยะเวลา')+': '+check.calculated.interval_minutes+' นาที'));box.append(el('p','ตรวจรูปแบบด้วยโปรแกรมแล้ว ความเหมาะสมทางสุขภาพยังไม่ได้รับการตรวจ','muted'));return box}
async function preview(record){const r=await api('records/preview',record);pending={draft_id:r.draft_id,idempotency_key:crypto.randomUUID(),confirmed:true};const box=$('#reviewBody');box.replaceChildren(fieldsView(record.data),checkView(r.check));if(r.check.calculated?.energy){const energy=el('div');renderEnergy(energy,r.check.calculated.energy);box.append(energy)}$('#confirmReview').disabled=!r.can_confirm;$('#review').showModal()}
$('#cancelReview').onclick=()=>$('#review').close();$('#confirmReview').onclick=safely(async()=>{const b=$('#confirmReview');b.disabled=true;try{await api('confirm',pending);window.dispatchEvent(new CustomEvent('records-confirmed',{detail:{draftId:pending.draft_id}}));$('#review').close();editRecord=null;notice('บันทึกข้อมูลที่คุณยืนยันแล้ว');await refresh()}finally{b.disabled=false}});
$('#consent').onclick=safely(()=>preview({kind:'consent',data:{local_storage:true},source:'ผู้ใช้ยินยอมเก็บข้อมูลในเครื่อง',origin:'self_report'}));
const lines=s=>s.split('\n').map(x=>x.trim()).filter(Boolean);
$('#profileForm').onsubmit=safely(async e=>{const f=new FormData(e.target),split=s=>String(s||'').split(/[,\n]/).map(x=>x.trim()).filter(Boolean);if(f.has('no_allergies')&&split(f.get('allergies')).length)throw new Error('เลือกยืนยันว่าไม่มีการแพ้ หรือกรอกรายการแพ้ อย่างใดอย่างหนึ่ง');const data={...(currentProfile?.data||{}),age:f.get('age')?Number(f.get('age')):null,weight_kg:f.get('weight_kg')?Number(f.get('weight_kg')):null,height_cm:f.get('height_cm')?Number(f.get('height_cm')):null,timezone:f.get('timezone')||'Asia/Bangkok',reported_type2:f.has('reported_type2')?true:null,pregnant:f.has('pregnant'),complex_care:f.has('complex_care'),conditions:split(f.get('conditions')),medications:split(f.get('medications')),goals:split(f.get('goals')),preferences:split(f.get('preferences')),allergies:f.has('no_allergies')?[]:split(f.get('allergies')).length?split(f.get('allergies')):null,mobility_limits:split(f.get('mobility_limits'))};await reviewBatch([{kind:'profile',data,source:'ผู้ใช้กรอกและตรวจโปรไฟล์',previous_id:currentProfile?.id||null}])});
function buildFields(){const box=$('#recordFields');box.replaceChildren();for(const [k,spec]of Object.entries(specs[$('#recordKind').value])){const l=el('label',labels[k]);let inp;if(Array.isArray(spec)){inp=el('select');inp.append(new Option('เลือกหรือเว้นไว้เมื่อยังไม่ทราบ',''));spec.forEach(s=>{const [v,t]=s.split('|');inp.append(new Option(t,v))})}else{inp=el('input');inp.type=spec;if(spec==='number'){inp.step='any';inp.min='0'}}inp.name=k;l.append(inp);box.append(l)}if($('#recordKind').value==='meal'){const target=el('div');box.append(target);attachMealEnergy(target,()=>{const f=$('#recordForm').elements;return {kind:'meal',data:{name:f.namedItem('name').value,quantity:f.namedItem('quantity').value?Number(f.namedItem('quantity').value):null,unit:f.namedItem('unit').value,food_state:f.namedItem('food_state').value}}},box)}}
function categoryHint(){const suggest=/^เดิน(?:\s|$)/.test($('#freeText').value.trim())&&$('#recordKind').value!=='activity';$('#categoryHint').classList.toggle('hidden',!suggest)}
$('#freeText').oninput=categoryHint;
$('#useActivity').onclick=()=>{$('#recordKind').value='activity';editRecord=null;buildFields();categoryHint();notice('เปลี่ยนเป็นกิจกรรมแล้ว กดให้โมเดลแยกข้อมูลอีกครั้งได้')};
$('#recordKind').onchange=()=>{editRecord=null;buildFields();categoryHint()};buildFields();
function localISO(s){return s?new Date(s).toISOString():null}
$('#recordForm').onsubmit=safely(async e=>{const f=new FormData(e.target),kind=$('#recordKind').value,data={};for(const[k,s]of Object.entries(specs[kind])){const v=f.get(k);data[k]=!v?null:s==='number'?Number(v):s==='datetime-local'?localISO(v):v}await preview({kind,text:data.name||data.note||'',data,source:$('#recordSource').value,origin:$('#recordOrigin').value,previous_id:editRecord?.id||null})});
$('#extract').onclick=safely(async()=>{
  const button=$('#extract'),kind=$('#recordKind').value,text=$('#freeText').value;
  if(!text.trim()){notice('กรุณาพิมพ์ข้อความที่ต้องการบันทึกก่อน');return}
  button.disabled=true;notice('กำลังให้โมเดลในเครื่องอ่านข้อความ…');
  try{
    const r=await api('extract',{kind,text});
    if(kind!==$('#recordKind').value||text!==$('#freeText').value){notice('ข้อความหรือประเภทบันทึกเปลี่ยนแล้ว กรุณากดแยกข้อมูลอีกครั้ง');return}
    if(r.model_status==='invalid_model_output'||r.metrics?.extraction_status==='invalid_model_output'){
      notice('โมเดลยังแยกข้อความนี้เป็นช่องข้อมูลไม่ได้ ช่องที่คุณกรอกไว้ยังอยู่ กรุณากรอกเองหรือเขียนให้ชัดเจนแล้วลองใหม่ ยังไม่มีการบันทึก');return
    }
    let filled=0;const unavailable=[];
    for(const[k,v]of Object.entries(r.record.data)){
      const inp=$('#recordForm').elements.namedItem(k);
      if(!inp||v==null)continue;
      let value=String(v);
      if(inp.type==='datetime-local'){
        const dt=new Date(v);if(isNaN(dt)){unavailable.push(labels[k]||k);continue}
        value=new Date(dt.getTime()-dt.getTimezoneOffset()*60000).toISOString().slice(0,16);
      }
      if(inp.tagName==='SELECT'&&![...inp.options].some(o=>o.value===value)){unavailable.push(labels[k]||k);continue}
      inp.value=value;if(inp.value===value)filled++;else unavailable.push(labels[k]||k);
    }
    $('#recordFields').dispatchEvent(new Event('input',{bubbles:true}));
    if(!filled){notice('ยังไม่พบข้อมูลสำหรับประเภท '+names[kind]+' กรุณาตรวจว่าประเภทตรงกับข้อความ แล้วเลือกประเภทใหม่หรือกรอกข้อมูลด้านล่าง ยังไม่มีการบันทึก');return}
    const missing=[...new Set([...(r.check?.missing||[]).map(k=>labels[k]||k),...unavailable])];
    notice('โมเดลเติมข้อมูลให้ '+filled+' ช่อง กรุณาตรวจและแก้ไขก่อนบันทึก'+(missing.length?' · ต้องตรวจเพิ่ม: '+missing.join(', '):'')+(r.check?.errors?.length?' · '+r.check.errors.join(' · '):''));
    if(kind==='activity'&&!r.record.data.start)notice($('#notice').textContent+' · เวลาอย่าง 16.00 ยังขาดวันที่ กรุณาระบุวันที่ เวลาเริ่มและสิ้นสุด โดยระบบจะไม่เดาว่าเป็นวันนี้');
    $('#recordFields').scrollIntoView({behavior:'smooth',block:'nearest'});
  }finally{button.disabled=false}
});
Object.entries(names).filter(([k])=>Object.hasOwn(specs,k)).forEach(([k,v])=>$('#routineDomain').append(new Option(v,k)));
$('#constraintForm').onsubmit=safely(async e=>{const f=new FormData(e.target);await preview({kind:'constraint',data:{label:f.get('label'),start:localISO(f.get('start')),end:localISO(f.get('end'))},source:'ผู้ใช้ยืนยันช่วงเวลาที่เปลี่ยนไม่ได้'})});
$('#routineForm').onsubmit=safely(async e=>{const f=new FormData(e.target);const dates=[];for(let i=0;i<Number(f.get('days'));i++){const d=new Date(f.get('first_date')+'T00:00:00Z');d.setUTCDate(d.getUTCDate()+i);dates.push(d.toISOString().slice(0,10))}await preview({kind:'routine',source:'กิจกรรมและเป้าหมายที่ผู้ใช้เลือก',data:{domain:f.get('domain'),label:f.get('label'),goal:f.get('goal')||f.get('label'),dates,earliest:f.get('earliest'),latest:f.get('latest'),duration_minutes:Number(f.get('duration_minutes')),fixed:f.has('fixed'),instruction_source:f.get('instruction_source')||null,meal_relation:f.get('meal_relation')}})});
function renderPlan(p,target){target.replaceChildren();const a=el('article');a.append(el('h2',p.status==='pass'?'จัดเวลาได้ — รอคุณตรวจและยืนยัน':p.status==='infeasible'?'ยังจัดเวลาไม่ได้':'ต้องตรวจข้อมูลเพิ่ม'),el('p','ช่วง '+p.start_date+' ถึง '+p.end_date+' (ไม่รวมวันสิ้นสุด)'));for(const m of p.missing||[])a.append(el('p',m,'warn'));Object.entries(p.readiness||{}).forEach(([k,v])=>a.append(el('span',names[k]+': '+v,'tag')));for(const x of p.items){const row=el('div',undefined,'row');row.append(el('strong',x.label),el('p',names[x.domain]+' · '+new Date(x.start).toLocaleString('th-TH')+' · '+x.duration_minutes+' นาที'),el('small','เป้าหมาย: '+x.goal+' | ผ่านการตรวจเวลา | ความเหมาะสมทางสุขภาพ: ยังไม่ตรวจ'));a.append(row)}a.append(el('p','ระบบไม่รับรองความเหมาะสมทางสุขภาพและไม่กำหนดการรักษา แผนนี้จัดจากรายการที่คุณยืนยันเท่านั้น','muted'));target.append(a)}
$('#planForm').onsubmit=safely(async()=>{const r=await api('plans/preview',{start_date:$('#planStart').value,previous_plan_id:$('#previousPlan').value||null,reason:$('#planReason').value,general_time_only:true});renderPlan(r.plan,$('#planResult'));if(r.comparison){const a=el('article');a.append(el('h2','ก่อนและหลังปรับ'),el('p','เหตุผล: '+r.comparison.reason));for(const c of r.comparison.changes)a.append(el('p',(c.before?.label||c.after?.label)+': '+(c.before?.start||'ไม่มี')+' → '+(c.after?.start||'ยังจัดไม่ได้')));if(!r.comparison.changes.length)a.append(el('p','รายการและเวลาไม่เปลี่ยน'));$('#planResult').append(a)}if(r.can_confirm){const b=el('button','ตรวจและยืนยันแผนนี้','primary');b.onclick=()=>{pending={draft_id:r.draft_id,idempotency_key:crypto.randomUUID(),confirmed:true};renderPlan(r.plan,$('#reviewBody'));$('#confirmReview').disabled=false;$('#review').showModal()};$('#planResult').append(b)}});
$('#questionForm').onsubmit=safely(async()=>{const r=await api('knowledge',{query:$('#question').value});const box=$('#answers');box.replaceChildren(el('p',r.answer));for(const c of r.citations){const a=el('article'),link=el('a',c.publisher+' · '+c.heading);link.href=c.url;link.target='_blank';link.rel='noopener noreferrer';a.append(link,el('p',c.location+' · เข้าถึง '+c.accessed_at,'muted'),el('div',c.text,'evidence'));box.append(a)}});
async function loadRecords(reset=true){if(reset){offset=0;$('#records').replaceChildren()}const r=await api('records?limit=30&offset='+offset);revision=r.revision;for(const item of r.items){if(!specs[item.kind])continue;const row=el('div',undefined,'row');row.append(el('strong',names[item.kind]));if(item.journal){row.append(el('p',item.text),el('small',journalTimeLabel(item)+' · เวอร์ชัน '+item.version))}else row.append(fieldsView(item.data),el('small','ยืนยันแล้ว · เวอร์ชัน '+item.version));if(r.meal_energy?.[item.id]){const energy=el('div');renderEnergy(energy,r.meal_energy[item.id]);row.append(energy)}const b=el('button','แก้เป็นเวอร์ชันใหม่');b.onclick=()=>{if(item.journal){editJournalRecord(item);return}editRecord=item;$('#recordKind').value=item.kind;buildFields();for(const[k,v]of Object.entries(item.data)){const inp=$('#recordForm').elements[k];if(!inp)continue;if(inp.type==='datetime-local'&&v){const dt=new Date(v);inp.value=new Date(dt.getTime()-dt.getTimezoneOffset()*60000).toISOString().slice(0,16)}else inp.value=v??''}$('#recordFields').dispatchEvent(new Event('input',{bubbles:true}));$('#freeText').value=item.text||'';$('#recordSource').value=item.source;notice('กำลังแก้บันทึกเวอร์ชัน '+item.version+' ประวัติเดิมจะยังอยู่')};row.append(b);$('#records').append(row)}offset+=r.items.length;$('#moreRecords').disabled=r.items.length<30}
$('#moreRecords').onclick=safely(()=>loadRecords(false));
async function refresh(){const s=await api('summary');$('#domainCards').replaceChildren();for(const[k,v]of Object.entries(s.counts)){const a=el('article');a.append(el('h3',names[k]),el('div',v,'count'),el('small','บันทึกที่ยืนยันแล้ว'));$('#domainCards').append(a)}$('#summary').replaceChildren();if(s.energy_summary){const energy=s.energy_summary,a=el('article',undefined,'daily-energy');a.append(el('h3','แคลอรีวันนี้โดยประมาณ'),el('strong',energy.kcal?energyAmount(energy.kcal):energy.meal_count?'ยังประเมินไม่ได้':'ยังไม่มีบันทึกอาหาร'));if(energy.unknown_count)a.append(el('p',energy.unknown_count+' มื้อยังประเมินไม่ครบ รวมเฉพาะอาหารที่มีข้อมูล','muted'));if(energy.assumed_portion_count)a.append(el('p',energy.assumed_portion_count+' รายการใช้ปริมาณเสิร์ฟอ้างอิง เพราะยังไม่ระบุปริมาณ','muted'));a.append(el('small','สูตรและขนาดเสิร์ฟทำให้พลังงานต่างกัน'));const b=el('button','ดูรายละเอียดแคลอรีวันนี้');b.type='button';b.onclick=()=>sendAgentPrompt('วันนี้รวมกี่แคล');a.append(b);$('#summary').append(a)}if(!s.activity_sleep.length)$('#summary').append(el('p','ยังไม่มีช่วงเวลาเริ่ม–สิ้นสุดที่พร้อมสรุประยะเวลา','empty'));if(s.incomplete_records)$('#summary').append(el('p','มี '+s.incomplete_records+' รายการที่กลับมาเติมรายละเอียดภายหลังได้','muted'));for(const g of s.activity_sleep)$('#summary').append(el('p',names[g.domain]+' · '+(g.method==='time_in_bed'?'เวลาบนเตียง':g.method)+' · '+g.minutes+' นาที'));for(const g of s.measurements)$('#summary').append(el('p',(labels[g.name]||g.name)+' ('+g.unit+', '+g.context+', '+g.method+'): '+g.observations.map(x=>x.value).join(' → ')));await loadRecords();let all=[],off=0;while(true){const r=await api('records?limit=500&offset='+off);all.push(...r.items);if(r.items.length<500)break;off+=500}const profiles=all.filter(x=>x.kind==='profile');currentProfile=profiles.at(-1)||null;$('#goalSelect').replaceChildren(new Option('เลือกเป้าหมาย',''));(currentProfile?.data.goals||[]).forEach(g=>$('#goalSelect').append(new Option(g,g)));$('#profileForm').elements.no_allergies.checked=Array.isArray(currentProfile?.data.allergies)&&currentProfile.data.allergies.length===0;if(currentProfile)for(const[k,v]of Object.entries(currentProfile.data)){const inp=$('#profileForm').elements[k];if(!inp)continue;if(inp.type==='checkbox')inp.checked=v;else inp.value=Array.isArray(v)?v.join(inp.tagName==='INPUT'?', ':'\n'):v??''}$('#routines').replaceChildren();for(const r of all.filter(x=>['routine','constraint'].includes(x.kind))){const row=el('div',undefined,'row');row.append(el('strong',names[r.kind]),fieldsView(r.data));const b=el('button','แก้เวลาหรือรายละเอียด');b.onclick=()=>{const box=$('#reviewBody');box.replaceChildren();const form=el('form');for(const[k,v]of Object.entries(r.data)){const l=el('label',labels[k]||k),i=el('input');i.name=k;i.value=Array.isArray(v)?v.join(','):v??'';l.append(i);form.append(l)}const save=el('button','ตรวจการแก้ไข','primary');form.append(save);form.onsubmit=safely(async e=>{const fd=new FormData(e.target),data={};for(const[k,v]of Object.entries(r.data)){const n=fd.get(k);data[k]=Array.isArray(v)?n.split(',').map(x=>x.trim()):typeof v==='boolean'?n==='true':typeof v==='number'?Number(n):n||null}$('#review').close();await preview({...r,id:undefined,version:undefined,created_at:undefined,status:undefined,data,previous_id:r.id})});box.append(form);$('#confirmReview').disabled=true;$('#review').showModal()};row.append(b);$('#routines').append(row)}const ps=await api('plans');$('#planHistory').replaceChildren();$('#previousPlan').replaceChildren(new Option('สร้างแผนใหม่',''));for(const p of ps.items){$('#previousPlan').append(new Option('เวอร์ชัน '+p.version+' · '+p.start_date,p.id));const row=el('div',undefined,'row');row.append(el('strong','เวอร์ชัน '+p.version+' · '+p.start_date),el('p',p.requires_revalidation?'มีข้อมูลใหม่ ต้องตรวจแผนอีกครั้ง':'ยืนยันแล้วจากข้อมูลเวอร์ชัน '+p.input_revision));const b=el('button','ดูและตรวจด้วยข้อมูลล่าสุด');b.onclick=safely(async()=>{const x=await api('plans/'+p.id+'/recheck');renderPlan(x.current_check,$('#planResult'));$('#previousPlan').value=p.id;$('#planStart').value=p.start_date});row.append(b);$('#planHistory').append(row)}}
$('#export').onclick=safely(async()=>{const data=await api('export'),url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),a=el('a');a.href=url;a.download='routine-my-data.json';a.click();URL.revokeObjectURL(url)});
$('#delete').onclick=safely(async()=>{await api('delete',{confirmation:$('#deleteText').value});$('#deleteText').value='';await refresh();notice('ลบข้อมูลของเซสชันนี้จากฐานข้อมูลแล้ว ไฟล์ที่คุณเคยส่งออกต้องลบแยก')});
safely(async()=>{const s=await api('session');csrf=s.csrf;$('#sessionNote').textContent=s.note;$('#dateLabel').textContent=new Date().toLocaleDateString('th-TH',{dateStyle:'long'});await refresh()})();

// Shared review: nothing is written until the existing confirmation button.
async function reviewBatch(records,compact=false,onDraft=null){
  const r=await api('records/batch-preview',{records,compact});
  const body=$('#reviewBody');body.replaceChildren(el('p','ตรวจ '+r.records.length+' รายการก่อนเก็บ ข้อมูลที่ไม่ทราบเว้นไว้ได้'));
  const setPending=result=>{pending={draft_id:result.draft_id,idempotency_key:crypto.randomUUID(),confirmed:true};$('#confirmReview').disabled=!result.can_confirm||!!result.requires_consent;onDraft?.(result)};
  setPending(r);
  for(const [index,record]of r.records.entries()){
    const card=el('article');card.append(el('h3',names[record.kind]||record.kind));
    if(record.journal){card.append(el('p',record.text),el('p',journalTimeLabel(record),'tag'));const details=el('details');details.append(el('summary','ดูรายละเอียดที่แยกช่อง'),fieldsView(record.data));card.append(details)}
    else card.append(fieldsView(record.data));
    if(r.checks[index].calculated?.energy){const energy=el('div');renderEnergy(energy,r.checks[index].calculated.energy);card.append(energy)}
    for(const message of r.checks[index].errors||[])card.append(el('p',message,'fail'));
    body.append(card);
  }
  if(r.requires_consent){
    const label=el('label','ฉันยินยอมให้เก็บรายการที่ยืนยันในเครื่องนี้ ไม่ใช้ฝึก AI อัตโนมัติ','check'),box=el('input');box.type='checkbox';label.prepend(box);body.append(label);let attempt=0;
    box.onchange=safely(async()=>{const token=++attempt;$('#confirmReview').disabled=true;if(!box.checked){setPending(r);return}const consent={kind:'consent',data:{local_storage:true},source:'ผู้ใช้เลือกยินยอมก่อนยืนยันข้อมูลในเครื่อง'};const next=await api('records/batch-preview',{records:[consent,...records],compact});if(token===attempt&&box.checked)setPending(next)});
  }
  $('#review').showModal();return r;
}
