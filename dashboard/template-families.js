// Preparation only. Drafts and receipts stay in this page's RAM, never browser storage.
(()=>{
 const get=id=>document.getElementById(id),drafts=new Map(),remembered=new Map(),cards=new Map(),optionKeys=new WeakMap();
 let families=[],selectedId='',exampleName='',account='',revision=0,loading=false,ready=false,inFlight=null,sequence=0,loadError='',explicitBlank=false;
 let historySequence=0,historyPending=null,editor=null,renderPanel=null,referenceGallery=null;
 const fold=value=>String(value).toLocaleLowerCase('tr').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replaceAll('ı','i');
 const say=(id,text)=>{if(get(id).textContent!==text)get(id).textContent=text;};
 async function request(path,data){
  const headers={},options={cache:'no-store',credentials:'same-origin',headers};
  if(data!==undefined){options.method='POST';headers['Content-Type']='application/json';headers['X-Storymotion-Local']='1';options.body=JSON.stringify(data);}
  const response=await fetch(path,options);let result;
  try{result=await response.json();}catch{throw Error('Yerel API yanıtı okunamadı. / Invalid local API response.');}
  if(!response.ok){const error=Error(typeof result?.error==='string'?result.error:'Local template operation failed');error.validationRejected=path==='/api/template-families/validate'&&response.status===400&&typeof result?.error==='string'&&result.error.length>0;throw error;}return result;
 }
 function options(select,rows,value='',blank=null){
  const values=blank===null?rows:[{id:'',name:blank},...rows],key=JSON.stringify(values);
  if(optionKeys.get(select)!==key){select.replaceChildren(...values.map(row=>{const n=document.createElement('option');n.value=row.id;n.textContent=row.name||row.id;return n;}));optionKeys.set(select,key);}
  if(select.value!==value)select.value=value;
 }
 const currentFamily=()=>families.find(f=>f.id===selectedId);
 const key=()=>JSON.stringify([account,selectedId,exampleName]);
 function saveDraft(){if(currentFamily()&&exampleName)drafts.set(key(),{spec:get('family-spec').value,claims:get('family-claims').value,editor:editor?.snapshot()});}
 function loadDraft(){const f=currentFamily(),example=f?.examples.find(e=>e.name===exampleName);if(!example)return;
  const draft=drafts.get(key());get('family-spec').value=draft?draft.spec:JSON.stringify(example.spec,null,2);get('family-claims').value=draft?draft.claims:'[]';editor?.restore(draft?.editor);
 }
 function visible(){
  const query=fold(get('family-search').value.trim()),niche=get('family-filter-niche').value,kind=get('family-filter-type').value,media=get('family-filter-media').value,engine=get('family-filter-engine').value,state=get('family-filter-state').value;
  return families.filter(f=>{
   if(niche&&!f.niches.includes(niche)||kind&&!f.content_types.includes(kind))return false;
   if(media==='proxy'&&!f.requires_caller_media||media==='vector'&&f.requires_caller_media)return false;
   if(engine&&!f.engines[engine]?.implemented||state&&f.readiness!==state)return false;
   if(!query)return true;
   const hay=[f.id,f.name,f.description,f.editorial_description,f.audience_hypothesis,f.age_hypothesis.label,f.age_hypothesis.basis,f.age_hypothesis.status,
    f.preview_state,f.readiness,f.instagram_assessment.status,'hipotez hypothesis unmeasured',...f.niches,...f.content_types,...f.sample_topics,...f.examples.map(e=>e.name),...Object.keys(f.engines),...Object.values(f.engines).map(e=>e.state)].join(' ');
   return fold(hay).includes(query);
  });
 }
 function visibleFamily(){const f=currentFamily();return f&&get('family-select').value===f.id&&visible().some(v=>v.id===f.id)?f:null;}
 function selection(){const f=visibleFamily(),index=get('family-example').value;
  return f&&/^(0|[1-9]\d*)$/.test(index)&&f.examples[Number(index)]?.name===exampleName?f:null;
 }
 function check({forValidation=false}={}){
  const f=selection();if(loading)return {error:'Katalog yükleniyor; hazırlama bekliyor. / Catalog loading.'};
  if(!ready)return {error:loadError||'Önce kataloğu yükleyin. / Load the catalog first.'};
  if(!visibleFamily())return {error:'Görünür bir template seçin; filtre dışındaki taslak RAM’de korunur. / Select a visible template; the draft is retained.',field:'family-select'};
  if(!f)return {error:'Katalogdaki bir örneği açıkça seçin; eski taslak korunuyor. / Choose an available example; the earlier draft is retained.',field:'family-example'};
  if(!account||get('family-account').value!==account||!f.profile_ids.includes(account))return {error:'Bu template için geçerli bir AccountPack seçin. / Select an available account.',field:'family-account'};
  const planning=globalThis.StoryMotionTaxonomy?.prepareStatus(account);if(planning?.blocked)return {error:planning.message};
  const engine=get('family-engine').value;if(!['hyperframes','remotion'].includes(engine)||!f.engines[engine]?.implemented)return {error:'Kaynak hazırlamayı destekleyen motoru seçin. / Select an implemented preparation engine.',field:'family-engine'};
  const fieldError=editor?.blocking({forValidation});if(fieldError)return {error:fieldError};
  let spec,claims;
  try{spec=editor?editor.readSpec(get('family-spec').value):JSON.parse(get('family-spec').value);}catch{return {error:'Parametre JSON’u geçersiz. / Invalid parameter JSON.',field:'family-spec'};}
  if(!spec||typeof spec!=='object'||Array.isArray(spec)||spec.id!==f.id||spec.version!==f.version||!spec.parameters||typeof spec.parameters!=='object'||Array.isArray(spec.parameters)||Object.keys(spec).some(k=>!['id','version','parameters'].includes(k)))return {error:'Spec kimliği/sürümü ve parametre nesnesi görünür seçime uymalı. / Spec ID/version and parameter object must match the visible selection.',field:'family-spec'};
  try{claims=JSON.parse(get('family-claims').value);}catch{return {error:'İddia JSON’u geçersiz. / Invalid claims JSON.',field:'family-claims'};}
  if(!Array.isArray(claims))return {error:'İddialar JSON listesi olmalı. / Claims must be an array.',field:'family-claims'};
  return {data:{account,engine,spec,claims,...(planning?.token?{planning:planning.token}:{})}};
 }
 function context(){return JSON.stringify([account,selectedId,exampleName,get('family-engine').value,get('family-spec').value,get('family-claims').value,revision,globalThis.StoryMotionTaxonomy?.contextKey(account)]);}
 function validationContext(){return JSON.stringify([account,selectedId,exampleName,get('family-engine').value,get('family-spec').value,get('family-claims').value,globalThis.StoryMotionTaxonomy?.contextKey(account)]);}
 function controls(){const valid=check(),selected=Boolean(selection());
  referenceGallery?.controls();
  get('family-history-load').disabled=!ready||!account||Boolean(historyPending);
  get('family-load').disabled=loading;get('family-select').disabled=!families.length||!visible().length;get('family-example').disabled=!visibleFamily();
  get('family-spec').disabled=!selected;get('family-claims').disabled=!selected;
  get('family-prepare').disabled=Boolean(inFlight||valid.error);
  get('family-form').setAttribute('aria-busy',inFlight?'true':'false');
  for(const id of ['family-select','family-example','family-account','family-engine','family-spec','family-claims']){if(valid.field===id)get(id).setAttribute('aria-invalid','true');else get(id).removeAttribute('aria-invalid');}
  say('family-status',inFlight?'İstek #'+inFlight.id+' sürüyor: '+inFlight.label+'. Seçimi değiştirebilirsiniz; yanıt bu isteğe bağlı kalır. / In progress; response stays with this request.':valid.error||'Yalnız kaynak hazırlama. Render/görsel/medya kabulü ayrıca bekliyor. / Source preparation only; render, visual and media acceptance remain separate.');
  editor?.controls();
 }
 const accountId=value=>typeof value==='string'&&/^[a-z][a-z0-9-]{0,59}$/.test(value);
 const jobId=value=>typeof value==='string'&&/^[a-f0-9]{24}$/.test(value);
 function historyClear(){renderPanel?.clear();historySequence++;historyPending=null;get('family-history-list').replaceChildren();get('family-history-detail').hidden=true;say('family-history-status','Geçmiş için hesap seçin ve yükleyin. / Choose an account and load history.');}
 function historyRow(row,expected){
  return row&&row.ref?.kind==='family'&&row.ref.account===expected&&accountId(expected)&&jobId(row.ref.id)&&row.job===row.ref.id&&row.account===expected&&typeof row.family==='string'&&['hyperframes','remotion'].includes(row.engine);
 }
 async function historyDetail(expected,id){
  if(!accountId(expected)||!jobId(id))return;
  renderPanel?.clear();const ticket=++historySequence;historyPending=ticket;controls();get('family-history-detail').hidden=true;
  say('family-history-status',expected+' · '+id+' · ayrıntı yükleniyor / loading details');
  try{
   const row=await request('/api/family-jobs/'+expected+'/'+id);if(ticket!==historySequence)return;
   if(!historyRow(row,expected)||row.job!==id||!Array.isArray(row.files)||row.actual_render!==false)throw Error('Invalid family history receipt');
   get('family-history-detail').hidden=false;say('family-history-detail-title',expected+' · '+row.family+' · '+row.engine+' · '+id);
   say('family-history-summary','prepare: '+row.prepare_status+' · artifacts: '+row.artifacts_status+' · source_current: '+row.source_current+' · Native render/MP4/yayın kabulü yok / no native render or publication acceptance');
   say('family-history-spec',JSON.stringify(row.spec,null,2));const files=[];
   if(row.artifacts_status==='verified')for(const file of row.files){
    const prefix='/family-files/'+expected+'/'+id+'/',token=typeof file.download_url==='string'?file.download_url.slice(prefix.length):'';
    if(!file.download_url?.startsWith(prefix)||!/^[a-f0-9]{64}$/.test(token)||typeof file.name!=='string'||!/^[A-Za-z0-9][A-Za-z0-9_.-]*$/.test(file.name)||!Number.isSafeInteger(file.bytes)||file.bytes<0)throw Error('Invalid family artifact receipt');
    const item=document.createElement('li'),link=document.createElement('a');link.href=prefix+token;link.textContent=file.name+' · '+file.bytes+' bytes · indir / download';link.setAttribute('download',file.name);item.append(link);
    if(file.name==='cover.svg'&&file.view_url===prefix+token+'/view'){const view=document.createElement('a');view.href=prefix+token+'/view';view.textContent=' · SVG görüntüle / view';view.setAttribute('target','_blank');view.setAttribute('rel','noopener noreferrer');item.append(view);}files.push(item);
   }
   get('family-history-files').replaceChildren(...files);renderPanel?.bind(row);say('family-history-status',expected+' · '+id+' · '+row.artifacts_status+' · '+files.length+' erişilebilir dosya / accessible files');
  }catch(error){if(ticket===historySequence){get('family-history-detail').hidden=true;say('family-history-status','Geçmiş okunamadı; açıkça tekrar deneyin. / History failed; retry explicitly. '+error.message);}}
  finally{if(ticket===historySequence){historyPending=null;controls();}}
 }
 get('family-history-load').addEventListener('click',async()=>{
  if(!ready||!accountId(account)||historyPending)return;renderPanel?.clear();const expected=account,ticket=++historySequence;historyPending=ticket;controls();get('family-history-detail').hidden=true;
  say('family-history-status',expected+' · geçmiş yükleniyor / loading history');
  try{const result=await request('/api/family-jobs/'+expected);if(ticket!==historySequence)return;
   if(result?.kind!=='family'||result.account!==expected||!Array.isArray(result.jobs)||result.jobs.length>100||result.jobs.some(row=>!historyRow(row,expected)))throw Error('Invalid family history list');
   const items=result.jobs.map(row=>{const item=document.createElement('li'),button=document.createElement('button');button.type='button';button.textContent=row.account+' · '+row.family+' · '+row.engine+' · '+row.created+' · '+row.prepare_status+' · dosyalar ayrıntıda doğrulanır / files checked in details';button.addEventListener('click',()=>historyDetail(expected,row.job));item.append(button);return item;});get('family-history-list').replaceChildren(...items);
   say('family-history-status',expected+' · '+items.length+' kayıt / records · '+result.unavailable_records+' doğrulanamayan / unavailable. Prepare only; no MP4.');
  }catch(error){if(ticket===historySequence){get('family-history-list').replaceChildren();say('family-history-status','Geçmiş yüklenemedi / History failed: '+error.message);}}
  finally{if(ticket===historySequence){historyPending=null;controls();}}
 });
 function details(){const f=selection();get('family-details').hidden=!f;if(!f)return;
  say('family-details-title',f.name+' · '+f.id);
  const fields=[['Açıklama / Description',[f.description,f.editorial_description].filter(Boolean).join(' ')],['Nişler / Niches',f.niches.join(', ')],['İçerik türleri / Content types',f.content_types.join(', ')],
   ['Örnek konular / Topics',f.sample_topics.join(' · ')],['Hedef kitle / Audience',f.audience_hypothesis+' — editoryal hipotez, ölçülmemiş / unmeasured hypothesis'],
   ['Yaş / Age',f.age_hypothesis.label+' — ölçülmemiş hipotez / unmeasured hypothesis. '+(f.age_hypothesis.basis||'')],
   ['Medya / Media',f.requires_caller_media?'Gerçek kullanıcı medyası gerekir; mevcut örnek RGB vekildir. / Caller media required; example is a proxy.':'Kullanıcı medyası gerektirmeyen vektör kaynak. / No caller media required.'],
   ['Motorlar / Engines',Object.entries(f.engines).map(([id,e])=>id+': implemented='+e.implemented+', render_verified='+e.render_verified+', '+e.state).join(' · ')],
   ['Örnekler / Examples',f.examples.map(e=>e.name).join(' · ')],['Hazırlık / Readiness',f.readiness+' · yayın kabulü / publication acceptance: '+f.human_publication_acceptance],
   ['Önizleme / Preview',f.preview_url?'Katalog referansı / catalog reference: '+f.preview_url+' · '+f.preview_state:'Önizleme yok / missing preview · '+f.preview_state],
   ['Test durumu / Tests','Bu API test koşusu/sonucu sağlamıyor. / No test-run receipt in this API. Native state is reported per engine above.'],
   ['Görsel değerlendirme / Visual score',f.visual_score===null?'Ölçülmedi / visual score null':String(f.visual_score)+' (katalog bildirimi / catalog-reported)'],
   ['Instagram',f.instagram_assessment.status+' · score: '+(f.instagram_assessment.score_100===null?'null / ölçülmedi':f.instagram_assessment.score_100)]];
  const nodes=[];for(const [name,value]of fields){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=name;dd.textContent=value;nodes.push(dt,dd);}get('family-meta').replaceChildren(...nodes);
  say('family-claim-fields','İddia kapsamı / Claim surface: görünür metin / visible copy'+(f.claim_guarded_numbers.length?' + '+f.claim_guarded_numbers.join(', '):''));
 }
 function examples(){const f=currentFamily();if(!f)return;options(get('family-example'),f.examples.map((e,i)=>({id:String(i),name:e.name})),String(f.examples.findIndex(e=>e.name===exampleName)));}
 function cardStates(){for(const[id,record]of cards)record.button.setAttribute('aria-pressed',get('family-select').value===id?'true':'false');}
 function choose(id,name){const f=families.find(v=>v.id===id);if(!f){explicitBlank=true;revision++;details();cardStates();controls();return;}saveDraft();explicitBlank=false;
  const wanted=name??remembered.get(JSON.stringify([account,id]))??f.examples[0].name;
  const next=f.examples.some(e=>e.name===wanted)?wanted:f.examples[0].name,changed=id!==selectedId||next!==exampleName;
  selectedId=id;exampleName=next;remembered.set(JSON.stringify([account,id]),next);
  if(changed){renderPanel?.clear();revision++;loadDraft();}get('family-select').value=id;examples();details();cardStates();controls();
 }
 function render(){const rows=visible(),active=document.activeElement,focused=[...cards.values()].find(r=>r.button===active);
  get('family-count').hidden=false;
  say('family-count',rows.length+' / '+families.length+' görünür / visible. Katalog etiketleri / catalog tags: '+unique('niches').length+' niş, '+unique('content_types').length+' içerik türü; tüm olası alanlar değildir. / Not all possible niches or types.');
  get('family-empty').hidden=rows.length!==0;const list=get('family-cards');list.hidden=false;
  const nodes=rows.map(f=>{let record=cards.get(f.id);if(!record){const li=document.createElement('li'),button=document.createElement('button');button.type='button';button.dataset.family=f.id;button.setAttribute('aria-controls','family-form family-details');button.addEventListener('click',()=>choose(f.id));li.append(button);record={li,button};cards.set(f.id,record);}
   record.button.textContent=f.name+' · '+f.id+' · '+f.niches.join(', ')+' · '+(f.requires_caller_media?'RGB vekil / proxy':'vektör / vector')+' · '+f.preview_state+' · '+f.readiness;return record.li;});
  if(list.children.length!==nodes.length||nodes.some((n,i)=>list.children[i]!==n)){list.replaceChildren(...nodes);if(focused)(nodes.includes(focused.li)?focused.button:get('family-search')).focus({preventScroll:true});}
  options(get('family-select'),rows.map(f=>({id:f.id,name:f.name})),!explicitBlank&&rows.some(f=>f.id===selectedId)?selectedId:'','Görünür template seçin / Select a visible template');
  examples();details();cardStates();controls();
 }
 function unique(key){return [...new Set(families.flatMap(f=>f[key]))].sort((a,b)=>a.localeCompare(b,'tr'));}
 function validateCatalog(value){
  const rows=value?.families,texts=v=>Array.isArray(v)&&v.every(s=>typeof s==='string'),nonempty=v=>texts(v)&&v.length>0&&v.every(s=>s.trim());
  if(!Array.isArray(rows)||rows.length!==91||new Set(rows.map(f=>f?.id)).size!==91)throw Error('Katalog 91 benzersiz template içermeli. / Expected 91 unique templates.');
  for(const f of rows){
   const engines=f?.engines,expectedReadiness=f?.requires_caller_media?'caller_media_proxy_only':'prepare_only_native_pending';
   if(!f||typeof f.id!=='string'||!f.id||typeof f.name!=='string'||!f.name.trim()||typeof f.description!=='string'||typeof f.editorial_description!=='string'||typeof f.version!=='string'||!nonempty(f.profile_ids)||!['niches','content_types','sample_topics'].every(k=>nonempty(f[k]))||!texts(f.claim_guarded_numbers)||typeof f.requires_caller_media!=='boolean'||f.readiness!==expectedReadiness||f.human_publication_acceptance!=='pending'||f.preview_state!=='missing_preview'||f.preview_url!==null||f.age_hypothesis?.label!=='18+'||f.age_hypothesis?.status!=='hypothesis_not_measured'||typeof f.age_hypothesis?.basis!=='string'||typeof f.audience_hypothesis!=='string'||f.visual_score!==null||f.instagram_assessment?.score_100!==null||f.instagram_assessment?.status!=='not_assessed'||!engines||Array.isArray(engines)||Object.keys(engines).sort().join(',')!=='hyperframes,remotion'||!Object.values(engines).every(e=>e?.implemented===true&&e.render_verified===false&&e.state==='implemented_pending_native_acceptance')||!Array.isArray(f.examples)||f.examples.length!==2||new Set(f.examples.map(e=>e?.name)).size!==2||f.examples.some(e=>typeof e?.name!=='string'||!e.name.trim()||e.spec?.id!==f.id||e.spec?.version!==f.version||!e.spec?.parameters||typeof e.spec.parameters!=='object'||Array.isArray(e.spec.parameters)))throw Error('Katalog alanları geçersiz; taslak korundu. / Invalid catalog fields; draft retained.');
  }
  return rows;
 }
 get('family-load').addEventListener('click',async()=>{if(loading)return;saveDraft();loading=true;revision++;controls();try{
  const rows=validateCatalog(await request('/api/template-families')),first=!families.length;families=rows;ready=true;loadError='';
  const accounts=[...new Set(families.flatMap(f=>f.profile_ids))],previousAccount=account;if(first)account=accounts[0]||'';else if(!accounts.includes(account))account='';
  if(account!==previousAccount)historyClear();
  options(get('family-account'),accounts.map(id=>({id})),account,'AccountPack seçin / Select account');
  globalThis.StoryMotionTaxonomy?.accountChanged(account);
  for(const[id,key]of [['family-filter-niche','niches'],['family-filter-type','content_types']]){const select=get(id),value=select.value,values=unique(key);options(select,values.map(v=>({id:v,name:v})),values.includes(value)?value:'','Tümü / All');}
  const states=[...new Set(families.map(f=>f.readiness))];options(get('family-filter-state'),states.map(id=>({id})),states.includes(get('family-filter-state').value)?get('family-filter-state').value:'','Tümü / All');
  if(first){selectedId='';exampleName='';choose(families[0].id);}
  get('family-filters').hidden=false;get('family-form').hidden=false;render();
 }catch(error){ready=false;loadError='Katalog yüklenemedi; taslak korunuyor. / Catalog unavailable; draft retained. '+error.message;}finally{loading=false;controls();}});
 get('family-select').addEventListener('change',()=>choose(get('family-select').value));
 get('family-example').addEventListener('change',()=>{const f=currentFamily(),value=get('family-example').value,example=/^(0|[1-9]\d*)$/.test(value)?f?.examples[Number(value)]:null;if(example)choose(f.id,example.name);else controls();});
 get('family-account').addEventListener('change',()=>{historyClear();saveDraft();account=get('family-account').value;globalThis.StoryMotionTaxonomy?.accountChanged(account);const f=currentFamily();if(f){exampleName=remembered.get(JSON.stringify([account,f.id]))||f.examples[0].name;remembered.set(JSON.stringify([account,f.id]),exampleName);}revision++;loadDraft();examples();details();controls();});
 get('family-engine').addEventListener('change',()=>{renderPanel?.clear();revision++;controls();});
 for(const id of ['family-spec','family-claims'])get(id).addEventListener('input',()=>{revision++;if(id==='family-spec')editor?.rawChanged();saveDraft();controls();});
 get('family-search').addEventListener('input',render);
 for(const id of ['family-filter-niche','family-filter-type','family-filter-media','family-filter-engine','family-filter-state'])get(id).addEventListener('change',render);
 get('family-clear-search').addEventListener('click',()=>{for(const id of ['family-search','family-filter-niche','family-filter-type','family-filter-media','family-filter-engine','family-filter-state'])get(id).value='';render();});
 get('family-form').addEventListener('submit',async event=>{event.preventDefault();if(inFlight)return;const valid=check();if(valid.error){controls();return;}
  const data=valid.data,snapshot=context(),id=++sequence,label=account+' · '+selectedId+' · '+exampleName+' · '+data.engine;
  const item=document.createElement('li'),title=document.createElement('h4'),status=document.createElement('p'),output=document.createElement('pre');title.textContent='İstek / Request #'+id+' · '+label;status.textContent='Hazırlanıyor / Preparing';item.append(title,status,output);get('family-results').append(item);
  inFlight={id,label};say('family-result','İstek #'+id+' · '+label+' · hazırlanıyor / preparing');controls();
  try{
   if(data.claims.length){const bound=await request('/api/writing-contexts/'+encodeURIComponent(data.account));data.source_revision=bound.sources?.revision||null;data.canon_revision=bound.canon?.revision||null;}
   const result=await request('/api/template-families/prepare',data),stale=snapshot!==context()||!selection(),bound=result?.account===data.account&&result?.family===data.spec.id&&result?.engine===data.engine;
   status.textContent=!bound?'Yanıtın hesap/template/motor bağı uyuşmuyor; geçerli seçime bağlanmadı. / Receipt context mismatch; not attached to the current selection.':stale?'Önceki istek bağlamının sonucu; geçerli seçime ait değildir. / Result belongs to the earlier request context.':'Bu isteğin kaynak hazırlama yanıtı; render kabulü değildir. / Preparation receipt, not render acceptance.';
   output.textContent=JSON.stringify(result,null,2);say('family-result','İstek #'+id+' · '+label+' · '+status.textContent);
   if(bound&&result?.ref?.kind==='family'&&result.ref.account===data.account&&result.ref.id===result.job&&jobId(result.job)){const open=document.createElement('button');open.type='button';open.textContent='Kayıtlı hazırlamayı aç / Open saved preparation · '+data.account;open.addEventListener('click',()=>historyDetail(data.account,result.job));item.append(open);}
  }catch(error){status.textContent='İstek başarısız; otomatik tekrar yok. / Failed; no automatic retry.'+(snapshot!==context()?' Önceki bağlam / earlier context.':'');output.textContent=error.message;say('family-result','İstek #'+id+' · '+label+' · '+status.textContent+' '+error.message);}
  finally{inFlight=null;controls();}
 });
 editor=globalThis.StoryMotionTemplateEditor?.connect({get,request,raw:()=>get('family-spec').value,context,validationContext,check,save:saveDraft,controls,
  binding:()=>{const f=selection();return ready&&!loading&&f&&account&&f.profile_ids.includes(account)?{account,family:f.id,version:f.version,example:exampleName}:null;},
  write:raw=>{get('family-spec').value=raw;revision++;editor?.rawChanged();saveDraft();controls();}
 });
 globalThis.StoryMotionTaxonomy?.subscribe(controls);
 renderPanel=globalThis.StoryMotionFamilyRender?.connect({get,request,currentAccount:()=>account});
 referenceGallery=globalThis.StoryMotionReferenceGallery?.connect({get,request,context:()=>JSON.stringify([context(),Boolean(selection()),get('family-account').value]),account:()=>account,
  family:()=>selection()?.id||'',families:()=>families.map(f=>f.id),
  paletteFamilies:()=>families.filter(f=>f.adaptation?.strategy==='original_implementation_not_source_code_port').map(f=>f.id),
  canApply:()=>Boolean(editor&&!inFlight&&!check({forValidation:true}).error),
  apply:palette=>{if(!editor||inFlight||check({forValidation:true}).error)throw Error('Geçerli düzenlenebilir taslak gerekli / Editable draft required');
   const raw=editor.withPalette(get('family-spec').value,palette);get('family-spec').value=raw;revision++;editor.rawChanged();saveDraft();controls();}
 });
 controls();
})();
