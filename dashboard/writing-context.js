'use strict';
(()=>{
 const $=id=>document.getElementById(id);if(!$('writing-context-panel'))return;
 let current=null,epoch=0,busy=false,editorAccount=null;
 const drafts={sources:{version:0,dirty:false},canon:{version:0,dirty:false}};
 const dirty=()=>Object.values(drafts).some(draft=>draft.dirty);
 const same=account=>current!==null&&typeof account==='string'&&current.account===account;
 const compatible=()=>!current?.canon||current.canon.data.source_revision===(current.sources?.revision||null);
 globalThis.writingContextReady=account=>same(account)&&!busy&&!dirty()&&compatible();
 globalThis.writingContextRefs=account=>same(account)?{...(current.sources?{source_revision:current.sources.revision}:{}),...(current.canon?{canon_revision:current.canon.revision}:{})}:{};
 function invalidate(){if(typeof writer!=='undefined'&&writer.result&&(dirty()||!same(state.account?.id)||!compatible()||['source_revision','canon_revision'].some(k=>writer.result.context?.[k]!==writingContextRefs(state.account?.id)[k])))writer.result={...writer.result,context_current:false};if(typeof writerInvalidate==='function')writerInvalidate();if(typeof writerControls==='function')writerControls();}
 function apply(data,savedKind=null,savedVersion=null,readVersions=null){if(!data||data.account!==state.account?.id)throw Error('Kaynak hesabı eşleşmedi');current=data;busy=false;
  for(const kind of ['sources','canon']){
   const draft=drafts[kind];
   // A save owns only its submitted editor version. Other dirty drafts and
   // edits made during the await remain local, even when server heads advance.
   if(!draft.dirty||(kind===savedKind&&draft.version===savedVersion)||(readVersions&&draft.version===readVersions[kind])){
    $('writing-'+kind+'-json').value=JSON.stringify(data[kind]?.data||{},null,2);draft.dirty=false;
    for(const id of kind==='sources'?['writing-source-rights']:['writing-canon-confirm','writing-canon-rights'])$(id).checked=false;
   }
  }
  $('writing-canon-area').hidden=!packSerial(data.account);
  $('writing-context-status').textContent=(dirty()?'Kaydedilmemiş yerel düzenlemeler korundu; üretim onayı kullanılamaz. ':'')+(!compatible()?'Kaynak ve önceki bölüm sürümü eşleşmiyor; önceki final referansını açıkça güncelleyin.':(data.sources?'Kaynak '+data.sources.revision.slice(0,12):'Kaynak kaydı boş')+' · '+(data.canon?'Önceki final referansı '+data.canon.revision.slice(0,12):'Accepted bölüm referansı yok')+' · İnsan kaynak kabulü bekliyor.');
  invalidate();}
 globalThis.writingContextChanged=async account=>{const own=++epoch;busy=true;current=null;if(editorAccount!==account){editorAccount=account;for(const kind of ['sources','canon']){drafts[kind].version++;drafts[kind].dirty=false;$('writing-'+kind+'-json').value='{}';}}const readVersions={sources:drafts.sources.version,canon:drafts.canon.version};invalidate();$('writing-context-status').textContent='Kaynak kaydı okunuyor…';
  try{const response=await fetch('/api/writing-contexts/'+encodeURIComponent(account),{cache:'no-store',credentials:'same-origin'});if(!response.ok)throw Error('Kaynak kaydı okunamadı');const data=await response.json();if(own===epoch)apply(data,null,null,readVersions);}
  catch(error){if(own===epoch){busy=false;current=null;$('writing-context-status').textContent='Kaynak durumu doğrulanamadı; yeniden okuyun.';invalidate();}}};
 for(const kind of ['sources','canon'])$('writing-'+kind+'-json').addEventListener('input',()=>{drafts[kind].version++;drafts[kind].dirty=true;$('writing-context-status').textContent='Yerel değişiklik kaydedilmedi; mevcut üretim onayı kullanılmaz.';invalidate();});
 async function save(kind){if(busy||!same(state.account?.id))return;const account=state.account.id,own=epoch,editor=kind==='accept-reference'?'canon':'sources',savedVersion=drafts[editor].version;busy=true;invalidate();
  try{const canon=kind==='accept-reference';const body=canon?{account,expected_revision:current.canon?.revision||null,reference:JSON.parse($('writing-canon-json').value),accepted_final_confirmed:$('writing-canon-confirm').checked,rights_confirmed:$('writing-canon-rights').checked}:{account,expected_revision:current.sources?.revision||null,sources:JSON.parse($('writing-sources-json').value),rights_confirmed:$('writing-source-rights').checked};
   const result=await api('/api/writing-context/'+kind,body);if(own===epoch)apply(result,editor,savedVersion);
  }catch(error){if(own===epoch){busy=false;drafts[editor].dirty=true;$('writing-context-status').textContent=error.message||'Kayıt kaydedilmedi; tekrar okuyun.';invalidate();}}
 }
 $('writing-save-sources').addEventListener('click',()=>save('save-sources'));
 $('writing-accept-reference').addEventListener('click',()=>save('accept-reference'));
 $('writing-context-reload').addEventListener('click',()=>writingContextChanged(state.account?.id));
 if(typeof state!=='undefined'&&state.account)writingContextChanged(state.account.id);
})();
