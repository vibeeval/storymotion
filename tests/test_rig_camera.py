from pack_fixture_case import PackFixtureCase
"""Canonical global-frame rig/object camera contracts; no native/browser calls."""
import copy
import json
import math
from pathlib import Path
import random
import re
import shutil
import subprocess
import unittest

from storymotion.rig_revision import rig_camera_operations, rig_camera_program

ROOT = Path(__file__).resolve().parents[1]


def camera_scenes():
    return [
        {'id': 'first', 'start': 0, 'end': 1.6, 'camera_motion': []},
        {'id': 'push', 'start': 1.6, 'end': 3.21, 'camera_motion': [
            {'target': 'camera', 'op': 'tween', 'offset': .1, 'duration': 1.41,
             'before': {'scale': 1, 'svgOrigin': '540 450'},
             'after': {'scale': 1.08, 'svgOrigin': '540 450'}, 'ease': 'cubic-in-out'}]},
        {'id': 'follow', 'start': 3.21, 'end': 4.82, 'camera_motion': [
            {'target': 'camera', 'op': 'tween', 'offset': .1, 'duration': 1.41,
             'before': {'x': 0}, 'after': {'x': 45}, 'ease': 'cubic-in-out'}]},
        {'id': 'locked', 'start': 4.82, 'end': 6.43, 'camera_motion': []},
    ]


class RigCameraContractTests(PackFixtureCase):
    def test_remotion_scene_and_cue_sequences_use_same_half_open_frame_timestamp_as_rig(self):
        source = (ROOT / 'renderers/remotion/entry.jsx').read_text()
        compact = re.sub(r'\s+', '', source)
        for name in ('scene', 'cue'):
            self.assertIn(f'from={{Math.ceil({name}.start*fps-1e-8)}}', compact)
            self.assertIn(f'durationInFrames={{Math.ceil({name}.end*fps-1e-8)-Math.ceil({name}.start*fps-1e-8)}}', compact)
        self.assertIn('constframe=useCurrentFrame(),seconds=frame/fps;', compact)
        creative = source.split('function CreativeVector(', 1)[1].split('function Objects(', 1)[0]
        self.assertNotIn('useCurrentFrame()', creative)
        self.assertIn('seconds-editScene.start', creative)
        self.assertGreaterEqual(compact.count('seconds={seconds}'), 2)
        self.assertIn('s.start<=seconds&&seconds<s.end', compact)
        # This old clock makes the envelope enter a frame before its rig camera.
        frames = [1.6, 1.61, 3.21, 4.82]
        for boundary in frames:
            for frame in range(195):
                visible = frame >= math.ceil(boundary * 30 - 1e-8)
                self.assertEqual(visible, frame / 30 >= boundary)
        self.assertEqual(math.floor(3.21 * 30 + .5), 96)
        self.assertLess(96 / 30, 3.21)
        self.assertEqual(math.ceil(3.21 * 30 - 1e-8), 97)
        # Animation phase follows global f/30 - raw source start, never the
        # rounded Sequence-local frame. No audio or anchor retiming is needed.
        self.assertAlmostEqual(54 / 30 - 1.61, .19)
        self.assertNotAlmostEqual((54 - round(1.61 * 30)) / 30, .19)

    def test_rig_camera_converts_origin_once_and_preserves_object_motion_input(self):
        original = camera_scenes()[1]['camera_motion']
        before = copy.deepcopy(original)
        value = rig_camera_operations(original)
        self.assertEqual(original, before)
        self.assertEqual(value[0]['before']['svgOrigin'], '540 1000')
        self.assertEqual(value[0]['after']['svgOrigin'], '540 1000')
        self.assertEqual(value[0]['target'], 'camera')
        self.assertNotEqual(value, original)
        program = rig_camera_program(camera_scenes()[1])
        self.assertIn('"#rig-camera"', program)
        self.assertIn('"svgOrigin": "540 1000"', program)
        self.assertIn('"immediateRender": false', program)
        self.assertIn('tl.set(', program)
        self.assertNotIn('onUpdate', program)

    @unittest.skipUnless(shutil.which('node'), 'Existing Node and bundled GSAP required')
    def test_global_camera_resets_and_matches_canonical_sampler_in_shuffled_seeks(self):
        scenes = camera_scenes()
        frames = list(range(194))
        random.Random(143).shuffle(frames)
        times = [f / 30 for f in list(range(194)) + list(reversed(range(194))) + frames + [0, 48, 96, 97, 144, 145, 0]]
        program = ''.join(rig_camera_program(scene) for scene in scenes)
        script = r"""import assert from'node:assert/strict';import{createRequire}from'node:module';import{sampleMotion}from'./renderers/edit-motion.mjs';const gsap=createRequire(import.meta.url)('./vendor/gsap.min.js').gsap;let raw='';for await(const c of process.stdin)raw+=c;const v=JSON.parse(raw),target={x:0,y:0,scale:1,rotation:0},core=gsap.timeline({paused:true});
        const vars=q=>{const a={...q};delete a.svgOrigin;return a;};const tl={set:(s,a,t)=>core.set(target,vars(a),t),fromTo:(s,a,b,t)=>core.fromTo(target,vars(a),vars(b),t)},direct={set:(s,a)=>gsap.set(target,vars(a))};Function('tl','gsap',v.program)(tl,direct);let checked=0;
        for(const seconds of v.times){core.totalTime(seconds,true);const scene=v.scenes.find(s=>s.start<=seconds&&seconds<s.end)||v.scenes.at(-1);const expected=sampleMotion(scene.camera_motion,seconds-scene.start).camera||{};for(const key of['x','y','scale','rotation'])assert.ok(Math.abs(target[key]-(expected[key]??(key==='scale'?1:0)))<.0002,`${scene.id}/${key}@${seconds}`);checked++;}
        core.kill();gsap.ticker.sleep();console.log(JSON.stringify({checked,scope:'object property model, not DOM/native render'}));"""
        result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT,
                                input=json.dumps({'program': program, 'scenes': scenes, 'times': times}),
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['checked'], len(times))


if __name__ == '__main__':
    unittest.main()
