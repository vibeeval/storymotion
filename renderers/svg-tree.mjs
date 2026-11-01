// Bounded SVG data parser. No HTML sink, script, URLs, event handlers or caller code.
const tags=new Set(['svg','g','path','circle','defs','mask','rect','text','clipPath','ellipse','tspan','line','polygon','filter','feGaussianBlur','polyline','feColorMatrix','feComposite']);
const names=new Set(['xmlns','viewBox','width','height','x','y','dx','dy','xml:space','x1','y1','x2','y2','cx','cy','r','rx','ry','d','points','id','transform','fill','stroke','stroke-width','stroke-linecap','stroke-linejoin','stroke-dasharray','stroke-dashoffset','fill-rule','clip-rule','fill-opacity','stroke-opacity','opacity','pathLength','text-anchor','font-size','font-family','font-weight','letter-spacing','dominant-baseline','filter','mask','clip-path','maskUnits','maskContentUnits','filterUnits','color-interpolation-filters','in','in2','result','stdDeviation','type','mode','values','operator','role']);
const number=String.raw`[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?`;
const numbers=new RegExp(`^(?:${number})(?:[ ,]+${number})*$`);
const fail=()=>{throw Error('TEMPLATE_SVG_INVALID');};
function decode(value){
 if(value.length>8192||/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/u.test(value))fail();
 return value.replace(/&([^;\s]{1,15});|&/g,(whole,entity)=>{
  const known={amp:'&',lt:'<',gt:'>',quot:'"',apos:"'"};if(Object.hasOwn(known,entity))return known[entity];
  if(!entity||!/^#(?:\d{1,7}|x[0-9a-fA-F]{1,6})$/u.test(entity))fail();
  const n=entity[1]==='x'?parseInt(entity.slice(2),16):Number(entity.slice(1));
  if(!Number.isInteger(n)||n<32||n>0x10ffff||(n>=0xd800&&n<=0xdfff))fail();return String.fromCodePoint(n);
 });
}
function numeric(value){if(!numbers.test(value)||value.match(new RegExp(number,'g')).some(v=>!Number.isFinite(Number(v))||Math.abs(Number(v))>1e9))fail();}
export function svgAttribute(name,value){
 if((!names.has(name)&&!/^data-[a-z0-9-]{1,50}$/u.test(name)&&!/^aria-[a-z-]{1,40}$/u.test(name))||typeof value!=='string'||value.length>8192||/[<>\u0000-\u0008\u000B\u000C\u000E-\u001F]/u.test(value))fail();
 if(name==='xmlns'){if(value!=='http://www.w3.org/2000/svg')fail();}
 else if(['fill','stroke'].includes(name)){if(!/^(?:#[a-fA-F0-9]{3,8}|none|transparent|currentColor|white|url\(#[a-zA-Z0-9_-]+\))$/u.test(value))fail();}
 else if(['filter','mask','clip-path'].includes(name)){if(!/^(?:none|url\(#[a-zA-Z0-9_-]+\))$/u.test(value))fail();}
 else if(name==='transform'){
  if(!/^(?:(?:translate|rotate|scale|matrix|skewX|skewY)\([-+., eE0-9]+\)\s*)+$/u.test(value))fail();
  for(const part of value.matchAll(/\(([^)]+)\)/g))numeric(part[1]);
 }else if(name==='d'){if(!/^[MmZzLlHhVvCcSsQqTtAa0-9eE+.,\s-]*$/u.test(value))fail();}
 else if(name==='points'||name==='viewBox'||name==='values'){numeric(value);}
 else if(name==='xml:space'){if(!['preserve','default'].includes(value))fail();}
 else if(name==='id'){if(!/^[a-zA-Z][a-zA-Z0-9_-]{0,100}$/u.test(value))fail();}
 else if(['x','y','dx','dy','x1','y1','x2','y2','cx','cy','r','rx','ry','width','height','stroke-width','stroke-dashoffset','pathLength','font-size','letter-spacing','opacity','fill-opacity','stroke-opacity','stdDeviation'].includes(name)){numeric(value.endsWith('%')?value.slice(0,-1):value);}
 else if(name==='stroke-dasharray'&&value!=='none')numeric(value);
 else if(name==='font-family'&&!/^[a-zA-Z ,'-]{1,100}$/u.test(value))fail();
 else if(/(?:javascript|https?|data):|expression\s*\(|@import/iu.test(value))fail();
 return value;
}
export function parseSvg(value){
 if(typeof value!=='string'||value.length>1000000||/<!|<\?/u.test(value))fail();
 let i=0,count=0,root=null;const stack=[];
 function add(node){if(++count>4096||stack.length>64)fail();if(stack.length)stack.at(-1).children.push(node);else if(!root&&node.tag==='svg')root=node;else fail();}
 while(i<value.length){
  if(value[i]!=='<'){
   const end=value.indexOf('<',i),next=end<0?value.length:end,raw=value.slice(i,next);i=next;
   if(raw.trim()){if(!stack.length)fail();add({tag:'#text',text:decode(raw),attrs:{},children:[]});}continue;
  }
  const slice=value.slice(i),close=/^<\/([A-Za-z][A-Za-z0-9]*)\s*>/u.exec(slice);
  if(close){if(!stack.length||stack.at(-1).tag!==close[1])fail();stack.pop();i+=close[0].length;continue;}
  const open=/^<([A-Za-z][A-Za-z0-9]*)(\s[^<>]*?)?\s*(\/?)>/u.exec(slice);
  if(!open||!tags.has(open[1]))fail();
  const raw=open[2]||'',attrs={};let offset=0;
  while(offset<raw.length){const attr=/^\s+([A-Za-z][A-Za-z0-9:-]*)\s*=\s*"([^"<]*)"/u.exec(raw.slice(offset));if(!attr){if(raw.slice(offset).trim())fail();break;}
   if(Object.hasOwn(attrs,attr[1])||Object.keys(attrs).length>=64)fail();attrs[attr[1]]=svgAttribute(attr[1],decode(attr[2]));offset+=attr[0].length;}
  const node={tag:open[1],attrs,children:[],text:null};add(node);if(!open[3])stack.push(node);i+=open[0].length;
 }
 if(stack.length||!root||root.attrs.viewBox!=='0 0 1080 1920'||root.attrs.width!=='1080'||root.attrs.height!=='1920')fail();return root;
}
export function svgDom(tree,document){
 if(tree.tag==='#text')return document.createTextNode(tree.text);
 if(!tags.has(tree.tag))fail();const node=document.createElementNS('http://www.w3.org/2000/svg',tree.tag);
 for(const [name,value]of Object.entries(tree.attrs))node.setAttribute(name,svgAttribute(name,value));
 for(const child of tree.children)node.appendChild(svgDom(child,document));return node;
}
