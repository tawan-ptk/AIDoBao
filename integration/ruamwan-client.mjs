/** Node.js 20+ backend client. Never import this file or API key into browser code.
 * userId must come from your verified login, e.g. `my-site:${session.user.id}`.
 * Requests never confirm, retry, or execute model actions automatically.
 */
const GET_PATHS=new Set(['records','plans','summary','personal-context','export','food-catalog','readiness']);
const POST_PATHS=new Set(['chat','journal/prepare','records/preview','records/batch-preview','records/delete-preview','confirm','plans/preview','knowledge','food-energy','extract']);
export class RuamwanAPIError extends Error {
  constructor(status,detail){super(typeof detail==='string'?detail:`AI API returned ${status}`);this.status=status;this.detail=detail;}
}
export function createRuamwanClient({apiKey,userId,baseUrl='http://127.0.0.1:8765',gatewayUrl,fetchImpl=globalThis.fetch,timeoutMs=210000}){
  if(typeof window!=='undefined')throw new Error('Use Ruamwan client in your backend only');
  // gatewayUrl is trusted SERVER configuration, never browser/model input.
  const url=new URL(gatewayUrl??baseUrl);
  const remote=typeof gatewayUrl==='string'&&url.protocol==='https:'&&!url.port&&url.hostname.includes('.')&&!['localhost','127.0.0.1','[::1]'].includes(url.hostname);
  const local=gatewayUrl===undefined&&['http://127.0.0.1:8765','http://localhost:8765'].includes(url.origin);
  if((!remote&&!local)||url.username||url.password||url.pathname!=='/'||url.search||url.hash)throw new Error('Use local API or an explicitly configured HTTPS gateway origin');
  if(typeof apiKey!=='string'||apiKey.length<32||/[\r\n]/.test(apiKey))throw new Error('Set server RUAMWAN_API_KEY (at least 32 characters)');
  if(typeof userId!=='string'||!userId.length||userId.length>200||/[^\x21-\x7E]/.test(userId))throw new Error('Pass a stable authenticated opaque user ID');
  async function request(path,{method='GET',body}={}){
    const endpoint=path.split('?')[0];
    if(!(method==='GET'?GET_PATHS:method==='POST'?POST_PATHS:new Set()).has(endpoint)&&!(method==='GET'&&/^plans\/[A-Za-z0-9_-]+\/recheck$/.test(endpoint)))throw new Error('Unsupported AI API action');
    // Reject redirects, path traversal, and arbitrary endpoints. Never forward
    // browser Authorization/Origin headers or accept a target URL from a model.
    if(/[\\#]/.test(path)||path.includes('..')||path.startsWith('/'))throw new Error('Invalid AI API path');
    const response=await fetchImpl(url.origin+'/api/'+path,{method,redirect:'error',
      headers:{'Authorization':'Bearer '+apiKey,'X-Ruamwan-User':userId,...(body!==undefined?{'Content-Type':'application/json'}:{})},
      ...(body!==undefined?{body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(timeoutMs)});
    let result;
    try{result=await response.json()}catch{throw new RuamwanAPIError(response.status,'AI service did not return JSON')}
    if(!response.ok)throw new RuamwanAPIError(response.status,result.detail??'AI request failed');
    return result;
  }
  return Object.freeze({request,
    chat:(messages,{captured_at=new Date().toISOString(),scope='auto'}={})=>request('chat',{method:'POST',body:{messages,scope,captured_at}}),
    prepare:(text,{captured_at=new Date().toISOString(),use_model=true}={})=>request('journal/prepare',{method:'POST',body:{text,captured_at,use_model,compact:true}}),
    preview:(records)=>request('records/batch-preview',{method:'POST',body:{records,compact:true}}),
    // Call only after the UI's explicit confirmation. Keep the SAME key for a
    // retry of this exact confirmation, and a NEW key for another operation.
    confirm:(draft_id,idempotency_key)=>request('confirm',{method:'POST',body:{draft_id,idempotency_key,confirmed:true}})
  });
}
