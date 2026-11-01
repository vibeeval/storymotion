// One cue-bound emphasis event; sentence layout stays still and every word remains.
import {VERSION,validateBase,choice,number,text,textUnits,defaulted,fail,smooth,sampleTime,activeCue,fmt,esc,frameShell} from './1239407120d9-shared.mjs';
export const ID='caption-impact-rig',SOURCE_ID='source-mg-style-18-hanazi';
export const DEFAULT_PALETTE=Object.freeze({background:'#F6F0E8',ink:'#352B2C',muted:'#6B5B5D',accent:'#A03838'});
export const PARAMETER_SCHEMA=Object.freeze({focus:{maxLength:28,uniqueWholeExpressionInOneCue:true},punctuation:{enum:['!','?','.']},impact_fraction:{minimum:.18,maximum:.65},impact_seconds:{minimum:.12,maximum:.4},cue_end_margin:.1,terminal_hold_seconds:.6});
export function layoutCaption(value,focus=null) {
  const index=focus===null?-1:value.indexOf(focus),tokens=[];
  const words=[...value.matchAll(/\S+/gu)].map(match=>({text:match[0],start:match.index,end:match.index+match[0].length}));
  if(index<0) tokens.push(...words.map(word=>({text:word.text,focus:false})));
  else {
    const first=words.findIndex(word=>word.end>index);let last=first;
    while(last+1<words.length&&words[last+1].start<index+focus.length)last++;
    tokens.push(...words.slice(0,first).map(word=>({text:word.text,focus:false})));
    // Adjacent punctuation stays attached to this one unbroken expression.
    tokens.push({text:value.slice(words[first].start,words[last].end),focus:true});
    tokens.push(...words.slice(last+1).map(word=>({text:word.text,focus:false})));
  }
  for(let size=76;size>=48;size--) {
    const rows=[];let row=[],width=0,valid=true;
    for(const token of tokens) {
      const advance=textUnits(token.text)*size;
      if(advance>740){valid=false;break;}
      const gap=row.length?textUnits(' ')*size:0;
      if(row.length&&width+gap+advance>740){rows.push(row);row=[];width=0;}
      const actualGap=row.length?textUnits(' ')*size:0;
      row.push({...token,x:width+actualGap,width:advance});width+=actualGap+advance;
    }
    if(row.length)rows.push(row);
    if(valid&&rows.length<=5) return {fontSize:size,lineHeight:size*1.24,rows:rows.map(row=>({text:row.map(token=>token.text).join(' '),tokens:row}))};
  }
  fail('caption/focus cannot fit without splitting or losing words');
}
export function validateSpec(spec) {
  const p=validateBase(spec,ID,['focus','punctuation'],['impact_fraction','impact_seconds'],DEFAULT_PALETTE),r=spec.parameters;
  p.focus=text(r.focus,'focus',28);p.punctuation=choice(r.punctuation,'punctuation',['!','?','.']);
  const index=p.narration.indexOf(p.focus),after=index+p.focus.length;
  if(index<0||p.narration.indexOf(p.focus,index+1)>=0||/[\p{L}\p{N}]/u.test(p.narration[index-1]??'')||/[\p{L}\p{N}]/u.test(p.narration[after]??'')) fail('focus must occur exactly once as a whole expression');
  const cueIndex=p.cues.findIndex(cue=>cue.text.includes(p.focus));if(cueIndex<0)fail('focus must fit wholly inside one supplied cue');
  p.impact_fraction=number(defaulted(r.impact_fraction,.3),'impact fraction',.18,.65);
  p.impact_seconds=number(defaulted(r.impact_seconds,.18),'impact seconds',.12,.4);
  const cue=p.cues[cueIndex];
  if((cue.end-cue.start)*(1-p.impact_fraction)-p.impact_seconds<.1-1e-9)fail('focus cue needs 0.1 second reading hold after impact');
  // Keep supplied speech/cue times intact. Refuse an emphasis event that cannot
  // finish before the final eighteen frames, or disappears inside that hold.
  const holdStart=(Math.round(p.duration*30)-18)/30,impactEnd=cue.start+(cue.end-cue.start)*p.impact_fraction+p.impact_seconds;
  if(impactEnd>holdStart+1e-9)fail('focus impact must finish before the final 0.6 second hold; move emphasis earlier or extend duration');
  if(cue.end>holdStart+1e-9&&cue.end<p.duration-1e-9)fail('focus cue cannot disappear during the final 0.6 second hold');
  p.cues.forEach((cue,i)=>layoutCaption(cue.text,i===cueIndex?p.focus:null));
  return {id:ID,version:VERSION,parameters:p};
}
function state(p,seconds) {
  const time=sampleTime(seconds,p.duration),cue=activeCue(p.cues,time),cueIndex=cue?p.cues.indexOf(cue):-1;
  const focusCueIndex=p.cues.findIndex(cue=>cue.text.includes(p.focus)),focusCue=p.cues[focusCueIndex];
  const impactStart=focusCue.start+(focusCue.end-focusCue.start)*p.impact_fraction;
  const activeFocus=cueIndex===focusCueIndex,impact=activeFocus?smooth((time-impactStart)/p.impact_seconds):0;
  const layout=cue?layoutCaption(cue.text,activeFocus?p.focus:null):null;
  return {seconds:time,cueIndex,focusCueIndex,impactStart,impact,layout,
    phase:!cue?'gap':!activeFocus||time<impactStart?'reading':impact<1?'impact':'emphasis'};
}
export function sample(spec,seconds) {return state(validateSpec(spec).parameters,seconds);}
export const sampleFrame=sample;
export function render(spec,seconds) {
  const p=validateSpec(spec).parameters,s=state(p,seconds),c=p.palette;
  let body='';
  if(s.layout) {
    const y0=790,rows=s.layout.rows.map((row,i)=>{
      const y=y0+i*s.layout.lineHeight;
      return `<text x="100" y="${fmt(y)}" fill="${c.ink}" font-size="${s.layout.fontSize}" font-weight="550" data-template-text="true" data-full-text="${esc(row.text)}" data-slot-width="740">${row.tokens.map((token,j)=>`<tspan x="${fmt(100+token.x)}" font-weight="${token.focus?800:550}" fill="${token.focus&&s.impact>0?c.accent:c.ink}">${esc(token.text)}${j<row.tokens.length-1?' ':''}</tspan>`).join('')}</text>`;
    }).join('');
    const lines=s.layout.rows.flatMap((row,i)=>row.tokens.filter(t=>t.focus).map(token=>`<path d="M${fmt(100+token.x)} ${fmt(y0+i*s.layout.lineHeight+14)}H${fmt(100+token.x+token.width*s.impact)}" stroke="${c.accent}" stroke-width="7"/>`)).join('');
    const cue=p.cues[s.cueIndex];
    body=`<g id="family-cue-${s.cueIndex}" data-cue-start="${fmt(cue.start)}" data-cue-end="${fmt(cue.end)}">${rows}${lines}<text x="${fmt(920+10*(1-s.impact))}" y="1150" fill="${c.accent}" font-size="190" font-weight="800" text-anchor="middle" opacity="${fmt(s.impact)}">${esc(p.punctuation)}</text></g>`;
  }
  return frameShell(ID,p,s.seconds,body,{captions:false});
}
export const renderFrame=render;
