// Local metadata only. External links never load media, scripts or executable code.
(()=>{
 const hex=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v),ident=v=>typeof v==='string'&&/^[a-z][a-z0-9-]{0,79}$/.test(v);
 const text=v=>typeof v==='string'&&v.length>0&&v.length<=200;
 const keys=(v,names)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).sort().join(',')===names.split(' ').sort().join(',');
 const unique=v=>Array.isArray(v)&&v.every(ident)&&new Set(v).size===v.length;
 const palette=v=>keys(v,'background ink muted accent')&&Object.values(v).every(c=>typeof c==='string'&&/^#[0-9A-F]{6}$/.test(c));
 const fold=v=>String(v).toLocaleLowerCase('tr').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replaceAll('ı','i');
 function validate(value,kind,account,families,paletteFamilies){
  if(!keys(value,'schema_version account kind items count provider_calls actual_render planning_supported revision')||value.schema_version!==1||value.account!==account||value.kind!==kind||!hex(value.revision)||value.provider_calls!==0||value.actual_render!==false||value.planning_supported!==false||!Array.isArray(value.items)||value.items.length>100||value.count!==value.items.length||!unique(value.items.map(r=>r?.id)))throw Error('Geçersiz katalog yanıtı / Invalid catalog response');
  for(const row of value.items){
   if(!text(row.name)||!unique(row.family_ids)||!row.family_ids.length||row.family_ids.some(id=>!families.includes(id))||row.preview_url!==null||row.planning_mapping!==null)throw Error('Geçersiz katalog alanı / Invalid catalog field');
   if(kind==='references'){
    if(!keys(row,'id name kind repository_url reference_urls commit license attribution notice_path notice_sha256 license_scope asset_rights reference_only preview_url preview_state family_ids planning_mapping')||row.kind!=='technique_reference'||!/^https:\/\/github\.com\/[A-Za-z0-9_-]+\/[A-Za-z0-9_.-]+$/.test(row.repository_url)||typeof row.commit!=='string'||!(/^[a-f0-9]{40}$/).test(row.commit)||!Array.isArray(row.reference_urls)||!row.reference_urls.length||new Set(row.reference_urls).size!==row.reference_urls.length||row.reference_urls.some(url=>typeof url!=='string'||!url.startsWith(row.repository_url+'/blob/'+row.commit+'/')||!/^https:\/\/github\.com\/[A-Za-z0-9_./-]+$/.test(url))||row.license!=='MIT'||!text(row.attribution)||row.notice_path!=='vendor/notices/mg-styles-15-MIT.txt'||!hex(row.notice_sha256)||row.license_scope!=='bounded_code_only'||row.asset_rights!=='not_assessed'||row.reference_only!==true||row.preview_state!=='missing_preview')throw Error('Geçersiz referans / Invalid reference');
   }else if(!keys(row,'id name kind palette origin_family license_scope preview_url preview_state compatibility planning_mapping family_ids excluded_family_ids')||row.kind!=='palette'||!palette(row.palette)||!['kinetic-grid','causal-path','exploded-blueprint','isometric-process'].includes(row.origin_family)||!unique(row.excluded_family_ids)||row.excluded_family_ids.some(id=>!paletteFamilies.includes(id)||row.family_ids.includes(id))||[...row.family_ids,...row.excluded_family_ids].sort().join(',')!==[...paletteFamilies].sort().join(',')||row.license_scope!=='original_product_terms'||row.preview_state!=='palette_values_only'||row.compatibility!=='development_common_palette')throw Error('Geçersiz palet / Invalid palette');
  }
  return value.items;
 }
 function connect(host){
  const $=host.get;
  function mount(name,kind,path){
   const id='family-'+name+'-',get=part=>$(id+part),say=s=>{get('status').textContent=s;};
   let rows=[],loadedAccount='',ticket=0,pending=false,selected='',selectedContext='',lastContext=host.context();
   const account=()=>host.account();
   function visible(){const q=fold(get('search').value.trim()),filter=get('filter').value,family=host.family();return rows.filter(r=>(!q||fold([r.id,r.name,r.kind,r.license_scope,...r.family_ids].join(' ')).includes(q))&&(!filter||filter==='compatible'&&r.family_ids.includes(family)||filter==='unknown_rights'&&r.asset_rights==='not_assessed'));}
   function clear(){selected='';selectedContext='';get('detail').hidden=true;get('meta').replaceChildren();get('apply').disabled=true;explain();}
   function explain(){
    if(kind!=='styles')return;
    const row=rows.find(r=>r.id===selected),family=host.family(),node=get('apply-reason');
    const incompatible=Boolean(row&&family&&selectedContext===host.context()&&!row.family_ids.includes(family));
    const message=incompatible?family+' bu palet ile uyumlu değil; desteklenen eşleşmeler Uyumluluk bölümünde listelenir. / This palette does not support the selected template; see Compatibility.':'';
    if(node.textContent!==message)node.textContent=message;node.hidden=!incompatible;
   }
   function details(row){
    selected=row.id;selectedContext=host.context();get('detail').hidden=false;
    get('title').textContent=row.name+' · '+row.id;
    const fields=[['Kapsam / Scope',kind==='references'?'Yalnız referans; üçüncü taraf kaynak, film veya medya içe aktarılmaz. / Reference only.':'Yeniden kullanılabilir renk paleti; hareket veya yeni template değildir. / Reusable palette, not a motion preset.'],
     ['Haklar / Rights',row.license_scope+(kind==='references'?' · MIT kod bildirimi; diğer asset hakları değerlendirilmedi. / Other asset rights unknown.':' · Özgün ürün koşulları; template/toolchain hakları ayrıdır. / Template/toolchain rights remain separate.')],
     ['Önizleme / Preview',kind==='references'?'Önizleme yok / Missing preview':'Yalnız renk değerleri / Palette values only; no video preview'],
     ['Uyumluluk / Compatibility',row.family_ids.join(', ')],
     ['Plan / Planning','Bu kayıt için kayıtlı niş/konu planı bağlantısı yok. / No supported saved planning mapping.']];
    if(kind==='references')fields.push(['Atıf / Attribution',row.attribution],['Commit',row.commit]);
    else fields.push(['Palet / Palette',JSON.stringify(row.palette,null,2)],['Desteklenmeyen / Unsupported',row.excluded_family_ids.join(', ')||'Bu sınırlı palet sözleşmesinde yok / None in the bounded palette scope']);
    const nodes=[];for(const[label,value]of fields){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;nodes.push(dt,dd);}
    if(kind==='references')for(const url of [row.repository_url,...row.reference_urls]){const dt=document.createElement('dt'),dd=document.createElement('dd'),a=document.createElement('a');dt.textContent='Dış kaynak / External reference';a.textContent=url;a.setAttribute('href',url);a.setAttribute('target','_blank');a.setAttribute('rel','noopener noreferrer');dd.append(a);nodes.push(dt,dd);}
    get('meta').replaceChildren(...nodes);render();
   }
   function render(){
    const found=visible();if(selected&&!found.some(r=>r.id===selected))clear();
    get('count').textContent=found.length+' / '+rows.length+' '+(kind==='references'?'kaynak referansı / references':'palet / palettes')+' · 91 template / 182 input examples ayrı katalogdadır. / Separate executable catalog.';
    get('empty').hidden=found.length>0||!loadedAccount;
    const active=document.activeElement,focusId=get('cards').contains(active)?active?.dataset?.catalogItem:null;
    const nodes=found.map(row=>{const li=document.createElement('li'),button=document.createElement('button');button.type='button';button.dataset.catalogItem=row.id;button.setAttribute('aria-controls',id+'detail');button.setAttribute('aria-pressed',String(selected===row.id));button.textContent=row.name+' · '+row.license_scope+' · '+row.preview_state;button.addEventListener('click',()=>details(row));li.append(button);return li;});
    get('cards').replaceChildren(...nodes);
    if(focusId){const n=nodes.find(n=>n.children[0].dataset.catalogItem===focusId);(n?n.children[0]:get('search')).focus({preventScroll:true});}
    const row=rows.find(r=>r.id===selected);
    get('apply').hidden=kind==='references';get('apply').disabled=pending||kind!=='styles'||selectedContext!==host.context()||!row?.family_ids.includes(host.family())||!host.canApply();
    get('load').disabled=!account()||pending;explain();
   }
   function sync(){
    const next=host.context();if(next!==lastContext){lastContext=next;ticket++;pending=false;clear();
     if(loadedAccount!==account()){rows=[];loadedAccount='';}
     say('Seçim değişti; ayrıntıyı yeniden seçin. / Context changed; select details again.');render();
    }else{
     get('load').disabled=!account()||pending;
     const row=rows.find(r=>r.id===selected);
     get('apply').disabled=pending||kind!=='styles'||selectedContext!==host.context()||!row?.family_ids.includes(host.family())||!host.canApply();explain();
    }
   }
   get('load').addEventListener('click',async()=>{
    sync();if(pending||!account())return;const expected=host.context(),owner=account(),current=++ticket;pending=true;clear();render();say('Yerel metadata yükleniyor / Loading local metadata');
    try{const value=await host.request(path+encodeURIComponent(owner));if(current!==ticket||expected!==host.context()||owner!==account())return;
     rows=validate(value,kind,owner,host.families(),host.paletteFamilies());loadedAccount=owner;render();say('Yerel metadata yüklendi; render kabulü değildir. / Local metadata loaded, not render acceptance.');
    }catch(error){if(current===ticket&&expected===host.context()){rows=[];loadedAccount='';clear();render();say('Katalog yüklenemedi / Catalog unavailable: '+error.message);}}
    finally{if(current===ticket){pending=false;render();}}
   });
   for(const part of ['search','filter'])get(part).addEventListener(part==='search'?'input':'change',render);
   get('reset').addEventListener('click',()=>{get('search').value='';get('filter').value='';render();});
   get('close').addEventListener('click',()=>{const previous=selected;clear();render();const li=[...get('cards').children].find(n=>n.children[0].dataset.catalogItem===previous);(li?li.children[0]:get('search')).focus();});
   get('apply').addEventListener('click',()=>{
    const row=rows.find(r=>r.id===selected);if(kind!=='styles'||pending||selectedContext!==host.context()||loadedAccount!==account()||!visible().includes(row)||!row?.family_ids.includes(host.family())||!host.canApply())return;
    try{host.apply(row.palette);say('Palet yalnız geçerli RAM JSON taslağına uygulandı. Yerel doğrulama/hazırlama ayrı işlemdir. / Palette applied to the current RAM JSON draft only.');}
    catch(error){say('Palet uygulanmadı; taslak korundu / Palette not applied; draft retained: '+error.message);}
   });
   render();return sync;
  }
  const syncs=[mount('references','references','/api/reference-catalog/'),mount('styles','styles','/api/style-gallery/')];
  return {controls:()=>syncs.forEach(sync=>sync())};
 }
 globalThis.StoryMotionReferenceGallery={connect};
})();
