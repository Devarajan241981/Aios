"""The AIOS web UI — a single self-contained page served by the daemon.

No external resources (works offline, CSP-friendly): all CSS and JS are inline.
The daemon serves this at ``GET /``. Designed for local, no-token use; if
``AIOS_TOKEN`` is set, use the CLI or add the header yourself.

``__AIOS_VERSION__`` is replaced with the running version at serve time.
"""

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AIOS</title>
<style>
  :root{
    --bg:#f7f7f8; --panel:#ffffff; --border:#e5e5e8; --text:#1a1a1f; --muted:#6b6b76;
    --accent:#4f46e5; --accent-fg:#fff; --user:#eef0ff; --assistant:#f3f4f6;
    --warn-bg:#fff7ed; --warn-border:#fdba74; --code:#0f172a; --code-fg:#e2e8f0;
  }
  @media (prefers-color-scheme: dark){
    :root{
      --bg:#111114; --panel:#1a1a1f; --border:#2a2a31; --text:#eaeaf0; --muted:#9a9aa6;
      --accent:#7c74ff; --accent-fg:#fff; --user:#232544; --assistant:#202027;
      --warn-bg:#2a1f10; --warn-border:#7c5514; --code:#0b1020; --code-fg:#e2e8f0;
    }
  }
  /* Explicit theme choices win over the system preference. */
  :root[data-theme="light"]{
    --bg:#f7f7f8; --panel:#ffffff; --border:#e5e5e8; --text:#1a1a1f; --muted:#6b6b76;
    --accent:#4f46e5; --accent-fg:#fff; --user:#eef0ff; --assistant:#f3f4f6;
    --warn-bg:#fff7ed; --warn-border:#fdba74; --code:#0f172a; --code-fg:#e2e8f0;
  }
  :root[data-theme="dark"]{
    --bg:#111114; --panel:#1a1a1f; --border:#2a2a31; --text:#eaeaf0; --muted:#9a9aa6;
    --accent:#7c74ff; --accent-fg:#fff; --user:#232544; --assistant:#202027;
    --warn-bg:#2a1f10; --warn-border:#7c5514; --code:#0b1020; --code-fg:#e2e8f0;
  }
  *{box-sizing:border-box}
  html,body{height:100%;margin:0}
  body{font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
       background:var(--bg);color:var(--text);display:flex;height:100vh;overflow:hidden}
  aside{width:250px;flex:0 0 250px;background:var(--panel);border-right:1px solid var(--border);
        display:flex;flex-direction:column;min-height:0}
  .brand{padding:14px 16px;font-weight:700;letter-spacing:.5px;border-bottom:1px solid var(--border);
         display:flex;align-items:baseline;gap:8px}
  .brand small{font-weight:400;color:var(--muted);font-size:11px}
  .newbtn{margin:12px;padding:9px 12px;border:1px solid var(--border);border-radius:9px;
          background:transparent;color:var(--text);cursor:pointer;font-size:14px}
  .newbtn:hover{border-color:var(--accent)}
  .sessions{flex:1;overflow-y:auto;padding:4px 8px}
  .session{padding:9px 10px;border-radius:8px;cursor:pointer;color:var(--text);
           white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:14px}
  .session:hover{background:var(--assistant)}
  .session.active{background:var(--user)}
  .session .meta{display:block;color:var(--muted);font-size:11px;margin-top:1px}
  main{flex:1;display:flex;flex-direction:column;min-width:0;min-height:0}
  .topbar{padding:10px 16px;border-bottom:1px solid var(--border);display:flex;
          align-items:center;gap:14px;background:var(--panel)}
  .status{font-size:12px;color:var(--muted)}
  .status b{color:var(--text);font-weight:600}
  .controls{margin-left:auto;display:flex;align-items:center;gap:12px}
  .accent-dots{display:flex;gap:6px}
  .dot{width:14px;height:14px;border-radius:50%;cursor:pointer;border:2px solid transparent}
  .dot.sel{border-color:var(--text)}
  #themebtn,#bell{background:transparent;border:1px solid var(--border);border-radius:8px;
            color:var(--text);cursor:pointer;padding:2px 9px;font-size:15px;line-height:1.4}
  #bell{position:relative}
  #nbadge{position:absolute;top:-7px;right:-7px;background:#e11d73;color:#fff;border-radius:9px;
          font-size:10px;line-height:1.6;padding:0 5px;display:none}
  #npanel{position:fixed;top:50px;right:16px;width:320px;max-height:64vh;overflow-y:auto;
          background:var(--panel);border:1px solid var(--border);border-radius:12px;
          box-shadow:0 10px 30px rgba(0,0,0,.25);display:none;z-index:20}
  #npanel .nhead{display:flex;justify-content:space-between;align-items:center;
                 padding:9px 12px;border-bottom:1px solid var(--border)}
  #npanel .nitem{padding:9px 12px;border-bottom:1px solid var(--border);font-size:13px}
  #npanel .nitem.unread{background:var(--user)}
  #npanel .nitem .nlvl{font-size:11px;color:var(--muted)}
  #npanel .nempty{padding:18px;color:var(--muted);text-align:center}
  .toolgle{font-size:13px;color:var(--muted);display:flex;align-items:center;gap:6px;cursor:pointer}
  .thread{flex:1;overflow-y:auto;padding:22px 18px;min-height:0}
  .wrap{max-width:760px;margin:0 auto;display:flex;flex-direction:column;gap:14px}
  .msg{padding:11px 14px;border-radius:12px;white-space:pre-wrap;word-wrap:break-word}
  .msg.user{background:var(--user);align-self:flex-end;max-width:85%}
  .msg.assistant{background:var(--assistant);align-self:flex-start;max-width:92%}
  .msg .role{font-size:11px;color:var(--muted);margin-bottom:3px;text-transform:uppercase;letter-spacing:.5px}
  .steps{font-size:12px;color:var(--muted);margin-top:6px;border-left:2px solid var(--border);padding-left:8px}
  .approval{align-self:flex-start;max-width:92%;background:var(--warn-bg);
            border:1px solid var(--warn-border);border-radius:12px;padding:12px 14px}
  .approval h4{margin:0 0 8px;font-size:13px}
  .approval pre{background:var(--code);color:var(--code-fg);padding:10px;border-radius:8px;
                overflow-x:auto;font-size:12px;margin:6px 0;white-space:pre-wrap}
  .approval pre .d-add{color:#3fb950}
  .approval pre .d-del{color:#f85149}
  .approval pre .d-hunk{color:#79c0ff}
  .approval .tool{font-weight:600;font-size:13px}
  .approval .btns{display:flex;gap:8px;margin-top:10px}
  .btn{padding:7px 14px;border-radius:8px;border:1px solid var(--border);cursor:pointer;font-size:13px}
  .btn.primary{background:var(--accent);color:var(--accent-fg);border-color:var(--accent)}
  .btn.allow{background:transparent;color:var(--accent);border-color:var(--accent)}
  .btn.ghost{background:transparent;color:var(--text)}
  .composer{border-top:1px solid var(--border);padding:12px 16px;background:var(--panel)}
  .composer .row{max-width:760px;margin:0 auto;display:flex;gap:10px;align-items:flex-end}
  textarea{flex:1;resize:none;border:1px solid var(--border);border-radius:10px;padding:10px 12px;
           font:inherit;background:var(--bg);color:var(--text);max-height:160px}
  textarea:focus{outline:none;border-color:var(--accent)}
  .send{padding:10px 18px;border-radius:10px;border:none;background:var(--accent);
        color:var(--accent-fg);cursor:pointer;font-size:14px}
  .send:disabled{opacity:.5;cursor:default}
  .empty{color:var(--muted);text-align:center;margin-top:14vh}
  .empty h2{font-weight:600;margin:0 0 6px;color:var(--text)}
  @media (max-width:640px){ aside{display:none} }
</style>
</head>
<body>
<aside>
  <div class="brand">AIOS <small>__AIOS_VERSION__</small></div>
  <button class="newbtn" onclick="newChat()">+ New chat</button>
  <div class="sessions" id="sessions"></div>
</aside>
<main>
  <div class="topbar">
    <div class="status" id="status">connecting…</div>
    <div class="controls">
      <span class="accent-dots" id="dots"></span>
      <button id="bell" title="Notifications">🔔<span id="nbadge">0</span></button>
      <button id="themebtn" title="Theme: system / light / dark">◐</button>
      <label class="toolgle"><input type="checkbox" id="tools"> tools</label>
    </div>
  </div>
  <div id="npanel"></div>
  <div class="thread" id="thread">
    <div class="wrap" id="wrap">
      <div class="empty" id="empty">
        <h2>Your local AI</h2>
        <div>Everything runs on this machine. Ask anything, or turn on <b>tools</b>
             to let the assistant read files and act — with your approval.</div>
      </div>
    </div>
  </div>
  <div class="composer">
    <div class="row">
      <textarea id="input" rows="1" placeholder="Message AIOS…  (Enter to send, Shift+Enter for newline)"></textarea>
      <button class="send" id="send" onclick="send()">Send</button>
    </div>
  </div>
</main>
<script>
window.AIOS_ACCENT = "__AIOS_ACCENT__";
const $ = s => document.querySelector(s);
let session = null;
let busy = false;

async function api(method, path, body){
  const opt = {method, headers:{}};
  if(body !== undefined){ opt.headers['Content-Type']='application/json'; opt.body=JSON.stringify(body); }
  const r = await fetch(path, opt);
  return {status:r.status, body: await r.json()};
}

async function loadStatus(){
  try{
    const {body} = await api('GET','/health');
    const b = body.backend || {};
    $('#status').innerHTML = `backend <b>${b.backend||'?'}</b>` +
      (b.ok===false ? ' · <span style="color:#e11">offline</span>' : ' · ok') +
      ` · index <b>${(body.index&&body.index.documents)||0}</b> docs`;
  }catch(e){ $('#status').textContent='daemon unreachable'; }
}

async function loadSessions(){
  const {body} = await api('GET','/v1/sessions');
  const el = $('#sessions'); el.innerHTML='';
  (body.sessions||[]).forEach(s=>{
    const d=document.createElement('div');
    d.className='session'+(s.id===session?' active':'');
    d.innerHTML = `${escapeHtml(s.title)}<span class="meta">${s.messages} msgs</span>`;
    d.onclick=()=>openSession(s.id);
    el.appendChild(d);
  });
}

function clearThread(){ $('#wrap').innerHTML=''; }
function escapeHtml(s){ return (s||'').replace(/[&<>]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function formatPreview(text){
  return (text||'').split('\n').map(l=>{
    const e=escapeHtml(l);
    if(l.startsWith('+')&&!l.startsWith('+++')) return '<span class="d-add">'+e+'</span>';
    if(l.startsWith('-')&&!l.startsWith('---')) return '<span class="d-del">'+e+'</span>';
    if(l.startsWith('@@')) return '<span class="d-hunk">'+e+'</span>';
    return e;
  }).join('\n');
}

function bubble(role, text){
  const d=document.createElement('div'); d.className='msg '+role;
  d.innerHTML='<div class="role">'+(role==='user'?'you':'aios')+'</div>';
  const body=document.createElement('div'); body.textContent=text||''; d.appendChild(body);
  $('#wrap').appendChild(d); scroll(); d._body=body; return d;
}
function scroll(){ const t=$('#thread'); t.scrollTop=t.scrollHeight; }

async function openSession(id){
  session=id; clearThread();
  const {status, body}=await api('GET','/v1/sessions/'+id);
  if(status===200){ (body.messages||[]).forEach(m=>bubble(m.role==='user'?'user':'assistant', m.content)); }
  loadSessions();
}

async function newChat(){
  const {body}=await api('POST','/v1/sessions',{});
  session=body.id; clearThread();
  bubble('assistant','New session started. What can I do?');
  loadSessions();
}

function setBusy(b){ busy=b; $('#send').disabled=b; }

async function send(){
  const inp=$('#input'); const text=inp.value.trim();
  if(!text || busy) return;
  if(!session){ const {body}=await api('POST','/v1/sessions',{}); session=body.id; }
  const empty=$('#empty'); if(empty) empty.remove();
  inp.value=''; inp.style.height='auto';
  bubble('user', text);
  setBusy(true);
  try{
    if($('#tools').checked){ await sendTools(text, []); }
    else { await sendStream(text); }
  }catch(e){ bubble('assistant','⚠️ '+e.message); }
  setBusy(false);
  loadSessions();
}

async function sendStream(text){
  const resp=await fetch('/v1/chat',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({prompt:text, session_id:session, stream:true})});
  const b=bubble('assistant',''); let acc='';
  const reader=resp.body.getReader(); const dec=new TextDecoder(); let buf='';
  while(true){
    const {done,value}=await reader.read(); if(done) break;
    buf+=dec.decode(value,{stream:true});
    let i; while((i=buf.indexOf('\n\n'))>=0){
      const line=buf.slice(0,i).trim(); buf=buf.slice(i+2);
      if(!line.startsWith('data:')) continue;
      const p=line.slice(5).trim(); if(p==='[DONE]') continue;
      const o=JSON.parse(p);
      if(o.delta){ acc+=o.delta; b._body.textContent=acc; scroll(); }
      else if(o.error){ b._body.textContent='⚠️ '+o.error; }
    }
  }
}

async function sendTools(text, approved){
  const {body}=await api('POST','/v1/chat',
    {prompt:text, session_id:session, use_tools:true, approved_signatures:approved});
  if(body.status==='needs_approval'){ renderApproval(text, body.pending, approved); return; }
  const b=bubble('assistant', body.reply||'');
  if(body.steps && body.steps.length){
    const s=document.createElement('div'); s.className='steps';
    s.textContent='ran: '+body.steps.map(x=>x.tool).join(', ');
    b.appendChild(s);
  }
}

function renderApproval(text, pending, approved){
  const card=document.createElement('div'); card.className='approval';
  let html='<h4>The assistant wants to run '+pending.length+' action(s):</h4>';
  pending.forEach(p=>{ html+='<div class="tool">▸ '+escapeHtml(p.tool)+'</div><pre>'+formatPreview(p.preview)+'</pre>'; });
  html+='<div class="btns"><button class="btn primary">Approve once</button>'+
        '<button class="btn allow">Always allow</button>'+
        '<button class="btn ghost">Deny</button></div>';
  card.innerHTML=html; $('#wrap').appendChild(card); scroll();
  card.querySelector('.primary').onclick=async()=>{
    card.remove();
    const sigs=approved.concat(pending.map(p=>p.signature));
    setBusy(true); try{ await sendTools(text, sigs); }catch(e){ bubble('assistant','⚠️ '+e.message); } setBusy(false);
  };
  card.querySelector('.allow').onclick=async()=>{
    card.remove();
    const tools=[...new Set(pending.map(p=>p.tool))];
    for(const t of tools){ await api('POST','/v1/sessions/'+session+'/grants',{tool:t}); }
    setBusy(true); try{ await sendTools(text, approved); }catch(e){ bubble('assistant','⚠️ '+e.message); } setBusy(false);
  };
  card.querySelector('.ghost').onclick=()=>{ card.remove(); bubble('assistant','Declined — nothing was changed.'); };
}

// --- notifications ---
let notifItems=[];
async function refreshNotifications(){
  try{
    const {body}=await api('GET','/v1/notifications?n=20');
    notifItems=body.notifications||[];
    const badge=$('#nbadge'); const u=body.unread||0;
    badge.textContent=u; badge.style.display=u?'inline-block':'none';
  }catch(e){}
}
function renderNotifPanel(){
  let html='<div class="nhead"><b>Notifications</b><button class="btn ghost" id="nread">Mark all read</button></div>';
  if(!notifItems.length) html+='<div class="nempty">Nothing yet</div>';
  else notifItems.forEach(n=>{
    html+='<div class="nitem'+(n.read?'':' unread')+'"><div class="nlvl">'+escapeHtml(n.level)+'</div><b>'+
      escapeHtml(n.title)+'</b>'+(n.body?'<div>'+escapeHtml(n.body)+'</div>':'')+'</div>';
  });
  $('#npanel').innerHTML=html;
  const rb=$('#nread'); if(rb) rb.onclick=async()=>{ await api('POST','/v1/notifications/read',{}); await refreshNotifications(); renderNotifPanel(); };
}
function toggleNotifPanel(){
  const p=$('#npanel');
  if(p.style.display==='block'){ p.style.display='none'; return; }
  renderNotifPanel(); p.style.display='block';
}

// --- theme + accent (persisted in localStorage) ---
const THEMES=['system','light','dark'];
const THEME_ICON={system:'◐', light:'☀', dark:'☾'};
const ACCENTS=['#4f46e5','#7c74ff','#2e9e5b','#d97706','#e11d73'];

function applyTheme(){
  const t=localStorage.getItem('aios-theme')||'system';
  if(t==='system') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme',t);
  const b=$('#themebtn'); if(b) b.textContent=THEME_ICON[t];
}
function cycleTheme(){
  const t=localStorage.getItem('aios-theme')||'system';
  localStorage.setItem('aios-theme', THEMES[(THEMES.indexOf(t)+1)%THEMES.length]);
  applyTheme();
}
function renderDots(sel){
  const el=$('#dots'); if(!el) return; el.innerHTML='';
  ACCENTS.forEach(c=>{ const d=document.createElement('span');
    d.className='dot'+(c===sel?' sel':''); d.style.background=c; d.title=c;
    d.onclick=()=>{ localStorage.setItem('aios-accent',c); applyAccent(); }; el.appendChild(d); });
}
function applyAccent(){
  const a=localStorage.getItem('aios-accent')||window.AIOS_ACCENT||'';
  if(a) document.documentElement.style.setProperty('--accent',a);
  else document.documentElement.style.removeProperty('--accent');
  renderDots(a);
}

const input=$('#input');
input.addEventListener('input',()=>{ input.style.height='auto'; input.style.height=Math.min(input.scrollHeight,160)+'px'; });
input.addEventListener('keydown',e=>{ if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); send(); } });
$('#themebtn').addEventListener('click', cycleTheme);
$('#bell').addEventListener('click', toggleNotifPanel);

applyTheme(); applyAccent(); refreshNotifications();
loadStatus(); loadSessions();
setInterval(()=>{ loadStatus(); refreshNotifications(); }, 15000);
</script>
</body>
</html>
"""


def index_html(version: str, accent: str = "") -> str:
    return (INDEX_HTML
            .replace("__AIOS_VERSION__", version)
            .replace("__AIOS_ACCENT__", accent))
