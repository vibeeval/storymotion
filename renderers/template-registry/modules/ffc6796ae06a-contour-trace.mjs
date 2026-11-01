// Original continuous contour construction and clipped hatching. No node graph.
import {VERSION,defaulted, validateBase, choice, number, text, fitText, windowPair, fail, phaseAt,
  sampleTime, motionTime, fmt, frameShell, svgText} from './cabbfda44beb-shared.mjs';

export const ID = 'contour-trace';
export const SOURCE_ID = 'source-mg-style-02-line-art';
export const DEFAULT_PALETTE = Object.freeze({background:'#FAF6EC',ink:'#263A30',muted:'#647165',accent:'#9C4D30'});
export const PARAMETER_SCHEMA = Object.freeze({
  illustration: {enum:['leaf','vessel']}, width:{minimum:240,maximum:520}, height:{minimum:300,maximum:520},
  stroke_width:{minimum:2,maximum:8}, hatch_spacing:{minimum:10,maximum:30},
  draw_window:{normalized:true,minimumSpan:0.1}, hatch_window:{normalized:true,minimumSpan:0.1},
  label:{maxLength:110},
});
export function validateSpec(spec) {
  const p = validateBase(spec, ID, ['illustration','label'],
    ['width','height','stroke_width','hatch_spacing','draw_window','hatch_window'], DEFAULT_PALETTE);
  const raw = spec.parameters;
  p.illustration = choice(raw.illustration,'illustration',['leaf','vessel']);
  p.label = text(raw.label,'illustration label',110);
  fitText(p.label,{maximum:38,minimum:28,maxLines:3});
  p.width = number(defaulted(raw.width,440),'width',240,520);
  p.height = number(defaulted(raw.height,500),'height',300,520);
  p.stroke_width = number(defaulted(raw.stroke_width,4),'stroke width',2,8);
  p.hatch_spacing = number(defaulted(raw.hatch_spacing,18),'hatch spacing',10,30);
  p.draw_window = windowPair(defaulted(raw.draw_window,[0.04,0.62]),'draw window');
  p.hatch_window = windowPair(defaulted(raw.hatch_window,[0.65,0.96]),'hatch window');
  if (p.draw_window[1] > p.hatch_window[0]) fail('hatching must follow the completed contour');
  return {id:ID,version:VERSION,parameters:p};
}
export function traceGeometry(p) {
  const w=p.width, h=p.height;
  const pair = (x,y) => `${fmt(x)} ${fmt(y)}`;
  let outline, mask;
  if (p.illustration === 'leaf') {
    mask=`M${pair(0,h/2)}C${pair(-w*.52,h*.30)} ${pair(-w*.55,-h*.28)} ${pair(0,-h/2)}C${pair(w*.55,-h*.28)} ${pair(w*.52,h*.30)} ${pair(0,h/2)}Z`;
    // One pen-down path outlines the leaf and returns along the midrib.
    outline=`${mask}C${pair(w*.03,h*.16)} ${pair(-w*.03,-h*.17)} ${pair(0,-h/2)}`;
  } else {
    mask=`M${pair(-w*.18,-h/2)}L${pair(w*.18,-h/2)}C${pair(w*.23,-h*.35)} ${pair(w*.08,-h*.32)} ${pair(w*.26,-h*.1)}C${pair(w*.60,h*.22)} ${pair(w*.44,h*.48)} ${pair(w*.26,h/2)}L${pair(-w*.26,h/2)}C${pair(-w*.44,h*.48)} ${pair(-w*.60,h*.22)} ${pair(-w*.26,-h*.1)}C${pair(-w*.08,-h*.32)} ${pair(-w*.23,-h*.35)} ${pair(-w*.18,-h/2)}Z`;
    outline=mask;
  }
  const hatches=[],bounds={left:-w*.6,right:w*.6,top:-h/2,bottom:h/2};
  // x+y=offset, analytically clipped to the illustration rectangle first.
  // The subsequent shape clip preserves the leaf/vessel interior. Every raw
  // segment stays bounded too, so layout inspectors need not ignore clipping.
  for (let offset=bounds.left+bounds.top; offset<=bounds.right+bounds.bottom; offset+=p.hatch_spacing) {
    const lowY=Math.max(bounds.top,offset-bounds.right),highY=Math.min(bounds.bottom,offset-bounds.left);
    if (highY-lowY>1e-8) hatches.push({x1:offset-highY,y1:highY,x2:offset-lowY,y2:lowY});
  }
  return {outline,mask,hatches,bounds};
}
function state(p,seconds) {
  const time=sampleTime(seconds,p.duration),motion=motionTime(time,p.duration);
  const draw=phaseAt(motion,p.duration,p.draw_window);
  const hatch=phaseAt(motion,p.duration,p.hatch_window);
  return {seconds:time,draw,hatch,constructionOpacity:(1-draw)*.36,
    phase:draw<1?'trace':hatch<1?'hatch':'hold',geometry:traceGeometry(p)};
}
export function sampleFrame(spec,seconds) { return state(validateSpec(spec).parameters,seconds); }
export function renderFrame(spec,seconds) {
  const p=validateSpec(spec).parameters,s=state(p,seconds),c=p.palette,g=s.geometry;
  const hatches=g.hatches.map((line,i)=>{
    const reveal=Math.max(0,Math.min(1,s.hatch*g.hatches.length-i));
    return `<path d="M${fmt(line.x1)} ${fmt(line.y1)}L${fmt(line.x2)} ${fmt(line.y2)}" pathLength="1" stroke-dasharray="1" stroke-dashoffset="${fmt(1-reveal)}"/>`;
  }).join('');
  const body=`<defs><clipPath id="ct-mask"><path d="${g.mask}"/></clipPath></defs><g transform="translate(540 930)" fill="none" stroke-linecap="round" stroke-linejoin="round"><g stroke="${c.muted}" stroke-width="1.5" opacity="${fmt(s.constructionOpacity)}"><path d="M${fmt(-p.width*.65)} 0H${fmt(p.width*.65)}M0 ${fmt(-p.height*.56)}V${fmt(p.height*.56)}"/><rect x="${fmt(-p.width*.6)}" y="${fmt(-p.height/2)}" width="${fmt(p.width*1.2)}" height="${fmt(p.height)}" stroke-dasharray="6 12"/></g><g clip-path="url(#ct-mask)" stroke="${c.accent}" stroke-width="${fmt(p.stroke_width*.38)}">${hatches}</g><path data-continuous-contour="true" d="${g.outline}" stroke="${c.ink}" stroke-width="${fmt(p.stroke_width)}" pathLength="1" stroke-dasharray="1" stroke-dashoffset="${fmt(1-s.draw)}"/></g>${svgText(p.label,{y:1380,maximum:38,minimum:28,maxLines:3,fill:c.ink})}`;
  return frameShell(ID,p,s.seconds,body);
}

// Direct public aliases retain the original validated frame API.
export const sample=sampleFrame;
export const render=renderFrame;
