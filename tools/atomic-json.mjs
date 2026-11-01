import * as filesystem from 'node:fs';
import {basename, dirname, join} from 'node:path';
import {randomUUID} from 'node:crypto';

export function writeJsonAtomic(path, value, io=filesystem) {
  const text=JSON.stringify(value,(key,item)=>{
    if(typeof item==='number' && !Number.isFinite(item))throw new TypeError('Non-finite JSON number');
    return item;
  },2);
  if(typeof text!=='string')throw new TypeError('JSON value required');
  const raw=Buffer.from(text+'\n');
  const temporary=join(dirname(path),'.'+basename(path)+'.'+randomUUID()+'.tmp');
  let descriptor=null,owned=false;
  try {
    descriptor=io.openSync(temporary,'wx',0o600);owned=true;
    io.writeFileSync(descriptor,raw);io.fsyncSync(descriptor);io.closeSync(descriptor);descriptor=null;
    io.renameSync(temporary,path);
    if(process.platform==='win32')return; // file fsync + same-directory rename; Windows has no POSIX directory fsync
    const directory=io.openSync(dirname(path),filesystem.constants.O_RDONLY|filesystem.constants.O_DIRECTORY);
    try {io.fsyncSync(directory);} finally {io.closeSync(directory);}
  } finally {
    if(descriptor!==null)io.closeSync(descriptor);
    if(owned)try {io.unlinkSync(temporary);} catch(error) {if(error.code!=='ENOENT')throw error;}
  }
}
