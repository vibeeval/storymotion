// Small DOM model for source behavior, not a browser or accessibility acceptance.
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';
export function harness({catalog,html,source,prependSources=[]}){
 const ids=new Map();let document;
 class Element{
  constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.attrs={};this.dataset={};this.listeners={};this._value='';this._text='';this.disabled=false;this.hidden=false;this.selectionStart=0;this.scrollTop=0;}
  get value(){if(this.tagName!=='SELECT')return this._value;return this.children.some(n=>n.value===this._value)?this._value:'';}
  set value(v){this._value=String(v);this.selectionStart=0;this.scrollTop=0;}
  get options(){return this.children;}
  get textContent(){return this._text+this.children.map(n=>n.textContent).join('');}
  set textContent(v){this.replaceChildren();this._text=String(v);}
  contains(n){return this===n||this.children.some(c=>c.contains(n));}
  append(...nodes){for(const n of nodes){if(n.parentNode){const i=n.parentNode.children.indexOf(n);if(i>=0)n.parentNode.children.splice(i,1);}n.parentNode=this;this.children.push(n);}}
  appendChild(n){this.append(n);return n;}
  replaceChildren(...nodes){if(this.children.some(c=>c.contains(document?.activeElement)))document.activeElement=document.body;for(const c of this.children)c.parentNode=null;this.children=[];this._text='';this.append(...nodes);if(this.tagName==='SELECT')this._value=this.children[0]?.value??'';}
  setAttribute(k,v){this.attrs[k]=String(v);}
  getAttribute(k){return this.attrs[k]??null;}
  removeAttribute(k){delete this.attrs[k];}
  addEventListener(k,fn){(this.listeners[k]??=[]).push(fn);}
  emit(k){return Promise.all((this.listeners[k]??[]).map(fn=>fn({target:this,currentTarget:this,preventDefault(){}})));}
  focus(){document.activeElement=this;}
 }
 document={body:null,activeElement:null,createElement:tag=>new Element(tag),getElementById:id=>{if(!ids.has(id))throw Error('Missing actual HTML ID '+id);return ids.get(id);}};
 document.body=new Element('body');document.activeElement=document.body;
 for(const match of html.matchAll(/<([a-z0-9-]+)\b([^>]*\bid="((?:family|taxonomy)-[^"]+)")[^>]*>/g)){
  const n=new Element(match[1]);n.id=match[3];n.hidden=/\bhidden\b/.test(match[0]);n.disabled=/\bdisabled\b/.test(match[0]);ids.set(n.id,n);document.body.append(n);
  for(const a of match[0].matchAll(/([a-z-]+)="([^"]*)"/g))n.attrs[a[1]]=a[2];
 }
 for(const[id,n]of ids){
  if(n.tagName==='SELECT'){const block=html.match(new RegExp('<select[^>]*id="'+id+'"[^>]*>([\\s\\S]*?)</select>'))?.[1]??'';
   for(const m of block.matchAll(/<option[^>]*value="([^"]*)"[^>]*>([^<]*)<\/option>/g)){const o=new Element('option');o.value=m[1];o.textContent=m[2];n.append(o);}n.value=n.children[0]?.value??'';}
  if(n.tagName==='TEXTAREA')n.value=html.match(new RegExp('<textarea[^>]*id="'+id+'"[^>]*>([\\s\\S]*?)</textarea>'))?.[1]??'';
 }
 const calls=[];let responder=null,loadCatalog=catalog;
 const fetch=async(path,options)=>{const call={path,options:JSON.parse(JSON.stringify(options)),data:options.body?JSON.parse(options.body):null};calls.push(call);
  if(path!=='/api/template-families'&&path!=='/api/template-families/prepare'&&path!=='/api/template-families/fields'&&path!=='/api/template-families/validate'&&!path.startsWith('/api/writing-contexts/')&&!path.startsWith('/api/family-jobs/')&&!path.startsWith('/api/family-renders/')&&!path.startsWith('/api/taxonomy/')&&!path.startsWith('/api/reference-catalog/')&&!path.startsWith('/api/style-gallery/'))throw Error('Unexpected endpoint '+path);
  if(responder){const result=await responder(call);if(result!==undefined)return result;}
  const value=path==='/api/template-families'?loadCatalog:path.startsWith('/api/writing-contexts/')?{sources:{revision:'a'.repeat(64)},canon:null}:{job:'synthetic-job',account:call.data.account,family:call.data.spec.id,engine:call.data.engine,actual_render:false,provider_calls:0};
  return {ok:true,json:async()=>value};};
 const context=vm.createContext({document,window:{},fetch,crypto:webcrypto,TextEncoder});for(const before of prependSources)vm.runInContext(before,context);vm.runInContext(source,context);
 return {get:id=>document.getElementById(id),document,calls,run:script=>vm.runInContext(script,context),planning:()=>context.StoryMotionTaxonomy,load:()=>ids.get('family-load').emit('click'),
  respond:fn=>{responder=fn;},catalog:value=>{loadCatalog=value;},
  set:async(id,value,event='change')=>{const n=ids.get(id);n.value=value;await n.emit(event);},
  flush:async()=>{for(let i=0;i<12;i++)await Promise.resolve();}};
}
