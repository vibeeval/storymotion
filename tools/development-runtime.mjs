// Pure private receipt inspection. Never invokes a binary, download or package.
import {readFileSync,lstatSync,realpathSync,readdirSync,existsSync,accessSync,constants} from 'node:fs';
import {resolve,relative,join,dirname,isAbsolute} from 'node:path';
import {createHash} from 'node:crypto';

export const POLICY_SHA='5fb8ded307f2f111201a4e764c68668f839f8687db824250bfd0f3a6bf82faee';
export const EVIDENCE_SHA='d132d5b9675daf93e006fd8a7621d5142e8f222f116b27e44f85bed44039d0ed';
export const RECIPE_SHA='9a64dae21b2115e46158520fcb983705bc784970480fbec304840fb423bd67bb';
export const PROVIDER='source-ffmpeg-8.1.3-x264-b35605a';
export const FIXTURE_SHA='92a04ed2faad9018addf20d13150733007d3f7131b68420c79f287de7c51be46';
export const CHROME_LICENSE_SHA='92b1cf9cde6cc452b041c55f97154e32500a535c4a13b3e4676d689789c7d89b';
export const FLAGS=['owner_eula_accepted','third_party_terms_accepted','customer_installation','native_acceptance','customer_acceptance','creative_acceptance','publication_ready','commercial_clearance'];
export const PROCESS_BASE='.runtime/development/process';
const PROCESS_PATHS={HOME:'home',CFFIXED_USER_HOME:'home',TMPDIR:'tmp',TMP:'tmp',TEMP:'tmp',
  XDG_CACHE_HOME:'home/.cache',XDG_CONFIG_HOME:'home/.config',XDG_STATE_HOME:'home/.local/state',
  XDG_DATA_HOME:'home/.local/share',XDG_RUNTIME_DIR:'run',NODE_COMPILE_CACHE:'compile-cache',
  HYPERFRAMES_EXTRACT_CACHE_DIR:'extract',HYPERFRAMES_FONT_CACHE_DIR:'home/.cache/hyperframes/fonts',
  HYPERFRAMES_MEDIA_HOME:'media',PUPPETEER_CACHE_DIR:'home/.cache/puppeteer',CLANG_MODULE_CACHE_PATH:'clang-cache'};
const PROCESS_CONTROLS={DO_NOT_TRACK:'1',HYPERFRAMES_TELEMETRY_DISABLED:'1',HYPERFRAMES_NO_TELEMETRY:'1',
  HYPERFRAMES_NO_UPDATE_CHECK:'1',HYPERFRAMES_NO_AUTO_INSTALL:'1',HYPERFRAMES_MEDIA_HOME_REQUIRED:'1',PYTHONDONTWRITEBYTECODE:'1'};
const record=v=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const fail=()=>{throw new Error('DEVELOPMENT_METADATA_INVALID');};
const compare=(a,b)=>{const x=[...a],y=[...b];for(let i=0;i<Math.min(x.length,y.length);i++){const d=x[i].codePointAt(0)-y[i].codePointAt(0);if(d)return d;}return x.length-y.length;};
export const stable=v=>JSON.stringify(v,(_,x)=>record(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>compare(a,b))):x);
const hash=b=>createHash('sha256').update(b).digest('hex');
const same=(a,b)=>stable(a)===stable(b);
export function owned(root,name,maximum=4*1024*1024) {
  if(typeof name!=='string'||isAbsolute(name)||name.split('/').some(v=>['','.','..'].includes(v)))fail();
  const path=resolve(root,name),info=lstatSync(path);
  if(realpathSync(path)!==path||!info.isFile()||info.uid!==process.getuid()||info.nlink!==1||info.size>maximum)fail();
  return path;
}
export const fileSha=(root,name,maximum)=>hash(readFileSync(owned(root,name,maximum)));
export function strictJSON(text) {
  let index=0,nodes=0;
  const space=()=>{while(index<text.length&&/[\t\n\r ]/.test(text[index]))index++;};
  function string(){
    const start=index++;let escaped=false;
    while(index<text.length){
      const c=text[index++];
      if(c==='"'&&!escaped)return JSON.parse(text.slice(start,index));
      if(c==='\\'&&!escaped)escaped=true;else escaped=false;
    }
    fail();
  }
  function value(depth=0){
    if(depth>12||++nodes>30000)fail();space();
    const c=text[index];
    if(c==='"')return string();
    if(c==='{'){
      index++;space();const object=Object.create(null),keys=new Set();
      if(text[index]==='}'){index++;return object;}
      while(index<text.length){
        space();if(text[index]!=='"')fail();const key=string();
        if(keys.has(key)||['__proto__','constructor','prototype'].includes(key))fail();keys.add(key);
        space();if(text[index++]!==':')fail();object[key]=value(depth+1);space();
        const end=text[index++];if(end==='}')return object;if(end!==',')fail();
      }
      fail();
    }
    if(c==='['){
      index++;space();const array=[];if(text[index]===']'){index++;return array;}
      while(index<text.length){array.push(value(depth+1));space();const end=text[index++];if(end===']')return array;if(end!==',')fail();}
      fail();
    }
    for(const[word,result]of [['true',true],['false',false],['null',null]])if(text.startsWith(word,index)){index+=word.length;return result;}
    const match=/^-?(?:0|[1-9][0-9]*)/.exec(text.slice(index));if(!match)fail();index+=match[0].length;
    if(/[.eE0-9]/.test(text[index]??''))fail();const number=Number(match[0]);if(!Number.isSafeInteger(number))fail();return number;
  }
  const result=value();space();if(index!==text.length)fail();return result;
}
export function readJSON(root,name,maximum) {
  const text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(readFileSync(owned(root,name,maximum)));
  return strictJSON(text);
}
export function developmentMode(root) {
  for(const name of ['.runtime/development','.runtime/ffmpeg']){
    try{lstatSync(join(root,name));return true;}catch(error){if(error.code!=='ENOENT')return true;}
  }
  return false;
}
export function processEnvironment(root,source=process.env) {
  if(realpathSync(root)!==root)fail();
  const base=join(root,PROCESS_BASE),dirs=['',...new Set([...Object.values(PROCESS_PATHS),'home/.cache/hyperframes/history','home/.hyperframes/running'])];
  for(const name of dirs){
    const path=join(base,name),info=lstatSync(path);
    if(realpathSync(path)!==path||!info.isDirectory()||info.uid!==process.getuid()||(info.mode&0o777)!==0o700)fail();
  }
  function visit(folder){
    for(const name of readdirSync(folder)){
      const path=join(folder,name),info=lstatSync(path);
      if(info.uid!==process.getuid()||info.isSymbolicLink()||realpathSync(path)!==path)fail();
      if(info.isDirectory())visit(path);else if(!info.isFile()||info.nlink!==1)fail();
    }
  }
  visit(base);
  const allowed=['PATH','USER','LOGNAME','LANG','LC_ALL','SHELL'];
  return {...Object.fromEntries(allowed.filter(k=>source[k]!==undefined).map(k=>[k,source[k]])),
    ...Object.fromEntries(Object.entries(PROCESS_PATHS).map(([k,v])=>[k,join(base,v)])),...PROCESS_CONTROLS};
}
export function policy(root,engine='hyperframes') {
  if(engine!=='hyperframes'||process.platform!=='darwin'||process.arch!=='arm64')fail();
  if(realpathSync(root)!==root)fail();
  if(fileSha(root,'ci/hf-development-policy.json',512*1024)!==POLICY_SHA)fail();
  const value=readJSON(root,'ci/hf-development-policy.json',512*1024);
  if(value.schema_version!==1||value.engine!=='hyperframes'||value.platform!=='Darwin'||value.architecture!=='arm64'
    ||value.provider!==PROVIDER||value.fixture!=='fixtures/turkish-font-smoke.json'||value.fixture_sha256!==FIXTURE_SHA
    ||value.npm_mode!=='ignore_scripts'||!same(value.lifecycle_allowlist,[])||!same(value.allowed_operations,['npm','setup','render'])
    ||!same(value.probe_bootstrap,{provider:'source-ffprobe-8.1.3-lgpl-private-silent-v1',recipe:'renderers/ffprobe-source.json',recipe_sha256:'2354151b834791ba3b00d29301c15b0d03236ca0b4f6a4b1bcc65fce42eaccbd',namespace:'.runtime/development/probe',profile:'private-generated-silence-v1',fixture_sha256:'643f8a8dc8bd9c19225afffad2becfec5426180b3749cb208abdf1a6c8354efc',repository_media:false,build_strategy:'in_source_no_links'})
    ||!same(value.flags,Object.fromEntries(FLAGS.map(k=>[k,false])))||!record(value.reviewed_files)||!Object.keys(value.reviewed_files).length)fail();
  for(const [name,sha]of Object.entries(value.reviewed_files))if(fileSha(root,name)!==sha)fail();
  installationArtifacts(root);
  if(fileSha(root,'LICENSE')!=='5ecd8a56929f982bf1cfae4c7e5a7aedf3c31c13e8355bedab67ce0d70055682')fail();
  if(fileSha(root,value.fixture)!==FIXTURE_SHA)fail();
  sourceRecipe(root);return value;
}
export function sourceBinding(root,value) {
  return hash(stable({policy:POLICY_SHA,files:value.reviewed_files,validator:fileSha(root,'storymotion/development_policy.py'),js_validator:fileSha(root,'tools/development-runtime.mjs')}));
}
export function sourceRecipe(root) {
  if(fileSha(root,'renderers/ffmpeg-source.json',32768)!==RECIPE_SHA)fail();
  const value=readJSON(root,'renderers/ffmpeg-source.json',32768);
  for(const [name,sha]of Object.entries(value.license_files))if(fileSha(root,name)!==sha)fail();
  return value;
}
export function mode(root) {
  const value=readJSON(root,'.runtime/development/mode.json',32768),p=policy(root);
  if(!record(value)||!same(Object.keys(value).sort(),['schema_version','mode_id','policy_sha256','source_binding','root_sha256','provider','fixture_sha256','node'].sort())
    ||value.schema_version!==1||typeof value.mode_id!=='string'||!(/^[a-f0-9]{32}$/).test(value.mode_id)
    ||value.policy_sha256!==POLICY_SHA||value.source_binding!==sourceBinding(root,p)||value.root_sha256!==hash(root)
    ||value.provider!==PROVIDER||value.fixture_sha256!==FIXTURE_SHA)fail();
  if(!record(value.node)||!same(Object.keys(value.node).sort(),['binary','sha256','version'])||value.node.binary!==realpathSync(process.execPath)
    ||value.node.sha256!==hash(readFileSync(process.execPath))||value.node.version!==process.version||!(/^v22\./).test(process.version)
    ||Number(process.versions.node.split('.')[1])<23||(Number(process.versions.node.split('.')[1])===23&&Number(process.versions.node.split('.')[2])<2))fail();
  return value;
}
export function installationArtifacts(root) {
  if(fileSha(root,'ci/hf-development-evidence.json')!==EVIDENCE_SHA)fail();
  const evidence=readJSON(root,'ci/hf-development-evidence.json'),rows=evidence.artifacts;
  if(fileSha(root,'package-lock.json')!==evidence.package_lock_sha256||!record(rows)||Object.keys(rows).length!==94)fail();
  const lock=readJSON(root,'package-lock.json'),compatible=Object.entries(lock.packages).filter(([path,v])=>path
    &&(!Object.hasOwn(v,'os')||v.os.includes('darwin'))&&(!Object.hasOwn(v,'cpu')||v.cpu.includes('arm64'))).map(([path])=>path);
  if(!same(Object.keys(rows).sort(),compatible.sort()))fail();
  for(const[path,row]of Object.entries(rows)){
    const entry=lock.packages[path];
    if(row.name!==path.split('node_modules/').at(-1)||!same([entry.version,entry.resolved,entry.integrity],[row.version,row.url,row.integrity])
      ||!['package_text','pinned_upstream_text','publisher_declaration'].includes(row.evidence_class))fail();
  }
  return rows;
}
export function installedPackages(root) {
  const expected=installationArtifacts(root),actual=[];
  function visit(folder){
    if(!existsSync(folder))return;
    if(realpathSync(folder)!==folder||!lstatSync(folder).isDirectory())fail();
    for(const name of readdirSync(folder).sort()){
      if(['.bin','.package-lock.json'].includes(name))continue;
      const child=join(folder,name),candidates=name.startsWith('@')?readdirSync(child).sort().map(v=>join(child,v)):[child];
      for(const p of candidates){
        if(realpathSync(p)!==p||!lstatSync(p).isDirectory())fail();
        const key=relative(root,p),row=expected[key],value=readJSON(root,key+'/package.json');
        if(!row||!record(value)||value.name!==row.name||value.version!==row.version)fail();
        actual.push(key);visit(join(p,'node_modules'));
      }
    }
  }
  visit(join(root,'node_modules'));
  if(!same(actual.sort(),Object.keys(expected).sort()))fail();
  try{lstatSync(join(root,'node_modules/ffmpeg-static/ffmpeg'));fail();}catch(error){if(error.code!=='ENOENT')throw error;}
  return actual.sort();
}
export function installedTree(root) {
  const base=join(root,'node_modules'),rows={};let total=0;
  if(realpathSync(base)!==base)fail();
  function visit(folder){
    for(const name of readdirSync(folder).sort()){
      const path=join(folder,name),info=lstatSync(path),key=relative(root,path);
      if(info.uid!==process.getuid())fail();
      if(info.isSymbolicLink()){
        const target=realpathSync(path),rel=relative(base,target),actual=lstatSync(target);
        if(rel.startsWith('..')||isAbsolute(rel)||!actual.isFile()||actual.uid!==process.getuid()||actual.nlink!==1||actual.size>128*1024*1024)fail();
        rows[key]={target:relative(root,target),sha256:hash(readFileSync(target))};total+=actual.size;
      }else if(info.isFile()){
        if(info.nlink!==1||info.size>128*1024*1024)fail();
        rows[key]={sha256:fileSha(root,key,128*1024*1024)};total+=info.size;
      }else if(info.isDirectory())visit(path);else fail();
      if(Object.keys(rows).length>50000||total>512*1024*1024)fail();
    }
  }
  visit(base);return hash(stable(rows));
}
export function npmReceiptMatches(receipt,m,lockSha,packageSha,treeSha,packages) {
  const expected={schema_version:4,graph:'core',npm_ci:'complete_ignored_scripts',npm_mode:'ignore_scripts',lifecycle_allowlist:[],provider:PROVIDER,
    policy_sha256:POLICY_SHA,source_binding:m.source_binding,mode_id:m.mode_id,package_lock_sha256:lockSha,package_json_sha256:packageSha,
    installed_tree_sha256:treeSha,installed_packages:packages};
  expected.node=m.node;
  return record(receipt)&&same(receipt,expected);
}
export function npmReady(root) {
  try{return npmReceiptMatches(readJSON(root,'.runtime/npm-core.json',32768),mode(root),fileSha(root,'package-lock.json'),fileSha(root,'package.json'),installedTree(root),installedPackages(root));}catch{return false;}
}
function toolchainMatches(value) {
  try{
    if(!record(value)||!same(Object.keys(value).sort(),['cc','make','sdk','pkg_config','cc_sha256','make_sha256','pkg_config_sha256','sdk_settings_sha256'].sort())
      ||value.cc!=='/Library/Developer/CommandLineTools/usr/bin/clang'||value.make!=='/usr/bin/make'
      ||!(/^\/Library\/Developer\/CommandLineTools\/SDKs\/MacOSX(?:[0-9.]+)?\.sdk$/).test(value.sdk)
      ||typeof value.pkg_config!=='string'||!(/^(?:\/usr\/bin\/pkg-config|\/(?:opt\/homebrew|usr\/local)\/(?:bin\/pkg-config|Cellar\/pkgconf\/[0-9A-Za-z._-]+\/bin\/pkgconf))$/).test(value.pkg_config))return false;
    for(const name of ['cc','make','pkg_config'])if(hash(readFileSync(value[name]))!==value[name+'_sha256'])return false;
    const json=join(value.sdk,'SDKSettings.json'),settings=existsSync(json)?json:join(value.sdk,'SDKSettings.plist');
    return hash(readFileSync(settings))===value.sdk_settings_sha256;
  }catch{return false;}
}
export function sourceFFmpeg(root) {
  const r=sourceRecipe(root),base={ready:false,provider:PROVIDER,path:r.binary,reason:'SOURCE_FFMPEG_NOT_READY'};
  try{
    const v=readJSON(root,r.receipt,65536),m=mode(root),keys=['schema_version','provider','policy_sha256','source_binding','recipe_sha256','platform','architecture','binary','binary_sha256','sources','toolchain','configuration_files','license_files','capabilities','capabilities_sha256'];
    if(!record(v)||!same(Object.keys(v).sort(),keys.sort())||v.schema_version!==1||v.provider!==PROVIDER||v.policy_sha256!==POLICY_SHA
      ||v.source_binding!==m.source_binding||v.recipe_sha256!==RECIPE_SHA||v.platform!=='Darwin'||v.architecture!=='arm64'
      ||v.binary!==r.binary||!toolchainMatches(v.toolchain)||fileSha(root,r.binary,64*1024*1024)!==v.binary_sha256)return base;
    accessSync(owned(root,r.binary,64*1024*1024),constants.X_OK);
    if(!same(Object.keys(v.sources).sort(),Object.keys(r.sources).sort()))return base;
    for(const[name,path]of Object.entries(v.sources)){
      const s=r.sources[name],expected='.runtime/development/sources/'+s.sha256+(s.format==='r:xz'?'.tar.xz':'.tar.gz');
      if(path!==expected&&!(name==='ffmpeg'&&(/^\.runtime\/probe\/stages\/[a-f0-9]{32}\/source\.tar\.xz$/).test(path)))return base;
      if(fileSha(root,path,s.maximum_archive_bytes)!==s.sha256)return base;
    }
    if(!record(v.configuration_files)||Object.keys(v.configuration_files).length!==3)return base;
    const stages=new Set(Object.keys(v.configuration_files).filter(p=>(/^\.runtime\/ffmpeg\/stages\/[a-f0-9]{32}\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/).test(p)).map(p=>p.split('/')[3]));
    if(stages.size!==1)return base;
    const stage='.runtime/ffmpeg/stages/'+[...stages][0];
    if(!same(Object.keys(v.configuration_files).sort(),[stage+'/ffmpeg-source/config.h',stage+'/ffmpeg-source/config_components.h',stage+'/x264-source/config.mak'].sort()))return base;
    if(!same(Object.keys(v.license_files).sort(),['.runtime/ffmpeg/COPYING.GPLv2','.runtime/ffmpeg/x264-COPYING.GPLv2','.runtime/ffmpeg/LICENSE.md'].sort())
      ||v.license_files['.runtime/ffmpeg/x264-COPYING.GPLv2']!==r.license_files['vendor/licenses/x264-b35605a-COPYING.GPLv2']
      ||v.license_files['.runtime/ffmpeg/LICENSE.md']!==r.license_files['vendor/licenses/ffmpeg-8.1.3-LICENSE.md']
      ||v.license_files['.runtime/ffmpeg/COPYING.GPLv2']!==fileSha(root,stage+'/ffmpeg-source/COPYING.GPLv2'))return base;
    for(const group of ['configuration_files','license_files']){
      if(!record(v[group])||!Object.keys(v[group]).length)return base;
      for(const[path,sha]of Object.entries(v[group]))if(!(/^\.runtime\/ffmpeg\/(?:stages\/[a-f0-9]{32}\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+|[A-Za-z0-9_.-]+)$/).test(path)||fileSha(root,path)!==sha)return base;
    }
    const caps=readJSON(root,'.runtime/ffmpeg/capabilities.json',32768),required=Object.fromEntries(['required_filters','required_encoders','required_decoders','required_muxers','required_bitstream_filters'].map(k=>[k,r[k]]));
    if(!record(caps)||!same(Object.keys(caps).sort(),['validated','required','buildconf_sha256'].sort())||typeof caps.buildconf_sha256!=='string'||!(/^[a-f0-9]{64}$/).test(caps.buildconf_sha256)
      ||fileSha(root,'.runtime/ffmpeg/capabilities.json')!==v.capabilities_sha256||!same(caps,v.capabilities)||caps.validated!==true||!same(caps.required,required))return base;
    return {...base,ready:true,reason:null,binary_sha256:v.binary_sha256};
  }catch{return base;}
}
export const PROBE_PROVIDER='source-ffprobe-8.1.3-lgpl-private-silent-v1';
export const PROBE_PROFILE='private-generated-silence-v1';
export const PROBE_BASE='.runtime/development/probe';
export const PROBE_RECIPE_SHA='2354151b834791ba3b00d29301c15b0d03236ca0b4f6a4b1bcc65fce42eaccbd';
export const WAV_SHA='643f8a8dc8bd9c19225afffad2becfec5426180b3749cb208abdf1a6c8354efc';
const probeValidation={profile:PROBE_PROFILE,codec:'pcm_s16le',sample_rate:16000,channels:1,bits_per_sample:16,duration_microseconds:1000000,format:'wav',stream_count:1};
export function probeReceiptMatches(root,v,m,tools) {
  try{
    if(!record(v)||typeof v.stage!=='string'||!(/^\.runtime\/development\/probe\/stages\/[a-f0-9]{32}$/).test(v.stage))return false;
    const stage=v.stage,build=stage+'/ffmpeg-source',s=sourceRecipe(root).sources.ffmpeg;
    const archive='.runtime/development/sources/'+s.sha256+'.tar.xz';
    if(fileSha(root,'renderers/ffprobe-source.json',32768)!==PROBE_RECIPE_SHA||fileSha(root,archive,s.maximum_archive_bytes)!==s.sha256)return false;
    const r=readJSON(root,'renderers/ffprobe-source.json',32768);
    const licenseFiles={[PROBE_BASE+'/COPYING.LGPLv2.1']:r.license_sha256,[PROBE_BASE+'/LICENSE.md']:'2e1d16c72fd74e12063776371da757322f8b77589386532f4fd8634bde7de1af'};
    for(const[path,sha]of Object.entries(licenseFiles))if(fileSha(root,path)!==sha)return false;
    const config=readFileSync(owned(root,build+'/config.h',1024*1024),'utf8')+readFileSync(owned(root,build+'/config_components.h',1024*1024),'utf8');
    for(const[name,n]of [['GPL',0],['NONFREE',0],['VERSION3',0],['NETWORK',0],['ZLIB',1],['PNG_DECODER',1]])if(!(new RegExp('^#define CONFIG_'+name+' '+n+'$','m')).test(config))return false;
    const generated=owned(root,stage+'/silent.wav',32044);
    if(lstatSync(generated).size!==32044||fileSha(root,stage+'/silent.wav',32044)!==WAV_SHA)return false;
    accessSync(owned(root,PROBE_BASE+'/ffprobe',64*1024*1024),constants.X_OK);
    const inv=readJSON(root,stage+'/inventory.json',4096),disk=inv?.disk_before;
    if(!record(disk)||!same(Object.keys(disk).sort(),['free_bytes','minimum_free_bytes','upper_bound_guaranteed'].sort())
      ||!Number.isSafeInteger(disk.free_bytes)||disk.free_bytes<6442450944||disk.minimum_free_bytes!==6442450944||disk.upper_bound_guaranteed!==false)return false;
    if(!same(inv,{schema_version:1,provider:PROBE_PROVIDER,stage,source_archive:archive,generated_roots:[build,stage+'/silent.wav',stage+'/logs'],disk_before:disk,retained:true,deletion_authorized:false}))return false;
    const expected={schema_version:1,provider:PROBE_PROVIDER,profile:PROBE_PROFILE,policy_sha256:POLICY_SHA,source_binding:m.source_binding,mode_id:m.mode_id,
      recipe_sha256:PROBE_RECIPE_SHA,version:'8.1.3',platform:'Darwin',architecture:'arm64',binary:PROBE_BASE+'/ffprobe',binary_sha256:fileSha(root,PROBE_BASE+'/ffprobe',64*1024*1024),
      source_url:s.url,source_sha256:s.sha256,source_archive:archive,toolchain:tools,stage,
      fixture:{path:stage+'/silent.wav',sha256:WAV_SHA,bytes:32044},validation:probeValidation,
      configuration_files:Object.fromEntries(['config.h','config_components.h'].map(name=>[build+'/'+name,fileSha(root,build+'/'+name)])),license_files:licenseFiles,inventory_sha256:fileSha(root,stage+'/inventory.json')};
    return same(v,expected);
  }catch{return false;}
}
export function privateProbe(root) {
  const base={ready:false,provider:PROBE_PROVIDER,profile:PROBE_PROFILE,path:PROBE_BASE+'/ffprobe',version:'8.1.3',reason:'DEVELOPMENT_PROBE_NOT_READY'};
  try{
    policy(root);const v=readJSON(root,PROBE_BASE+'/receipt.json',32768),m=mode(root);
    const cc='/Library/Developer/CommandLineTools/usr/bin/clang',make='/usr/bin/make';let tools=null;
    for(const sdk of ['/Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk','/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk']){
      if(!existsSync(sdk)||dirname(realpathSync(sdk))!=='/Library/Developer/CommandLineTools/SDKs'||!existsSync(join(sdk,'usr/lib/libSystem.tbd'))||!existsSync(join(sdk,'usr/include/zlib.h'))||!existsSync(join(sdk,'usr/include/ctype.h'))||!existsSync(cc)||!existsSync(make))continue;
      const json=join(sdk,'SDKSettings.json'),settings=existsSync(json)?json:join(sdk,'SDKSettings.plist');
      tools={cc,make,sdk,cc_sha256:hash(readFileSync(cc)),make_sha256:hash(readFileSync(make)),sdk_settings_sha256:hash(readFileSync(settings))};break;
    }
    if(!tools||!probeReceiptMatches(root,v,m,tools))return base;
    return {...base,ready:true,reason:null,binary_sha256:v.binary_sha256,validation:probeValidation};
  }catch{return base;}
}
export function inspectDevelopment(root,engine,probe,requireCompletion=true) {
  const base={ok:false,requested_engine:engine,engines:{hyperframes:{ready:false},remotion:{ready:false}},packages:{hyperframes:{ok:false},'ffmpeg-static':{ok:false}},
    network_during_inspection:false,runtime_scope:'fixed private silent fixture only',provider_calls:0,...Object.fromEntries(FLAGS.map(k=>[k,false]))};
  try{
    policy(root,engine);const m=mode(root),ffmpeg=sourceFFmpeg(root),npm=npmReady(root),b=readJSON(root,'.runtime/development/browser.json',32768);
    const expected=['schema_version','policy_sha256','source_binding','mode_id','browser','browser_version','browser_sha256','license_sha256','browser_drawing_smoke','platform','architecture'];
    if(!record(b)||!same(Object.keys(b).sort(),expected.sort())||b.schema_version!==4||b.policy_sha256!==POLICY_SHA||b.source_binding!==m.source_binding||b.mode_id!==m.mode_id
      ||b.browser_version!=='152.0.7977.30'||b.license_sha256!==CHROME_LICENSE_SHA||b.browser_drawing_smoke!=='pass'||b.platform!=='Darwin'||b.architecture!=='arm64'
      ||typeof b.browser!=='string'||!b.browser.startsWith('.runtime/chrome/')||!b.browser.endsWith('/chrome-headless-shell'))return base;
    accessSync(owned(root,b.browser,256*1024*1024),constants.X_OK);
    const browserOK=fileSha(root,b.browser,256*1024*1024)===b.browser_sha256&&fileSha(root,join(dirname(b.browser),'LICENSE.headless_shell'))===CHROME_LICENSE_SHA;
    let ready=npm&&ffmpeg.ready&&probe.ready&&browserOK;
    if(requireCompletion){
      const receipts=Object.fromEntries(['.runtime/npm-core.json','.runtime/ffmpeg/receipt.json','.runtime/development/browser.json','.runtime/development/probe/receipt.json'].map(name=>[name,fileSha(root,name)]));
      const expected={schema_version:1,state:'complete',policy_sha256:POLICY_SHA,source_binding:m.source_binding,mode_id:m.mode_id,receipts};
      ready=ready&&same(readJSON(root,'.runtime/development/setup.json',32768),expected);
    }
    return {...base,ok:ready,policy_sha256:POLICY_SHA,source_binding:m.source_binding,packages:{hyperframes:{ok:npm},'ffmpeg-static':{ok:npm,inert_wrapper_only:true}},
      engines:{hyperframes:{ready},remotion:{ready:false}},browser:{path:b.browser,version:b.browser_version,ok:browserOK},ffmpeg,probe,npm_receipt_matches_scope:npm};
  }catch{return base;}
}
