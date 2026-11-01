// Saved protected preparations only. No polling, provider calls or browser storage.
globalThis.StoryMotionFamilyRender={connect({get,request,currentAccount}){
 const records=new Map(),active=new Set(['queued','running','cancel_requested']);
 const retryable=new Set(['failed','cancelled','blocked_runtime','invalidated','failed_before_start','interrupted_unconfirmed']);
 const states=new Set(['not_started',...active,...retryable,'complete']);
 const labels={not_started:'Render başlatılmadı',queued:'Kuyrukta',running:'Yerel render çalışıyor',cancel_requested:'İptal istendi',cancelled:'İptal edildi',failed:'Render başarısız',blocked_runtime:'Runtime hazır değil',invalidated:'Çıktı doğrulaması geçersiz',failed_before_start:'İşçi başlatılamadı',interrupted_unconfirmed:'Tamamlanma doğrulanamadı',complete:'Tamamlandı'};
 const hex=(v,n)=>typeof v==='string'&&new RegExp('^[a-f0-9]{'+n+'}$').test(v);
 const record=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
 let selected=null,epoch=0,operation=null;
 const files=get('family-render-files'),ack=get('family-render-ack');
 function current(r,e){return selected===r&&epoch===e&&currentAccount()===r.binding.account;}
 function url(r){return '/api/family-renders/'+r.binding.account+'/'+r.binding.job;}
 function receipt(value,r){
  const b=r.binding;
  if(!record(value)||value.account!==b.account||value.prepare_job!==b.job||value.engine!==b.engine
   ||!hex(value.preparation_revision,64)||!hex(value.execution_binding,64)||typeof value.source_current!=='boolean'
   ||!states.has(value.status)||!Number.isSafeInteger(value.generation)||value.generation<0
   ||value.provider_calls!==0||value.publication_ready!==false&&!(value.status==='not_started'&&value.publication_ready===undefined)
   ||!Array.isArray(value.files)||typeof value.actual_render!=='boolean')throw Error('Render yanıtının kayıt/motor bağı geçersiz.');
  if(r.pins&&(value.preparation_revision!==r.pins.preparation_revision||value.execution_binding!==r.pins.execution_binding))throw Error('Kayıtlı hazırlığın render bağı değişti; kaynağı yeniden doğrulayın.');
  if(value.status==='not_started'){
   if(value.generation!==0||value.actual_render||value.files.length||value.attempt!==undefined||value.request_key!==undefined||value.ref!==undefined||value.previous_attempt!==undefined)throw Error('Geçersiz başlangıç durumu.');
  }else{
   if(value.generation<1||!hex(value.attempt,32)||!hex(value.request_key,32)||!record(value.ref)
    ||value.ref.kind!=='family_render'||value.ref.account!==b.account||value.ref.prepare_job!==b.job
    ||value.ref.id!==value.attempt||value.ref.generation!==value.generation
    ||!(value.previous_attempt===null||hex(value.previous_attempt,32))
    ||value.output_profile!=='silent-1080x1920-540x960-30fps-v1')throw Error('Geçersiz render girişimi bağı.');
  }
  if(value.status==='complete'){
   if(value.actual_render!==true||value.files.length!==2||new Set(value.files.map(f=>f?.name)).size!==2)throw Error('Tamamlanmış çıktı doğrulaması eksik.');
   const prefix='/family-render-files/'+b.account+'/'+b.job+'/'+value.attempt+'/';
   for(const f of value.files)if(!record(f)||!['render-1080.mp4','render-mobile.mp4'].includes(f.name)||!hex(f.sha256,64)
    ||typeof f.download_url!=='string'||!f.download_url.startsWith(prefix)||!hex(f.download_url.slice(prefix.length),64))throw Error('Geçersiz doğrulanmış MP4 bağlantısı.');
  }else if(value.actual_render||value.files.length)throw Error('Tamamlanmamış iş çıktı sunamaz.');
  return value;
 }
 function confirms(row,intent){
  const d=intent.data;
  if(row.engine!==d.engine)return false;
  if(intent.action==='cancel')return row.attempt===d.attempt&&row.generation===d.generation&&row.request_key===intent.requestKey
   &&!['not_started','queued','running'].includes(row.status);
  return row.preparation_revision===d.preparation_revision&&row.execution_binding===d.execution_binding
   &&row.generation===d.expected_generation+1&&row.request_key===d.request_key
   &&row.previous_attempt===(d.previous_attempt??null)&&row.attempt!==d.previous_attempt;
 }
 function paint(){
  files.replaceChildren();const r=selected,row=r?.row,busy=Boolean(operation||r?.reading);
  get('family-render-panel').hidden=!r;
  for(const id of ['start','retry','cancel'])get('family-render-'+id).disabled=true;
  get('family-render-refresh').disabled=!r||busy;ack.disabled=!r||busy;
  if(!r)return;
  const b=r.binding;get('family-render-binding').textContent=b.account+' · '+b.family+' · '+b.engine+' · kayıt '+b.job;
  get('family-render-status').textContent=r.notice||(row?labels[row.status]+' · '+(row.generation?'girişim '+row.attempt+' · deneme #'+row.generation:'Runtime başlatmada kontrol edilir.'):'Kayıtlı render durumunu yenileyin.');
  get('family-render-start').textContent=r.intent?.action==='start'?'Aynı başlangıç isteğini tekrar gönder':'Yerel sessiz render başlat';
  get('family-render-retry').textContent=r.intent?.action==='retry'?'Aynı yeniden deneme isteğini gönder':'Yeni render girişimi oluştur';
  if(!busy&&r.intent){
   if(!r.conflict)get('family-render-'+r.intent.action).disabled=r.intent.action!=='cancel'&&(!ack.checked||r.row?.source_current===false);
  }else if(!busy&&r.confirmed&&row){
   get('family-render-start').disabled=!(row.status==='not_started'&&row.source_current&&ack.checked);
   get('family-render-retry').disabled=!(retryable.has(row.status)&&row.source_current&&row.generation<Number.MAX_SAFE_INTEGER&&ack.checked);
   get('family-render-cancel').disabled=!active.has(row.status);
  }
  if(r.confirmed&&!r.intent&&row?.status==='complete')for(const f of row.files){
   const li=document.createElement('li'),a=document.createElement('a');a.href=f.download_url;a.textContent=f.name+' · doğrulanmış dosyayı indir';a.setAttribute('download',f.name);li.append(a);files.append(li);
  }
 }
 function clear(){epoch++;selected=null;ack.checked=false;paint();}
 function bind(row){
  clear();if(row.account!==currentAccount()||row.artifacts_status!=='verified'||row.prepare_status!=='complete')return;
  const binding={account:row.account,job:row.job,engine:row.engine,family:row.family};
  if(!/^[a-z][a-z0-9-]{0,59}$/.test(binding.account)||!hex(binding.job,24)||!['hyperframes','remotion'].includes(binding.engine))return;
  const key=JSON.stringify([binding.account,binding.job,binding.engine]);let r=records.get(key);
  if(!r){r={binding,seq:0,intent:null};records.set(key,r);}
  r.binding=binding;r.row=null;r.confirmed=false;r.reading=false;r.notice='Kayıtlı render durumunu yenileyin. Editör taslağı bu işlemde kullanılmaz.';selected=r;paint();
 }
 async function refresh(){
  const r=selected;if(!r||operation||r.reading||currentAccount()!==r.binding.account)return;
  const e=epoch,ticket=++r.seq;r.reading=true;r.confirmed=false;r.notice='Render durumu okunuyor; yeni iş başlatılmaz.';paint();
  try{
   const path=r.intent?.action==='cancel'?url(r)+'/attempts/'+r.intent.data.attempt:url(r);
   const value=await request(path);if(!current(r,e)||ticket!==r.seq)return;
   const row=receipt(value,r);r.pins={preparation_revision:row.preparation_revision,execution_binding:row.execution_binding};r.row=row;r.confirmed=true;r.notice='';r.conflict=false;
   if(r.intent){
    if(confirms(row,r.intent)){r.intent=null;ack.checked=false;}
    else{
     r.conflict=r.intent.action!=='cancel'&&row.generation>r.intent.data.expected_generation;
     r.notice=r.conflict?'Başka girişim/istek görüldü; belirsiz istek yeniden gönderilmedi. Durumu ayrıca inceleyin.':'Önceki işlem henüz doğrulanmadı. Otomatik tekrar yok; aynı isteği açıkça gönderebilirsiniz.';
    }
   }
   if(row.status==='blocked_runtime')r.notice='Runtime hazır değil. Kurulum veya başka motora geçiş yapılmadı; hazır olduğunda yeni girişimi açıkça onaylayın.';
   if(row.status==='interrupted_unconfirmed')r.notice='Önceki işin tamamlandığı doğrulanamadı. Otomatik devam yok; yeni girişim ayrıca onay ister.';
   if(!row.source_current)r.notice='Kaynak hazırlığı güncel değil; yeni render için kaynağı yeniden hazırlayın. Geçmiş çıktıların doğrulaması ayrıca yapılır.';
  }catch(error){if(current(r,e)&&ticket===r.seq){r.confirmed=false;r.notice='Durum okunamadı; tekrar yenileyin. '+error.message;}}
  finally{if(ticket===r.seq)r.reading=false;if(current(r,e))paint();}
 }
 function requestKey(){const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);return Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');}
 async function act(action){
  const r=selected;if(!r||operation||r.reading||currentAccount()!==r.binding.account||get('family-render-'+action).disabled)return;
  if(!r.intent){
   const row=r.row;if(!r.confirmed||!row)return;
   let data;try{data=action==='cancel'?{engine:row.engine,attempt:row.attempt,generation:row.generation}:
    {engine:row.engine,preparation_revision:row.preparation_revision,execution_binding:row.execution_binding,request_key:requestKey(),expected_generation:row.generation,ack_local_render:true,...(action==='retry'?{previous_attempt:row.attempt}:{})};
   }catch{r.notice='Güvenli istek kimliği oluşturulamadı; işlem gönderilmedi.';paint();return;}
   r.intent={action,data,requestKey:row.request_key};
  }
  if(r.intent.action!==action||r.conflict)return;
  const intent=r.intent,e=epoch,ticket=++r.seq,op={r,ticket};operation=op;r.confirmed=false;r.notice='Yerel '+action+' isteği gönderiliyor; otomatik tekrar yok.';paint();
  try{
   const value=await request(url(r)+'/'+action,intent.data);if(!current(r,e)||ticket!==r.seq)return;
   const row=receipt(value,r);if(!confirms(row,intent))throw Error('Yanıt gönderilen işlem/girişimi doğrulamıyor.');
   r.row=row;r.intent=null;r.conflict=false;r.confirmed=true;r.notice='';ack.checked=false;
   if(row.status==='blocked_runtime')r.notice='Runtime hazır değil; kurulum veya motor geçişi yapılmadı.';
  }catch(error){if(current(r,e)&&ticket===r.seq){r.notice='İşlem sonucu doğrulanamadı. Önce durumu yenileyin veya aynı isteği açıkça gönderin. '+error.message;r.confirmed=false;}}
  finally{if(operation===op)operation=null;paint();}
 }
 for(const action of ['start','retry','cancel'])get('family-render-'+action).addEventListener('click',()=>act(action));
 get('family-render-refresh').addEventListener('click',refresh);ack.addEventListener('change',paint);paint();
 return {clear,bind};
}};
