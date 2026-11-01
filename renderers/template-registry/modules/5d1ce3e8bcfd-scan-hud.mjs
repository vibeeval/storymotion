// Original procedural scan → target lock → gauge sequence; not a color profile.
import {VERSION,FPS,defaulted,validateBase,keys,number,text,fitText,fail,smooth,sampleTime,fmt,esc,frameShell,svgText} from './cabbfda44beb-shared.mjs';

export const ID='scan-hud';
export const SOURCE_ID='source-mg-style-22-hud';
export const DEFAULT_PALETTE=Object.freeze({background:'#101E2A',ink:'#E6F4E9',muted:'#8EAEAC',accent:'#7FE7C4'});
export const RADAR_RADIUS=300;
// Reserve a readable, frame-aligned final rest; cue/audio use the full clip clock.
export const FINAL_HOLD_FRAMES=18;
export const PARAMETER_SCHEMA=Object.freeze({
  targets:{minimumItems:2,maximumItems:4,item:{id:{pattern:'^[a-z][a-z0-9-]{0,19}$'},label:{maxLength:65},bearing:{minimum:-170,maximum:170},range:{minimum:.18,maximum:.92},value:{minimum:0,maximum:'gauge_max'}}},
  range_rings:{minimum:2,maximum:5,integer:true},sweep_turns:{minimum:1,maximum:3,integer:true},
  lock_at:{minimum:.25,maximum:.5},gauge_at:{minimum:.6,maximum:.8},gauge_max:{minimum:1,maximum:1000},unit:{maxLength:12},
});
export function validateSpec(spec) {
  const p=validateBase(spec,ID,['targets'],['range_rings','sweep_turns','lock_at','gauge_at','gauge_max','unit'],DEFAULT_PALETTE);
  const raw=spec.parameters;
  p.range_rings=number(defaulted(raw.range_rings,3),'range rings',2,5,true);
  p.sweep_turns=number(defaulted(raw.sweep_turns,1),'sweep turns',1,3,true);
  p.lock_at=number(defaulted(raw.lock_at,.4),'lock fraction',.25,.5);
  p.gauge_at=number(defaulted(raw.gauge_at,.65),'gauge fraction',.6,.8);
  if (p.gauge_at-p.lock_at<.1-1e-9) fail('gauge must follow a completed lock window');
  p.gauge_max=number(defaulted(raw.gauge_max,100),'gauge maximum',1,1000);
  p.unit=text(defaulted(raw.unit,'%'),'unit',12);
  if (!Array.isArray(raw.targets)||raw.targets.length<2||raw.targets.length>4) fail('targets: 2–4 targets required');
  const seen=new Set();
  p.targets=raw.targets.map((item,i)=>{
    keys(item,['id','label','bearing','range','value'],[],`target ${i}`);
    if (typeof item.id!=='string'||!/^[a-z][a-z0-9-]{0,19}$/u.test(item.id)||seen.has(item.id)) fail('unique short target IDs required');
    seen.add(item.id);const label=text(item.label,'target label',65);
    fitText(label,{maximum:32,minimum:26,maxLines:2});
    return {id:item.id,label,bearing:number(item.bearing,'bearing',-170,170),
      range:number(item.range,'range',.18,.92),value:number(item.value,'target value',0,p.gauge_max)};
  });
  const points=p.targets.map(targetPoint);
  for (let a=0;a<points.length;a++) for (let b=a+1;b<points.length;b++) {
    if (Math.hypot(points[a].x-points[b].x,points[a].y-points[b].y)<70) fail('target markers require at least 70 pixels of separation');
  }
  return {id:ID,version:VERSION,parameters:p};
}
export function targetPoint(target) {
  const angle=target.bearing*Math.PI/180,radius=target.range*RADAR_RADIUS;
  return {x:Math.sin(angle)*radius,y:-Math.cos(angle)*radius};
}
export function arcPath(radius,fraction) {
  number(radius,'arc radius',1,300);number(fraction,'arc fraction',0,1);
  const start=-120*Math.PI/180,end=start+240*Math.PI/180*fraction;
  const a={x:Math.sin(start)*radius,y:-Math.cos(start)*radius},b={x:Math.sin(end)*radius,y:-Math.cos(end)*radius};
  return `M${fmt(a.x)} ${fmt(a.y)}A${fmt(radius)} ${fmt(radius)} 0 ${fraction>.75?1:0} 1 ${fmt(b.x)} ${fmt(b.y)}`;
}
function state(p,seconds) {
  const time=sampleTime(seconds,p.duration);
  const animationDuration=(Math.round(p.duration*FPS)-FINAL_HOLD_FRAMES)/FPS;
  const holding=time>=animationDuration;
  const position=Math.min(time,animationDuration)/animationDuration*p.targets.length;
  const index=Math.min(p.targets.length-1,Math.floor(position)),local=position-index,target=p.targets[index];
  const scan=smooth(local/p.lock_at),lock=smooth((local-p.lock_at)/.1);
  const gauge=smooth((local-p.gauge_at)/(1-p.gauge_at));
  return {seconds:time,animationDuration,finalHoldSeconds:FINAL_HOLD_FRAMES/FPS,holding,index,local,targetId:target.id,target:targetPoint(target),
    phase:local<p.lock_at?'scan':local<p.gauge_at?'lock':'gauge',
    scanAngle:target.bearing-360*p.sweep_turns*(1-scan),lockProgress:lock,
    reticleSize:86-52*lock,gaugeProgress:gauge,gaugeValue:target.value*gauge,
    gaugeRatio:target.value/p.gauge_max*gauge,completed:index+(local===1?1:0)};
}
export function sampleFrame(spec,seconds) { return state(validateSpec(spec).parameters,seconds); }
export function renderFrame(spec,seconds) {
  const p=validateSpec(spec).parameters,s=state(p,seconds),c=p.palette;
  const rings=Array.from({length:p.range_rings},(_,i)=>`<circle r="${fmt(RADAR_RADIUS*(i+1)/p.range_rings)}"/>`).join('');
  const ticks=Array.from({length:24},(_,i)=>{
    const angle=i*Math.PI/12,r=i%3?RADAR_RADIUS-8:RADAR_RADIUS-18;
    return `<path d="M${fmt(Math.sin(angle)*r)} ${fmt(-Math.cos(angle)*r)}L${fmt(Math.sin(angle)*(RADAR_RADIUS+5))} ${fmt(-Math.cos(angle)*(RADAR_RADIUS+5))}"/>`;
  }).join('');
  const markers=p.targets.map((target,i)=>{
    const point=targetPoint(target),active=i===s.index,done=i<s.completed;
    return `<g transform="translate(${fmt(point.x)} ${fmt(point.y)})" opacity="${done?1:active?.7:.24}"><circle r="7" fill="${active?c.accent:c.muted}"/><text x="14" y="-12" font-size="21" fill="${c.ink}">${i+1}</text></g>`;
  }).join('');
  const r=s.reticleSize,arm=16;
  const reticle=[[-1,-1],[1,-1],[1,1],[-1,1]].map(([x,y])=>`M${fmt(x*(r-arm))} ${fmt(y*r)}H${fmt(x*r)}V${fmt(y*(r-arm))}`).join('');
  const status=s.phase==='scan'?'TARAMA':s.phase==='lock'?'HEDEF KİLİDİ':'ÖLÇÜM';
  const body=`<text x="90" y="550" fill="${c.accent}" font-size="28">${status} · ${s.index+1}/${p.targets.length}</text><g transform="translate(540 920)"><g fill="none" stroke="${c.muted}" stroke-width="1.5" opacity="0.55">${rings}${ticks}<path d="M-320 0H320M0 -320V320"/></g><g transform="rotate(${fmt(s.scanAngle)})" opacity="${s.phase==='scan'?.8:.22}"><path d="M0 0L-52 -295A300 300 0 0 1 0 -300Z" fill="${c.accent}" fill-opacity="0.15"/><path d="M0 0V-300" stroke="${c.accent}" stroke-width="3"/></g>${markers}<g transform="translate(${fmt(s.target.x)} ${fmt(s.target.y)})" fill="none" stroke="${c.accent}" stroke-width="4" opacity="${fmt(s.lockProgress)}"><path d="${reticle}"/><circle r="${fmt(22+10*(1-s.lockProgress))}" stroke-width="1.5"/></g></g>${svgText(p.targets[s.index].label,{y:1295,maximum:32,minimum:26,maxLines:2,fill:c.ink})}<g transform="translate(540 1460)" fill="none"><path d="${arcPath(82,1)}" stroke="${c.muted}" stroke-width="9" opacity="0.4"/>${s.gaugeRatio>0?`<path d="${arcPath(82,s.gaugeRatio)}" stroke="${c.accent}" stroke-width="9"/>`:''}<text data-hud-gauge-value="true" y="8" text-anchor="middle" fill="${c.ink}" font-size="36">${s.holding?esc(String(p.targets[s.index].value)):fmt(Math.round(s.gaugeValue*10)/10)}</text><text y="45" text-anchor="middle" fill="${c.muted}" font-size="24">${esc(p.unit)}</text></g>`;
  return frameShell(ID,p,s.seconds,body);
}

// Direct public aliases retain the original validated frame API.
export const sample=sampleFrame;
export const render=renderFrame;
