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
 await wait("document.querySelector('#record-file')!==null",'application loads');
 if(await evaluate("document.querySelector('h2')?.textContent")!=='Overview')throw Error('Overview is not the default destination');
 if(await evaluate("document.querySelector('#start-example')?.disabled")!==false)throw Error('Example experiment unavailable');
 await upload('#record-file','pending-record.json');await wait("document.body.innerText.includes('SHA-256 chain verified')",'pending ledger');
 if(await evaluate("document.querySelectorAll('[role=tab]').length")!==3)throw Error('Three-tab regression');
 await upload('#v4-file','pending-v4.json');await wait("document.querySelector('#v4-summary')?.textContent.includes('AWAITING_OPERATOR')",'pending approval display');
 if(!await evaluate("document.querySelector('#v4-summary').textContent.includes('cannot authorize')"))throw Error('Missing replay/authority distinction');
 await upload('#record-file','joint-record.json');await wait("document.body.innerText.includes('joint')",'joint ledger');
 await upload('#v4-file','joint-v4.json');await wait("document.querySelector('#v4-summary')?.textContent.includes('COMPLETED')",'joint evidence');
 await wait("document.querySelector('#download-report')?.tagName==='A'",'deterministic report link');
 if(!await evaluate("fetch(document.querySelector('#download-report').href).then(r=>r.text()).then(t=>t.includes('V4 safety')&&t.includes('current&#95;y')&&t.includes('heading&#95;bias&#95;rad'))"))throw Error('V4 report content');
 await evaluate("document.querySelector('[data-section=dashboards]').click()");await wait("document.body.innerText.includes('Numerical fit evidence')",'dashboards');
 await evaluate("document.querySelector('[data-section=workspace]').click()");await wait("document.querySelectorAll('[role=tab]').length===3",'workspace sub-navigation');
 await evaluate("document.querySelector('[data-tab=Trajectory]').click()");await wait("document.querySelector('#visual-file')!==null",'trajectory controls');
 await upload('#visual-file','joint-visual.json');await wait("document.querySelector('#scene canvas,#scene svg')!==null",'Three.js or SVG pose rendering');
 const renderer=await evaluate("document.querySelector('#scene svg')?'svg':'canvas'");
 await evaluate("document.querySelector('#play').click()");await wait("parseFloat(document.querySelector('#clock').textContent)>0",'playback clock');
 await evaluate("document.querySelector('[data-tab=Investigator]').click()");await wait("document.querySelector('#v4-summary')?.textContent.includes('joint_enabled')",'state survives section changes');
 if(fs.existsSync(directory+'/evaluation-summary.json')){await upload('#v4-evaluation-file','evaluation-summary.json');await wait("document.querySelector('#v4-evaluation table')!==null",'aggregate table');}
 const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(directory+'/browser.png',Buffer.from(shot.data,'base64'),{mode:0o600});
 if(errors.length)throw Error('Browser exceptions: '+errors.join('; '));
 console.log(JSON.stringify({application_loaded:true,overview_default:true,example_available:true,tabs:3,pending_approval_read_only:true,joint_evidence:true,report_download:true,dashboards:true,renderer,playback:true,tab_state_preserved:true,evaluation_table:fs.existsSync(directory+'/evaluation-summary.json'),browser_exceptions:errors.length}));
}finally{ws.close();}
