// Only the bundled, bounded template is compiled. Arbitrary user JS/URLs are not inputs.
import {createRequire} from 'node:module';
import {readFileSync, writeFileSync, mkdirSync, rmSync} from 'node:fs';
import {resolve, join} from 'node:path';
import {requireRuntime,root,addonRoot} from './runtime.mjs';
const [operation, directory]=process.argv.slice(2);
if(!['check','render'].includes(operation) || !directory || process.argv.length!==4) throw new Error('Usage: node tools/remotion.mjs check|render JOB_DIRECTORY');
const runtime=requireRuntime('remotion');
const require=createRequire(join(addonRoot,'package.json'));
const {bundle}=require('@remotion/bundler');
const {openBrowser,selectComposition,renderMedia,renderStill}=require('@remotion/renderer');
const out=resolve(directory);
const inputProps=JSON.parse(readFileSync(join(out,'remotion-props.json'),'utf8'));
const bundleDir=join(out,'.remotion-bundle');
const serveUrl=await bundle({entryPoint:join(root,'renderers/remotion/entry.jsx'),outDir:bundleDir,
  publicDir:join(out,'assets'),enableCaching:false,
  webpackOverride:config=>({...config,resolve:{...config.resolve,
    modules:[join(addonRoot,'node_modules'),...(config.resolve?.modules??['node_modules'])]}})});
const browser=await openBrowser('chrome',{browserExecutable:runtime.browser,logLevel:'error'});
try {
  const composition=await selectComposition({serveUrl,id:'StoryMotion',inputProps,puppeteerInstance:browser,logLevel:'error',
    onBrowserLog:entry=>console.error('Remotion browser:',entry.text)});
  if(composition.width!==1080 || composition.height!==1920 || composition.fps!==30 || composition.durationInFrames!==Math.round(inputProps.brief.duration*30)) throw new Error('Remotion composition metadata mismatch');
  if(operation==='check') {
    const samples=[0,Math.floor(composition.durationInFrames/2),composition.durationInFrames-1];
    const sampleDir=join(out,'remotion-check');mkdirSync(sampleDir,{recursive:true});
    for(const frame of samples) await renderStill({serveUrl,composition,inputProps,frame,imageFormat:'png',output:join(sampleDir,`frame-${frame}.png`),puppeteerInstance:browser,logLevel:'error'});
    console.log(JSON.stringify({ok:true,browserSkipped:false,engine:'remotion',version:'4.0.537',sample_frames:samples,metadata:{width:composition.width,height:composition.height,fps:composition.fps,durationInFrames:composition.durationInFrames},network_assets:'local-only template',paid_provider_calls:0}));
  } else {
    await renderMedia({serveUrl,composition,inputProps,codec:'h264',imageFormat:'png',pixelFormat:'yuv420p',audioCodec:'aac',crf:16,concurrency:1,
      outputLocation:join(out,'render-1080.mp4'),puppeteerInstance:browser,logLevel:'error'});
    console.log(JSON.stringify({ok:true,engine:'remotion',output:'render-1080.mp4',paid_provider_calls:0}));
  }
} finally {await browser.close({silent:true});rmSync(bundleDir,{recursive:true,force:true});}
