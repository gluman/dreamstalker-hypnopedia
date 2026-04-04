// DreamStalker - App Logic
const API = '';

// === Helpers ===
function $(sel){return document.querySelector(sel)}
function $$(sel){return document.querySelectorAll(sel)}
function show(el){if(typeof el==='string')el=$(el);if(el)el.classList.remove('hidden')}
function hide(el){if(typeof el==='string')el=$(el);if(el)el.classList.add('hidden')}
function toast(msg,type){
  type=type||'success';
  let c=$('.toast-container');if(!c){c=document.createElement('div');c.className='toast-container';document.body.appendChild(c)}
  const t=document.createElement('div');t.className='toast toast-'+type;t.textContent=msg;c.appendChild(t);
  setTimeout(function(){t.remove()},4000);
}
function setProgress(el,pct){
  if(typeof el==='string')el=$(el);if(!el)return;
  show(el);el.style.width=pct+'%';
}
function setLoading(btn,loading){
  if(loading){btn.disabled=true;btn.dataset.orig=btn.innerHTML;btn.innerHTML='<span class="spinner"></span> '+btn.textContent.trim()}
  else{btn.disabled=false;if(btn.dataset.orig)btn.innerHTML=btn.dataset.orig}
}

// === Upload ===
async function uploadFiles(files){
  if(!files||!files.length)return;
  const fd=new FormData();
  for(let i=0;i<files.length;i++)fd.append('files',files[i]);
  const bar=$('#upload-progress .progress-bar');
  const container=$('#upload-progress');
  if(container)show(container);
  try{
    const xhr=new XMLHttpRequest();
    const p=new Promise(function(res,rej){
      xhr.upload.onprogress=function(e){if(e.lengthComputable&&bar)setProgress(bar,Math.round(e.loaded/e.total*100))};
      xhr.onload=function(){if(xhr.status>=200&&xhr.status<300)res(JSON.parse(xhr.responseText));else rej(xhr.responseText)};
      xhr.onerror=function(){rej('Network error')};
    });
    xhr.open('POST',API+'/api/upload');
    xhr.send(fd);
    const data=await p;
    toast('Files uploaded successfully');
    if(typeof onUploadComplete==='function')onUploadComplete(data);
    return data;
  }catch(e){toast('Upload failed: '+e,'error');throw e}
}

// === Plan ===
async function createPlan(goal,count){
  const btn=$('#btn-create-plan');if(btn)setLoading(btn,true);
  try{
    const res=await fetch(API+'/api/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({goal:goal,count:count})});
    if(!res.ok)throw new Error(await res.text());
    const data=await res.json();
    toast('Plan created');
    if(typeof onPlanCreated==='function')onPlanCreated(data);
    return data;
  }catch(e){toast('Plan error: '+e.message,'error');throw e}
  finally{if(btn)setLoading(btn,false)}
}

// === Prepare ===
async function prepareSession(planPath){
  const btn=$('#btn-prepare');if(btn)setLoading(btn,true);
  const bar=$('#prepare-progress .progress-bar');
  if(bar){show($('#prepare-progress'));setProgress(bar,50);bar.classList.add('animated')}
  try{
    const res=await fetch(API+'/api/prepare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan_path:planPath})});
    if(!res.ok)throw new Error(await res.text());
    const data=await res.json();
    if(bar)setProgress(bar,100);
    toast('Session prepared');
    if(typeof onSessionPrepared==='function')onSessionPrepared(data);
    return data;
  }catch(e){toast('Prepare failed: '+e.message,'error');throw e}
  finally{if(btn)setLoading(btn,false);if(bar)bar.classList.remove('animated')}
}

// === Submit Test ===
async function submitTest(sessionId,answers){
  const btn=$('#btn-submit-test');if(btn)setLoading(btn,true);
  try{
    const res=await fetch(API+'/api/test/'+sessionId+'/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({answers:answers})});
    if(!res.ok)throw new Error(await res.text());
    const data=await res.json();
    toast('Test submitted');
    if(typeof onTestSubmitted==='function')onTestSubmitted(data);
    return data;
  }catch(e){toast('Submit failed: '+e.message,'error');throw e}
  finally{if(btn)setLoading(btn,false)}
}

// === Drag and Drop ===
function initUploadZone(zoneSel,inputSel){
  const zone=$(zoneSel),inp=$(inputSel);
  if(!zone)return;
  ['dragenter','dragover'].forEach(function(e){zone.addEventListener(e,function(ev){ev.preventDefault();zone.classList.add('dragover')})});
  ['dragleave','drop'].forEach(function(e){zone.addEventListener(e,function(ev){ev.preventDefault();zone.classList.remove('dragover')})});
  zone.addEventListener('drop',function(ev){const files=ev.dataTransfer.files;if(files.length)uploadFiles(Array.from(files))});
  zone.addEventListener('click',function(){if(inp)inp.click()});
  if(inp)inp.addEventListener('change',function(){if(inp.files.length)uploadFiles(Array.from(inp.files))});
}

// === Audio Player ===
function initAudioPlayers(){
  document.querySelectorAll('.audio-player').forEach(function(p){
    const audio=p.querySelector('audio');
    const name=p.querySelector('.track-name');
    if(audio&&name){audio.addEventListener('loadedmetadata',function(){name.textContent=audio.src.split('/').pop()})}
  });
}

// === Form Validation ===
function validateForm(formSel){
  const form=$(formSel);if(!form)return true;
  let valid=true;
  form.querySelectorAll('[required]').forEach(function(el){
    const err=el.parentElement.querySelector('.field-error');
    if(err)err.remove();
    if(!el.value.trim()){
      valid=false;
      el.style.borderColor='var(--error)';
      const msg=document.createElement('span');msg.className='field-error';msg.style.cssText='color:var(--error);font-size:.75rem';
      msg.textContent='Required';el.parentElement.appendChild(msg);
    }else{el.style.borderColor=''}
  });
  return valid;
}

// === Init ===
document.addEventListener('DOMContentLoaded',function(){
  initUploadZone('.upload-zone','#file-input');
  initAudioPlayers();
});
