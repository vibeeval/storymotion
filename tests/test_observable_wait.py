"""Real timer/monotonic timeout behavior for the test-only request wait helper."""
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ObservableWaitTests(unittest.TestCase):
    def run_js(self, body):
        script = "import assert from 'node:assert/strict';import {performance} from 'node:perf_hooks';import {until} from './tests/observable_wait.mjs';\n" + body
        result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT,
            capture_output=True, text=True, timeout=5, env={'PATH':os.environ.get('PATH','')})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_observable_condition_can_arrive_later_than_fifty_immediate_turns(self):
        self.run_js("let started=false;const timer=setTimeout(()=>{started=true;},80);try{await until(()=>started,{timeoutMs:2000});assert.equal(started,true);}finally{clearTimeout(timer);}")

    def test_genuine_timeout_rejects_on_monotonic_deadline(self):
        self.run_js("const start=performance.now();await assert.rejects(until(()=>false,{timeoutMs:25,pollMs:3}),/Expected deferred request did not start within 25ms/);assert.ok(performance.now()-start>=25);")

    def test_predicate_failure_propagates_and_invalid_wait_bounds_reject(self):
        self.run_js("const error=Error('TEST_ONLY_PREDICATE_FAILURE');await assert.rejects(until(()=>{throw error;}),e=>e===error);for(const options of [{timeoutMs:0},{timeoutMs:Infinity},{pollMs:0},{pollMs:NaN}])await assert.rejects(until(()=>false,options),TypeError);")
