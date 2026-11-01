// Owned scene-graph sampling. No clocks, network, HTML inputs or random state.
const esc=value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const clamp=n=>Math.max(0,Math.min(1,n));
function ease(p,name){p=clamp(p);if(name==='none')return p;if(name==='power2.inOut')return p<.5?4*p*p*p:1-Math.pow(-2*p+2,3)/2;return 1-Math.pow(1-p,3);}
// GSAP's object clock has six decimal places. Recover an exact 30fps video
// boundary only within half a microsecond; arbitrary seek times stay intact.
export function videoFrameTime(seconds){const frame=Math.round(seconds*30)/30;return Math.abs(seconds-frame)<=.0000005?frame:seconds;}
export function sampleMotion(motions,seconds){
 seconds=videoFrameTime(seconds);
 const state={x:0,y:0,scaleX:1,scaleY:1,rotation:0,opacity:1},seen=new Set();
 const sorted=[...motions].sort((a,b)=>a.start-b.start);
 for(const motion of sorted)for(const [k,v] of Object.entries(motion.from))if(!seen.has(k)){state[k]=v;seen.add(k);}
 for(const motion of sorted){if(seconds<motion.start)continue;const p=motion.duration===0?1:ease((seconds-motion.start)/motion.duration,motion.ease);for(const [k,v] of Object.entries(motion.to))state[k]=motion.from[k]+(v-motion.from[k])*p;}
 return state;
}
export function familyFrameSvg(scene,seconds){
 if(!Number.isFinite(seconds)||seconds<0)throw Error('Bounded frame time required');
 function render(n){
  const attrs=Object.entries(n.attrs).map(([k,v])=>`${k}="${esc(v)}"`).join(' ');
  const content=n.text===null?n.children.map(render).join(''):esc(n.text);
  const raw=`<${n.tag} ${attrs}>${content}</${n.tag}>`;
  if(!n.id)return raw;
  const v=sampleMotion(n.motion,seconds),dash=v.strokeDashoffset===undefined?'':` stroke-dashoffset="${v.strokeDashoffset}"`;
  return `<g id="${esc(n.id)}" transform="translate(${v.x} ${v.y}) rotate(${v.rotation}) scale(${v.scaleX} ${v.scaleY})" opacity="${v.opacity}"${dash}>${raw}</g>`;
 }
 return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920" width="1080" height="1920" role="img" aria-label="Parametrik şablon sahnesi">${scene.nodes.map(render).join('')}</svg>`;
}
