// SOFTWARE TEST ONLY. Execute the real click handler with DOM/API stand-ins.
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('demo/app.js','utf8');
const handler=source.slice(source.indexOf("$('#extract').onclick="),source.indexOf('\nObject.entries(names)'));
function setup(response){
  let message='';const field={value:'existing',type:'text',tagName:'INPUT'};
  const nodes={'#extract':{disabled:false},'#recordKind':{value:'wellbeing'},'#freeText':{value:'SOFTWARE TEST ONLY'},'#recordForm':{elements:{namedItem:k=>k==='note'?field:null}},'#recordFields':{scrollIntoView(){},dispatchEvent(){}}};
  vm.runInNewContext(handler,{$:s=>nodes[s],Event:class Event{},safely:f=>f,notice:s=>message=s,api:async()=>response,names:{wellbeing:'ความเป็นอยู่'},labels:{note:'ความรู้สึก',occurred_at:'วันและเวลา'}});
  return {click:()=>nodes['#extract'].onclick(),field,message:()=>message,button:nodes['#extract']};
}
test('failed extraction preserves typed fields and does not claim success',async()=>{
  const ui=setup({model_status:'invalid_model_output',record:{data:{note:null}}});await ui.click();
  assert.match(ui.message(),/แยกข้อความนี้เป็นช่องข้อมูลไม่ได้/);assert.equal(ui.field.value,'existing');assert.equal(ui.button.disabled,false);
});
test('partial proposal populates field and explains missing date',async()=>{
  const ui=setup({model_status:'proposal',record:{data:{note:'SOFTWARE TEST ONLY',occurred_at:null}},check:{missing:['occurred_at']}});await ui.click();
  assert.equal(ui.field.value,'SOFTWARE TEST ONLY');assert.match(ui.message(),/1 ช่อง/);assert.match(ui.message(),/วันและเวลา/);
});
test('all-null response does not claim fields were filled',async()=>{
  const ui=setup({model_status:'no_supported_fields',record:{data:{note:null}}});await ui.click();assert.match(ui.message(),/ยังไม่พบข้อมูล/);
});
