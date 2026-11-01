"""Generated HF clock parity, including reverse seeks at real cue boundaries."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from storymotion import development_templates
from storymotion.engine import Engine
from storymotion.security import write_json
from tools.harness_fixtures import template_fixture_brief

ROOT = Path(__file__).resolve().parents[1]
ENV = {'PATH': os.environ.get('PATH', ''), 'DO_NOT_TRACK': '1'}


class GeneratedTemplateClockTests(unittest.TestCase):
    def probe(self, spec, times, off_grid=()):
        with tempfile.TemporaryDirectory() as td, \
             patch('storymotion.engine.checked_process', side_effect=AssertionError('No native process')), \
             patch('socket.socket.connect', side_effect=AssertionError('No network')):
            root = Path(td).resolve();source = root / 'input.json'
            write_json(source, template_fixture_brief('neutral', spec))
            with Engine(root / 'work') as engine:
                job = engine.create(source, render_engine='hyperframes')['job']
                engine.run(job, 'prepare');out = engine.directory(job)
                result = subprocess.run(['node', str(ROOT / 'tests/template_clock_probe.mjs')],
                    input=json.dumps({'out': str(out), 'times': times, 'offGrid': off_grid}),
                    cwd=ROOT, capture_output=True, text=True, timeout=60, env=ENV)
                self.assertEqual(result.returncode, 0, result.stderr[-3000:])
                value = json.loads(result.stdout)
                self.assertEqual(value['samples'], len(times))
                self.assertEqual(value['off_grid'], len(off_grid))
                self.assertFalse((out / 'render-1080.mp4').exists())
                return value

    def test_known_cue_boundaries_in_actual_generated_program_forward_and_reverse(self):
        for family in ('scan-hud', 'shape-morph'):
            with self.subTest(family=family):
                self.probe(development_templates.examples(family)[0]['spec'],
                    [32 / 30, 64 / 30, 32 / 30, 0, 64 / 30],
                    [.123456, .123457, 1.066668, 2.133332])

    def test_all_168_generated_programs_at_cue_adjacent_video_frames(self):
        cases = samples = 0
        for family in sorted(development_templates.FAMILIES):
            for index, case in enumerate(development_templates.examples(family)):
                spec = case['spec'];p = spec['parameters'];last = round(p['duration'] * 30)
                boundaries = {round(c[k] * 30) for c in p['cues'] for k in ('start', 'end')}
                frames = sorted({max(0, min(last, frame + delta)) for frame in boundaries for delta in (-1, 0, 1)})
                times = [frame / 30 for frame in frames]
                times += list(reversed(times)) + [0, frames[-1] / 30, 0]
                with self.subTest(family=family, case=index):
                    value = self.probe(spec, times);samples += value['samples'];cases += 1
        self.assertEqual(cases, 168)
        self.assertGreater(samples, 2000)

    def test_existing_helper_normalizes_only_inside_half_microsecond_tolerance(self):
        script = """import assert from 'node:assert/strict';import {videoFrameTime} from './renderers/template-motion.mjs';
for(const n of [0,1,32,64,95,120]){const frame=n/30;assert.equal(videoFrameTime(frame),frame);
for(const sign of [-1,1]){const recovered=n===0&&sign<0?-0:frame;assert.equal(videoFrameTime(frame+sign*.00000049),recovered);
const outside=frame+sign*.00000051;assert.equal(videoFrameTime(outside),outside);}}
for(const t of [.123456,.123457,1.066668,2.133332])assert.equal(videoFrameTime(t),t);
console.log(JSON.stringify({ok:true}));"""
        result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT,
            capture_output=True, text=True, timeout=30, env=ENV)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'ok': True})
