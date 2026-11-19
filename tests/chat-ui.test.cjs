// SOFTWARE TEST ONLY: chat HTML/script in jsdom; no real records or API writes.
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{JSDOM,VirtualConsole}=require('jsdom');
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r))};
function setup(responder){
  const errors=[],requests=[];const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e));
  const dom=new JSDOM(fs.readFileSync('demo/index.html','utf8'),{url:'http://127.0.0.1:8765',runScripts:'dangerously',virtualConsole:vc});const w=dom.window;
  w.$=s=>w.document.querySelector(s);w.el=(tag,text,cls)=>{const e=w.document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e};w.csrf='SOFTWARE';w.page=()=>{};w.notice=()=>{};
  w.fetch=async(url,options)=>{const body=JSON.parse(options.body);requests.push({url,body});return responder?responder(url,options,body):{ok:true,json:async()=>({answer:'จากบันทึกของคุณ: <script>not executable</script>',record_sources:[{record_id:'software',version:1,label:'กิจกรรม',time:'2026-10-12 ตอนบ่าย',text:'SOFTWARE TEST ONLY',source:'software fixture'}],citations:[],suggestions:['ค่าตรวจล่าสุดของฉัน']})}};
  const script=w.document.createElement('script');script.textContent=fs.readFileSync('demo/chat.js','utf8');w.document.body.append(script);return {w,requests,errors,close:()=>w.close()};
}
test('chat sends scope/history, renders sources as text, and resets without health writes',async()=>{
  const ui=setup(),w=ui.w,d=w.document;
  try{
    assert.ok(d.querySelector('[data-page=chat]'));assert.equal(d.querySelector('#chatScope'),null);d.querySelector('#chatInput').value='วันนี้ทำอะไรไปบ้าง';d.querySelector('#chatForm').requestSubmit();await settle();
    assert.equal(ui.requests[0].url,'/api/chat');assert.equal(ui.requests[0].body.scope,'auto');assert.equal(d.querySelectorAll('.chat-source-item').length,1);
    assert.match(d.querySelector('#chatMessages').textContent,/<script>not executable<\/script>/);assert.equal(d.querySelectorAll('#chatMessages script').length,0);
    d.querySelector('#chatInput').value='แล้วเมื่อวานล่ะ';d.querySelector('#chatInput').dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));await settle();
    assert.equal(ui.requests[1].body.messages.length,3);assert.equal(ui.requests[1].body.messages[0].content,'วันนี้ทำอะไรไปบ้าง');
    d.querySelector('#chatReset').click();assert.equal(d.querySelectorAll('.chat-row').length,1);assert.equal(d.querySelectorAll('.chat-source-item').length,0);assert.deepEqual(ui.errors,[]);
  }finally{ui.close()}
});
test('reset cancels pending request and cannot leak an old answer into new conversation',async()=>{
  const ui=setup((url,options)=>new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>{const e=new Error('aborted');e.name='AbortError';reject(e)}))),d=ui.w.document;
  try{d.querySelector('#chatInput').value='ข้อมูลของฉัน';d.querySelector('#chatForm').requestSubmit();await settle();assert.equal(d.querySelector('#chatSend').disabled,true);d.querySelector('#chatReset').click();await settle();assert.equal(d.querySelectorAll('.chat-row').length,1);assert.equal(d.querySelector('#chatSend').disabled,false);assert.deepEqual(ui.errors,[])}finally{ui.close()}
});
test('missing chat API explains restart and preserves question for retry',async()=>{
  const ui=setup(()=>({ok:false,status:404,json:async()=>({detail:'Not Found'})})),d=ui.w.document;
  try{
    d.querySelector('#chatInput').value='เป็นเบาหวานควรกินอะไร';d.querySelector('#chatForm').requestSubmit();await settle();
    assert.match(d.querySelector('#chatMessages').textContent,/127\.0\.0\.1:8765/);
    assert.match(d.querySelector('#chatMessages').textContent,/scripts\/run_demo\.py/);
    assert.equal(d.querySelector('#chatInput').value,'เป็นเบาหวานควรกินอะไร');
    assert.equal(d.querySelector('#chatSend').disabled,false);assert.deepEqual(ui.errors,[]);
  }finally{ui.close()}
});

test('off-topic refusal has no misleading health-search or model labels',async()=>{
  const ui=setup(()=>({ok:true,json:async()=>({route:'out_of_scope',status:'out_of_scope',answer:'คำถามนี้อยู่นอกเรื่องสุขภาพครับ',citations:[],suggestions:[]})})),d=ui.w.document;
  try{
    d.querySelector('#chatInput').value='ดอกไม้คืออะไร';d.querySelector('#chatForm').requestSubmit();await settle();
    const answer=[...d.querySelectorAll('.chat-row.assistant')].at(-1);
    assert.match(answer.textContent,/นอกเรื่องสุขภาพ/);
    assert.doesNotMatch(answer.textContent,/ความรู้สุขภาพ|แหล่งข้อมูลอัตโนมัติ|AI ในเครื่อง/);
    assert.equal(answer.querySelectorAll('details').length,0);assert.deepEqual(ui.errors,[]);
  }finally{ui.close()}
});

test('meal context and recipe details start collapsed while allergy warning stays visible',async()=>{
  const ui=setup(()=>({ok:true,json:async()=>({route:'personalized_menu',answer:'ลองข้าวกับไก่ต้มครับ เช็กเครื่องปรุงและการปนเปื้อนกับผู้ปรุงด้วยนะครับ',engine:'local_ai_validated_selection',details:['BMI 24.7 เป็นค่าคำนวณ'],menus:[{id:'software',name:'ข้าวกับไก่ต้ม',note:'SOFTWARE RECIPE',kcal_note:'ยังไม่ทราบแคลอรี',ingredients:['ข้าว','ไก่']}],suggestions:[]})})),d=ui.w.document;
  try{
    d.querySelector('#chatInput').value='ตอนเย็นกินอะไรดี';d.querySelector('#chatForm').requestSubmit();await settle();
    const answer=[...d.querySelectorAll('.chat-row.assistant')].at(-1);
    assert.doesNotMatch(answer.querySelector('.chat-message-text').textContent,/BMI|SOFTWARE RECIPE/);
    assert.match(answer.querySelector('.chat-message-text').textContent,/เช็กเครื่องปรุงและการปนเปื้อน/);
    assert.equal(answer.querySelectorAll('details').length,2);
    assert.ok([...answer.querySelectorAll('details')].every(x=>!x.open));
    const context=answer.querySelector('.chat-answer-details');assert.match(context.textContent,/BMI 24.7/);
    context.open=true;assert.equal(context.open,true);assert.deepEqual(ui.errors,[]);
  }finally{ui.close()}
});
