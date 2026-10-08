function initCameraWidget(prefix){
 const video=document.getElementById(prefix+"_webcam"), canvas=document.getElementById(prefix+"_canvas"), snap=document.getElementById(prefix+"_snap_btn"), hidden=document.getElementById(prefix+"_camera_data");
 if(!video||!canvas||!snap||!hidden)return;
 let stream=null, ready=false;
 const lang=()=>document.body.dataset.language==="Hindi"?"Hindi":"English";
 const toast=(en,hi,type)=>window.showAppToast?.(lang()==="Hindi"?hi:en,type);
 const fallback=document.createElement('input');fallback.type='file';fallback.accept='image/*';fallback.setAttribute('capture','environment');fallback.hidden=true;document.body.appendChild(fallback);
 fallback.addEventListener('change',()=>{const f=fallback.files?.[0];if(!f)return;const r=new FileReader();r.onload=e=>{hidden.value=e.target.result;const holder=document.getElementById(prefix+'-preview')||document.getElementById(prefix+'_preview');if(holder){holder.innerHTML=`<img src="${e.target.result}" alt="Captured photo">`;holder.style.display='block';}toast('Photo captured. Now check the product.','फोटो तैयार है। अब उत्पाद जांचें।','success')};r.readAsDataURL(f);});
 async function start(){
   if(!navigator.mediaDevices?.getUserMedia){return fallback.click();}
   try{stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'},width:{ideal:1280},height:{ideal:720}},audio:false});video.srcObject=stream;await video.play();ready=true;}
   catch(e){ready=false;}
 }
 start();
 snap.addEventListener('click',()=>{
   if(!ready||!video.videoWidth){toast('Camera is not ready. Opening the device camera instead.','कैमरा तैयार नहीं है। डिवाइस कैमरा खोला जा रहा है।','error');return fallback.click();}
   canvas.width=video.videoWidth;canvas.height=video.videoHeight;canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);hidden.value=canvas.toDataURL('image/jpeg',.9);
   const holder=document.getElementById(prefix+'-preview')||document.getElementById(prefix+'_preview');if(holder){holder.innerHTML=`<img src="${hidden.value}" alt="Captured photo">`;holder.style.display='block';}
   toast('Photo captured. Now check the product.','फोटो तैयार है। अब उत्पाद जांचें।','success');
 });
 window.addEventListener('beforeunload',()=>stream?.getTracks().forEach(t=>t.stop()));
}
