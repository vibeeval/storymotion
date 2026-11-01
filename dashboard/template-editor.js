// Inert declared controls over the gallery's single RAM draft. No storage or rendering.
(()=>{
 const unsafe=new Set(['__proto__','prototype','constructor']),hex=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
 function parse(raw){
  if(typeof raw!=='string'||!raw.length||new TextEncoder().encode(raw).length>100000)throw Error('Bounded JSON required');
  let at=0,count=0;const spans=new Map(),space=()=>{while(/[\t\n\r ]/.test(raw[at]||'!'))at++;};
  function string(){const start=at++;while(at<raw.length){const c=raw[at++];if(c==='"')return JSON.parse(raw.slice(start,at));if(c==='\\')at++;}throw Error('Incomplete JSON string');}
  function value(path,depth){
   space();const start=at;if(depth>24||++count>20000)throw Error('JSON too deep or large');let result;
   if(raw[at]==='{'){
    result={};at++;space();const keys=new Set();if(raw[at]!=='}')for(;;){space();if(raw[at]!=='"')throw Error('JSON key required');const k=string();if(unsafe.has(k)||keys.has(k))throw Error('Duplicate or unsafe JSON key');keys.add(k);space();if(raw[at++]!==':')throw Error('JSON colon required');result[k]=value([...path,k],depth+1);space();if(raw[at]!==',')break;at++;}if(raw[at++]!=='}')throw Error('JSON object incomplete');
   }else if(raw[at]==='['){
    result=[];at++;space();if(raw[at]!==']')for(;;){result.push(value([...path,result.length],depth+1));space();if(raw[at]!==',')break;at++;}if(raw[at++]!==']')throw Error('JSON array incomplete');
   }else if(raw[at]==='"')result=string();
   else if(/^(true|false|null)/.test(raw.slice(at))){const token=raw.slice(at).match(/^(true|false|null)/)[0];at+=token.length;result=JSON.parse(token);}
   else{const token=raw.slice(at).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/)?.[0];if(!token)throw Error('Complete JSON value required');at+=token.length;result=Number(token);if(!Number.isFinite(result)||Math.abs(result)>Number.MAX_SAFE_INTEGER||result===0&&/[1-9]/.test(token.split(/[eE]/)[0]))throw Error('Number is outside the representable safe range');}
   spans.set(JSON.stringify(path),{start,end:at,value:result});return result;
  }
  const spec=value([],0);space();if(at!==raw.length)throw Error('Trailing or malformed JSON');return {spec,spans};
 }
 function validSchema(node,depth=0,budget={count:0}){
  if(!node||typeof node!=='object'||Array.isArray(node)||depth>20||++budget.count>4000||!['object','array','string','number','integer','boolean','unknown'].includes(node.type))throw Error('Invalid field descriptor');
  for(const key of Object.keys(node))if(unsafe.has(key))throw Error('Unsafe descriptor');
  for(const name of ['minimum','maximum','minLength','maxLength','multipleOf','minItems','maxItems'])if(name in node&&(!Number.isFinite(node[name])||Math.abs(node[name])>Number.MAX_SAFE_INTEGER))throw Error('Invalid descriptor bound');
  if('minItems' in node||'maxItems' in node)if(!Number.isInteger(node.minItems)||!Number.isInteger(node.maxItems)||node.minItems<0||node.maxItems<node.minItems||node.maxItems>1000)throw Error('Invalid collection bounds');
  if('enum' in node&&(!Array.isArray(node.enum)||!node.enum.length||node.enum.length>128||node.enum.some(v=>v===null||!['string','boolean','number'].includes(typeof v))))throw Error('Invalid enum');
  if(node.enum&&node.enum.some(v=>typeof v!==(node.type==='integer'?'number':node.type)||typeof v==='number'&&(!Number.isFinite(v)||node.type==='integer'&&!Number.isInteger(v))))throw Error('Enum type mismatch');
  if(node.type==='object'){
   if(!node.properties||typeof node.properties!=='object'||Array.isArray(node.properties)||!Array.isArray(node.required)||node.required.some(k=>typeof k!=='string'||!Object.hasOwn(node.properties,k)))throw Error('Invalid object descriptor');
   for(const[k,v]of Object.entries(node.properties)){if(unsafe.has(k))throw Error('Unsafe property');validSchema(v,depth+1,budget);}
  }
  if(node.type==='array')validSchema(node.items,depth+1,budget);
 }
 const sha=async text=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text))),v=>v.toString(16).padStart(2,'0')).join('');
 const stable=v=>v&&typeof v==='object'?(Array.isArray(v)?v.map(stable):Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])]))):v;
 const same=(a,b)=>JSON.stringify(stable(a))===JSON.stringify(stable(b));
 function connect(host){
  const $=host.get;let state={schema:null,base:'',edits:{},editContract:null,open:true,validationRequired:false,validatedDraft:null},ticket=0,pending=false,pendingTicket=0,result=null,renderedFor=null;
  const status=text=>{$('family-editor-status').textContent=text;};
  const binding=()=>host.binding();
  const context=()=>JSON.stringify([host.context(),globalThis.writingContextReady?.(binding()?.account),globalThis.writingContextRefs?.(binding()?.account)]);
  const validationKey=()=>JSON.stringify([host.validationContext(),state.schema?.digest,globalThis.writingContextReady?.(binding()?.account),globalThis.writingContextRefs?.(binding()?.account)]);
  const hasEdits=()=>Object.keys(state.edits).length>0;
  const sameBinding=()=>state.schema&&binding()&&['account','family','version','example'].every(k=>state.schema[k]===binding()[k]);
  function invalidate(){ticket++;result=null;$('family-editor-normalized').textContent='';$('family-editor-normalize').disabled=true;}
  function save(){host.save();host.controls();}
  function controls(){
   if(renderedFor!==JSON.stringify(binding())){render();return;}
   if(result&&result.context!==context()){result=null;$('family-editor-normalized').textContent='';}
   $('family-editor-load').disabled=pending||!binding();$('family-editor-validate').disabled=pending||!sameBinding()||hasEdits()||Boolean(host.check({forValidation:true}).error);
   $('family-editor-apply').disabled=pending||!sameBinding()||!hasEdits()||state.base!==host.raw()||state.editContract!==state.schema.digest;
   $('family-editor-discard').disabled=!hasEdits();$('family-editor-panel').hidden=!state.open;
   $('family-editor-toggle').textContent=state.open?'Alan panelini gizle / Hide fields':'Alan panelini göster / Show fields';
   $('family-editor-normalize').disabled=pending||!result||result.context!==context();
   function disable(node){for(const child of node.children){if(['INPUT','SELECT'].includes(child.tagName))child.disabled=!sameBinding();disable(child);}}disable($('family-editor-fields'));
  }
  function edited(path,text,kind){
   if(!hasEdits()){state.base=host.raw();state.editContract=state.schema?.digest;}state.edits[JSON.stringify(path)]={text,kind};invalidate();
   status('Alan taslağı RAM’de. JSON’a uygula veya açıkça bırak. / Field draft retained; apply to JSON or discard explicitly.');save();controls();
  }
  function scalar(node,value,path,parent){
   const kind=node.type;if(!['string','number','integer','boolean'].includes(kind))return false;const numeric=['number','integer'].includes(kind),matches=numeric?typeof value==='number':typeof value===kind;
   if(!matches)return false;
   const line=document.createElement('div'),label=document.createElement('label'),input=document.createElement(node.enum||kind==='boolean'?'select':'input'),hint=document.createElement('small');
   const key=JSON.stringify(path),edit=state.edits[key];input.id='family-field-'+Array.from(key).map(c=>c.codePointAt(0).toString(16)).join('-');input.dataset.path=key;
   label.setAttribute('for',input.id);label.textContent=path.join(' / ');
   if(node.enum||kind==='boolean'){
    const values=node.enum||[false,true];let selected=edit?values.findIndex(v=>JSON.stringify(v)===edit.text):values.findIndex(v=>same(v,value));
    const blank=document.createElement('option');blank.value='';blank.textContent='Değer seçin / Choose value';input.append(blank);
    values.forEach((v,i)=>{const option=document.createElement('option');option.value=String(i);option.textContent=JSON.stringify(v);input.append(option);});input.value=selected<0?'':String(selected);
    input.addEventListener('change',()=>edited(path,input.value===''?'':JSON.stringify(values[Number(input.value)]),kind));
   }else{
    input.type='text';if(numeric)input.setAttribute('inputmode','decimal');input.value=edit?edit.text:String(value);
    input.addEventListener('input',()=>edited(path,input.value,kind));
   }
   hint.textContent=Object.entries(node).filter(([k])=>!['type','enum','default'].includes(k)).map(([k,v])=>k+': '+JSON.stringify(v)).join(' · ')+' · Sunucu doğrular / server validates';
   line.append(label,input,hint);parent.append(line);return true;
  }
  function changeCollection(path,operation,node){
   if(hasEdits()||pending||!sameBinding())return;
   try{
    const raw=host.raw(),{spans}=parse(raw),span=spans.get(JSON.stringify(path)),items=span?.value;if(!Array.isArray(items))throw Error('Collection changed');
    let next;
    if(operation==='add'){
     if(items.length===0||items.length>=node.maxItems)throw Error('Declared collection bound');const last=spans.get(JSON.stringify([...path,items.length-1]));next=raw.slice(0,span.end-1)+','+raw.slice(last.start,last.end)+raw.slice(span.end-1);
    }else{
     if(items.length<=node.minItems)throw Error('Declared collection bound');const last=spans.get(JSON.stringify([...path,items.length-1])),previous=spans.get(JSON.stringify([...path,items.length-2]));
     next=items.length===1?raw.slice(0,last.start)+raw.slice(last.end):raw.slice(0,previous.end)+raw.slice(last.end);
    }
    parse(next);invalidate();host.write(next);state.base=next;render();status('Koleksiyon JSON’u güncellendi; ilişkili kuralları doğrulayın. / Collection updated; validate coupled rules.');save();
   }catch(error){status(error.message);}
  }
  function render(){
   renderedFor=JSON.stringify(binding());
   const root=$('family-editor-fields');root.replaceChildren();if(!sameBinding()){$('family-editor-coverage').textContent='Alan kapsamı bu seçim için yüklenmedi. / Coverage unavailable; load fields for this selection.';controls();return;}
   let parsed;try{parsed=parse(host.raw());}catch(error){status('JSON korunuyor: '+error.message+' / Raw draft retained.');controls();return;}
   if(parsed.spec?.id!==binding().family||parsed.spec?.version!==binding().version){status('JSON kimliği seçime uymuyor; taslak korundu. / Identity mismatch; draft retained.');controls();return;}
   function walk(node,value,path,parent){
    if(node?.type==='object'&&value&&typeof value==='object'&&!Array.isArray(value)){
     const keys=new Set([...Object.keys(value),...Object.keys(node.properties)]);
     for(const key of keys){const child=node.properties[key];if(!Object.hasOwn(value,key)){
      const label=document.createElement('p');label.textContent=[...path,key].join(' / ')+' · eksik / absent';
      if(child&&Object.hasOwn(child,'default')){const add=document.createElement('button');add.type='button';add.textContent='Beyan edilen varsayılanı ekle / Insert declared default';add.disabled=hasEdits()||pending;
       add.addEventListener('click',()=>{if(hasEdits()||pending)return;try{const raw=host.raw(),current=parse(raw),span=current.spans.get(JSON.stringify(path));if(!span||Object.hasOwn(span.value,key))throw Error('Object changed');const insertion=(Object.keys(span.value).length?',':'')+JSON.stringify(key)+':'+JSON.stringify(child.default);const next=raw.slice(0,span.end-1)+insertion+raw.slice(span.end-1);parse(next);invalidate();host.write(next);render();save();}catch(error){status(error.message);}});label.append(add);}
      parent.append(label);
     }else walk(child,value[key],[...path,key],parent);}return;
    }
    if(node?.type==='array'&&Array.isArray(value)){
     const group=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent=path.join(' / ')+' · '+value.length;group.append(legend);
     value.forEach((v,i)=>walk(node.items,v,[...path,i],group));
     if(Number.isInteger(node.minItems)&&Number.isInteger(node.maxItems)&&node.items.type!=='unknown'&&!node.permutation&&!node.unique&&!Object.hasOwn(node,'first')){
      const add=document.createElement('button'),remove=document.createElement('button');add.type=remove.type='button';add.textContent='Son öğeyi çoğalt / Duplicate last';remove.textContent='Son öğeyi kaldır / Remove last';
      add.disabled=pending||hasEdits()||!value.length||value.length>=node.maxItems;remove.disabled=pending||hasEdits()||value.length<=node.minItems;
      add.dataset.collection=remove.dataset.collection=JSON.stringify(path);add.addEventListener('click',()=>changeCollection(path,'add',node));remove.addEventListener('click',()=>changeCollection(path,'remove',node));group.append(add,remove);
     }else{const note=document.createElement('p');note.textContent='Öğe sayısı/sıra değişiklikleri için JSON kullanın; eksik/bağlı sözleşme. / Use JSON for cardinality/order changes; missing or coupled contract.';group.append(note);}
     parent.append(group);return;
    }
    if(node&&scalar(node,value,path,parent))return;
    const fallback=document.createElement('p');fallback.dataset.fallback=JSON.stringify(path);fallback.textContent=path.join(' / ')+' · JSON alternatifi / JSON fallback: alan türü veya sözleşme eksik/uyumsuz.';parent.append(fallback);
   }
   walk(state.schema.parameters,parsed.spec.parameters,['parameters'],root);
   const coverage=state.schema.coverage;$('family-editor-coverage').textContent='Örnekte '+coverage.supported_observed_count+'/'+coverage.observed_count+' beyanlı alan yolu; kısmi kapsam. Bilinmeyen alanlar JSON’da korunur. / Partial observed coverage; unknown fields stay in JSON.';
   controls();
  }
  $('family-editor-load').addEventListener('click',async()=>{
   if(pending||!binding())return;invalidate();const data={...binding()},snapshot=context(),own=++ticket;pending=true;pendingTicket=own;controls();status('Alan sözleşmesi yükleniyor / Loading field contract');
   try{
    const value=await host.request('/api/template-families/fields',data);if(own!==ticket||snapshot!==context())return;
    if(value?.schema_version!==1||!['account','family','version','example'].every(k=>value[k]===data[k])||![value.digest,value.example_sha256,value.declaration_sha256,value.contract_source_sha256].every(hex)||!Number.isInteger(value.coverage?.observed_count)||!Number.isInteger(value.coverage?.supported_observed_count)||value.coverage.supported_observed_count<0||value.coverage.supported_observed_count>value.coverage.observed_count||value.coverage.fully_typed!==false||value.coverage.exhaustive_contract_coverage!==false)throw Error('Unconfirmed field contract; draft retained');
    validSchema(value.parameters);state.schema=value;if(!hasEdits())state.base=host.raw();render();status(hasEdits()&&state.editContract!==value.digest?'Sözleşme değişti; alan taslağı korundu. JSON’u değiştirmeden alan taslağını açıkça bırakın. / Contract changed; field edits retained. Discard field edits explicitly; raw JSON remains.':value.coverage.supported_observed_count?'Beyanlı alanlar hazır; eksikler JSON’da. / Declared fields ready; missing fields use JSON.':'Bu örnek için beyanlı alan kontrolü yok; JSON kullanın. / No declared typed controls for this example; use JSON.');save();
   }catch(error){if(own===ticket&&snapshot===context())status(error.message);}
   finally{if(pendingTicket===own){pending=false;pendingTicket=0;}controls();}
  });
  $('family-editor-apply').addEventListener('click',()=>{
   if(pending||!sameBinding()||!hasEdits()||state.base!==host.raw()||state.editContract!==state.schema.digest)return;
   try{
    const raw=host.raw(),parsed=parse(raw),replacements=[];
    for(const[key,edit]of Object.entries(state.edits)){
     const span=parsed.spans.get(key);if(!span)throw Error('Field path changed; draft retained');
     // Enum text edits are already JSON tokens; ordinary string controls are plain text.
     let node=state.schema.parameters;for(const part of JSON.parse(key).slice(1))node=typeof part==='number'?node.items:node.properties?.[part];
     const replacement=node?.enum||edit.kind==='boolean'?edit.text:edit.kind==='string'?JSON.stringify(edit.text):edit.text;
     const value=parse(replacement).spec;if(edit.kind==='integer'&&!Number.isInteger(value)||['number','integer'].includes(edit.kind)&&typeof value!=='number'||edit.kind==='string'&&typeof value!=='string'||edit.kind==='boolean'&&typeof value!=='boolean')throw Error('Complete typed value required; field draft retained');
     replacements.push({...span,token:replacement});
    }
    let next=raw;for(const r of replacements.sort((a,b)=>b.start-a.start))next=next.slice(0,r.start)+r.token+next.slice(r.end);
    parse(next);state.edits={};state.editContract=null;invalidate();host.write(next);state.base=next;render();status('Alan düzenlemeleri JSON’a uygulandı; doğrulayın. / Edits applied to JSON; validate before preparation.');save();
   }catch(error){status(error.message);}
  });
  $('family-editor-discard').addEventListener('click',()=>{state.edits={};state.editContract=null;invalidate();state.base=host.raw();render();status('Alan taslağı açıkça bırakıldı; JSON korundu. / Field edits discarded explicitly; JSON retained.');save();});
  $('family-editor-toggle').addEventListener('click',()=>{state.open=!state.open;controls();save();});
  $('family-editor-validate').addEventListener('click',async()=>{
   if(pending||!sameBinding()||hasEdits())return;const checked=host.check({forValidation:true});if(checked.error)return;
   const raw=host.raw(),schema=state.schema,data={...binding(),engine:checked.data.engine,raw_spec:raw,contract_digest:schema.digest,claims:checked.data.claims,...(checked.data.planning?{planning:checked.data.planning}:{})},snapshot=context(),own=++ticket;
   pending=true;pendingTicket=own;result=null;if(state.validationRequired)state.validatedDraft=null;$('family-editor-normalized').textContent='';save();controls();status('Yerel doğrulama sürüyor / Validating locally');
   try{
    parse(raw);const rawHash=await sha(raw);
    if(data.claims.length){const refs=await host.request('/api/writing-contexts/'+encodeURIComponent(data.account));if(refs.account!==data.account)throw Error('Source account mismatch');data.source_revision=refs.sources?.revision||null;data.canon_revision=refs.canon?.revision||null;}
    if(own!==ticket||snapshot!==context())return;
    const value=await host.request('/api/template-families/validate',data);if(own!==ticket||snapshot!==context())return;
    if(value?.schema_version!==1||!['account','family','version','example','engine','contract_digest'].every(k=>value[k]===data[k])||value.raw_sha256!==rawHash||!hex(value.request_digest)||value.source_revision!==(data.source_revision??null)||value.canon_revision!==(data.canon_revision??null)||!same(value.planning,data.planning??null)||typeof value.normalization_changed!=='boolean'||value.authorization!==false||value.actual_render!==false||value.provider_calls!==0)throw Error('Unconfirmed validation reply; raw draft retained');
    const normalized=parse(JSON.stringify(value.normalized_spec)).spec;if(normalized?.id!==data.family||normalized?.version!==data.version||!normalized.parameters||typeof normalized.parameters!=='object'||Array.isArray(normalized.parameters)||Object.keys(normalized).some(k=>!['id','version','parameters'].includes(k)))throw Error('Invalid normalized identity');
    state.validatedDraft=validationKey();result={value,context:snapshot,data};$('family-editor-normalized').textContent='Sunucu değerleri / Server values (JSON Number; normalizasyon ve varsayılanlar):\n'+JSON.stringify(normalized,null,2);status('Doğrulandı; JSON değiştirilmedi. Aşağıdaki değerleri inceleyin. Hazırlama yeniden doğrular. / Validated; raw JSON unchanged. Review normalized values; preparation revalidates.');save();
   }catch(error){if(own===ticket&&snapshot===context()){if(error.validationRejected){state.validationRequired=true;state.validatedDraft=null;save();}status(error.message);}}
   finally{if(pendingTicket===own){pending=false;pendingTicket=0;}controls();}
  });
  $('family-editor-normalize').addEventListener('click',async()=>{
   controls();if(pending||!result||result.context!==context())return;const captured=result,own=++ticket;pending=true;pendingTicket=own;controls();
   try{
    if(captured.data.claims.length){const refs=await host.request('/api/writing-contexts/'+encodeURIComponent(captured.data.account));if(refs.account!==captured.data.account||(refs.sources?.revision||null)!==captured.value.source_revision||(refs.canon?.revision||null)!==captured.value.canon_revision)throw Error('Source/canon changed; validate again');}
    if(own!==ticket||captured.context!==context())return;
    const raw=JSON.stringify(captured.value.normalized_spec,null,2);parse(raw);invalidate();host.write(raw);state.base=raw;state.validatedDraft=validationKey();render();status('İncelenen normalizasyon açıkça uygulandı. / Reviewed normalization applied explicitly.');save();
   }catch(error){if(own===ticket&&captured.context===context()){status(error.message);result=null;}}
   finally{if(pendingTicket===own){pending=false;pendingTicket=0;}controls();}
  });
  return {
   readSpec:raw=>parse(raw).spec,
   withPalette:(raw,palette)=>{
    const parsed=parse(raw),span=parsed.spans.get(JSON.stringify(['parameters','palette']));
    if(!span||!palette||Object.keys(palette).sort().join(',')!=='accent,background,ink,muted'||Object.values(palette).some(c=>typeof c!=='string'||!/^#[0-9A-F]{6}$/.test(c)))throw Error('Desteklenen palet alanı yok / Supported palette field unavailable');
    const next=raw.slice(0,span.start)+JSON.stringify(palette,null,2)+raw.slice(span.end);
    parse(next);return next;
   },
   snapshot:()=>JSON.parse(JSON.stringify(state)),
   restore:value=>{invalidate();state=value?JSON.parse(JSON.stringify(value)):{schema:null,base:host.raw(),edits:{},editContract:null,open:true,validationRequired:false,validatedDraft:null};pending=false;pendingTicket=0;status('Alanlar mevcut JSON’u korur. / Fields preserve the raw draft.');render();controls();},
   rawChanged:()=>{invalidate();if(!hasEdits())state.base=host.raw();render();controls();},
   controls,
   blocking:({forValidation=false}={})=>hasEdits()?'Uygulanmamış alan taslağı var; uygula veya bırak. / Apply or discard pending field edits.':!forValidation&&state.validationRequired&&state.validatedDraft!==validationKey()?'Doğrulama başarısız; güncel taslağı yerel doğrulayın. / Validate the current draft before preparation.':null,
  };
 }
 globalThis.StoryMotionTemplateEditor={connect};
})();
