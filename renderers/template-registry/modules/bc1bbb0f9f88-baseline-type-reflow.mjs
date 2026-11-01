import {base,number,list,copy,textUnits,done,time,ease,lerp,fmt,esc,line,page,PALETTES,meta,fail} from './f2b8a056cce3-shared.mjs';
export const ID='baseline-type-reflow',SOURCE_ID='source-lemo-style-swiss-motion',DEFAULT_PALETTE=PALETTES.paper;
export const METADATA=meta('Ortak tabanda yeniden akan yazı','measured-type','two-to-one-type','measured word anchor reflow with size and tracking endpoints','asymmetric rule / two columns / final single passage');
export const PARAMETER_SCHEMA={copy:{maxLength:150},column_ratios:{exactItems:2,range:[.35,.65],sum:1},baseline_step:[60,76],type_scale:[.85,1.1],tracking_curve:{exactItems:2,range:[-.5,1.5]}};
function wordLayout(p,size,tracking,widths){
 const tokens=[];let column=0,row=0,x=0;
 for(const word of p.copy.split(' ')){
  const width=textUnits(word)*size+Math.max(0,[...word].length-1)*tracking,gap=x?size*.36+tracking:0;
  if(width>widths[column])return null;
  if(x&&x+gap+width>widths[column]){row++;x=0;}
  if(row>=9){column++;row=0;x=0;}
  if(column>=widths.length||width>widths[column])return null;
  const actualGap=x?size*.36+tracking:0;
  tokens.push({word,x:110+(column?widths[0]+36:0)+x+actualGap,y:730+row*p.baseline_step,width,column,row});
  x+=actualGap+width;
 }
 return tokens;
}
function packed(p,amount){
 const size=lerp(38,50,amount)*p.type_scale,tracking=lerp(...p.tracking_curve,amount),first=lerp(850*p.column_ratios[0]-18,850,amount);
 let tokens=wordLayout(p,size,tracking,amount===1?[850]:[first,850-first-36]);
 // Line breaks change atomically. Never interpolate individual words through
 // another row. When a shrinking second column cannot hold its words, merge
 // into the full field; bounded advances never exceed the validated endpoint.
 if(!tokens&&amount>0&&amount<1)tokens=wordLayout(p,size,tracking,[850]);
 if(!tokens)fail('copy exceeds its measured columns or registered baseline field');
 return{tokens,size,tracking};
}
export function validateSpec(spec){const p=base(spec,ID,['copy','column_ratios','baseline_step','type_scale','tracking_curve'],{},DEFAULT_PALETTE),r=spec.parameters;p.copy=copy(r.copy,'copy',150,850,38,8);p.column_ratios=list(r.column_ratios,2,2,'column ratios').map(v=>number(v,'column ratio',.35,.65));if(Math.abs(p.column_ratios[0]+p.column_ratios[1]-1)>1e-9)fail('column ratios must sum to one');p.baseline_step=number(r.baseline_step,'baseline step',60,76);p.type_scale=number(r.type_scale,'type scale',.85,1.1);p.tracking_curve=list(r.tracking_curve,2,2,'tracking curve').map(v=>number(v,'tracking',-.5,1.5));if(p.baseline_step<50*p.type_scale*1.24)fail('baseline spacing must clear the largest type');packed(p,0);packed(p,1);return done(ID,p);}
function state(p,seconds){const q=time(p,seconds),amount=ease(q.u,.12,.85),a=packed(p,0),b=packed(p,1),current=packed(p,amount),tokens=current.tokens.map((v,i)=>({word:v.word,x:v.x,y:v.y,width:v.width,from:a.tokens[i],to:b.tokens[i]}));return{...q,amount,fontSize:current.size,tracking:current.tracking,tokens,anchor:{x:110,y:730}};}
export const sample=(spec,seconds)=>state(validateSpec(spec).parameters,seconds);
export function render(spec,seconds){const p=validateSpec(spec).parameters,s=state(p,seconds),c=p.palette;let body=Array.from({length:10},(_,i)=>line({x:110,y:730+i*p.baseline_step},{x:960,y:730+i*p.baseline_step},c.muted,1,'opacity="0.25"')).join('');body+=s.tokens.map(v=>`<text data-motion-role="reflow-word" x="${fmt(v.x)}" y="${fmt(v.y)}" fill="${c.ink}" font-size="${fmt(s.fontSize)}" letter-spacing="${fmt(s.tracking)}" font-weight="550">${esc(v.word)}</text>`).join('');return page(ID,p,s.seconds,body,{layout:'side'});}
