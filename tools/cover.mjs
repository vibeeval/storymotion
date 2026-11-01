// Same installed Chromium dependency as HyperFrames. No network or generation.
import { createRequire } from 'node:module';
import { readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { homedir } from 'node:os';
const [hf,out] = process.argv.slice(2);
const require = createRequire(resolve(hf));
const puppeteer = require('puppeteer-core');
const sharp = require('sharp');
const {getInstalledBrowsers} = require('@puppeteer/browsers');
// Prefer the existing renderer-managed shell; no browser downloads or OS patches.
const installed = await getInstalledBrowsers({cacheDir:join(homedir(),'.cache/hyperframes/chrome')});
const cached = installed.find(b=>b.browser==='chrome-headless-shell')?.executablePath;
const candidates = [process.env.STORYMOTION_BROWSER,process.env.CHROME_PATH,cached,'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','/usr/bin/google-chrome','/usr/bin/chromium'].filter(Boolean);
const executablePath = candidates.find(p=>existsSync(p));
if(!executablePath) throw new Error('Installed Chrome missing; set CHROME_PATH to existing executable');
const browser=await puppeteer.launch({executablePath,headless:true,args:['--disable-background-networking']});
try {
  const page=await browser.newPage();
  await page.setRequestInterception(true);
  page.on('request',r=>r.url().startsWith('file:')||r.url().startsWith('data:')?r.continue():r.abort());
  await page.setViewport({width:1080,height:1920,deviceScaleFactor:1});
  await page.goto(pathToFileURL(join(out,'cover.html')).href);
  await page.evaluate(async()=>{
    await document.fonts.load('650 86px Schibsted','İıŞşĞğÇçÖöÜü');
    await document.fonts.ready;
  });
  const fonts=await page.evaluate(()=>({loaded:document.fonts.check('650 86px Schibsted','İıŞşĞğÇçÖöÜü'),faces:[...document.fonts].map(f=>({family:f.family,status:f.status}))}));
  if(!fonts.loaded || fonts.faces.some(f=>f.status!=='loaded')) throw new Error('Font failed to load');
  await page.screenshot({path:join(out,'cover.png')});
  await sharp(join(out,'cover.png')).resize(360,640).png().toFile(join(out,'cover-360.png'));
  await writeFile(join(out,'browser-evidence.json'),JSON.stringify({fonts,cover:{width:1080,height:1920},mobile_preview:{width:360,height:640,mode:'simulated'},physical_device_test:false},null,2));
} finally {await browser.close();}
