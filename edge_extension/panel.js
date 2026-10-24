import {edgeDOM} from './page.js';
const tabId=Number(new URL(location.href).searchParams.get('tab'));
const status=document.getElementById('status');
let base='',secret='',shared=false,origin='',generation=0;
const tell=text=>{status.textContent=text;};
const target=await chrome.tabs.get(tabId).catch(()=>null);
document.getElementById('tab').textContent=target ? (target.title+'\n'+target.url) : 'Selected tab unavailable.';

async function request(path,data) {
  const response=await fetch(base+path,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+secret},
    body:JSON.stringify(data),cache:'no-store',credentials:'omit',redirect:'error',signal:AbortSignal.timeout(4000)});
  if(!response.ok) throw Error('Connection refused or revoked. Reconnect in the app.');
  return response.json();
}
async function disconnect() {
  shared=false;generation++;
  if(secret)try{await request('/disconnect',{});}catch{}
  secret='';base='';
  document.getElementById('share').disabled=false;document.getElementById('stop').disabled=true;
  tell('Disconnected. No further commands will run.');
}
async function loop(serial) {
  while(shared && serial===generation) {
    try {
      const current=await chrome.tabs.get(tabId);
      if(new URL(current.url).origin!==origin)throw Error('The tab left its shared origin. Share it again.');
      const data=await request('/poll',{tab:tabId});
      if(!shared || serial!==generation)break;
      const command=data.command;
      if(command) {
        if(command.tab!==tabId || Date.now()>=command.expires)throw Error('Expired command.');
        let result;
        try {
          if(command.op==='prepare' && !['read','copy'].includes(command.args?.action))throw Error('Personal tabs are read/handoff only.');
          // This fixed function runs only in our isolated world, top frame only.
          const values=await chrome.scripting.executeScript({target:{tabId,frameIds:[0]},world:'ISOLATED',
              func:edgeDOM,args:[{op:command.op,args:command.args,expires:command.expires}]});
          result=values[0]?.result || {error:'no result'};
        }catch{result={error:'page unavailable'};}
        await request('/result',{id:command.id,result});
      }
    }catch(error){tell(String(error.message));await disconnect();break;}
    await new Promise(resolve=>setTimeout(resolve,200));
  }
}
document.getElementById('share').addEventListener('click',async()=>{
  try {
    const code=document.getElementById('pair').value;
    const match=/^([0-9]{1,5}):([A-Za-z0-9_-]{43})$/.exec(code);
    if(!match || Number(match[1])<1 || Number(match[1])>65535)throw Error('Use the fresh code from the app.');
    const tab=await chrome.tabs.get(tabId),url=new URL(tab.url);
    if(url.protocol!=='https:' || url.username || url.password)throw Error('Only ordinary HTTPS pages are supported.');
    base='http://127.0.0.1:'+match[1];secret=match[2];origin=url.origin;
    await request('/pair',{tab:tabId,url:tab.url,title:(tab.title||'').slice(0,200)});
    shared=true;document.getElementById('pair').value='';
    document.getElementById('share').disabled=true;document.getElementById('stop').disabled=false;
    tell('Selected tab shared. Review each operation in Local Studio.');
    loop(++generation);
  }catch(error){tell(String(error.message));secret='';base='';}
});
document.getElementById('stop').addEventListener('click',disconnect);
async function closeConnector(){
  const close=document.getElementById('close');close.disabled=true;close.textContent='Closing...';
  // Revoke immediately; a dead relay cannot keep this window open for seconds.
  await Promise.race([disconnect(),new Promise(resolve=>setTimeout(resolve,500))]);
  window.close();
}
document.getElementById('close').addEventListener('click',closeConnector);
window.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();closeConnector();}});
window.addEventListener('pagehide',()=>{shared=false;generation++;});
