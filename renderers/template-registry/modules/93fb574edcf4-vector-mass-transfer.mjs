// Original quantitative transfer diagram: source + transit + destination is constant.
import {VERSION,validateBase,keys,number,text,fitText,windowPair,defaulted,fail,clamp,smooth,lerp,sampleTime,motionTime,fmt,esc,svgText,frameShell} from './1239407120d9-shared.mjs';
export const ID='vector-mass-transfer',SOURCE_ID='source-mg-style-01-flat-vector';
export const DEFAULT_PALETTE=Object.freeze({background:'#F5F1E8',ink:'#243D3C',muted:'#596761',accent:'#9B4431'});
export const PARAMETER_SCHEMA=Object.freeze({stores:{minItems:2,maxItems:2,item:{label:{maxLength:50},amount:{minimum:0,maximum:1000}}},transfer_amount:{minimum:1,maximum:'source amount'},unit:{maxLength:10},batches:{minimum:2,maximum:5,integer:true},lift:{minimum:60,maximum:160},transfer_window:{normalized:true,minimumSpan:.3}});
export function validateSpec(spec) {
  const p=validateBase(spec,ID,['stores','transfer_amount','unit'],['batches','lift','transfer_window'],DEFAULT_PALETTE),raw=spec.parameters;
  if(!Array.isArray(raw.stores)||raw.stores.length!==2)fail('stores: exactly two reservoirs required');
  p.stores=raw.stores.map((item,i)=>{
    keys(item,['label','amount']);const label=text(item.label,'store label',50);fitText(label,{width:380,maximum:34,minimum:28,maxLines:3});
    return {label,amount:number(item.amount,'store amount',i===0?1:0,1000)};
  });
  p.transfer_amount=number(raw.transfer_amount,'transfer amount',1,p.stores[0].amount);
  p.unit=text(raw.unit,'unit',10);fitText(p.unit,{width:380,maximum:26,minimum:24,maxLines:1});
  p.batches=number(defaulted(raw.batches,3),'batches',2,5,true);
  p.lift=number(defaulted(raw.lift,110),'lift',60,160);
  p.transfer_window=windowPair(defaulted(raw.transfer_window,[.14,.84]),'transfer window');
  if(p.transfer_window[1]-p.transfer_window[0]<.3-1e-9)fail('transfer window: at least 30% of clip required');
  return {id:ID,version:VERSION,parameters:p};
}
const WIDTH=250,BASE=1260,AREA_BUDGET=96000;
function state(p,seconds) {
  const time=sampleTime(seconds,p.duration),u=clamp((motionTime(time,p.duration)/p.duration-p.transfer_window[0])/(p.transfer_window[1]-p.transfer_window[0]));
  const position=u*p.batches,index=Math.min(p.batches-1,Math.floor(position)),local=position-index;
  const batch=p.transfer_amount/p.batches,depart=smooth(local/.18),arrive=smooth((local-.72)/.28),travel=smooth((local-.18)/.54);
  const withdrawn=(index+depart)*batch,received=(index+arrive)*batch;
  const source=p.stores[0].amount-withdrawn,destination=p.stores[1].amount+received,transit=withdrawn-received,total=p.stores[0].amount+p.stores[1].amount;
  const unitArea=AREA_BUDGET/total,side=Math.sqrt(Math.max(0,transit*unitArea));
  const topSource=BASE-source*unitArea/WIDTH,topDestination=BASE-destination*unitArea/WIDTH;
  const parcel={x:lerp(295,785,travel),y:lerp(topSource,topDestination,travel)-side/2-p.lift*Math.sin(Math.PI*travel),side};
  const fills=[{x:170,y:topSource,width:WIDTH,height:BASE-topSource},{x:660,y:topDestination,width:WIDTH,height:BASE-topDestination}];
  return {seconds:time,phase:u===0?'before':u===1?'after':'transfer',batchIndex:index,local,source,destination,transit,total,unitArea,
    areaTotal:(source+destination+transit)*unitArea,parcel,fills,progress:u};
}
export function sample(spec,seconds) {return state(validateSpec(spec).parameters,seconds);}
export const sampleFrame=sample;
export function render(spec,seconds) {
  const p=validateSpec(spec).parameters,s=state(p,seconds),c=p.palette;
  const fills=s.fills.map((box,i)=>`<rect x="${fmt(box.x)}" y="${fmt(box.y)}" width="${box.width}" height="${fmt(box.height)}" fill="${c.accent}"/><path d="M${box.x-8} 1260H${box.x+258}" stroke="${c.ink}" stroke-width="4"/>${svgText(p.stores[i].label,{x:150+i*490,y:620,width:380,maximum:34,minimum:28,maxLines:3,fill:c.ink})}<text x="${box.x}" y="1335" fill="${c.ink}" font-size="48" font-weight="700">${fmt(Math.round((i?s.destination:s.source)*100)/100)}</text><text x="${box.x}" y="1385" fill="${c.muted}" font-size="26">${esc(p.unit)}</text>`).join('');
  const parcel=s.parcel.side>1e-8?`<rect data-transit-area="${fmt(s.transit*s.unitArea)}" x="${fmt(s.parcel.x-s.parcel.side/2)}" y="${fmt(s.parcel.y-s.parcel.side/2)}" width="${fmt(s.parcel.side)}" height="${fmt(s.parcel.side)}" fill="${c.accent}" stroke="${c.ink}" stroke-width="3"/>`:'';
  const body=`<path d="M170 1460H910" stroke="${c.muted}" stroke-width="1"/>${fills}${parcel}<text x="170" y="1510" fill="${c.muted}" font-size="28">TOPLAM ${fmt(s.total)} ${esc(p.unit)}</text>`;
  return frameShell(ID,p,s.seconds,body);
}
export const renderFrame=render;
