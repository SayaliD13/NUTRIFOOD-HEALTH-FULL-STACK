document.addEventListener("DOMContentLoaded", () => {
  const btn=document.getElementById("lang-toggle"); if(!btn) return;
  const label=document.getElementById("lang-label");
  let language=document.body.dataset.language || "English";
  const originals=new Map();
  const dictionary={
    "Dashboard":"डैशबोर्ड","Meal Scan":"मील स्कैन","Packed Food":"पैकेज्ड फूड","Compare Products":"उत्पाद तुलना",
    "Fitness & Scale":"फिटनेस और स्केल","Diary":"डायरी","Allergy Alert":"एलर्जी अलर्ट","Edit Profile":"प्रोफाइल संपादित करें",
    "Log out":"लॉग आउट","Health Assistant":"हेल्थ असिस्टेंट","Ask questions about this page":"इस पेज के बारे में सवाल पूछें",
    "Hello. Ask me a question about food, nutrition, fitness or safety.":"नमस्ते। भोजन, पोषण, फिटनेस या सुरक्षा से जुड़ा सवाल पूछें।",
    "Search NutriFood":"NutriFood खोजें","Personal health space":"व्यक्तिगत स्वास्थ्य स्थान","PERSONAL HEALTH WORKSPACE":"व्यक्तिगत स्वास्थ्य कार्यक्षेत्र",
    "Review your food, fitness and personal health activity in one place.":"अपने भोजन, फिटनेस और स्वास्थ्य गतिविधि को एक ही जगह देखें।",
    "DAILY HEALTH TIP":"दैनिक स्वास्थ्य सुझाव","Health workspace":"स्वास्थ्य कार्यक्षेत्र","Edit profile":"प्रोफाइल संपादित करें"
  };
  function applyStatic(){
    document.querySelectorAll("[data-i18n]").forEach(el=>{
      if(!el.dataset.originalText) el.dataset.originalText=el.textContent;
      const key=el.dataset.originalText.trim();
      el.textContent=language==="Hindi"?(dictionary[key]||el.dataset.originalText):el.dataset.originalText;
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(el=>{
      if(!el.dataset.originalPlaceholder) el.dataset.originalPlaceholder=el.placeholder;
      el.placeholder=language==="Hindi"?"अपना प्रश्न या खोज लिखें...":el.dataset.originalPlaceholder;
    });
  }
  async function translateDynamic(){
    if(language==="English") return;
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,{acceptNode(node){
      const p=node.parentElement; if(!p||["SCRIPT","STYLE","NOSCRIPT","INPUT","TEXTAREA","SELECT","OPTION"].includes(p.tagName)||p.closest(".brand,.user-pill,[data-no-translate],.chat-fab,[data-i18n]")) return NodeFilter.FILTER_REJECT;
      const text=node.nodeValue.replace(/\s+/g," ").trim(); if(!text||text.length<3||/^[\d\W]+$/.test(text)||/[\u0900-\u097F]/.test(text)) return NodeFilter.FILTER_REJECT; return NodeFilter.FILTER_ACCEPT;
    }});
    const nodes=[];let n;while(n=walker.nextNode())nodes.push(n);
    nodes.forEach(n=>{if(!originals.has(n)) originals.set(n,n.nodeValue);});
    const texts=nodes.map(n=>n.nodeValue.replace(/\s+/g," ").trim());
    for(let i=0;i<texts.length;i+=40){
      try{const r=await fetch("/api/translate-batch",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({texts:texts.slice(i,i+40)})});const d=await r.json();(d.translations||[]).forEach((t,j)=>{if(nodes[i+j])nodes[i+j].nodeValue=nodes[i+j].nodeValue.replace(texts[i+j],t);});}catch(_){break;}
    }
  }
  function restore(){originals.forEach((v,n)=>{if(n.parentNode)n.nodeValue=v;});}
  async function apply(){document.documentElement.lang=language==="Hindi"?"hi":"en";document.body.dataset.language=language; if(language==="English")restore(); applyStatic(); if(language==="Hindi")await translateDynamic(); label.textContent=language==="English"?"Hindi":"English";}
  btn.addEventListener("click",async()=>{btn.disabled=true;language=language==="English"?"Hindi":"English";try{await fetch("/api/language",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({language})});await apply();}finally{btn.disabled=false;}});
  apply();
});
