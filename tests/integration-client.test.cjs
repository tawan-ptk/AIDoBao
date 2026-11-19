const {test}=require('node:test'),assert=require('node:assert/strict');
const load=()=>import('../integration/ruamwan-client.mjs');
test('server client separates authenticated users and forwards capture and confirmation exactly once',async()=>{
  const {createRuamwanClient}=await load(),calls=[];
  const fetchImpl=async(url,options)=>{calls.push({url,...options});return {ok:true,status:200,json:async()=>({status:'ok'})}};
  const config={apiKey:'k'.repeat(48),fetchImpl},a=createRuamwanClient({...config,userId:'site:a'}),b=createRuamwanClient({...config,userId:'site:b'});
  await a.chat([{role:'user',content:'กินข้าว'}],{captured_at:'2026-10-13T12:15:00+07:00'});
  await b.prepare('ตอนเช้ากินข้าว');
  assert.equal(calls.length,2);assert.equal(calls[0].headers['X-Ruamwan-User'],'site:a');assert.equal(calls[1].headers['X-Ruamwan-User'],'site:b');
  assert.equal(JSON.parse(calls[0].body).captured_at,'2026-10-13T12:15:00+07:00');assert.equal(calls[0].redirect,'error');
  await a.confirm('draft-a','stable-key');assert.equal(calls.length,3);
  assert.deepEqual(JSON.parse(calls[2].body),{draft_id:'draft-a',idempotency_key:'stable-key',confirmed:true});
});
test('server client rejects arbitrary targets, actions and missing identity; never silently retries errors',async()=>{
  const {createRuamwanClient,RuamwanAPIError}=await load();let count=0;
  const config={apiKey:'k'.repeat(48),userId:'site:a',fetchImpl:async()=>{count++;return {ok:false,status:401,json:async()=>({detail:'Invalid API credentials'})}}};
  assert.throws(()=>createRuamwanClient({...config,baseUrl:'https://untrusted.example'}));
  assert.throws(()=>createRuamwanClient({...config,userId:''}));
  assert.throws(()=>createRuamwanClient({...config,apiKey:'short'}));
  const client=createRuamwanClient(config);
  await assert.rejects(client.request('../records'));await assert.rejects(client.request('delete',{method:'POST',body:{}}));assert.equal(count,0);
  await assert.rejects(client.request('records'),error=>error instanceof RuamwanAPIError&&error.status===401);assert.equal(count,1);
});
test('Vercel client uses explicit HTTPS gateway configuration without exposing a key in a URL',async()=>{
  const {createRuamwanClient}=await load(),calls=[];
  const config={apiKey:'k'.repeat(48),userId:'site:a',fetchImpl:async(url,options)=>{calls.push({url,...options});return {ok:true,status:200,json:async()=>({status:'ok'})}}};
  const ai=createRuamwanClient({...config,gatewayUrl:'https://ai.example.com'});
  await ai.request('records?limit=10');assert.equal(calls[0].url,'https://ai.example.com/api/records?limit=10');
  assert.equal(calls[0].headers.Authorization,'Bearer '+'k'.repeat(48));assert.equal(calls[0].redirect,'error');
  for(const gatewayUrl of ['http://ai.example.com','https://key@ai.example.com','https://ai.example.com/api','https://ai.example.com?token=secret','https://localhost','https://ai.example.com:8443'])assert.throws(()=>createRuamwanClient({...config,gatewayUrl}));
});
