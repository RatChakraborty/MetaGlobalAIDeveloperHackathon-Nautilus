// Local Chromium CDP regression. Start Vite + Chromium on loopback; no public endpoints.
// node frontend/tests/v4-browser.mjs /absolute/private/demo-directory
import fs from 'node:fs';
const directory=process.argv[2];if(!directory)throw Error('Pass private fixture directory');
const base=process.env.NAUTILUS_TEST_URL??'http://127.0.0.1:5173';
const cdp=process.env.NAUTILUS_CDP_URL??'http://127.0.0.1:9222';
const targets=await(await fetch(cdp+'/json/list')).json();const ws=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{ws.onopen=resolve;ws.onerror=reject;});
let id=0;const pending=new Map(),errors=[];
ws.onmessage=event=>{const m=JSON.parse(event.data);if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(Error(JSON.stringify(m.error))):p.resolve(m.result);}}else if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails.text);};
const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params}));});
async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result?.value;}
async function wait(expression,label){for(let i=0;i<100;i++){if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,100));}throw Error('Timed out: '+label);}
async function upload(selector,name){const {root}=await send('DOM.getDocument');const {nodeId}=await send('DOM.querySelector',{nodeId:root.nodeId,selector});if(!nodeId)throw Error('Missing input '+selector);await send('DOM.setFileInputFiles',{nodeId,files:[directory+'/'+name]});}
try{
 await send('Page.enable');await send('Runtime.enable');await send('Page.navigate',{url:base});
 await wait("document.querySelector('#workbench-files')!==null",'workbench controls');
 const names=['investigation.json','configuration-evaluation.json','comparison.json','baseline.public.json','baseline.visualization.json','candidate.public.json','candidate.visualization.json'];
 const uploadFiles=async(names)=>{const {root}=await send('DOM.getDocument');const {nodeId}=await send('DOM.querySelector',{nodeId:root.nodeId,selector:'#workbench-files'});await send('DOM.setFileInputFiles',{nodeId,files:names.map(n=>directory+'/'+n)});};
 await uploadFiles(names);await wait("document.querySelector('#compare-runs')?.disabled===false",'comparison ready after one selection');
 if(await evaluate("document.querySelectorAll('[role=tab]').length")!==3)throw Error('Three-tab regression');
 if(await evaluate("document.querySelector('h2')?.textContent")!=='Investigator')throw Error('Loaded record did not open Investigator');
 const original=JSON.parse(fs.readFileSync(directory+'/investigation.json','utf8')).run_id;
 await wait("document.querySelector('#download-report')?.tagName==='A'",'report download');
 await evaluate("document.querySelector('#compare-runs').click()");await wait("document.querySelector('h2')?.textContent==='Trajectory'&&document.querySelector('#scene canvas,#scene svg')!==null",'recorded comparison renderer');
 await wait("document.querySelector('#download-report')?.tagName==='A'",'comparison-view report');
 const report=await evaluate("fetch(document.querySelector('#download-report').href).then(r=>r.text())");
 if(!report.includes('- Run: &#34;'+original+'&#34;'))throw Error('Comparison overwrote investigation report context');
 const comparison=await evaluate("fetch(document.querySelector('#download-comparison').href).then(r=>r.json())");
 const host=JSON.parse(JSON.parse(fs.readFileSync(directory+'/configuration-evaluation.json','utf8')).events[0].body_canonical);
 if(JSON.stringify(comparison)!==JSON.stringify(host.comparison))throw Error('Comparison download values changed');
 const config=await evaluate("fetch(document.querySelector('#download-config').href).then(r=>r.json())");if(config.deployment_ready!==false||config.baseline_value!==7||config.candidate_value!==3)throw Error('Config diff values');
 await evaluate("document.querySelector('#seek').value='1.5';document.querySelector('#seek').dispatchEvent(new Event('input',{bubbles:true}))");
 if(!await evaluate("document.querySelector('#reference-clock').textContent.includes('1.50')&&document.querySelector('#scene-time').textContent.includes('1.50')"))throw Error('Comparison clocks differ');
 if(!await evaluate("document.querySelector('#reference-record').disabled&&document.querySelector('#visual-file').disabled"))throw Error('Verified comparison sources can be replaced silently');
 await evaluate("document.querySelector('#return-investigation').click()");await wait("document.querySelector('h2')?.textContent==='Investigator'",'return to investigation');
 if(!await evaluate("document.querySelector('.run-info strong').textContent==="+JSON.stringify(original.slice(0,12))))throw Error('Investigation identity lost');
 await uploadFiles(['private-session.json']);await wait("document.querySelector('#error')?.textContent.includes('private')",'private import rejected');
 if(!await evaluate("document.querySelector('.run-info strong').textContent==="+JSON.stringify(original.slice(0,12))))throw Error('Invalid import replaced valid state');
 await uploadFiles(['pending-record.json','pending-v4.json']);await wait("document.querySelector('.evidence-overview')?.textContent.includes('AWAITING_OPERATOR')",'pending V4 summary');
 if(!await evaluate("document.querySelector('#compare-runs').disabled&&document.querySelector('#download-config').disabled&&document.querySelector('#download-comparison').disabled"))throw Error('Stale comparison/config leaked into new session');
 if(errors.length)throw Error('Browser exceptions: '+errors.join('; '));
 const screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(directory+'/workbench-browser.png',Buffer.from(screenshot.data,'base64'),{mode:0o600});
 console.log(JSON.stringify({one_selection_load:true,one_click_comparison:true,three_tabs_preserved:true,comparison_clock_sync:true,original_investigation_restored:true,report_context_preserved:true,comparison_json_exact:true,config_values_exact:true,invalid_import_atomic:true,v4_pending_state:true,stale_companions_cleared:true,browser_exceptions:0}));
}finally{ws.close();}
