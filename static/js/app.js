(function(){
const drawer=document.getElementById("side-drawer"), overlay=document.getElementById("drawer-overlay");
function toggleDrawer(open){if(drawer)drawer.classList.toggle("open",open);if(overlay)overlay.classList.toggle("show",open)}
document.getElementById("drawer-toggle")?.addEventListener("click",()=>toggleDrawer(true));
document.getElementById("drawer-close")?.addEventListener("click",()=>toggleDrawer(false));
overlay?.addEventListener("click",()=>toggleDrawer(false));

window.showAppToast=function(message,type="success"){
 let stack=document.querySelector(".toast-stack"); if(!stack){stack=document.createElement("div");stack.className="toast-stack";document.body.appendChild(stack)}
 const el=document.createElement("div");el.className="toast "+type;el.innerHTML=`<i class="fa-solid ${type==="success"?"fa-circle-check":"fa-circle-exclamation"}"></i>${message}`;
 stack.appendChild(el);setTimeout(()=>el.remove(),4500);
};

window.openReminderSettings=function(){
 const old=document.getElementById("reminder-modal"); if(old)old.remove();
 const saved=JSON.parse(localStorage.getItem("nf_reminders")||"{}");
 const modal=document.createElement("div");modal.className="reminder-modal";modal.id="reminder-modal";
 modal.innerHTML=`<div class="reminder-card"><button class="icon-button close-rem"><i class="fa-solid fa-xmark"></i></button><span class="eyebrow">PERSONAL REMINDERS</span><h2>Set a gentle reminder</h2><p class="muted">Keep the browser page open for on-screen reminders.</p>
 <label>Reminder type</label><select id="rem-type"><option value="water">Water</option><option value="meal">Meal time</option></select>
 <label>Every (minutes)</label><input id="rem-min" type="number" min="15" value="${saved.minutes||60}">
 <div class="form-actions"><button class="ghost-button close-rem">Cancel</button><button class="primary-button" id="save-rem"><i class="fa-regular fa-bell"></i> Save reminder</button></div></div>`;
 document.body.appendChild(modal);
 modal.querySelectorAll(".close-rem").forEach(x=>x.onclick=()=>modal.remove());
 modal.querySelector("#save-rem").onclick=()=>{const minutes=Math.max(15,Number(modal.querySelector("#rem-min").value)||60);localStorage.setItem("nf_reminders",JSON.stringify({minutes,type:modal.querySelector("#rem-type").value,next:Date.now()+minutes*60000}));modal.remove();showAppToast("Reminder saved. Browser page open rakho for alerts.","success");};
};
function checkReminder(){const r=JSON.parse(localStorage.getItem("nf_reminders")||"null");if(!r||!r.next)return;if(Date.now()>=r.next){showAppToast(r.type==="water"?"Time for some water.":"Meal time check: choose a balanced meal.","success");r.next=Date.now()+Number(r.minutes||60)*60000;localStorage.setItem("nf_reminders",JSON.stringify(r));}}
setInterval(checkReminder,15000);checkReminder();
})();
// Global product-style search across the health workspace.
(function(){
  const input=document.getElementById("global-search-input"), box=document.getElementById("global-search-results");
  if(!input||!box) return;
  let timer=null;
  function close(){box.classList.remove("show");box.innerHTML="";}
  async function search(){
    const q=input.value.trim(); if(q.length<2){close();return;}
    try{
      const r=await fetch(`/search?q=${encodeURIComponent(q)}`); const d=await r.json();
      box.innerHTML="";
      if(!d.results?.length){box.innerHTML=`<div class="search-empty">${document.body.dataset.language==="Hindi"?"कोई परिणाम नहीं मिला।":"No matching section found."}</div>`;box.classList.add("show");return;}
      d.results.forEach(item=>{
        const a=document.createElement("a"); a.href=item.url; a.className="search-result";
        a.innerHTML=`<span class="search-result-icon"><i class="fa-solid ${item.icon}"></i></span><span><b></b><small></small></span>`;
        a.querySelector("b").textContent=item.title; a.querySelector("small").textContent=item.description; box.appendChild(a);
      });
      box.classList.add("show");
    }catch(_){close();}
  }
  input.addEventListener("input",()=>{clearTimeout(timer);timer=setTimeout(search,180);});
  input.addEventListener("focus",()=>{if(input.value.trim().length>=2) search();});
  document.addEventListener("click",e=>{if(!document.getElementById("global-search")?.contains(e.target)) close();});
})();
