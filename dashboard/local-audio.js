'use strict';
// Explicit local file import; no provider connection or credential fields.
const localAudio={epoch:0,job:null,jobEpoch:0,pending:null};
function localAudioForm(){return {audio:$('local-audio-file').files?.[0],alignment:$('local-audio-alignment').files?.[0],approved_by:$('local-audio-approved-by').value,rights_note:$('local-audio-rights-note').value,rights_confirmed:$('local-audio-rights').checked,spans:$('local-audio-spans').value};}
function localAudioValid(){const f=localAudioForm();return !!f.audio&&f.audio.size>=100&&f.audio.size<=12*1024*1024&&!!f.alignment&&f.alignment.size<=100000&&!!f.approved_by.trim()&&f.approved_by.length<=200&&!!f.rights_note.trim()&&f.rights_note.length<=1000&&f.rights_confirmed;}
function localAudioControls(){const supported=state.job?.id===localAudio.job&&state.job?.payload?.format?.adapter==='account-pack'&&!state.job.payload.audio_revision&&!state.job.payload.edit_revision&&!state.job.payload.raster_revision;$('local-audio-step').hidden=!supported;$('local-audio-submit').disabled=!supported||!!localAudio.pending||!localAudioValid();$('local-audio-form').setAttribute('aria-busy',String(!!localAudio.pending));}
function localAudioJobChanged(job){if(localAudio.job===job?.id&&localAudio.jobEpoch===state.jobEpoch){localAudioControls();return;}localAudio.epoch++;localAudio.job=job?.id||null;localAudio.jobEpoch=state.jobEpoch;for(const id of ['local-audio-file','local-audio-alignment','local-audio-approved-by','local-audio-rights-note','local-audio-spans'])$(id).value='';$('local-audio-rights').checked=false;$('local-audio-status').textContent='';$('local-audio-step').open=false;localAudioControls();}
function localAudioCurrent(snapshot){const f=localAudioForm(),s=snapshot.form;return localAudio.epoch===snapshot.epoch&&state.jobEpoch===snapshot.jobEpoch&&state.job?.id===snapshot.job&&f.audio===s.audio&&f.alignment===s.alignment&&f.approved_by===s.approved_by&&f.rights_note===s.rights_note&&f.rights_confirmed===s.rights_confirmed&&f.spans===s.spans;}
function localAudioChanged(clearRights){localAudio.epoch++;if(clearRights)$('local-audio-rights').checked=false;$('local-audio-status').textContent=localAudio.pending?'Seçim değişti; eski yanıt görünümü değiştirmeyecek.':'';localAudioControls();}
['local-audio-file','local-audio-alignment'].forEach(id=>$(id).addEventListener('change',()=>localAudioChanged(true)));
['local-audio-approved-by','local-audio-rights-note','local-audio-spans'].forEach(id=>$(id).addEventListener('input',()=>localAudioChanged(true)));
$('local-audio-rights').addEventListener('change',()=>localAudioChanged(false));
$('local-audio-form').addEventListener('submit',async event=>{
 event.preventDefault();if(localAudio.pending)return;if(!localAudioValid()||state.job?.id!==localAudio.job){$('local-audio-status').textContent='Ses, exact metne bağlı timing JSON ve kullanım hakkı onayı gerekiyor.';return;}
 const snapshot={epoch:localAudio.epoch,job:localAudio.job,jobEpoch:state.jobEpoch,form:localAudioForm()};localAudio.pending=snapshot;localAudioControls();$('local-audio-status').textContent='Yerel dosyalar doğrulanıyor; API veya render çağrısı yok.';
 try{
  const bytes=await snapshot.form.audio.arrayBuffer();if(!localAudioCurrent(snapshot))return;
  const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');if(!localAudioCurrent(snapshot))return;
  const alignment=JSON.parse(await snapshot.form.alignment.text());if(!localAudioCurrent(snapshot))return;
  const spans=snapshot.form.spans.trim()?JSON.parse(snapshot.form.spans):null,container=snapshot.form.audio.name.split('.').pop().toLowerCase();if(!['mp3','wav','m4a'].includes(container))throw Error('MP3/WAV/M4A dosyası seçin.');
  let binary='';const data=new Uint8Array(bytes);for(let i=0;i<data.length;i+=16384)binary+=String.fromCharCode(...data.subarray(i,i+16384));const encoded=btoa(binary);if(!localAudioCurrent(snapshot))return;
  const result=await api('/api/jobs/'+snapshot.job+'/audio-import',{audio_base64:encoded,container,expected_audio_sha256:hash,alignment,approved_by:snapshot.form.approved_by,rights_note:snapshot.form.rights_note,rights_confirmed:true,scene_word_spans:spans,viseme_required:false});
  if(!localAudioCurrent(snapshot))return;if(!/^[a-f0-9]{24}$/.test(result.child_job||'')||result.child_job===snapshot.job||result.parent_job!==snapshot.job||result.job?.id!==result.child_job||result.publication_ready!==false)throw Error('Yerel ses revizyonu yanıtı doğrulanamadı.');
  await refreshJobs();if(!localAudioCurrent(snapshot))return;await selectJob(result.child_job);notice('Yerel ses ve taze kelime/sahne/altyazı zamanı yeni işe bağlandı. Hazırla ve render ayrı eylemlerdir; insan dinleme kabulü bekler.');
 }catch(error){if(localAudioCurrent(snapshot))$('local-audio-status').textContent=error.message||'Yerel import tamamlanmadı; otomatik tekrar yapılmadı.';}
 finally{if(localAudio.pending===snapshot)localAudio.pending=null;localAudioControls();}
});
