// Fixed owned registry only. Machine output stays on stdout; errors never echo inputs.
import {compileStaged} from '../renderers/template-registry/registry.mjs';
import {parseSvg} from '../renderers/svg-tree.mjs';
let raw='';
try{
 for await(const chunk of process.stdin){raw+=chunk;if(Buffer.byteLength(raw)>262144)throw Error();}
 const input=JSON.parse(raw);
 if(!input||typeof input!=='object'||Array.isArray(input)||!['validate','frames','batch'].includes(input.op))throw Error();
 function validate(spec){return compileStaged(spec).spec;}
 let result;
 if(input.op==='validate')result=validate(input.spec);
 else if(input.op==='batch'){
  if(!Array.isArray(input.specs)||input.specs.length>168)throw Error();
  const phases=input.phases??[0];if(!Array.isArray(phases)||phases.length>4||phases.some(t=>!Number.isFinite(t)||t<0||t>=1))throw Error();
  result=input.specs.map(spec=>{const compiled=compileStaged(spec);return {spec:compiled.spec,frames:phases.map(q=>({seconds:q*compiled.spec.parameters.duration,tree:parseSvg(compiled.render(q*compiled.spec.parameters.duration))}))};});
 }else{
  if(!Array.isArray(input.times)||input.times.length>8||input.times.some(t=>!Number.isFinite(t)||t<0||t>45))throw Error();
  const compiled=compileStaged(input.spec);result={spec:compiled.spec,frames:input.times.map(t=>{const svg=compiled.render(t);return {seconds:t,tree:parseSvg(svg)};})};
 }
 const text=JSON.stringify({ok:true,result});if(Buffer.byteLength(text)>8000000)throw Error();process.stdout.write(text);
}catch(error){
 const numeric=error?.name==='InputError'&&error.message==='TEMPLATE_INPUT: domain_bounds: exact tick labels need shorter decimals (155px axis slot, minimum 28px)';
 process.stderr.write(numeric?'TEMPLATE_NUMERIC_DOMAIN_LABELS_INVALID\n':'TEMPLATE_REGISTRY_INPUT_INVALID\n');process.exitCode=2;
}
