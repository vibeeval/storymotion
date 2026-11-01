// Test-only observable wait. WebCrypto completion is not bounded by event-loop turns.
import {performance} from 'node:perf_hooks';
import {setTimeout as pause} from 'node:timers/promises';
export async function until(predicate,{timeoutMs=5000,pollMs=5}={}){
 if(typeof predicate!=='function'||!Number.isFinite(timeoutMs)||timeoutMs<=0||!Number.isFinite(pollMs)||pollMs<=0)throw TypeError('A predicate and positive finite wait bounds are required');
 const deadline=performance.now()+timeoutMs;
 for(;;){
  const remaining=deadline-performance.now();
  if(remaining<=0)throw Error('Expected deferred request did not start within '+timeoutMs+'ms');
  if(predicate())return;
  await pause(Math.min(pollMs,remaining));
 }
}
