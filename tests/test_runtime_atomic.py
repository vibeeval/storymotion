"""Real Node filesystem writes over private temporary fixtures; no renderer."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'),'Node required for JS atomic filesystem contracts')
class RuntimeAtomicTests(unittest.TestCase):
    def run_node(self,script):
        prefix='import {writeJsonAtomic} from '+json.dumps((ROOT/'tools/atomic-json.mjs').as_uri())+';'
        result=subprocess.run(['node','--input-type=module','-e',prefix+script],cwd=ROOT,capture_output=True,text=True,timeout=45)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_failures_preserve_prior_file_and_owned_temp_cleanup_and_sync_file_directory(self):
        self.run_node(r'''
        import * as fs from 'node:fs';import os from 'node:os';import path from 'node:path';import assert from 'node:assert/strict';
        const root=fs.mkdtempSync(path.join(os.tmpdir(),'runtime-atomic-')),target=path.join(root,'runtime.json');
        try {
          fs.writeFileSync(target,'{"old":true}');fs.writeFileSync(target+'.tmp','keep existing file');
          for(const method of ['fsyncSync','renameSync']) {
            const io={...fs,[method](){throw new Error('synthetic failure');}};
            assert.throws(()=>writeJsonAtomic(target,{next:true},io));
            assert.equal(fs.readFileSync(target,'utf8'),'{"old":true}');
            assert.deepEqual(fs.readdirSync(root).sort(),['runtime.json','runtime.json.tmp']);
          }
          const synced=[];writeJsonAtomic(target,{next:true},{...fs,fsyncSync(fd){synced.push(fs.fstatSync(fd).isDirectory()?'dir':'file');fs.fsyncSync(fd);}});
          assert.deepEqual(synced,['file','dir']);assert.deepEqual(JSON.parse(fs.readFileSync(target,'utf8')),{next:true});
          assert.equal(fs.statSync(target).mode&0o777,0o600);assert.equal(fs.readFileSync(target+'.tmp','utf8'),'keep existing file');
          const absent=path.join(root,'absent','state.json');assert.throws(()=>writeJsonAtomic(absent,{invalid:NaN}));assert.ok(!fs.existsSync(path.dirname(absent)));
        } finally {fs.rmSync(root,{recursive:true});}
        ''')

    def test_concurrent_processes_publish_complete_json_without_temp_collision(self):
        self.run_node(r'''
        import * as fs from 'node:fs';import os from 'node:os';import path from 'node:path';import {spawn} from 'node:child_process';import assert from 'node:assert/strict';
        const root=fs.mkdtempSync(path.join(os.tmpdir(),'runtime-parallel-')),target=path.join(root,'runtime.json');
        const moduleURL=new URL('./tools/atomic-json.mjs',`file://${process.cwd()}/`).href;
        try {
          writeJsonAtomic(target,{writer:-1,data:'x'.repeat(3000)});let observed=0;
          const reader=setInterval(()=>{const value=JSON.parse(fs.readFileSync(target,'utf8'));assert.equal(value.data,'x'.repeat(3000));observed++;},1);
          try {
            await Promise.all(Array.from({length:6},(_,writer)=>new Promise((resolve,reject)=>{
              const code=`import {writeJsonAtomic} from ${JSON.stringify(moduleURL)};for(let n=0;n<8;n++)writeJsonAtomic(${JSON.stringify(target)},{writer:${writer},data:'x'.repeat(3000)});`;
              const child=spawn(process.execPath,['--input-type=module','-e',code],{stdio:['ignore','ignore','pipe'],env:{PATH:process.env.PATH}});let errors='';child.stderr.on('data',chunk=>errors+=chunk);child.on('error',reject);child.on('exit',code=>code===0?resolve():reject(new Error(errors)));
            })));
          } finally {clearInterval(reader);}
          assert.ok(observed>0);assert.equal(JSON.parse(fs.readFileSync(target,'utf8')).data,'x'.repeat(3000));assert.deepEqual(fs.readdirSync(root),['runtime.json']);
        } finally {fs.rmSync(root,{recursive:true});}
        ''')
