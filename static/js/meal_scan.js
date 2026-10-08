document.addEventListener("DOMContentLoaded",()=>{
 const form=document.querySelector('.scan-input-panel form');
 const file=document.getElementById("meal-file"), strip=document.getElementById("meal-preview-strip"), hidden=document.getElementById("meal_camera_data");
 const lang=()=>document.body.dataset.language==="Hindi"?"hi-IN":"en-IN";
 const toast=(msg,type)=>window.showAppToast?.(msg,type);
 file?.addEventListener("change",()=>{if(!strip)return;strip.innerHTML="";[...file.files].slice(0,3).forEach(f=>{const r=new FileReader();r.onload=e=>{const img=document.createElement("img");img.src=e.target.result;img.alt="Selected food";img.title=f.name;strip.appendChild(img)};r.readAsDataURL(f)});});
 const video=document.getElementById("meal_webcam"),canvas=document.getElementById("meal_canvas"),snap=document.getElementById("meal_snap_btn");
 let stream=null, cameraReady=false;
 const fallbackInput=document.createElement('input');
 fallbackInput.type='file'; fallbackInput.accept='image/*'; fallbackInput.setAttribute('capture','environment'); fallbackInput.hidden=true;
 document.body.appendChild(fallbackInput);
 fallbackInput.addEventListener('change',()=>{const f=fallbackInput.files?.[0];if(!f)return;if(file){const dt=new DataTransfer();dt.items.add(f);file.files=dt.files;}const r=new FileReader();r.onload=e=>{if(hidden)hidden.value='';if(strip)strip.innerHTML=`<img src="${e.target.result}" alt="Camera capture">`;toast(document.body.dataset.language==="Hindi"?"फोटो तैयार है। अब विश्लेषण करें।":"Photo captured. Start the analysis.","success")};r.readAsDataURL(f);});
 async function startCamera(){
   if(!video||!canvas||!snap||!hidden)return;
   if(!navigator.mediaDevices?.getUserMedia){toast(document.body.dataset.language==="Hindi"?"इस डिवाइस पर कैमरा सीधे उपलब्ध नहीं है।":"Direct camera access is unavailable. Opening the device camera instead.","error");return fallbackInput.click();}
   try{stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1280},height:{ideal:720}},audio:false});video.srcObject=stream;await video.play();cameraReady=true;snap.disabled=false;}
   catch(err){cameraReady=false;toast(document.body.dataset.language==="Hindi"?"कैमरा अनुमति नहीं मिली। कैमरा खोलने के लिए फिर बटन दबाएँ।":"Camera permission was not granted. Press Capture again to open the device camera.","error");}
 }
 startCamera();
 snap?.addEventListener('click',()=>{
   if(!cameraReady||!video?.videoWidth){fallbackInput.click();return;}
   canvas.width=video.videoWidth;canvas.height=video.videoHeight;canvas.getContext("2d").drawImage(video,0,0,canvas.width,canvas.height);
   hidden.value=canvas.toDataURL("image/jpeg",.9);if(strip)strip.innerHTML=`<img src="${hidden.value}" alt="Camera capture">`;
   toast(document.body.dataset.language==="Hindi"?"फोटो तैयार है। अब विश्लेषण करें।":"Photo captured. Start the analysis.","success");
 });
 window.addEventListener("beforeunload",()=>stream?.getTracks().forEach(t=>t.stop()));
 const voice=document.getElementById("voice-btn"),input=document.getElementById("meal-text");
 const Speech=window.SpeechRecognition||window.webkitSpeechRecognition;
 let recorder=null,recordedChunks=[],recordingTimer=null;
 async function transcribeBlob(blob){const fd=new FormData();fd.append("audio",blob,"meal-voice.webm");const r=await fetch("/api/transcribe",{method:"POST",body:fd});let d={};try{d=await r.json()}catch(e){}if(!r.ok||!d.text)throw new Error(d.error||"transcription failed");return String(d.text).trim();}
 function fallbackVoice(){
   if(!voice||!input||!Speech){toast(document.body.dataset.language==="Hindi"?"इस ब्राउज़र में वॉइस इनपुट उपलब्ध नहीं है। कृपया भोजन का नाम लिखें।":"Voice input is not available in this browser. Please type the food name.","error");return;}
   const rec=new Speech();rec.lang=lang();rec.interimResults=false;rec.continuous=false;voice.classList.add("listening");
   rec.onresult=e=>{const text=e.results?.[0]?.[0]?.transcript?.trim();if(text){input.value=text;toast(document.body.dataset.language==="Hindi"?"वॉइस समझ लिया गया। विश्लेषण शुरू हो रहा है।":"Voice understood. Starting analysis.","success");setTimeout(()=>form?.requestSubmit(),100);}};
   rec.onerror=()=>toast(document.body.dataset.language==="Hindi"?"वॉइस समझ नहीं आया। कृपया फिर बोलें।":"Voice could not be understood. Please try again.","error");
   rec.onend=()=>voice.classList.remove("listening");try{rec.start()}catch(e){voice.classList.remove("listening");}
 }
 async function stopRecording(){if(!recorder||recorder.state==="inactive")return;clearTimeout(recordingTimer);recorder.stop();}
 voice?.addEventListener("click",async()=>{
   if(recorder&&recorder.state==="recording"){await stopRecording();return;}
   if(!navigator.mediaDevices?.getUserMedia||typeof MediaRecorder==="undefined"){fallbackVoice();return;}
   try{
     const stream=await navigator.mediaDevices.getUserMedia({audio:true});
     const preferred=["audio/webm;codecs=opus","audio/webm","audio/ogg;codecs=opus"].find(t=>MediaRecorder.isTypeSupported?.(t));
     recorder=new MediaRecorder(stream,preferred?{mimeType:preferred}:undefined);recordedChunks=[];
     recorder.ondataavailable=e=>{if(e.data?.size)recordedChunks.push(e.data)};
     recorder.onstop=async()=>{
       stream.getTracks().forEach(t=>t.stop());voice.classList.remove("listening");
       const blob=new Blob(recordedChunks,{type:recorder.mimeType||"audio/webm"});recorder=null;
       try{toast(document.body.dataset.language==="Hindi"?"वॉइस समझी जा रही है...":"Transcribing your voice...","success");const text=await transcribeBlob(blob);if(text){input.value=text;toast(document.body.dataset.language==="Hindi"?"वॉइस समझ लिया गया। विश्लेषण शुरू हो रहा है।":"Voice understood. Starting analysis.","success");setTimeout(()=>form?.requestSubmit(),100);}}
       catch(e){fallbackVoice();}
     };
     recorder.start();voice.classList.add("listening");toast(document.body.dataset.language==="Hindi"?"बोलना शुरू करें। 8 सेकंड बाद रिकॉर्डिंग अपने आप रुक जाएगी।":"Start speaking. Recording stops automatically after 8 seconds.","success");recordingTimer=setTimeout(stopRecording,8000);
   }catch(e){fallbackVoice();}
 });
});
