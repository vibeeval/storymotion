// Account-scoped planning only. No parameter-schema editor or native renderer.
(()=>{
 const get=id=>document.getElementById(id),cache=new Map(),listeners=new Set(),optionKeys=new WeakMap();
 let account='',sequence=0,pending=null;
 const current=()=>cache.get(account);
 const draft=()=>({niche:'',topic:'',nicheName:'',topicName:''});
 const dirty=e=>Boolean(e&&(e.draft.niche!==(e.data?.selection?.niche||'')||e.draft.topic!==(e.data?.selection?.topic||'')||e.draft.nicheName||e.draft.topicName));
 // Full casefold exceptions preserve the backend's name_key semantics (e.g. ß/ss,
 // Greek sigma and dotless ı), without accent stripping or locale collation.
 const casefoldExceptions=Object.freeze({"\u00b5":"\u03bc","\u00df":"ss","\u0149":"\u02bcn","\u017f":"s","\u01f0":"j\u030c","\u0345":"\u03b9","\u0390":"\u03b9\u0308\u0301","\u03b0":"\u03c5\u0308\u0301","\u03c2":"\u03c3","\u03d0":"\u03b2","\u03d1":"\u03b8","\u03d5":"\u03c6","\u03d6":"\u03c0","\u03f0":"\u03ba","\u03f1":"\u03c1","\u03f5":"\u03b5","\u0587":"\u0565\u0582","\u13a0":"\u13a0","\u13a1":"\u13a1","\u13a2":"\u13a2","\u13a3":"\u13a3","\u13a4":"\u13a4","\u13a5":"\u13a5","\u13a6":"\u13a6","\u13a7":"\u13a7","\u13a8":"\u13a8","\u13a9":"\u13a9","\u13aa":"\u13aa","\u13ab":"\u13ab","\u13ac":"\u13ac","\u13ad":"\u13ad","\u13ae":"\u13ae","\u13af":"\u13af","\u13b0":"\u13b0","\u13b1":"\u13b1","\u13b2":"\u13b2","\u13b3":"\u13b3","\u13b4":"\u13b4","\u13b5":"\u13b5","\u13b6":"\u13b6","\u13b7":"\u13b7","\u13b8":"\u13b8","\u13b9":"\u13b9","\u13ba":"\u13ba","\u13bb":"\u13bb","\u13bc":"\u13bc","\u13bd":"\u13bd","\u13be":"\u13be","\u13bf":"\u13bf","\u13c0":"\u13c0","\u13c1":"\u13c1","\u13c2":"\u13c2","\u13c3":"\u13c3","\u13c4":"\u13c4","\u13c5":"\u13c5","\u13c6":"\u13c6","\u13c7":"\u13c7","\u13c8":"\u13c8","\u13c9":"\u13c9","\u13ca":"\u13ca","\u13cb":"\u13cb","\u13cc":"\u13cc","\u13cd":"\u13cd","\u13ce":"\u13ce","\u13cf":"\u13cf","\u13d0":"\u13d0","\u13d1":"\u13d1","\u13d2":"\u13d2","\u13d3":"\u13d3","\u13d4":"\u13d4","\u13d5":"\u13d5","\u13d6":"\u13d6","\u13d7":"\u13d7","\u13d8":"\u13d8","\u13d9":"\u13d9","\u13da":"\u13da","\u13db":"\u13db","\u13dc":"\u13dc","\u13dd":"\u13dd","\u13de":"\u13de","\u13df":"\u13df","\u13e0":"\u13e0","\u13e1":"\u13e1","\u13e2":"\u13e2","\u13e3":"\u13e3","\u13e4":"\u13e4","\u13e5":"\u13e5","\u13e6":"\u13e6","\u13e7":"\u13e7","\u13e8":"\u13e8","\u13e9":"\u13e9","\u13ea":"\u13ea","\u13eb":"\u13eb","\u13ec":"\u13ec","\u13ed":"\u13ed","\u13ee":"\u13ee","\u13ef":"\u13ef","\u13f0":"\u13f0","\u13f1":"\u13f1","\u13f2":"\u13f2","\u13f3":"\u13f3","\u13f4":"\u13f4","\u13f5":"\u13f5","\u13f8":"\u13f0","\u13f9":"\u13f1","\u13fa":"\u13f2","\u13fb":"\u13f3","\u13fc":"\u13f4","\u13fd":"\u13f5","\u1c80":"\u0432","\u1c81":"\u0434","\u1c82":"\u043e","\u1c83":"\u0441","\u1c84":"\u0442","\u1c85":"\u0442","\u1c86":"\u044a","\u1c87":"\u0463","\u1c88":"\ua64b","\u1e96":"h\u0331","\u1e97":"t\u0308","\u1e98":"w\u030a","\u1e99":"y\u030a","\u1e9a":"a\u02be","\u1e9b":"\u1e61","\u1e9e":"ss","\u1f50":"\u03c5\u0313","\u1f52":"\u03c5\u0313\u0300","\u1f54":"\u03c5\u0313\u0301","\u1f56":"\u03c5\u0313\u0342","\u1f80":"\u1f00\u03b9","\u1f81":"\u1f01\u03b9","\u1f82":"\u1f02\u03b9","\u1f83":"\u1f03\u03b9","\u1f84":"\u1f04\u03b9","\u1f85":"\u1f05\u03b9","\u1f86":"\u1f06\u03b9","\u1f87":"\u1f07\u03b9","\u1f88":"\u1f00\u03b9","\u1f89":"\u1f01\u03b9","\u1f8a":"\u1f02\u03b9","\u1f8b":"\u1f03\u03b9","\u1f8c":"\u1f04\u03b9","\u1f8d":"\u1f05\u03b9","\u1f8e":"\u1f06\u03b9","\u1f8f":"\u1f07\u03b9","\u1f90":"\u1f20\u03b9","\u1f91":"\u1f21\u03b9","\u1f92":"\u1f22\u03b9","\u1f93":"\u1f23\u03b9","\u1f94":"\u1f24\u03b9","\u1f95":"\u1f25\u03b9","\u1f96":"\u1f26\u03b9","\u1f97":"\u1f27\u03b9","\u1f98":"\u1f20\u03b9","\u1f99":"\u1f21\u03b9","\u1f9a":"\u1f22\u03b9","\u1f9b":"\u1f23\u03b9","\u1f9c":"\u1f24\u03b9","\u1f9d":"\u1f25\u03b9","\u1f9e":"\u1f26\u03b9","\u1f9f":"\u1f27\u03b9","\u1fa0":"\u1f60\u03b9","\u1fa1":"\u1f61\u03b9","\u1fa2":"\u1f62\u03b9","\u1fa3":"\u1f63\u03b9","\u1fa4":"\u1f64\u03b9","\u1fa5":"\u1f65\u03b9","\u1fa6":"\u1f66\u03b9","\u1fa7":"\u1f67\u03b9","\u1fa8":"\u1f60\u03b9","\u1fa9":"\u1f61\u03b9","\u1faa":"\u1f62\u03b9","\u1fab":"\u1f63\u03b9","\u1fac":"\u1f64\u03b9","\u1fad":"\u1f65\u03b9","\u1fae":"\u1f66\u03b9","\u1faf":"\u1f67\u03b9","\u1fb2":"\u1f70\u03b9","\u1fb3":"\u03b1\u03b9","\u1fb4":"\u03ac\u03b9","\u1fb6":"\u03b1\u0342","\u1fb7":"\u03b1\u0342\u03b9","\u1fbc":"\u03b1\u03b9","\u1fbe":"\u03b9","\u1fc2":"\u1f74\u03b9","\u1fc3":"\u03b7\u03b9","\u1fc4":"\u03ae\u03b9","\u1fc6":"\u03b7\u0342","\u1fc7":"\u03b7\u0342\u03b9","\u1fcc":"\u03b7\u03b9","\u1fd2":"\u03b9\u0308\u0300","\u1fd3":"\u03b9\u0308\u0301","\u1fd6":"\u03b9\u0342","\u1fd7":"\u03b9\u0308\u0342","\u1fe2":"\u03c5\u0308\u0300","\u1fe3":"\u03c5\u0308\u0301","\u1fe4":"\u03c1\u0313","\u1fe6":"\u03c5\u0342","\u1fe7":"\u03c5\u0308\u0342","\u1ff2":"\u1f7c\u03b9","\u1ff3":"\u03c9\u03b9","\u1ff4":"\u03ce\u03b9","\u1ff6":"\u03c9\u0342","\u1ff7":"\u03c9\u0342\u03b9","\u1ffc":"\u03c9\u03b9","\uab70":"\u13a0","\uab71":"\u13a1","\uab72":"\u13a2","\uab73":"\u13a3","\uab74":"\u13a4","\uab75":"\u13a5","\uab76":"\u13a6","\uab77":"\u13a7","\uab78":"\u13a8","\uab79":"\u13a9","\uab7a":"\u13aa","\uab7b":"\u13ab","\uab7c":"\u13ac","\uab7d":"\u13ad","\uab7e":"\u13ae","\uab7f":"\u13af","\uab80":"\u13b0","\uab81":"\u13b1","\uab82":"\u13b2","\uab83":"\u13b3","\uab84":"\u13b4","\uab85":"\u13b5","\uab86":"\u13b6","\uab87":"\u13b7","\uab88":"\u13b8","\uab89":"\u13b9","\uab8a":"\u13ba","\uab8b":"\u13bb","\uab8c":"\u13bc","\uab8d":"\u13bd","\uab8e":"\u13be","\uab8f":"\u13bf","\uab90":"\u13c0","\uab91":"\u13c1","\uab92":"\u13c2","\uab93":"\u13c3","\uab94":"\u13c4","\uab95":"\u13c5","\uab96":"\u13c6","\uab97":"\u13c7","\uab98":"\u13c8","\uab99":"\u13c9","\uab9a":"\u13ca","\uab9b":"\u13cb","\uab9c":"\u13cc","\uab9d":"\u13cd","\uab9e":"\u13ce","\uab9f":"\u13cf","\uaba0":"\u13d0","\uaba1":"\u13d1","\uaba2":"\u13d2","\uaba3":"\u13d3","\uaba4":"\u13d4","\uaba5":"\u13d5","\uaba6":"\u13d6","\uaba7":"\u13d7","\uaba8":"\u13d8","\uaba9":"\u13d9","\uabaa":"\u13da","\uabab":"\u13db","\uabac":"\u13dc","\uabad":"\u13dd","\uabae":"\u13de","\uabaf":"\u13df","\uabb0":"\u13e0","\uabb1":"\u13e1","\uabb2":"\u13e2","\uabb3":"\u13e3","\uabb4":"\u13e4","\uabb5":"\u13e5","\uabb6":"\u13e6","\uabb7":"\u13e7","\uabb8":"\u13e8","\uabb9":"\u13e9","\uabba":"\u13ea","\uabbb":"\u13eb","\uabbc":"\u13ec","\uabbd":"\u13ed","\uabbe":"\u13ee","\uabbf":"\u13ef","\ufb00":"ff","\ufb01":"fi","\ufb02":"fl","\ufb03":"ffi","\ufb04":"ffl","\ufb05":"st","\ufb06":"st","\ufb13":"\u0574\u0576","\ufb14":"\u0574\u0565","\ufb15":"\u0574\u056b","\ufb16":"\u057e\u0576","\ufb17":"\u0574\u056d"});
 function nameKey(value,maximum){
  if(typeof value!=='string'||![...value].length||[...value].length>maximum||/[<>\p{C}]/u.test(value))throw Error('Invalid planning name');
  const normalized=value.normalize('NFKC').trim().replace(/\s+/gu,' ');
  if(!normalized||[...normalized].length>maximum)throw Error('Invalid planning name');
  return [...normalized].map(c=>Object.hasOwn(casefoldExceptions,c)?casefoldExceptions[c]:c.toLowerCase()).join('');
 }
 function sameSelection(actual,expected){
  return expected===null?actual===null:Boolean(actual&&Object.keys(actual).sort().join(',')==='niche,topic'&&actual.niche===expected.niche&&actual.topic===expected.topic);
 }
 function confirmWrite(action,submitted,result,value,expected,priorSelection){
  if(action==='select'){
   const chosen=submitted.niche===null&&submitted.topic===null?null:{niche:submitted.niche,topic:submitted.topic};
   if(!sameSelection(value.selection,chosen))throw Error('Planning reply does not match submitted selection');
   return;
  }
  const item=result?.item,kind=submitted.kind,rows=kind==='niche'?value.niches:kind==='topic'?value.topics:null;
  const member=rows?.find(row=>row.id===item?.id);
  if(typeof result?.created!=='boolean'||!member||!item||Array.isArray(item)||!sameSelection(value.selection,priorSelection))throw Error('Planning reply does not match submitted creation');
  const keys=['id','name','origin','family_ids',...(member.origin==='customer_local'?['account']:[]),...(kind==='topic'?['niche']:[])].sort();
  if(Object.keys(member).sort().join(',')!==keys.join(',')||Object.keys(item).sort().join(',')!==keys.join(',')||keys.some(key=>JSON.stringify(item[key])!==JSON.stringify(member[key]))||
     (member.origin==='customer_local'&&member.account!==expected)||(result.created&&member.origin!=='customer_local')||
     (kind==='topic'&&member.niche!==submitted.niche)||nameKey(member.name,kind==='niche'?100:160)!==nameKey(submitted.name,kind==='niche'?100:160))throw Error('Planning reply does not match submitted item');
 }
 function options(node,rows,value){
  const values=[{id:'',name:'Seçin / Choose'},...rows];
  if(value&&!rows.some(row=>row.id===value))values.push({id:value,name:'Önceki seçim artık kullanılamıyor / Previous choice unavailable'});
  const key=JSON.stringify(values);if(optionKeys.get(node)!==key){node.replaceChildren(...values.map(row=>{const n=document.createElement('option');n.value=row.id;n.textContent=row.name;return n;}));optionKeys.set(node,key);}
  if(node.value!==value)node.value=value;
 }
 function validState(value,expected){
  const id=v=>typeof v==='string'&&/^[a-z][a-z0-9-]{0,63}$/.test(v);
  if(!value||value.account!==expected||!/^[a-f0-9]{64}$/.test(value.revision)||!Array.isArray(value.niches)||!Array.isArray(value.topics)||value.niches.length>1074||value.topics.length>1182||value.custom_limit!==1000||!Number.isInteger(value.custom_count)||value.custom_count<0||value.custom_count>1000)throw Error('Invalid planning catalog');
  for(const rows of [value.niches,value.topics])if(new Set(rows.map(row=>row?.id)).size!==rows.length||rows.some(row=>!row||!id(row.id)||typeof row.name!=='string'||!['bundled_editorial','customer_local'].includes(row.origin)))throw Error('Invalid planning records');
  const ids=new Set(value.niches.map(row=>row.id));if(value.topics.some(row=>!ids.has(row.niche)))throw Error('Invalid topic parent');
  if(value.selection!==null){const s=value.selection;if(!s||!ids.has(s.niche)||!value.topics.some(row=>row.id===s.topic&&row.niche===s.niche)||value.planning_context?.sources_verified!==false||value.planning_context?.style_applied_by_taxonomy!==false||value.planning_context?.capability?.render_verified!==false)throw Error('Invalid planning selection');}
  else if(value.planning_context!==null)throw Error('Unexpected planning context');
  return value;
 }
 async function request(action,data){
  const response=await fetch('/api/taxonomy/'+action,{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json','X-Storymotion-Local':'1'},body:JSON.stringify(data)});
  const value=await response.json();if(!response.ok)throw Error(typeof value?.error==='string'?value.error:'Local planning failed');return value;
 }
 function status(expected){
  const e=current();if(!expected||expected!==account||!e?.data)return {blocked:true,message:'Konu planını yükleyin / Load planning context'};
  if(pending||e.error||dirty(e))return {blocked:true,message:'Plan bekliyor veya düzenlendi; yükleyin, uygulayın ya da yerel düzenlemeleri bırakın. / Resolve pending planning edits first.'};
  return {blocked:false,token:e.data.selection?{...e.data.selection,revision:e.data.revision}:null};
 }
 function notify(){for(const listener of listeners)listener();}
 function render(){
  const e=current(),data=e?.data,d=e?.draft||draft(),busy=Boolean(pending),valid=Boolean(data&&data.niches.some(row=>row.id===d.niche)&&data.topics.some(row=>row.id===d.topic&&row.niche===d.niche));
  get('taxonomy-panel').hidden=!account;get('taxonomy-panel').setAttribute('aria-busy',busy?'true':'false');
  options(get('taxonomy-niche'),data?.niches||[],d.niche);options(get('taxonomy-topic'),data?.topics.filter(row=>row.niche===d.niche)||[],d.topic);
  for(const[id,key]of [['taxonomy-niche-name','nicheName'],['taxonomy-topic-name','topicName']])if(get(id).value!==d[key])get(id).value=d[key];
  get('taxonomy-reload').disabled=!account||busy;get('taxonomy-niche').disabled=!data;get('taxonomy-topic').disabled=!data||!d.niche;
  get('taxonomy-add-niche').disabled=!data||busy||e?.error||!d.nicheName.trim();get('taxonomy-add-topic').disabled=!data||busy||e?.error||!data.niches.some(row=>row.id===d.niche)||!d.topicName.trim();
  get('taxonomy-apply').disabled=!valid||busy||e?.error||Boolean(d.nicheName||d.topicName);get('taxonomy-clear').disabled=!data||busy||e?.error;get('taxonomy-revert').disabled=!data||busy||!dirty(e);
  const selection=data?.selection,niche=data?.niches.find(row=>row.id===selection?.niche),topic=data?.topics.find(row=>row.id===selection?.topic);
  get('taxonomy-context').textContent=selection?account+' · '+niche.name+' → '+topic.name+' · planning only; no factual/render acceptance':account?account+' · Kaydedilmiş konu seçimi yok / No saved topic selection':'';
  get('taxonomy-status').textContent=e?.message||'Galeri hesabını seçin / Select the gallery AccountPack';
  get('taxonomy-count').textContent=data?data.niches.length+' niş / niches · '+data.topics.length+' konu / topics · '+data.custom_count+'/'+data.custom_limit+' özel kayıt / custom records':'';
  notify();
 }
 function changed(){const e=current();if(!e)return;e.edit++;e.message=e.error?'Önce sunucu durumunu yeniden yükleyin; yerel düzenlemeler korundu. / Reload server state; local edits retained.':'Yerel plan düzenlendi; açıkça uygulayın / Local planning edits need explicit application';render();}
 async function reload(){
  if(!account||pending)return;const expected=account,e=current(),edit=e.edit,preserve=dirty(e),ticket=++sequence;pending=ticket;e.message='Konu planı yükleniyor / Loading planning';render();
  try{const value=validState(await request('state',{account:expected}),expected);if(ticket!==sequence||account!==expected)return;e.data=value;e.error=false;if(e.edit===edit&&!preserve)e.draft={...draft(),...(value.selection||{})};e.message='Editoryal plan; doğrulanmış kaynak veya yaş verisi değildir. / Editorial planning, not verified source or demographic data.';}
  catch(error){if(ticket===sequence){e.error=true;e.message='Plan yüklenemedi; yerel düzenlemeler korundu / Planning failed; edits retained. '+error.message;}}
  finally{if(ticket===sequence){pending=null;render();}}
 }
 function accountChanged(value){
  if(value===account)return;sequence++;pending=null;account=value;
  if(account&&!cache.has(account))cache.set(account,{data:null,draft:draft(),edit:0,error:false,message:''});
  render();if(account)reload();
 }
 async function write(action,values,success){
  const e=current();if(!e?.data||e.error||pending)return;const expected=account,edit=e.edit,ticket=++sequence,submitted=Object.freeze({...values}),revision=e.data.revision,priorSelection=e.data.selection?Object.freeze({...e.data.selection}):null;pending=ticket;e.message='Plan isteği sürüyor / Planning request in progress';render();
  try{const result=await request(action,{account:expected,...submitted,expected_revision:revision});if(ticket!==sequence||account!==expected)return;
   const value=validState(action==='create'?result.state:result,expected);confirmWrite(action,submitted,result,value,expected,priorSelection);e.data=value;e.error=false;
   if(e.edit===edit)success(e,result);e.message=e.edit===edit?'Plan kaydedildi; template/medya kabulü değildir. / Planning saved, not template/media acceptance.':'İstek kaydedildi; daha yeni yerel düzenlemeler korundu. / Saved request; newer local edits retained.';
  }catch(error){if(ticket===sequence){e.error=true;e.message='Yanıt doğrulanamadı; durum değişmiş olabilir. Yeniden yükleyin; otomatik tekrar yok. / Reply unconfirmed; reload state before retrying. '+error.message;}}
  finally{if(ticket===sequence){pending=null;render();}}
 }
 get('taxonomy-reload').addEventListener('click',reload);
 get('taxonomy-niche').addEventListener('change',()=>{const e=current();if(!e?.data)return;e.draft.niche=get('taxonomy-niche').value;e.draft.topic='';changed();});
 get('taxonomy-topic').addEventListener('change',()=>{if(!current()?.data)return;current().draft.topic=get('taxonomy-topic').value;changed();});
 for(const[id,key]of [['taxonomy-niche-name','nicheName'],['taxonomy-topic-name','topicName']])get(id).addEventListener('input',()=>{if(current()){current().draft[key]=get(id).value;changed();}});
 get('taxonomy-add-niche').addEventListener('click',()=>{if(current()?.data)return write('create',{kind:'niche',name:current().draft.nicheName},(e,result)=>{e.draft.niche=result.item.id;e.draft.topic='';e.draft.nicheName='';});});
 get('taxonomy-add-topic').addEventListener('click',()=>{if(current()?.data)return write('create',{kind:'topic',name:current().draft.topicName,niche:current().draft.niche},(e,result)=>{e.draft.topic=result.item.id;e.draft.topicName='';});});
 get('taxonomy-apply').addEventListener('click',()=>{if(current()?.data)return write('select',{niche:current().draft.niche,topic:current().draft.topic},(e,result)=>{e.draft={...draft(),...(result.selection||{})};});});
 get('taxonomy-clear').addEventListener('click',()=>write('select',{niche:null,topic:null},e=>{e.draft.niche='';e.draft.topic='';}));
 get('taxonomy-revert').addEventListener('click',()=>{const e=current();if(e?.data&&!pending){e.draft={...draft(),...(e.data.selection||{})};e.edit++;e.message=e.error?'Yerel düzenlemeler bırakıldı; sunucu durumu için yeniden yükleyin. / Edits discarded; reload server state.':'Yerel plan düzenlemeleri açıkça bırakıldı / Local planning edits explicitly discarded';render();}});
 globalThis.StoryMotionTaxonomy=Object.freeze({accountChanged,prepareStatus:status,contextKey:expected=>{const e=current();return JSON.stringify([expected,account,e?.edit,e?.data?.revision,Boolean(pending),Boolean(e?.error),dirty(e)]);},subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);}});
 render();
})();
