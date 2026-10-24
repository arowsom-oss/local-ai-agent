"use strict";
const $ = id => document.getElementById(id);
let csrf = "", chat = null, snapshot = null, selectedArtifact = null, pollTimer, expiryTimer, generation = 0, refreshSerial = 0;
let uncertain = null; // An uncertain submit keeps the same idempotency key; no automatic resubmit.
function notice(message) { $("notice").textContent = message; }
function signedOut(message) {
  generation++;
  clearTimeout(pollTimer); clearTimeout(expiryTimer); csrf = ""; snapshot = null; chat = null; uncertain = null;
  $("studio").hidden = $("navigation").hidden = true; $("login").hidden = false;
  $("messages").replaceChildren(); $("artifacts").replaceChildren(); $("artifact-body").textContent = "";
  $("chats").replaceChildren(); $("model").replaceChildren(); $("artifact-view").hidden = true;
  $("message").value = ""; selectedArtifact = null; notice(message);
}
async function api(path, body) {
  const epoch = generation;
  const response = await fetch(path, {method: body === undefined ? "GET" : "POST", credentials: "same-origin",
    cache: "no-store", headers: body === undefined ? {} : {"Content-Type": "application/json", "X-CSRF-Token": csrf},
    body: body === undefined ? undefined : JSON.stringify(body)});
  const data = await response.json();
  if (response.status === 401 && epoch === generation) signedOut("Your local session ended. Use the desktop app’s access link to sign in again.");
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
}
function el(tag, content, className) { const node = document.createElement(tag); node.textContent = content; if (className) node.className = className; return node; }
function action(label, fn) { const node = el("button", label); node.type = "button"; node.addEventListener("click", fn); return node; }
function bubble(label, content, kind) { const node = el("div", "", "message " + kind); node.append(el("span", label, "message-label"), document.createTextNode(content)); return node; }
function render(data) {
  csrf = data.csrf; snapshot = data; chat = data.chat;
  $("login").hidden = true; $("studio").hidden = $("navigation").hidden = false;
  clearTimeout(expiryTimer); expiryTimer = setTimeout(() => signedOut("Local session expired. Sign in again from the desktop app."), data.expires_in * 1000);
  $("chats").replaceChildren(...data.chats.map(c => { const b = action(c.title, () => { uncertain = null; chat = c.id; refresh(); }); b.className = "chat-link" + (c.id === chat ? " selected" : ""); return b; }));
  const oldModel = $("model").value;
  $("model").replaceChildren(...data.models.map(m => { const o = el("option", m); o.value = m; return o; }));
  if (data.models.includes(oldModel)) $("model").value = oldModel;
  const messages = $("messages"); messages.replaceChildren();
  if (!data.jobs.length) { const welcome = el("div", "", "empty"); welcome.append(el("h2", "What’s on your mind?"), el("p", "A question. A first draft. A small idea worth exploring.\nStart a conversation with the model on your laptop.")); messages.append(welcome); }
  let pending = false;
  for (const job of data.jobs) {
    messages.append(bubble("You", job.message, "user"));
    if (job.status === "completed") {
      messages.append(bubble("Local Studio", job.answer, "assistant"));
      const row = el("div", "", "reply-actions");
      for (const kind of ["document", "code"]) row.append(action("Keep as " + kind, async () => { try { await api("/api/keep", {job:job.id, kind}); await refresh(); notice("Kept as a web Artifact. Source code is displayed as text only."); } catch(e) { notice(e.message); } }));
      messages.append(row);
    } else if (["queued", "running"].includes(job.status)) {
      pending = true;
      const node = el("div", job.status === "queued" ? "Queued on your laptop. " : "Waiting for the shared model, or generating a reply. ", "pending");
      node.append(action("Cancel", async () => { try { await api("/api/cancel",{job:job.id}); await refresh(); } catch(e) { notice(e.message); } })); messages.append(node);
    } else messages.append(el("p", job.status + ": " + job.error, "job-meta"));
  }
  $("send").disabled = pending; $("send").textContent = uncertain ? "Retry same request ↑" : "Send message ↑";
  $("artifact-count").textContent = String(data.artifacts.length);
  $("artifacts").replaceChildren(...data.artifacts.map((a,i) => { const b=action(`${a.kind === "code" ? "〈/〉" : "▤"}  ${a.kind} ${data.artifacts.length-i}`,async () => { const epoch=generation; try { const result=await api("/api/artifacts/"+a.id); if(epoch!==generation) return; selectedArtifact={...result,id:a.id}; $("artifact-title").textContent=result.kind === "code" ? "Code · inert text" : "Document"; $("artifact-body").textContent=result.body; $("artifact-view").hidden=false; } catch(e) { if(epoch===generation) notice(e.message); } }); b.className="artifact-link"; return b; }));
  clearTimeout(pollTimer); if (pending) pollTimer=setTimeout(refresh,1500);
}
async function refresh() { const epoch=generation, serial=++refreshSerial; try { const data=await api("/api/state"+(chat ? "?chat="+chat : "")); if(epoch===generation && serial===refreshSerial) render(data); } catch(e) { if(epoch===generation) notice(e.message); } }
$("login-form").addEventListener("submit", async event => { event.preventDefault(); generation++; try { const key=$("access-key").value; await api("/api/session", {key}); $("access-key").value=""; await refresh(); notice("Local workspace connected. School access is not enabled yet."); } catch(e) { notice(e.message); } });
$("new-chat").addEventListener("click", async () => { try { const result=await api("/api/chats",{title:"Conversation "+(snapshot.chats.length+1)}); chat=result.chat; uncertain=null; $("message").value=""; await refresh(); } catch(e) { notice(e.message); } });
$("sign-out").addEventListener("click", async () => { generation++; try { await api("/api/logout",{}); signedOut("Signed out. Existing queued work is retained; signing out does not cancel it."); } catch(e) { signedOut("Page cleared, but server sign-out was not confirmed. Close this browser tab and retry when connected."); } });
$("compose").addEventListener("submit", async event => {
  event.preventDefault(); if ($("send").disabled) return;
  const message=$("message").value;
  const epoch=generation;
  if (!message.trim()) return;
  $("send").disabled=true;
  try {
    if (!chat) chat=(await api("/api/chats",{title:"Conversation "+(snapshot.chats.length+1)})).chat;
    if (uncertain && (uncertain.message !== message || uncertain.chat !== chat || uncertain.model !== $("model").value)) throw new Error("A prior submit is uncertain. Restore its message/model or reload the conversation before a different request.");
    uncertain = uncertain || {chat, request:crypto.randomUUID().replaceAll("-",""), message, model:$("model").value};
    await api("/api/jobs",uncertain); if(epoch!==generation) return; uncertain=null; $("message").value=""; await refresh(); if(epoch===generation) notice("Request accepted. If your connection drops, reload to find the same job.");
  } catch(e) { if(epoch!==generation) return; $("send").disabled=false; $("send").textContent=uncertain ? "Retry same request ↑" : "Send message ↑"; notice(e.message); }
});
$("download").addEventListener("click", async () => {
  if (!selectedArtifact) return;
  const epoch=generation;
  try {
    const result=await api("/api/artifacts/"+selectedArtifact.id); if(epoch!==generation) return;
    const url=URL.createObjectURL(new Blob([result.body],{type:"text/plain;charset=utf-8"}));
    const a=document.createElement("a"); a.href=url; a.download=result.kind === "code" ? "local-studio-code.txt" : "local-studio-document.txt"; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
  } catch(e) { if(epoch===generation) notice(e.message); }
});
const fragment=location.hash.slice(1); history.replaceState(null,"",location.pathname);
if (fragment) { $("access-key").value=fragment; $("login-form").requestSubmit(); } else refresh();
