'use strict';
(()=>{
 const get=id=>document.getElementById(id);if(!get('workflow-card'))return;
 const labels={bounded:'Var · sınırlı',partial:'Kısmi',missing:'Eksik',unverified:'Doğrulanmadı',not_applicable:'Bu provada gerekmiyor'};
 let epoch=0;
 const node=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;return n;};
 const clear=message=>{get('workflow-summary').textContent=message;get('workflow-context').textContent='';get('workflow-evidence').textContent='';get('workflow-stages').replaceChildren();};
 globalThis.workflowAccountChanged=async account=>{
  const own=++epoch;clear('Prosedür okunuyor…');
  try{
   const response=await fetch('/api/workflows',{cache:'no-store',credentials:'same-origin'});
   if(!response.ok)throw Error('Süreç kaydı okunamadı');const value=await response.json();if(own!==epoch)return;
   const profile=value.profiles.find(p=>p.account===account);if(!profile||profile.publication_ready!==false||value.publication_ready!==false)throw Error('Süreç kabul durumu belirsiz');
   const counts=profile.stages.reduce((c,r)=>(c[r.status]=(c[r.status]||0)+1,c),{});
   get('workflow-summary').textContent=Object.entries(labels).filter(([id])=>counts[id]).map(([id,label])=>`${counts[id]} ${label.toLocaleLowerCase('tr')}`).join(' · ');
   get('workflow-context').textContent=profile.topic+' · sürümlü konu prosedürü';
   get('workflow-evidence').textContent='Bu kaynak sürümünün native kabulü bekliyor. İnsan ve ticari kabul açık.';
   const rows=[];
   for(const step of profile.stages){
    if(!labels[step.status])throw Error('Süreç durumu tanınmıyor');
    const row=node('li','');row.className='workflow-step';const heading=node('div','');heading.className='workflow-step-heading';
    heading.append(node('strong',step.label),node('span',labels[step.status]));row.append(heading,node('p',step.implemented_scope),node('p','Sonraki: '+step.remaining));rows.push(row);
   }
   get('workflow-stages').replaceChildren(...rows);
  }catch(error){if(own===epoch)clear('Süreç durumu doğrulanamadı; yeniden okuyun.');}
 };
 if(typeof state!=='undefined'&&state.account)globalThis.workflowAccountChanged(state.account.id);
})();
