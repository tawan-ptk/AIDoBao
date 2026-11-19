// Actual HTTPS/client/API/model check. Synthetic inputs; no confirmation writes.
import {readFile,writeFile} from 'node:fs/promises';
import {randomUUID} from 'node:crypto';
import assert from 'node:assert/strict';
import {createRuamwanClient} from '../integration/ruamwan-client.mjs';
const root=new URL('../',import.meta.url);
const gatewayUrl=JSON.parse(await readFile(new URL('integration/gateway.json',root),'utf8')).url;
const origin=new URL(gatewayUrl).origin;
const report={label:'SOFTWARE HTTPS LIVE CHECK; not a deployed Vercel check or clinical evaluation',origin,checked_at:new Date().toISOString(),checks:[]};
async function raw(path,headers={}){
  const r=await fetch(origin+path,{headers,redirect:'error',signal:AbortSignal.timeout(30000)});
  return {status:r.status,body:await r.json()};
}
// Verify the actual protected ingress before reading/sending credentials.
const anon=await raw('/api/readiness');assert.equal(anon.status,401);assert.equal(anon.body.detail,'Invalid API credentials');
report.checks.push({case:'anonymous_denied',status:anon.status});
const wrong=await raw('/api/readiness',{'Authorization':'Bearer invalid','X-Ruamwan-User':'SOFTWARE-NO-WRITE'});assert.equal(wrong.status,401);
report.checks.push({case:'wrong_key_denied',status:wrong.status});
const apiKey=process.env.RUAMWAN_API_KEY??(await readFile(new URL('.secrets/api-key',root),'utf8')).trim();
const prefix='SOFTWARE-GATEWAY:'+randomUUID();
const a=createRuamwanClient({apiKey,userId:prefix+':a',gatewayUrl}),b=createRuamwanClient({apiKey,userId:prefix+':b',gatewayUrl});
const auth={'Authorization':'Bearer '+apiKey,'X-Ruamwan-User':prefix+':a'};
const missing=await raw('/api/readiness',{'Authorization':auth.Authorization});assert.equal(missing.status,422);
report.checks.push({case:'missing_account_denied',status:missing.status});
for(const path of ['/docs','/api/session'])assert.equal((await raw(path,auth)).status,404);
report.checks.push({case:'demo_and_sessions_not_published',passed:true});
const readiness=await a.request('readiness');assert.equal(readiness.model_available,true);
report.checks.push({case:'authenticated_origin_reached',model_available:readiness.model_available});
assert.deepEqual((await a.request('records')).items,[]);assert.deepEqual((await b.request('records')).items,[]);
const prepared=await a.prepare('กินข้าวกับไข่พะโล้',{use_model:false});
assert.equal(prepared.items.length,1);assert.equal(prepared.items[0].record.data.components.length,2);
assert.equal(prepared.items[0].record.journal.clock_source,'capture_time');
assert.deepEqual(prepared.items[0].check.calculated.energy.kcal,[432.9,432.9]);
report.checks.push({case:'composite_draft_and_time',result:prepared});
const advice=await a.chat([{role:'user',content:'กินข้าวกับอะไรดี'}]);
assert.equal(advice.status,'meal_ideas');assert.ok(advice.menus.length);assert.equal(advice.engine,'local_ai_validated_selection');
assert.ok(!advice.actions?.some(x=>x.type==='records'));
report.checks.push({case:'actual_local_model_via_https',status:advice.status,engine:advice.engine,menu_count:advice.menus.length});
assert.deepEqual((await a.request('records')).items,[]);assert.deepEqual((await b.request('records')).items,[]);
report.checks.push({case:'no_health_records_written',passed:true});
await writeFile(new URL('reports/gateway-live.json',root),JSON.stringify(report,null,2));
console.log(JSON.stringify({origin,checks:report.checks.length,no_health_records_written:true}));
