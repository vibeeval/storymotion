// Pure canonical scene sampling. No clock, DOM measurements, provider data or IO.
export function sampleMotion(operations,seconds){
 if(!Number.isFinite(seconds))throw Error('Finite local scene time required');
 const state={};
 for(const op of operations){
  const prior=state[op.target]||{};
  if(op.op==='set'){state[op.target]={...prior,...op.values};continue;}
  const t=Math.min(1,Math.max(0,(seconds-op.offset)/op.duration));
  const p=t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
  const value={...prior,...op.before};
  for(const [key,end]of Object.entries(op.after))value[key]=typeof end==='number'?op.before[key]+(end-op.before[key])*p:end;
  state[op.target]=value;
 }
 return state;
}
export function applyMotion(vector,ident,operations,seconds){
 let svg=vector;
 for(const [name,s]of Object.entries(sampleMotion(operations,seconds))){
  const id=ident+'-'+name,origin=String(s.svgOrigin||'0 0').split(' ').map(Number),[ox,oy]=origin;
  const transform=`translate(${s.x||0} ${s.y||0}) translate(${ox} ${oy}) rotate(${s.rotation||0}) scale(${s.scale??1}) translate(${-ox} ${-oy})`;
  svg=svg.replace(new RegExp('<(g|circle|path)([^>]*\\bid="'+id+'"[^>]*)>'),(_,tag,attrs)=>`<${tag}${attrs} transform="${transform}" opacity="${s.opacity??1}">`);
 }
 return svg;
}
