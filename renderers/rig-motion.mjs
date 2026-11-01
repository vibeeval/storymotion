// Original neutral geometry and frame-addressed manual rig state; no IO or clocks.
const mouths='ABCDEFGHX'.split('');
const paletteNames=['background','ink','accent','muted'];
const finite=(n,lo,hi)=>{if(typeof n!=='number'||!Number.isFinite(n)||n<lo||n>hi)throw Error('Invalid neutral rig number');return n;};
const clamp=(n,lo,hi)=>Math.min(hi,Math.max(lo,n));
const n=v=>Number(v.toFixed(10)).toString();
const esc=v=>String(v).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const exact=(v,keys)=>{if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).sort().join('|')!==[...keys].sort().join('|'))throw Error('Invalid neutral rig fields');};
function checkedSpec(spec){
 if(!spec||spec.rig_id!=='neutral-presenter-1'||typeof spec.account!=='string'||!/^[a-z][a-z0-9-]{0,59}$/.test(spec.account)||spec.fps!==30)throw Error('Unsupported neutral rig spec');
 const d=finite(spec.audio_duration_seconds,1,90),t=finite(spec.timeline_duration_seconds,d,90);
 if(!Array.isArray(spec.mouthCues)||!spec.mouthCues.length||spec.mouthCues.length>2000)throw Error('Invalid rig mouth cues');
 let end=0;for(const c of spec.mouthCues){exact(c,['start','end','value']);finite(c.start,0,d);finite(c.end,c.start,d);if(c.end<=c.start||c.start!==end||!mouths.includes(c.value))throw Error('Invalid rig mouth range');end=c.end;}if(end!==d)throw Error('Rig mouth cues must cover actual audio');
 const tracks=spec.visual_tracks;exact(tracks,['blinks','head']);
 if(!Array.isArray(tracks.blinks)||tracks.blinks.length>80||!Array.isArray(tracks.head)||tracks.head.length<2||tracks.head.length>1000)throw Error('Invalid rig tracks');
 end=0;for(const b of tracks.blinks){exact(b,['start','end']);finite(b.start,end,t);finite(b.end,b.start,t);if(b.end<=b.start)throw Error('Invalid blink interval');end=b.end;}
 end=-1;for(const h of tracks.head){exact(h,['time','rotate','x','y']);finite(h.time,0,t);finite(h.rotate,-8,8);finite(h.x,-12,12);finite(h.y,-12,12);if(h.time<=end)throw Error('Head keys must increase');end=h.time;}
 if(tracks.head[0].time!==0||end!==t)throw Error('Head keys must cover the timeline');
 return spec;
}
export function sampleRig(spec,seconds){
 checkedSpec(spec);if(typeof seconds!=='number'||!Number.isFinite(seconds)||seconds < -1e12||seconds > 1e12)throw Error('Finite rig sample time required');
 const frame=Math.max(0,Math.floor(seconds*30+1e-7));if(!Number.isSafeInteger(frame))throw Error('Rig frame is outside safe range');
 const time=frame/30,d=spec.audio_duration_seconds,t=Math.min(time,spec.timeline_duration_seconds);
 let value='X';if(time<d){const cue=spec.mouthCues.find(c=>c.start<=time&&time<c.end);if(cue)value=cue.value;}
 const blink=spec.visual_tracks.blinks.some(b=>b.start<=time&&time<b.end);
 const keys=spec.visual_tracks.head;let a=keys[0],b=keys[keys.length-1];
 for(let i=1;i<keys.length;i++){if(t<=keys[i].time){a=keys[i-1];b=keys[i];break;}a=keys[i];}
 const p=b.time===a.time?0:clamp((t-a.time)/(b.time-a.time),0,1),head={};
 for(const key of ['rotate','x','y'])head[key]=a[key]+(b[key]-a[key])*p;
 return{frame,value,blink,head};
}
const numericAttrs={path:[],circle:['cx','cy','r'],ellipse:['cx','cy','rx','ry'],rect:['x','y','width','height','rx'],line:['x1','y1','x2','y2']};
function primitives(rows,palette){
 if(!Array.isArray(rows)||!rows.length||rows.length>16)throw Error('Invalid rig geometry list');
 return rows.map(shape=>{exact(shape,['tag','attrs']);const keys=numericAttrs[shape.tag];if(!keys)throw Error('Unsupported rig primitive');
  const attrs=shape.attrs;if(!attrs||typeof attrs!=='object'||Array.isArray(attrs)||Object.keys(attrs).length>16)throw Error('Invalid rig geometry attributes');
  for(const [key,val]of Object.entries(attrs)){
   if(key==='d'&&shape.tag==='path'){if(typeof val!=='string'||!val.length||val.length>1000||!/^[MmLlHhVvCcSsQqTtAaZz0-9eE+., \-]+$/.test(val))throw Error('Invalid rig path');}
   else if(['fill','stroke'].includes(key)){if(![...paletteNames,'none'].includes(val))throw Error('Invalid rig paint');}
   else if(key==='stroke-linecap'){if(!['butt','round','square'].includes(val))throw Error('Invalid rig cap');}
   else if(key==='stroke-linejoin'){if(!['round','miter','bevel'].includes(val))throw Error('Invalid rig join');}
   else if(keys.includes(key)||key==='stroke-width'){finite(val,-1000,1000);if(['r','rx','ry','width','height','stroke-width'].includes(key)&&val<0)throw Error('Invalid rig dimension');}
   else throw Error('Unsupported rig attribute');
  }
  if(shape.tag==='path'&&!('d'in attrs))throw Error('Rig path missing');
  const rendered=Object.entries(attrs).map(([k,v])=>`${k}="${esc(['fill','stroke'].includes(k)&&v!=='none'?palette[v]:typeof v==='number'?n(v):v)}"`).join(' ');
  return`<${shape.tag} ${rendered}/>`;
 }).join('');
}
export function rigSvg(definition,palette,state,mode='inset'){
 exact(definition,['schema_version','rig_id','license','coordinate_system','modes','body','head','eyes','mouths']);
 if(definition.schema_version!==1||definition.rig_id!=='neutral-presenter-1'||definition.license!=='original_project_vectors')throw Error('Unsupported rig definition');
 exact(definition.coordinate_system,['width','height','neck']);const coords=definition.coordinate_system;if(coords.width!==1080||coords.height!==1920||!Array.isArray(coords.neck)||coords.neck.length!==2||coords.neck[0]!==0||coords.neck[1]!==80)throw Error('Unsupported rig coordinate system');
 exact(definition.modes,['inset','serial-courier']);for(const [key,expected]of Object.entries({inset:{x:850,y:960,scale:.55},'serial-courier':{x:245,y:785,scale:1}})){exact(definition.modes[key],['x','y','scale']);for(const prop of ['x','y','scale'])if(definition.modes[key][prop]!==expected[prop])throw Error('Unsupported rig placement');}
 if(!['inset','serial-courier'].includes(mode))throw Error('Unsupported rig mode');
 if(!palette||paletteNames.some(k=>typeof palette[k]!=='string'||!/^#[0-9a-fA-F]{6}$/.test(palette[k])))throw Error('Invalid rig palette');
 if(!state||!mouths.includes(state.value)||typeof state.blink!=='boolean'||!state.head)throw Error('Invalid rig state');
 exact(state.head,['rotate','x','y']);const head={rotate:finite(state.head.rotate,-8,8),x:finite(state.head.x,-12,12),y:finite(state.head.y,-12,12)};
 exact(definition.eyes,['open','closed']);exact(definition.mouths,mouths);
 const body=primitives(definition.body,palette),face=primitives(definition.head,palette);
 let mouthMarkup='';for(const value of mouths){const m=definition.mouths[value];exact(m,['label','shapes']);if(typeof m.label!=='string'||m.label.length>200)throw Error('Invalid rig mouth description');mouthMarkup+=`<g id="neutral-rig-mouth-${value}" opacity="${value===state.value?1:0}">${primitives(m.shapes,palette)}</g>`;}
 const pos=definition.modes[mode],transform=`translate(${n(head.x)} ${n(head.y)}) translate(0 80) rotate(${n(head.rotate)}) translate(0 -80)`;
 return`<svg id="neutral-rig-layer" class="neutral-rig" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920" width="1080" height="1920" style="position:absolute;inset:0;width:1080px;height:1920px;pointer-events:none" aria-label="Özgün nötr karakter; elle hizalanmış görsel prova"><g id="neutral-rig-placement" transform="translate(${n(pos.x)} ${n(pos.y)}) scale(${n(pos.scale)})"><g id="neutral-rig-body">${body}</g><g id="neutral-rig-head" transform="${transform}">${face}<g id="neutral-rig-eyes-open" opacity="${state.blink?0:1}">${primitives(definition.eyes.open,palette)}</g><g id="neutral-rig-eyes-closed" opacity="${state.blink?1:0}">${primitives(definition.eyes.closed,palette)}</g>${mouthMarkup}</g></g></svg>`;
}
