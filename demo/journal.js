// Journal capture uses Bangkok calendar dates, independent of the Mac timezone.
const periodNames={unspecified:'ยังไม่ระบุช่วงเวลา',morning:'ตอนเช้า',noon:'ตอนเที่ยง',afternoon:'ตอนบ่าย',evening:'ตอนเย็น',night:'ตอนกลางคืน'};
let journalCapturedAt=null,journalCards=[],journalRevision=0;
let journalConfirmation=null;
window.addEventListener('records-deleted',()=>{journalCapturedAt=null;journalCards=[];journalConfirmation=null;journalRevision++;$('#journalText').value='';$('#journalResults').replaceChildren();updateCaptureNote()});
window.addEventListener('records-confirmed',event=>{
  if(event.detail.draftId!==journalConfirmation?.draftId)return;
  $('#journalResults').replaceChildren();journalCards=[];
  if(!journalConfirmation.editing&&journalRevision===journalConfirmation.inputRevision){$('#journalText').value='';journalCapturedAt=null;journalRevision++;updateCaptureNote()}
  journalConfirmation=null;
});
function bangkokDate(stamp){const parts=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Bangkok',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(stamp)).map(p=>[p.type,p.value]));return parts.year+'-'+parts.month+'-'+parts.day}
function journalTimeLabel(r){const j=r.journal;if(!j)return '';return j.date+' · '+(j.clock?j.clock.slice(0,5)+' น.':periodNames[j.period])+(j.clock_source==='capture_time'?' (เวลาที่พิมพ์)':'')+' · เวลาไทย'}
function updateCaptureNote(){const stamp=journalCapturedAt||new Date().toISOString();$('#journalDateNote').textContent='วันที่บันทึก '+bangkokDate(stamp)+' · เวลาไทย · ทุกครั้งต้องตรวจและยืนยันก่อนเก็บ'}
$('#journalText').oninput=()=>{if(!journalCapturedAt&&$('#journalText').value.trim())journalCapturedAt=new Date().toISOString();if(!$('#journalText').value.trim())journalCapturedAt=null;journalRevision++;updateCaptureNote();if(journalCards.length)notice('ข้อความเปลี่ยนแล้ว กดแยกและตรวจรายการอีกครั้งเพื่อใช้ข้อความล่าสุด')};
function journalInput(label,type,value){const l=el('label',label),i=el('input');i.type=type;i.value=value??'';l.append(i);return {label:l,input:i}}
function journalSelect(label,options,value){const l=el('label',label),i=el('select');for(const[k,v]of Object.entries(options))i.append(new Option(v,k));i.value=value??'';l.append(i);return {label:l,input:i}}
function renderJournal(response,editing=false){
  const box=$('#journalResults');box.replaceChildren();journalCards=[];
  const title=el('article');title.append(el('h2',editing?'เติมเวลาและแก้รายละเอียด':'ตรวจรายการก่อนบันทึก'),el('p','เลือกเฉพาะรายการที่ต้องการเก็บ แก้หมวดได้ และเว้นเวลาเป๊ะไว้เติมภายหลังได้'));box.append(title);
  if(response.model_note)title.append(el('p',response.model_note,'muted'));
  const all=[...response.items,...response.unparsed.map(x=>({source_index:x.source_index,record:{kind:'',text:x.text,data:{},evidence:{},source:'ผู้ใช้เล่า; ต้องเลือกหมวดเอง',origin:'self_report',journal:x.journal||{date:response.default_date,timezone:'Asia/Bangkok',period:'unspecified',clock:null,date_source:'capture_date',captured_at:response.captured_at}},check:{missing:[]},warnings:[x.reason]}))].sort((a,b)=>(a.source_index??0)-(b.source_index??0));
  for(const item of all){
    const record=structuredClone(item.record),card=el('article',undefined,'journal-card');
    if(record.journal.clock_source==='capture_time')card.append(el('p','ไม่ได้ระบุเวลา จึงใช้เวลาที่พิมพ์ '+record.journal.clock.slice(0,5)+' น. แก้ไขได้','muted'));
    const include=el('input');include.type='checkbox';include.checked=true;const selectLabel=el('label','เก็บรายการนี้','check');selectLabel.prepend(include);card.append(selectLabel,el('p',record.text,'journal-original'));
    const kind=journalSelect('หมวด',{'':'เลือกหมวด',...Object.fromEntries(Object.keys(specs).map(k=>[k,names[k]]))},record.kind);card.append(kind.label);const primaryFields=el('div');card.append(primaryFields);
    for(const warning of item.warnings||[])card.append(el('p',warning,'tag warn'));
    if(record.journal.context_text)card.append(el('p','ช่วงเวลา/วันที่ตามข้อความก่อนหน้า: '+record.journal.context_text+' · แก้ได้ด้านล่าง','muted'));
    const timeRow=el('div',undefined,'grid');
    const period=journalSelect('ช่วงเวลา',periodNames,record.journal.period),clock=journalInput('เวลาเป๊ะ (เว้นไว้ได้)','time',record.journal.clock?.slice(0,5));timeRow.append(period.label,clock.label);card.append(timeRow);
    const detail=el('details'),summary=el('summary','แก้วันที่ เวลาสิ้นสุด และรายละเอียดเพิ่มเติม');detail.append(summary);
    const day=journalInput('วันที่','date',record.journal.date),end=journalInput('เวลาสิ้นสุด (ถ้าทราบ)','time',record.data.end?.slice(11,16));
    const nextDay=el('input');nextDay.type='checkbox';nextDay.checked=!!record.data.end&&record.data.end.slice(0,10)!==record.journal.date;
    const nextLabel=el('label','สิ้นสุดในวันถัดไป','check');nextLabel.prepend(nextDay);
    detail.append(day.label,end.label,nextLabel);
    const dataBox=el('div');detail.append(dataBox);card.append(detail);
    let inputs={},componentInputs=[];
    function readComponents(){return componentInputs.map(fields=>Object.fromEntries(Object.entries(fields).map(([key,input])=>[key,input.value===''?null:key==='quantity'?Number(input.value):input.value])))}
    function readData(){
      const data=Object.fromEntries(Object.entries(inputs).map(([key,{input,type}])=>[key,input.value===''?null:type==='number'?Number(input.value):input.value]));
      if(componentInputs.length){data.components=readComponents();data.name=data.components.map(p=>p.name||'').join(' กับ ')}
      return data;
    }
    function rebuildFields(){
      dataBox.replaceChildren();primaryFields.replaceChildren();inputs={};componentInputs=[];
      const composite=kind.input.value==='meal'&&record.kind==='meal'&&record.data.components?.length>1;
      for(const[k,spec]of Object.entries(specs[kind.input.value]||{})){
        if(['start','end','occurred_at'].includes(k))continue;
        if(composite&&['name','quantity','unit'].includes(k))continue;
        if(composite&&k==='food_state')continue;
        let field;
        if(Array.isArray(spec))field=journalSelect(labels[k],{'':'ยังไม่ทราบ',...Object.fromEntries(spec.map(x=>x.split('|')))},record.kind===kind.input.value?record.data[k]:'');
        else field=journalInput(labels[k],spec,record.kind===kind.input.value?record.data[k]:'');
        field.input.name=k;if(k==='name'&&kind.input.value==='meal')attachFoodNames(field.input);
        if(spec==='number'){field.input.step='any';field.input.min='0'}
        inputs[k]={input:field.input,type:spec};(k==='name'&&spec==='text'||k==='note'||kind.input.value==='meal'&&['quantity','unit'].includes(k)?primaryFields:dataBox).append(field.label);
      }
      if(composite){
        primaryFields.append(el('p','มื้อเดียว · แก้ปริมาณข้าวและกับข้าวแยกกันได้','muted'));
        for(const part of record.data.components){
          const row=el('div',undefined,'grid'),fields={};
          for(const key of ['name','quantity','unit']){
            const field=journalInput(key==='name'?'อาหาร':labels[key],key==='quantity'?'number':'text',part[key]);
            field.input.name='component-'+key;
            if(key==='quantity'){field.input.min='0';field.input.step='any'}
            if(key==='name')attachFoodNames(field.input);
            fields[key]=field.input;row.append(field.label);
          }
          const state=journalSelect('สถานะอาหาร',{'unknown':'ยังไม่ทราบ','cooked':'สุก','packaged':'ผลิตภัณฑ์','raw':'ดิบ'},part.food_state||'unknown');
          fields.food_state=state.input;row.append(state.label);
          componentInputs.push(fields);primaryFields.append(row);
        }
      }
      const interval=['activity','sleep','appointment'].includes(kind.input.value);end.label.classList.toggle('hidden',!interval);nextLabel.classList.toggle('hidden',!interval);
    }
    kind.input.onchange=rebuildFields;rebuildFields();
    const energyBox=el('div');primaryFields.after(energyBox);
    attachMealEnergy(energyBox,()=>({kind:kind.input.value,data:readData()}),card,item.check?.calculated?.energy);
    const status=el('p',item.check?.missing?.length?'เก็บข้อความได้ รายละเอียดที่ยังไม่ทราบค่อยเติมภายหลัง':'ตรวจรายการก่อนยืนยัน','muted');card.append(status);
    journalCards.push({record,include,kind:kind.input,period:period.input,clock:clock.input,day:day.input,end:end.input,nextDay,getInputs:()=>inputs,getData:readData});box.append(card);
  }
  if(!all.length){title.append(el('p','ยังไม่มีข้อความให้แยก กรุณาพิมพ์รายการที่ต้องการบันทึก'));return}
  const review=el('button',editing?'ตรวจการแก้ไข':'ตรวจและบันทึกรายการที่เลือก','primary');review.onclick=safely(async()=>{
    if(!editing&&journalRevision!==response.inputRevision)throw new Error('ข้อความเปลี่ยนแล้ว กรุณากดแยกและตรวจรายการอีกครั้ง');
    const records=collectJournalCards(journalCards);if(!records.length)throw new Error('เลือกรายการที่ต้องการเก็บอย่างน้อยหนึ่งรายการ');
    await reviewBatch(records,true,r=>{journalConfirmation={draftId:r.draft_id,editing,inputRevision:response.inputRevision}});
  });box.append(review);box.scrollIntoView({behavior:'smooth',block:'start'});
}
function collectJournalCards(cards){
  return cards.filter(c=>c.include.checked).map(c=>{
    if(!c.kind.value)throw new Error('กรุณาเลือกหมวดของข้อความที่ยังแยกไม่ได้ หรือเอาเครื่องหมายเก็บรายการนี้ออก');
    const record=structuredClone(c.record),data=c.getData?c.getData():{};
    if(!c.getData)for(const[k,{input,type}]of Object.entries(c.getInputs()))data[k]=input.value===''?null:type==='number'?Number(input.value):input.value;
    const j=record.journal;j.date=c.day.value;j.period=c.period.value;j.clock=c.clock.value||null;
    if((j.clock||'').slice(0,5)!==(c.record.journal.clock||'').slice(0,5))j.clock_source=j.clock?'user_edited':'unspecified';
    if(j.date!==c.record.journal.date)j.date_source='user_edited';
    const interval=['activity','sleep','appointment'].includes(c.kind.value);
    const field=interval?'start':'occurred_at';data[field]=j.clock?j.date+'T'+j.clock+':00+07:00':null;
    if(interval){
      let endDate=j.date;
      if(c.nextDay.checked){const dt=new Date(j.date+'T00:00:00Z');dt.setUTCDate(dt.getUTCDate()+1);endDate=dt.toISOString().slice(0,10)}
      data.end=c.end.value?endDate+'T'+c.end.value+':00+07:00':null;
      if(data.end&&!data.start)throw new Error('หากระบุเวลาสิ้นสุด กรุณาระบุเวลาเริ่มด้วย');
    }
    record.kind=c.kind.value;record.data=data;record.evidence=Object.fromEntries(Object.entries(record.evidence||{}).filter(([k])=>data[k]===c.record.data[k]));
    record.source='ผู้ใช้ตรวจและยืนยันบันทึกแบบเล่า; วันที่เริ่มต้นตามวันที่พิมพ์ (Asia/Bangkok)';record.origin='self_report';
    for(const key of ['id','version','created_at','status'])delete record[key];
    return record;
  });
}
$('#prepareJournal').onclick=safely(async()=>{
  const text=$('#journalText').value.trim();if(!text)throw new Error('พิมพ์สิ่งที่ต้องการบันทึกก่อน');
  const button=$('#prepareJournal');button.disabled=true;
  if(!journalCapturedAt)journalCapturedAt=new Date().toISOString();const inputRevision=journalRevision;
  try{notice('กำลังแยกหมวดและตรวจเวลา…');const r=await api('journal/prepare',{text,captured_at:journalCapturedAt});if(inputRevision!==journalRevision)throw new Error('ข้อความเปลี่ยนระหว่างรอ กรุณากดแยกรายการอีกครั้ง');renderJournal({...r,inputRevision});notice('แยกได้ '+r.items.length+' รายการ'+(r.unparsed.length?' · อีก '+r.unparsed.length+' ข้อความต้องเลือกหมวดเอง':'')+' ตรวจแล้วกดยืนยันพร้อมกันได้')}
  finally{button.disabled=false}
});
function editJournalRecord(item){const record=structuredClone(item);record.previous_id=item.id;renderJournal({items:[{record,check:{missing:[]},warnings:[]}],unparsed:[],default_date:item.journal.date,captured_at:item.journal.captured_at},true);page('record');notice('กำลังแก้บันทึกเดิม การยืนยันจะเก็บเป็นเวอร์ชันใหม่')}
updateCaptureNote();
