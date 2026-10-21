// Serialized by chrome.scripting; do not close over any module/global page code.
export async function edgeDOM(command) {
  try {
    const validURL=value=>{
      const u=new URL(value);
      if(u.protocol!=='https:' || u.username || u.password || (u.port && u.port!=='443')
         || !/^[\x21-\x7e]+$/.test(u.hostname) || u.hostname.includes('xn--')
         || !/[a-z]$/i.test(u.hostname) || !u.hostname.includes('.')
         || /(?:\.local|\.localhost|\.internal|\.lan|\.home|\.arpa)$/.test(u.hostname))throw Error('URL refused');
      return u.href;
    };
    validURL(location.href);
    if(!command || Date.now()>=command.expires)throw Error('command expired');
    const label=el=>(el.getAttribute('aria-label')||el.labels?.[0]?.innerText||el.innerText||el.placeholder||el.title||el.name||'(unlabelled)').replace(/\s+/g,' ').slice(0,100);
    const protectedField=el=>{
      const type=(el.getAttribute('type')||'text').toLowerCase();
      return !['text','search','textarea'].includes(el.tagName==='TEXTAREA'?'textarea':type)
        || /password|one-time-code|cc-|username|email/i.test(el.autocomplete||'')
        || /password|passcode|credit.?card|secret|token|otp/i.test([el.name,el.id,label(el)].join(' '));
    };
    const visible=el=>{
      const r=el.getBoundingClientRect(),s=getComputedStyle(el);
      for(let node=el;node;node=node.parentElement)if(getComputedStyle(node).opacity==='0')return false;
      const top=document.elementFromPoint(Math.max(0,Math.min(innerWidth-1,r.left+r.width/2)),Math.max(0,Math.min(innerHeight-1,r.top+r.height/2)));
      return (top===el || el.contains(top)) && r.width>0 && r.height>0 && r.bottom>0 && r.right>0 && r.top<innerHeight && r.left<innerWidth
        && s.display!=='none' && s.visibility!=='hidden' && s.opacity!=='0' && !el.disabled
        && !el.closest('[hidden],[inert],[aria-hidden="true"]');
    };
    function describe(el) {
      const tag=el.tagName.toLowerCase();
      if(tag==='input' && ['button','submit'].includes(el.type))
        return {kind:'button',label:label(el),type:el.type,formMethod:el.form?.method||''};
      if(tag==='input'||tag==='textarea') {
        if(protectedField(el))return null;
        return {kind:'text box',label:label(el),value:el.value.slice(0,500)};
      }
      if(tag==='a') {
        if(el.hasAttribute('download'))return null;
        const href=validURL(el.href);
        if(/\.(?:exe|msi|zip|7z|rar|dmg|iso|apk)(?:[?#]|$)/i.test(href))return null;
        return {kind:'link',label:label(el),destination:href};
      }
      if(tag==='button' || (tag==='input' && ['button','submit'].includes(el.type)))
        return {kind:'button',label:label(el),type:el.type||'',formMethod:el.form?.method||''};
      return null;
    }
    const snapshot=async()=>{
      const found=[];
      for(const el of [...document.querySelectorAll('a[href],button,input,textarea')].slice(0,500)) {
        if(!visible(el))continue;
        try{const info=describe(el);if(info)found.push({el,info});}catch{}
        if(found.length>=30)break;
      }
      const text=(document.body?.innerText||'').slice(0,20000);
      const value=JSON.stringify({url:location.href,title:document.title,text,elements:found.map(x=>x.info)});
      const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value)))].map(v=>v.toString(16).padStart(2,'0')).join('');
      return {found,text,digest,url:location.href};
    };
    const state=globalThis.__localStudioEdge || (globalThis.__localStudioEdge={counter:0,observed:null,pending:null});
    const args=command.args;
    state.counter=Math.max(state.counter,Number.isSafeInteger(args?._base)?args._base:0);
    if(command.op==='prepare') {
      if(!args || !['read','copy','click','type','scroll'].includes(args.action))throw Error('unsupported action');
      if(args.action==='scroll' && !['up','down'].includes(args.text))throw Error('invalid direction');
      const snap=await snapshot();let item=null;
      if(args.action==='click'||args.action==='type') {
        const old=state.observed;
        if(!old || old.digest!==snap.digest)throw Error('read again');
        item=old.controls.get(args.element);
        if(!item || !item.el.isConnected || !visible(item.el))throw Error('stale control');
        if(args.action==='type' && (item.info.kind!=='text box' || protectedField(item.el)
           || typeof args.text!=='string' || args.text.length<1 || args.text.length>500
           || /[@\r\n\t\x00-\x1f\x7f]|\d{7}/u.test(args.text)))throw Error('typing refused');
        if(args.action==='click' && item.info.kind==='text box')throw Error('not clickable');
      }
      const preview={action:args.action,url:location.href,title:document.title.slice(0,200)};
      if(args.action==='scroll')preview.direction=args.text;
      if(item) {
        preview.control=item.info.label;preview.kind=item.info.kind;
        if(args.action==='type'){preview.before=item.info.value;preview.text=args.text;}
        if(item.info.destination)preview.destination=item.info.destination;
      }
      const ticket=crypto.randomUUID();state.pending={ticket,expires:Date.now()+30000,snap,item,args};
      return {ticket,preview};
    }
    if(command.op!=='commit')throw Error('unsupported command');
    const pending=state.pending;state.pending=null; // one use, even on failure
    if(!pending || pending.ticket!==args.ticket || Date.now()>=pending.expires)throw Error('approval expired');
    const snap=await snapshot();
    if(snap.digest!==pending.snap.digest)throw Error('page changed');
    const action=pending.args.action;
    if(action==='copy')return {url:location.href};
    if(action==='read') {
      const controls=new Map(),lines=[];let used=0;
      for(const item of snap.found){
        const n=state.counter+1;
        const line=`[${n}] ${item.info.kind} ${JSON.stringify(item.info.label)}`+(item.info.kind==='text box'?' = '+JSON.stringify(item.info.value):'');
        if(used+line.length>1600)break;
        state.counter=n;controls.set(n,item);lines.push(line);used+=line.length+1;
      }
      state.observed={digest:snap.digest,controls};
      const suffix='\n\nVisible controls (main frame only):\n'+lines.join('\n');
      const header='URL: '+location.href+'\n';
      return {text:(header+snap.text.slice(0,Math.max(0,3900-header.length-suffix.length))+suffix).slice(0,3900),next_counter:state.counter};
    }
    if(action==='scroll'){
      state.observed=null;window.scrollBy(0,(pending.args.text==='up'?-1:1)*Math.min(innerHeight*.75,800));
      return {dispatched:true};
    }
    const item=pending.item;
    if(!item.el.isConnected || !visible(item.el) || JSON.stringify(describe(item.el))!==JSON.stringify(item.info))throw Error('control changed');
    state.observed=null;
    if(action==='type') {
      if(protectedField(item.el))throw Error('protected field');
      const proto=item.el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto,'value').set.call(item.el,pending.args.text);
      item.el.dispatchEvent(new Event('input',{bubbles:true}));item.el.dispatchEvent(new Event('change',{bubbles:true}));
    }else if(item.info.kind==='link') {
      // No page-supplied href handler: navigate to exactly the approved recorded destination.
      location.assign(item.info.destination);
    }else {
      item.el.click(); // Explicitly approved website-defined action; effects are unverified.
    }
    return {dispatched:true};
  }catch{return {error:'page changed, protected control, or unsupported operation; read again'};}
}
