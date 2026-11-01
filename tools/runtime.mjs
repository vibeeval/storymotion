// Pinned local graphs. Inspection never installs or contacts a provider.
import {readFileSync,mkdirSync,accessSync,lstatSync,realpathSync,unlinkSync,constants} from 'node:fs';
import * as development from './development-runtime.mjs';
import {writeJsonAtomic} from './atomic-json.mjs';
import {resolve,relative,join,dirname,isAbsolute} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';

export const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
export const addonRoot=join(root,'optional/remotion');
const record=v=>v!==null && typeof v==='object' && !Array.isArray(v);
const sameList=(a,b)=>Array.isArray(a) && a.length===b.length && a.every((v,i)=>v===b[i]);
const sha=p=>createHash('sha256').update(readFileSync(p)).digest('hex');
const local=p=>typeof p==='string' && !isAbsolute(p) && !relative(root,resolve(root,p)).startsWith('..') ? resolve(root,p) : null;
const windowsChecked=new Map();
function windowsOwned(p) {
  const python=process.env.STORYMOTION_PYTHON;
  if(!python || !isAbsolute(python))return false;
  const info=lstatSync(p),identity=[info.ino,info.size,info.mtimeMs,info.ctimeMs].join(':');
  if(windowsChecked.get(p)===identity)return true;
  try {execFileSync(python,['-X','utf8','-B',join(root,'tools/windows_file_check.py'),p],{timeout:10000,stdio:'pipe'});windowsChecked.set(p,identity);return true;}catch{return false;}
}
const ordinary=p=>{
  try {
    if (!local(relative(root,p)) || realpathSync(p)!==p) return false;
    const info=lstatSync(p);
    return info.isFile() && !info.isSymbolicLink() && info.nlink===1 && (process.platform==='win32' ? windowsOwned(p) : info.uid===process.getuid());
  } catch {return false;}
};
const readJSON=p=>{try {if (!ordinary(p) || lstatSync(p).size>4*1024*1024) return null;return JSON.parse(readFileSync(p,'utf8'));} catch{return null;}};
const executable=p=>{try {if(!ordinary(p))return false;accessSync(p,constants.X_OK);return true;}catch{return false;}};
const pins=readJSON(join(root,'renderers/versions.json'))??{};
export function selectedEngines(engine='hyperframes') {
  if (!['hyperframes','remotion','all'].includes(engine))throw new Error('INSTALL_ENGINE_INVALID');
  return engine==='all' ? ['hyperframes','remotion'] : [engine];
}
export function selectedGraphs(engine='hyperframes') {return selectedEngines(engine).includes('remotion') ? ['core','remotion'] : ['core'];}
export function graphDirectory(graph) {
  if (!['core','remotion'].includes(graph))throw new Error('INSTALL_GRAPH_INVALID');
  return graph==='core' ? root : addonRoot;
}
export function graphPackages(graph) {
  graphDirectory(graph);
  return graph==='core' ? ['hyperframes','ffmpeg-static'] : ['remotion','@remotion/cli','@remotion/bundler','@remotion/renderer','react','react-dom'];
}
export function requiredPackages(engine='hyperframes') {return selectedGraphs(engine).flatMap(graphPackages);}
export function packagesReady(packages,engine='hyperframes') {
  const required=requiredPackages(engine);
  return record(packages) && required.every(name=>record(packages[name]) && packages[name].ok===true);
}
export function selectedRuntimeReady(state,engine='hyperframes') {
  return packagesReady(state?.packages,engine) && selectedEngines(engine).every(name=>state?.engines?.[name]?.ready===true);
}
export function npmReceiptMatches(receipt,graph,lockSha,packageSha) {
  const required=graphPackages(graph),fields=['schema_version','graph','package_lock_sha256','package_json_sha256','npm_ci','required_packages'];
  return record(receipt) && Object.keys(receipt).length===fields.length && fields.every(name=>Object.hasOwn(receipt,name))
    && receipt.schema_version===3 && receipt.graph===graph && receipt.package_lock_sha256===lockSha
    && receipt.package_json_sha256===packageSha && receipt.npm_ci==='complete' && sameList(receipt.required_packages,required);
}
export function graphPlan(graph,packageJSON,lock) {
  const required=graphPackages(graph),blockers=[];
  if (!record(packageJSON?.dependencies) || !record(lock?.packages) || !record(lock.packages['']?.dependencies))
    return {graph,dependency_graph_ready:false,blockers:['INSTALL_METADATA_INVALID']};
  const dependencies=packageJSON.dependencies,locked=lock.packages[''].dependencies;
  if (Object.keys(dependencies).length!==Object.keys(locked).length || !Object.entries(dependencies).every(([name,version])=>
      typeof version==='string' && locked[name]===version && lock.packages['node_modules/'+name]?.version===version
      && typeof lock.packages['node_modules/'+name]?.integrity==='string'))blockers.push('PACKAGE_LOCK_MISMATCH');
  if (!sameList(Object.keys(dependencies).sort(),[...required].sort()))blockers.push('REQUIRED_ENGINE_PACKAGES_MISSING');
  if (graph==='core' && Object.keys(lock.packages).some(path=>{
    const name=path.split('node_modules/').at(-1);return name.startsWith('@remotion/') || ['remotion','react','react-dom'].includes(name);
  }))blockers.push('CORE_LOCK_REQUIRES_REMOTION');
  return {graph,dependency_graph_ready:blockers.length===0,blockers};
}
export function runtimeSetupPlan(engine='hyperframes',corePackage,coreLock,addonPackage,addonLock) {
  const selected=selectedGraphs(engine),graphs=[];
  for (const graph of selected) {
    const directory=graphDirectory(graph);
    const pkg=graph==='core' ? (corePackage===undefined ? readJSON(join(directory,'package.json')) : corePackage)
      : (addonPackage===undefined ? readJSON(join(directory,'package.json')) : addonPackage);
    const lock=graph==='core' ? (coreLock===undefined ? readJSON(join(directory,'package-lock.json')) : coreLock)
      : (addonLock===undefined ? readJSON(join(directory,'package-lock.json')) : addonLock);
    graphs.push(graphPlan(graph,pkg,lock));
  }
  const blockers=graphs.flatMap(g=>g.blockers);
  if (!probeRecipeReady())blockers.push('INDEPENDENT_FFPROBE_SOURCE_INVALID');
  return {selected_engines:selectedEngines(engine),selected_graphs:selected,required_packages:requiredPackages(engine),graphs,dependency_graph_ready:blockers.length===0,blockers};
}
export const platformSupported=(system,arch,glibc)=>(system==='win32' && arch==='x64') || ['arm64','x64'].includes(arch)
  && (system==='darwin' || (system==='linux' && typeof glibc==='string' && /^\d+\.\d+(?:\.\d+)*$/.test(glibc)));
const supportedPlatform=()=>platformSupported(process.platform,process.arch,
  process.platform==='linux' ? process.report?.getReport().header.glibcVersionRuntime : null);
export const compositorDirectory=()=>{
  if (!['darwin','linux','win32'].includes(process.platform) || !['arm64','x64'].includes(process.arch))return null;
  return join(addonRoot,'node_modules','@remotion/compositor-'+process.platform+'-'+process.arch+(process.platform==='linux'?'-gnu':process.platform==='win32'?'-msvc':''));
};
export function mediaEnvironment(engine='hyperframes') {
  if(development.developmentMode(root)){
    if(engine!=='hyperframes')throw new Error('DEVELOPMENT_SCOPE_REFUSED');
    return development.processEnvironment(root);
  }
  const dir=selectedEngines(engine).includes('remotion') ? compositorDirectory() : null;
  const allowed=['PATH','HOME','USER','LOGNAME','TMPDIR','TMP','TEMP','LANG','LC_ALL','SHELL','SYSTEMROOT','SystemRoot','USERPROFILE','LOCALAPPDATA','APPDATA','PATHEXT','COMSPEC','ComSpec','PYTHONUTF8'];
  const env=Object.fromEntries(allowed.filter(name=>process.env[name]!==undefined).map(name=>[name,process.env[name]]));
  Object.assign(env,{HYPERFRAMES_TELEMETRY_DISABLED:'1',DO_NOT_TRACK:'1'});
  if (dir && process.platform==='darwin')env.DYLD_LIBRARY_PATH=dir;
  if (dir && process.platform==='linux')env.LD_LIBRARY_PATH=dir;
  return env;
}
const WINDOWS_MEDIA_SHA='60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba';
function windowsRecipeReady() {
  const value=readJSON(join(root,'renderers/windows-media.json'));
  return value?.schema_version===1 && value.platform==='win32' && value.architecture==='x64'
    && value.version==='9.0.2' && value.archive_sha256===WINDOWS_MEDIA_SHA
    && value.archive_url==='https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip'
    && value.binary_redistributed===false && value.license==='GPL-3.0-or-later';
}
export function windowsMediaFilesMatch(directory,receipt,expected) {
  if(!record(expected) || Object.keys(expected).sort().join(',')!=='ffmpeg,ffprobe,license'
    || !Object.values(expected).every(v=>typeof v==='string' && /^[a-f0-9]{64}$/.test(v)))return false;
  if(!record(receipt?.binaries) || Object.keys(receipt.binaries).sort().join(',')!=='ffmpeg,ffprobe')return false;
  for(const name of ['ffmpeg','ffprobe']) {
    if(receipt.binaries[name]!==expected[name] || sha(join(directory,name+'.exe'))!==expected[name])return false;
  }
  return receipt.license_sha256===expected.license && sha(join(directory,'LICENSE.txt'))===expected.license;
}
function inspectWindowsMedia() {
  const base='.runtime/windows-media',receipt=readJSON(join(root,base,'receipt.json'));
  const result={ready:false,path:base+'/ffprobe.exe',version:'9.0.2',reason:'WINDOWS_MEDIA_NOT_READY'};
  try {
    if(!windowsRecipeReady() || receipt?.schema_version!==1 || receipt.platform!=='win32' || receipt.architecture!=='x64'
      || receipt.version!=='9.0.2' || receipt.archive_sha256!==WINDOWS_MEDIA_SHA
      || receipt.recipe_sha256!==sha(join(root,'renderers/windows-media.json'))
      || !ordinary(join(root,base,'source.zip')) || sha(join(root,base,'source.zip'))!==WINDOWS_MEDIA_SHA
      || !ordinary(join(root,base,'LICENSE.txt')) || sha(join(root,base,'LICENSE.txt'))!==receipt.license_sha256)return result;
    for(const name of ['ffmpeg','ffprobe']) {
      const binary=join(root,base,name+'.exe');
      if(!executable(binary) || receipt.binaries?.[name]!==sha(binary))return result;
    }
    const python=process.env.STORYMOTION_PYTHON;
    if(!python || !isAbsolute(python))return result;
    const expected=JSON.parse(execFileSync(python,['-X','utf8','-B',join(root,'tools/windows_file_check.py'),'--media-hashes'],
      {encoding:'utf8',timeout:60000,maxBuffer:4096,stdio:['ignore','pipe','pipe']}));
    if(!windowsMediaFilesMatch(join(root,base),receipt,expected))return result;
    return {...result,ready:true,reason:null};
  }catch{return result;}
}

const SOURCE_SHA='7138d28c96d9d3e3af4ee3d8cad72741f8ffb40da90c1112235dea3ecd3178a3';
const COPYING_SHA='246041b6ecf9bc32d718a62c57877c78b5eb397b6467e74ed7ae2626ab189c30';
export function probeRecipeReady() {
  if(process.platform==='win32')return windowsRecipeReady();
  const value=readJSON(join(root,'renderers/ffprobe-source.json'));
  try {return value?.version==='8.1.3' && value.source_sha256===SOURCE_SHA
    && value.source_url==='https://ffmpeg.org/releases/ffmpeg-8.1.3.tar.xz'
    && value.license==='LGPL-2.1-or-later' && value.license_path==='vendor/licenses/ffmpeg-8.1.3-COPYING.LGPLv2.1'
    && value.license_sha256===COPYING_SHA && value.binary_redistributed===false
    && value.source_date_epoch===1789951930
    && ordinary(join(root,value.license_path)) && sha(join(root,value.license_path))===COPYING_SHA
    && ordinary(join(root,'vendor/licenses/ffmpeg-8.1.3-LICENSE.md'))
    && sha(join(root,'vendor/licenses/ffmpeg-8.1.3-LICENSE.md'))==='2e1d16c72fd74e12063776371da757322f8b77589386532f4fd8634bde7de1af';}
  catch{return false;}
}
export function inspectProbe() {
  if(process.platform==='win32')return inspectWindowsMedia();
  const receipt=readJSON(join(root,'.runtime/probe/receipt.json'));
  const binary=join(root,'.runtime/probe/ffprobe');
  try {
    const archive=typeof receipt?.source_archive==='string' && /^\.runtime\/probe\/stages\/[a-f0-9]{32}\/source\.tar\.xz$/.test(receipt.source_archive) ? local(receipt.source_archive) : null;
    const ready=probeRecipeReady() && process.platform==='darwin' && process.arch==='arm64'
      && receipt?.schema_version===1 && receipt.version==='8.1.3' && receipt.source_sha256===SOURCE_SHA
      && receipt.recipe_sha256===sha(join(root,'renderers/ffprobe-source.json')) && receipt.platform==='Darwin'
      && receipt.architecture==='arm64' && receipt.binary==='.runtime/probe/ffprobe'
      && executable(binary) && receipt.binary_sha256===sha(binary) && archive && ordinary(archive) && sha(archive)===SOURCE_SHA
      && ordinary(join(root,'.runtime/probe/COPYING.LGPLv2.1')) && ordinary(join(root,'.runtime/probe/LICENSE.md'))
      && sha(join(root,'.runtime/probe/COPYING.LGPLv2.1'))===COPYING_SHA
      && sha(join(root,'.runtime/probe/LICENSE.md'))==='2e1d16c72fd74e12063776371da757322f8b77589386532f4fd8634bde7de1af';
    return {ready:!!ready,path:'.runtime/probe/ffprobe',version:'8.1.3',reason:ready?null:'INDEPENDENT_PROBE_NOT_READY'};
  } catch{return {ready:false,path:'.runtime/probe/ffprobe',version:'8.1.3',reason:'INDEPENDENT_PROBE_NOT_READY'};}
}
export function browserManifestMatches(manifest,core) {
  return manifest?.schema_version===3 && (process.platform!=='win32' || (manifest.platform==='win32' && manifest.architecture==='x64')) && manifest.package_lock_sha256===core.lock_sha256
    && manifest.package_json_sha256===core.package_sha256 && manifest.browser_version===pins.chrome_headless_shell;
}
export function inspectRuntime(engine='hyperframes') {
  if(development.developmentMode(root))return development.inspectDevelopment(root,engine,development.privateProbe(root));
  const graphs=selectedGraphs(engine),selected=selectedEngines(engine),required=requiredPackages(engine),supported=supportedPlatform();
  const expected={hyperframes:pins.hyperframes,'ffmpeg-static':pins.ffmpeg_static,remotion:pins.remotion,
    '@remotion/cli':pins.remotion,'@remotion/bundler':pins.remotion,'@remotion/renderer':pins.remotion,react:pins.react,'react-dom':pins.react};
  const packages={},states={};
  for (const graph of graphs) {
    const directory=graphDirectory(graph);
    const lock=readJSON(join(directory,'package-lock.json')),pkg=readJSON(join(directory,'package.json'));
    const plan=graphPlan(graph,pkg,lock);
    for (const name of graphPackages(graph)) {
      const actual=readJSON(join(directory,'node_modules',name,'package.json'))?.version??null;
      packages[name]={expected:expected[name],actual,ok:actual===expected[name],graph};
    }
    let lockSha=null,packageSha=null;
    try {lockSha=sha(join(directory,'package-lock.json'));packageSha=sha(join(directory,'package.json'));}catch{}
    const receipt=readJSON(join(root,'.runtime/npm-'+graph+'.json'));
    states[graph]={...plan,lock_sha256:lockSha,package_sha256:packageSha,
      npm_receipt_ok:plan.dependency_graph_ready && npmReceiptMatches(receipt,graph,lockSha,packageSha)};
  }
  const manifest=readJSON(join(root,'.runtime/runtime.json')),browser=manifest && local(manifest.browser);
  let browserOK=false;
  try {browserOK=!!browser && executable(browser) && browserManifestMatches(manifest,states.core) && manifest.browser_sha256===sha(browser);}catch{}
  const probe=inspectProbe();
  const binaries=Object.fromEntries(['ffmpeg','ffprobe'].map(name=>{
    const p=name==='ffmpeg' ? (process.platform==='win32' ? join(root,'.runtime/windows-media/ffmpeg.exe') : join(root,'node_modules/ffmpeg-static/ffmpeg')) : join(root,probe.path);
    let version=null,filtersOK=true;
    if(supported && executable(p) && (name!=='ffprobe'||probe.ready)) {
      try {version=execFileSync(p,['-version'],{encoding:'utf8',timeout:15000,env:mediaEnvironment(),stdio:['ignore','pipe','pipe']}).split('\n')[0];}catch{}
    }
    if(name==='ffmpeg' && version) {
      try {const filters=execFileSync(p,['-hide_banner','-filters'],{encoding:'utf8',timeout:15000,env:mediaEnvironment(),stdio:['ignore','pipe','pipe']});
        filtersOK=['setparams','scale','fps','color'].every(value=>filters.includes(value));}catch{filtersOK=false;}
    }
    return [name,{path:relative(root,p).split('\\').join('/'),version,required_filters_ok:filtersOK,ok:!!version && filtersOK && (name!=='ffprobe'||probe.ready)}];
  }));
  const common=supported && browserOK && probe.ready && states.core.npm_receipt_ok
    && graphPackages('core').every(name=>packages[name].ok) && Object.values(binaries).every(value=>value.ok);
  const engines={hyperframes:{ready:!!common},remotion:{ready:!!common && !!states.remotion?.npm_receipt_ok && packagesReady(packages,'remotion')}};
  return {schema_version:3,platform:process.platform,architecture:process.arch,node:process.version,
    requested_engine:engine,selected_engines:selected,selected_graphs:graphs,required_packages:required,packages,graphs:states,
    license_notice:selected.includes('remotion')?'Remotion selection requires fixed-version/current terms review: https://www.remotion.dev/docs/license/faq . No agreement accepted or commercial rights cleared.':null,
    supported_platform:supported,native_acceptance:'standalone probe recipe verified on macOS arm64; product/browser/other targets unverified',locking:process.platform==='win32'?'Windows LockFileEx':'POSIX fcntl',
    browser:{path:browser?relative(root,browser).split('\\').join('/'):null,version:pins.chrome_headless_shell,ok:browserOK},probe,binaries,
    setup_matches_lock:browserOK,npm_receipt_matches_scope:graphs.every(graph=>states[graph].npm_receipt_ok),engines,
    render_health:'Local dependency readiness only; engine MP4/human/clean-device acceptance is separate',
    network_during_inspection:false,live_provider_calls:false};
}
export function requireRuntime(engine) {
  if(!['hyperframes','remotion'].includes(engine))throw new Error('INSTALL_ENGINE_INVALID');
  const state=inspectRuntime(engine);
  if(!selectedRuntimeReady(state,engine))throw new Error('Selected project-local runtime missing or stale; review preflight, no global or engine fallback.');
  if(development.developmentMode(root))return {browser:resolve(root,state.browser.path),ffmpeg:resolve(root,state.ffmpeg.path),ffprobe:resolve(root,state.probe.path)};
  return {browser:resolve(root,state.browser.path),ffmpeg:resolve(root,state.binaries.ffmpeg.path),ffprobe:resolve(root,state.binaries.ffprobe.path)};
}
export async function setup(engine='hyperframes') {
  if(development.developmentMode(root))throw new Error('DEVELOPMENT_LEGACY_SETUP_REFUSED');
  selectedEngines(engine);
  if(!supportedPlatform())throw new Error('PLATFORM_UNSUPPORTED: macOS or Linux glibc arm64/x64 required; native acceptance is separate');
  const plan=runtimeSetupPlan(engine);
  if(!plan.dependency_graph_ready)throw new Error('DEPENDENCY_PLAN_BLOCKED: '+plan.blockers.join(','));
  const state=inspectRuntime(engine);
  if(!state.npm_receipt_matches_scope || !packagesReady(state.packages,engine))throw new Error('RUNTIME_NPM_RECEIPT_REQUIRED');
  if(!state.probe.ready)throw new Error('INDEPENDENT_PROBE_NOT_READY');
  const require=createRequire(join(root,'node_modules/hyperframes/package.json'));
  const {install,Browser,detectBrowserPlatform}=require('@puppeteer/browsers');
  const cacheDir=join(root,'.runtime/chrome');mkdirSync(cacheDir,{recursive:true});
  const installed=await install({browser:Browser.CHROMEHEADLESSSHELL,buildId:pins.chrome_headless_shell,platform:detectBrowserPlatform(),cacheDir});
  const browser=installed.executablePath;
  const version=execFileSync(browser,['--version'],{encoding:'utf8',timeout:20000,env:mediaEnvironment()});
  if(!version.includes(pins.chrome_headless_shell))throw new Error('Pinned browser version mismatch');
  const puppeteer=require('puppeteer-core');
  const instance=await puppeteer.launch({executablePath:browser,headless:true,args:['--disable-background-networking'],timeout:20000});
  try {
    const page=await instance.newPage();await page.goto('data:text/html,<h1>Local runtime</h1>',{timeout:15000});
    if((await page.screenshot({timeout:15000})).length<100)throw new Error('Browser drawing smoke failed');
  }finally{await instance.close();}
  writeJsonAtomic(join(root,'.runtime/runtime.json'),{schema_version:3,platform:process.platform,architecture:process.arch,
    browser:relative(root,browser).split('\\').join('/'),browser_version:pins.chrome_headless_shell,browser_sha256:sha(browser),browser_drawing_smoke:'pass',
    package_lock_sha256:state.graphs.core.lock_sha256,package_json_sha256:state.graphs.core.package_sha256});
  const ready=inspectRuntime(engine);
  if(!selectedRuntimeReady(ready,engine))throw new Error('Selected runtime incomplete; no fallback used');
  return ready;
}
export async function setupDevelopment(policySha,approved) {
  if(approved!==true||policySha!==development.POLICY_SHA)throw new Error('DEVELOPMENT_OPERATION_APPROVAL_REQUIRED');
  development.policy(root);const mode=development.mode(root);
  if(!development.npmReady(root)||!development.sourceFFmpeg(root).ready||!development.privateProbe(root).ready)throw new Error('DEVELOPMENT_PREREQUISITE_NOT_READY');
  const receipt=join(root,'.runtime/development/browser.json');
  try {development.owned(root,'.runtime/development/browser.json');unlinkSync(receipt);}catch(error){if(error.code!=='ENOENT')throw error;}
  const env=mediaEnvironment('hyperframes');
  for(const name of Object.keys(process.env))if(!Object.hasOwn(env,name))delete process.env[name];
  Object.assign(process.env,env);
  const require=createRequire(join(root,'node_modules/hyperframes/package.json'));
  const {install,Browser,detectBrowserPlatform}=require('@puppeteer/browsers');
  if(detectBrowserPlatform()!=='mac_arm')throw new Error('DEVELOPMENT_PLATFORM_REFUSED');
  const installed=await install({browser:Browser.CHROMEHEADLESSSHELL,buildId:pins.chrome_headless_shell,
    platform:detectBrowserPlatform(),cacheDir:join(root,'.runtime/chrome'),baseUrl:'https://storage.googleapis.com/chrome-for-testing-public'});
  const browser=installed.executablePath,relativeBrowser=relative(root,browser);
  if(!relativeBrowser.startsWith('.runtime/chrome/')||!relativeBrowser.endsWith('/chrome-headless-shell'))throw new Error('DEVELOPMENT_BROWSER_PATH_REFUSED');
  const license=join(dirname(relativeBrowser),'LICENSE.headless_shell');
  if(development.fileSha(root,license)!==development.CHROME_LICENSE_SHA)throw new Error('DEVELOPMENT_BROWSER_LICENSE_CHANGED');
  const version=execFileSync(browser,['--version'],{encoding:'utf8',timeout:20000,env});
  if(!version.includes(pins.chrome_headless_shell))throw new Error('DEVELOPMENT_BROWSER_VERSION_CHANGED');
  const puppeteer=require('puppeteer-core'),instance=await puppeteer.launch({executablePath:browser,headless:true,args:['--disable-background-networking'],timeout:20000,env});
  try{
    const page=await instance.newPage();await page.goto('data:text/html,<h1>Private fixture runtime</h1>',{timeout:15000});
    if((await page.screenshot({timeout:15000})).length<100)throw new Error('DEVELOPMENT_BROWSER_DRAWING_FAILED');
  }finally{await instance.close();}
  development.policy(root);
  writeJsonAtomic(receipt,{schema_version:4,policy_sha256:development.POLICY_SHA,source_binding:mode.source_binding,mode_id:mode.mode_id,
    browser:relativeBrowser,browser_version:pins.chrome_headless_shell,browser_sha256:development.fileSha(root,relativeBrowser,256*1024*1024),
    license_sha256:development.CHROME_LICENSE_SHA,browser_drawing_smoke:'pass',platform:'Darwin',architecture:'arm64'});
  const state=development.inspectDevelopment(root,'hyperframes',development.privateProbe(root),false);
  if(state.ok!==true)throw new Error('DEVELOPMENT_RUNTIME_NOT_READY');
  return state;
}
if(process.argv[1] && resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  try {
    if(process.argv[2]==='development-setup'){
      if(process.argv.length!==6||process.argv[3]!=='--policy-sha256'||process.argv[5]!=='--allow-private-test-execution')throw new Error('DEVELOPMENT_OPERATION_APPROVAL_REQUIRED');
      console.log(JSON.stringify(await setupDevelopment(process.argv[4],true),null,2));
    }else{
    if(!['inspect','setup'].includes(process.argv[2]) || ![3,5].includes(process.argv.length)
       || (process.argv.length===5 && process.argv[3]!=='--engine'))throw new Error('Usage: runtime.mjs inspect|setup [--engine hyperframes|remotion|all]');
    const engine=process.argv.length===5?process.argv[4]:'hyperframes';selectedEngines(engine);
    console.log(JSON.stringify(process.argv[2]==='setup'?await setup(engine):inspectRuntime(engine),null,2));
    }
  }catch(error){console.error(JSON.stringify({ok:false,error:String(error.message).replaceAll(root,'$PROJECT')}));process.exitCode=2;}
}
