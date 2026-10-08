document.addEventListener("DOMContentLoaded",()=>{
  const fab=document.getElementById("chat-fab"),panel=document.getElementById("chat-panel"),close=document.getElementById("chat-close"),
        form=document.getElementById("chat-form"),input=document.getElementById("chat-input"),messages=document.getElementById("chat-messages"),
        imageInput=document.getElementById("chat-image"),imageBtn=document.getElementById("chat-image-btn"),micBtn=document.getElementById("chat-mic-btn"),
        stopBtn=document.getElementById("chat-stop-speech"),attachment=document.getElementById("chat-attachment-preview"),
        widget=document.querySelector(".chat-widget"),baseContext=widget?.dataset.context||"General nutrition and fitness";
  let selectedImage=null,lastImage=null,history=[],currentAudio=null,busy=false;
  const language=()=>document.body.dataset.language||"English";
  const toast=(en,hi,type)=>window.showAppToast?.(language()==="Hindi"?hi:en,type);
  fab?.addEventListener("click",()=>panel.classList.toggle("open"));close?.addEventListener("click",()=>panel.classList.remove("open"));
  stopBtn?.addEventListener("click",()=>{window.speechSynthesis?.cancel();currentAudio?.pause();currentAudio=null;});
  imageBtn?.addEventListener("click",()=>imageInput?.click());
  function showAttachment(file){
    if(!attachment)return;attachment.innerHTML="";
    if(file){const img=document.createElement("img");img.src=URL.createObjectURL(file);img.alt=language()==="Hindi"?"जोड़ी गई इमेज":"Attached image";attachment.appendChild(img);}
    else if(lastImage){const s=document.createElement("span");s.textContent=language()==="Hindi"?"पिछली इमेज उपलब्ध है":"Previous image is available";attachment.appendChild(s);}
  }
  imageInput?.addEventListener("change",()=>{selectedImage=imageInput.files?.[0]||null;if(selectedImage)lastImage=selectedImage;showAttachment(selectedImage);});
  function fallbackSpeak(text){if(!window.speechSynthesis)return;window.speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(text);u.lang=language()==="Hindi"?"hi-IN":"en-IN";u.rate=.96;window.speechSynthesis.speak(u);}
  async function speak(text){try{const r=await fetch("/api/speak",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({text,language:language()})});if(!r.ok)throw new Error("tts");const blob=await r.blob();if(currentAudio){currentAudio.pause();}currentAudio=new Audio(URL.createObjectURL(blob));await currentAudio.play();}catch(e){fallbackSpeak(text);}}
  function addBubble(text,type){const b=document.createElement("div");b.className="chat-bubble "+type;b.textContent=text;messages.appendChild(b);messages.scrollTop=messages.scrollHeight;return b;}
  function pageContext(){
    let extra="";
    document.querySelectorAll(".result-card,.compare-result,.comparison-banner").forEach(el=>{const t=el.innerText?.trim();if(t)extra+="\n"+t.slice(0,5000);});
    return baseContext+(extra?"\nCurrent page result:\n"+extra:"");
  }
  function pageImage(){return document.querySelector(".result-card .result-image, .compare-result .result-image")?.getAttribute("src")||"";}
  async function sendMessage(msgOverride=""){
    if(busy)return;
    const msg=(msgOverride||input.value||"").trim();const imageForTurn=selectedImage||lastImage;const existingPageImage=pageImage();
    if(!msg&&!imageForTurn&&!existingPageImage)return;
    const displayText=msg||(language()==="Hindi"?"इस इमेज का विस्तार से विश्लेषण करें।":"Analyze this image in detail.");
    addBubble(displayText,"user");input.value="";const pending=addBubble(language()==="Hindi"?"उत्तर तैयार किया जा रहा है...":"Preparing your answer...","bot");busy=true;
    const fd=new FormData();fd.append("message",msg);fd.append("context",pageContext());fd.append("language",language());fd.append("history",JSON.stringify(history.slice(-12)));if(existingPageImage)fd.append("page_image",existingPageImage);if(imageForTurn)fd.append("image",imageForTurn);
    try{const r=await fetch("/api/chat",{method:"POST",body:fd});let d={};try{d=await r.json()}catch(e){}if(!r.ok||!d.answer)throw new Error(d.error||"request failed");const answer=d.answer.trim();pending.textContent=answer;history.push({role:"user",content:displayText});history.push({role:"assistant",content:answer});history=history.slice(-12);speak(answer);}
    catch(err){pending.textContent=language()==="Hindi"?"अभी उत्तर नहीं मिल सका। कृपया फिर प्रयास करें।":"I could not get the answer right now. Please try again.";}
    finally{busy=false;selectedImage=null;if(imageInput)imageInput.value="";showAttachment(null);}
  }
  form?.addEventListener("submit",e=>{e.preventDefault();sendMessage();});
  let recorder=null,recordedChunks=[],recordingTimer=null;
  async function transcribeBlob(blob){
    const fd=new FormData();fd.append("audio",blob,"voice.webm");
    const r=await fetch("/api/transcribe",{method:"POST",body:fd});
    let d={};try{d=await r.json()}catch(e){}
    if(!r.ok||!d.text)throw new Error(d.error||"transcription failed");
    return String(d.text).trim();
  }
  function fallbackVoice(){
    const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
    if(!SR){toast("Voice input is not available in this browser. Please type your question.","इस ब्राउज़र में वॉइस इनपुट उपलब्ध नहीं है। कृपया प्रश्न लिखें।","error");return;}
    const rec=new SR();rec.lang=language()==="Hindi"?"hi-IN":"en-IN";rec.interimResults=false;rec.continuous=false;micBtn.classList.add("recording");
    rec.onresult=e=>{const text=e.results?.[0]?.[0]?.transcript?.trim();if(text){input.value=text;sendMessage(text);}};
    rec.onerror=()=>toast("Voice could not be understood. Please try again.","वॉइस समझ नहीं आया। कृपया फिर बोलें।","error");
    rec.onend=()=>micBtn.classList.remove("recording");
    try{rec.start()}catch(e){micBtn.classList.remove("recording");toast("Voice could not start. Please try again.","वॉइस शुरू नहीं हो सका। कृपया फिर प्रयास करें।","error");}
  }
  async function stopRecording(){
    if(!recorder||recorder.state==="inactive")return;
    clearTimeout(recordingTimer);recorder.stop();
  }
  micBtn?.addEventListener("click",async()=>{
    if(busy)return;
    if(recorder&&recorder.state==="recording"){await stopRecording();return;}
    if(!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==="undefined"){fallbackVoice();return;}
    try{
      const stream=await navigator.mediaDevices.getUserMedia({audio:true});
      const preferred=["audio/webm;codecs=opus","audio/webm","audio/ogg;codecs=opus"].find(t=>MediaRecorder.isTypeSupported?.(t));
      recorder=new MediaRecorder(stream,preferred?{mimeType:preferred}:undefined);recordedChunks=[];
      recorder.ondataavailable=e=>{if(e.data?.size)recordedChunks.push(e.data)};
      recorder.onstop=async()=>{
        stream.getTracks().forEach(t=>t.stop());micBtn.classList.remove("recording");
        const blob=new Blob(recordedChunks,{type:recorder.mimeType||"audio/webm"});recorder=null;
        try{toast(language()==="Hindi"?"वॉइस समझी जा रही है...":"Transcribing your voice...","वॉइस समझी जा रही है...","success");const text=await transcribeBlob(blob);if(text){input.value=text;sendMessage(text);}}
        catch(e){fallbackVoice();}
      };
      recorder.start();micBtn.classList.add("recording");toast(language()==="Hindi"?"बोलना शुरू करें। 8 सेकंड बाद रिकॉर्डिंग अपने आप रुक जाएगी।":"Start speaking. Recording stops automatically after 8 seconds.","बोलना शुरू करें। 8 सेकंड बाद रिकॉर्डिंग अपने आप रुक जाएगी।","success");
      recordingTimer=setTimeout(stopRecording,8000);
    }catch(e){fallbackVoice();}
  });
});
