from pack_fixture_case import PackFixtureCase
from storymotion.account_packs import render_profile
"""Neutral rig geometry and frame seek equivalence; no native/browser claims."""
import copy
import json
import math
from pathlib import Path
import random
import shutil
import subprocess
import unittest
import xml.etree.ElementTree as ET

from storymotion.rig_render import hf_markup, hf_program, rig_svg, sample_rig, MOUTHS
from storymotion.security import WorkflowError, file_hash

ROOT = Path(__file__).resolve().parents[1]


def definition():
    return json.loads((ROOT / 'renderers/neutral-rig.json').read_text())


def palette():
    return render_profile('sample-flow')['palette']


def spec(account='sample-flow'):
    end = 2.017
    timeline = 61 / 30
    cues = [{'start': i / 10, 'end': (i + 1) / 10, 'value': value} for i, value in enumerate(MOUTHS)]
    cues.append({'start': .9, 'end': end, 'value': 'H'})
    return {'schema_version': 1, 'account': account, 'rig_id': 'neutral-presenter-1',
            'rig_sha256': file_hash(ROOT / 'renderers/neutral-rig.json'),
            'source_audio_sha256': 'a' * 64, 'source_script_sha256': 'b' * 64, 'source_timing_sha256': 'c' * 64,
            'audio_duration_seconds': end, 'timeline_duration_seconds': timeline, 'fps': 30,
            'provenance': {'method': 'synthetic_test', 'tool': 'Original synthetic frame fixture', 'note': 'Not phonetic acceptance',
                           'approved_by': 'Synthetic test operator', 'rights_confirmed': True,
                           'human_phonetic': 'pending', 'human_visual': 'pending'},
            'mouthCues': cues,
            'visual_tracks': {'blinks': [{'start': 3 / 30, 'end': 5 / 30}, {'start': .6, 'end': .67}],
                              'head': [{'time': 0, 'rotate': 0, 'x': 0, 'y': 0},
                                       {'time': .35, 'rotate': 4, 'x': 8, 'y': -4},
                                       {'time': 1.1, 'rotate': -8, 'x': -12, 'y': 12},
                                       {'time': timeline, 'rotate': 0, 'x': 0, 'y': 0}]}}


def node(script, value):
    result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT,
                            input=json.dumps(value, ensure_ascii=False), text=True,
                            capture_output=True, timeout=20)
    if result.returncode:
        raise AssertionError(result.stderr + result.stdout)
    return json.loads(result.stdout)


class NeutralRigGeometryTests(PackFixtureCase):
    def test_owned_descriptor_has_full_body_eyes_and_nine_distinct_manual_mouths(self):
        d = definition()
        self.assertEqual(d['license'], 'original_project_vectors')
        self.assertEqual(set(d['mouths']), set(MOUTHS))
        self.assertEqual(len({json.dumps(d['mouths'][m]['shapes'], sort_keys=True) for m in MOUTHS}), 9)
        self.assertTrue(d['body']); self.assertTrue(d['head'])
        self.assertEqual(set(d['eyes']), {'open', 'closed'})
        self.assertEqual(d['coordinate_system']['neck'], [0, 80])
        raw = json.dumps(d)
        for forbidden in ('http:', 'https:', '<script', 'Kıvrım', 'Deniz', 'data:', 'onload'):
            self.assertNotIn(forbidden, raw)

    def test_one_visible_mouth_blink_swap_and_fixed_body(self):
        original_body = None
        for mode in ('inset', 'serial-courier'):
            for value in MOUTHS:
                for blink in (False, True):
                    state = {'value': value, 'blink': blink, 'head': {'rotate': 4, 'x': 8, 'y': -4}}
                    markup = rig_svg(definition(), palette(), state, mode)
                    root = ET.fromstring(markup)
                    ids = {e.attrib['id']: e for e in root.iter() if 'id' in e.attrib}
                    visible = [m for m in MOUTHS if ids['neutral-rig-mouth-' + m].attrib['opacity'] == '1']
                    self.assertEqual(visible, [value])
                    self.assertEqual(ids['neutral-rig-eyes-open'].attrib['opacity'], '0' if blink else '1')
                    self.assertEqual(ids['neutral-rig-eyes-closed'].attrib['opacity'], '1' if blink else '0')
                    self.assertIn('translate(0 80) rotate(4) translate(0 -80)', ids['neutral-rig-head'].attrib['transform'])
                    body = ET.tostring(ids['neutral-rig-body'])
                    original_body = original_body or body
                    self.assertEqual(body, original_body)
                    self.assertNotIn('transform', ids['neutral-rig-body'].attrib)
                    self.assertEqual(len(ids), 15)
        self.assertIn('translate(850 960) scale(0.55)', hf_markup(spec(), palette()))
        self.assertIn('translate(245 785) scale(1)', hf_markup(spec('sample-series'), palette()))

    def test_markup_and_program_deterministic_and_no_audio_or_callbacks(self):
        value = spec()
        before = copy.deepcopy(value)
        a = hf_markup(value, palette()); program = hf_program(value)
        self.assertEqual(a, hf_markup(value, palette()))
        self.assertEqual(program, hf_program(value))
        self.assertEqual(value, before)
        self.assertIn('tl.set(', program)
        self.assertIn('"ease":"none"', program)
        self.assertIn('"immediateRender":false', program)
        for forbidden in ('onUpdate', 'call(', 'fetch(', 'audio', 'setTimeout', 'Math.random', 'Date.'):
            self.assertNotIn(forbidden, program)
        self.assertNotIn('mouthCues', a)

    def test_definition_palette_and_rig_hash_tampering_are_rejected(self):
        state = {'value': 'X', 'blink': False, 'head': {'rotate': 0, 'x': 0, 'y': 0}}
        for kind in ('script', 'url', 'attr', 'path', 'mode', 'extra'):
            d = definition()
            if kind == 'script': d['body'][0]['tag'] = 'script'
            elif kind == 'url': d['body'][0]['attrs']['fill'] = 'url(https://example.org)'
            elif kind == 'attr': d['body'][0]['attrs']['onload'] = 'alert(1)'
            elif kind == 'path': d['body'][0]['attrs']['d'] = 'M0 0"/><script/>'
            elif kind == 'mode': d['modes']['inset']['x'] = 0
            else: d['source'] = 'customer.svg'
            with self.subTest(kind=kind), self.assertRaises(WorkflowError):
                rig_svg(d, palette(), state)
        p = palette(); p['ink'] = 'red" onload="x'
        with self.assertRaises(WorkflowError): rig_svg(definition(), p, state)
        value = spec(); value['rig_sha256'] = 'd' * 64
        with self.assertRaises(WorkflowError): hf_markup(value, palette())
        with self.assertRaises(WorkflowError): hf_program(value)

    def test_state_and_times_reject_nonfinite_and_out_of_bound_data(self):
        for invalid in (math.nan, math.inf, -math.inf, True, '0'):
            with self.assertRaises(WorkflowError): sample_rig(spec(), invalid)
        for key, invalid in (('rotate', 8.1), ('x', 12.1), ('y', -12.1), ('x', math.nan)):
            state = {'value': 'X', 'blink': False, 'head': {'rotate': 0, 'x': 0, 'y': 0}}
            state['head'][key] = invalid
            with self.assertRaises(WorkflowError): rig_svg(definition(), palette(), state)
        for change in ('gap', 'overlap', 'unknown', 'blink', 'head', 'fps'):
            value = spec()
            if change == 'gap': value['mouthCues'][1]['start'] += .001
            elif change == 'overlap': value['mouthCues'][1]['start'] -= .001
            elif change == 'unknown': value['mouthCues'][0]['value'] = 'Q'
            elif change == 'blink': value['visual_tracks']['blinks'][0]['end'] = math.inf
            elif change == 'head': value['visual_tracks']['head'][1]['x'] = 13
            else: value['fps'] = 29
            with self.subTest(change=change), self.assertRaises(WorkflowError): hf_program(value)

    def test_exact_cue_boundaries_and_contract_track_limits(self):
        value = spec()
        value['mouthCues'][1]['start'] += 1e-10
        with self.assertRaises(WorkflowError): hf_program(value)
        value = spec()
        end = value['timeline_duration_seconds']
        value['visual_tracks']['head'] = [{'time': i * end / 999, 'rotate': 0, 'x': 0, 'y': 0} for i in range(1000)]
        value['visual_tracks']['head'][-1]['time'] = end
        self.assertEqual(sample_rig(value, .5)['head'], {'rotate': 0, 'x': 0, 'y': 0})
        value['visual_tracks']['head'].append({'time': end, 'rotate': 0, 'x': 0, 'y': 0})
        with self.assertRaises(WorkflowError): sample_rig(value, .5)
        value = spec()
        value['visual_tracks']['blinks'] = [{'start': i / 50, 'end': i / 50 + .005} for i in range(80)]
        sample_rig(value, .5)
        value['visual_tracks']['blinks'].append({'start': 1.7, 'end': 1.71})
        with self.assertRaises(WorkflowError): sample_rig(value, .5)

    def test_half_open_frame_cues_blinks_negative_clamp_and_audio_tail(self):
        value = spec()
        self.assertEqual(sample_rig(value, -.1), sample_rig(value, 0))
        self.assertEqual(sample_rig(value, .1)['value'], 'B')
        self.assertEqual(sample_rig(value, .099999)['value'], 'A')
        self.assertTrue(sample_rig(value, 3 / 30)['blink'])
        self.assertFalse(sample_rig(value, 5 / 30)['blink'])
        self.assertEqual(sample_rig(value, 60 / 30)['value'], 'H')
        self.assertEqual(sample_rig(value, 61 / 30)['value'], 'X')
        self.assertEqual(sample_rig(value, 100)['value'], 'X')
        self.assertEqual(sample_rig(value, 100)['head'], {'rotate': 0, 'x': 0, 'y': 0})
        # Seconds within one frame use its f/30 timestamp for every discrete state.
        self.assertEqual(sample_rig(value, .109), sample_rig(value, .1))


@unittest.skipUnless(shutil.which('node'), 'Existing Node required for pure JS equivalence')
class NeutralRigJsTests(PackFixtureCase):
    def test_shared_descriptor_geometry_is_byte_equal_between_python_and_js(self):
        states = [{'value': m, 'blink': b, 'head': {'rotate': 4, 'x': 8, 'y': -4}} for m in MOUTHS for b in (True, False)]
        data = {'definition': definition(), 'palette': palette(), 'states': states}
        result = node("""import{rigSvg}from'./renderers/rig-motion.mjs';let raw='';for await(const c of process.stdin)raw+=c;const v=JSON.parse(raw);console.log(JSON.stringify(v.states.map(s=>['inset','serial-courier'].map(m=>rigSvg(v.definition,v.palette,s,m)))));""", data)
        expected = [[rig_svg(data['definition'], data['palette'], s, mode) for mode in ('inset', 'serial-courier')] for s in states]
        self.assertEqual(result, expected)

    def test_canonicalized_descriptor_order_and_thousand_head_keys_are_supported(self):
        value = spec()
        end = value['timeline_duration_seconds']
        value['visual_tracks']['head'] = [{'time': i * end / 999, 'rotate': 0, 'x': 0, 'y': 0} for i in range(1000)]
        value['visual_tracks']['head'][-1]['time'] = end
        d = json.loads(json.dumps(definition(), sort_keys=True))
        script = """import{rigSvg,sampleRig}from'./renderers/rig-motion.mjs';let raw='';for await(const c of process.stdin)raw+=c;const v=JSON.parse(raw),state=sampleRig(v.spec,.5);console.log(JSON.stringify({svg:rigSvg(v.definition,v.palette,state),state}));"""
        result = node(script, {'spec': value, 'definition': d, 'palette': palette()})
        self.assertEqual(result['svg'], rig_svg(d, palette(), result['state']))
        self.assertEqual(result['state']['head'], {'rotate': 0, 'x': 0, 'y': 0})

    def test_sampler_matches_python_in_reverse_random_and_boundary_frame_orders(self):
        value = spec(); frames = list(range(63)); shuffled = frames.copy(); random.Random(47).shuffle(shuffled)
        times = [f / 30 for f in frames + list(reversed(frames)) + shuffled] + [-10, 100, .109]
        result = node("""import{sampleRig}from'./renderers/rig-motion.mjs';let raw='';for await(const c of process.stdin)raw+=c;const v=JSON.parse(raw);console.log(JSON.stringify(v.times.map(t=>sampleRig(v.spec,t))));""", {'spec': value, 'times': times})
        for state, time in zip(result, times):
            expected = sample_rig(value, time)
            self.assertEqual({k: state[k] for k in ('frame', 'value', 'blink')}, {k: expected[k] for k in ('frame', 'value', 'blink')})
            for key in ('rotate', 'x', 'y'): self.assertAlmostEqual(state['head'][key], expected['head'][key], places=10)

    def test_js_direct_calls_fail_closed_for_nonfinite_spec_state_and_executable_shapes(self):
        script = """import assert from'node:assert/strict';import{sampleRig,rigSvg}from'./renderers/rig-motion.mjs';let raw='';for await(const c of process.stdin)raw+=c;const v=JSON.parse(raw),fresh=()=>JSON.parse(JSON.stringify(v));let count=0;
        for(const t of [NaN,Infinity,-Infinity,true,'0']){assert.throws(()=>sampleRig(v.spec,t));count++;}
        for(const change of ['path','tag','url','mode']){const q=fresh();if(change==='path')q.definition.body[0].attrs.d='M0 0<script>';else if(change==='tag')q.definition.body[0].tag='image';else if(change==='url')q.definition.body[0].attrs.fill='https://example.org';else q.definition.modes.inset.scale=3;assert.throws(()=>rigSvg(q.definition,q.palette,{value:'X',blink:false,head:{rotate:0,x:0,y:0}}));count++;}
        const q=fresh();q.spec.visual_tracks.head[1].rotate=Infinity;assert.throws(()=>sampleRig(q.spec,0));count++;console.log(JSON.stringify({rejections:count}));"""
        self.assertEqual(node(script, {'spec': spec(), 'definition': definition(), 'palette': palette()}), {'rejections': 10})

    def test_hf_explicit_sets_and_linear_gsap_match_shared_sampler_at_independent_native_frames(self):
        value = spec(); frames = list(range(63)); shuffled = frames.copy(); random.Random(414).shuffle(shuffled)
        times = [f / 30 for f in frames + list(reversed(frames)) + shuffled + [0, 61, 0, 3, 5, 0]]
        script = """import assert from'node:assert/strict';import{createRequire}from'node:module';import{sampleRig}from'./renderers/rig-motion.mjs';const gsap=createRequire(import.meta.url)('./vendor/gsap.min.js').gsap;let raw='';for await(const c of process.stdin)raw+=c;const v=JSON.parse(raw),targets={};
        for(const m of 'ABCDEFGHX')targets['#neutral-rig-mouth-'+m]={opacity:m==='X'?1:0};targets['#neutral-rig-eyes-open']={opacity:1};targets['#neutral-rig-eyes-closed']={opacity:0};targets['#neutral-rig-head']={x:0,y:0,rotation:0};
        const core=gsap.timeline({paused:true});const vars=q=>{const r={...q};delete r.svgOrigin;return r;};const tl={set:(s,a,t)=>core.set(s.split(',').map(id=>targets[id]),vars(a),t),fromTo:(s,a,b,t)=>core.fromTo(targets[s],vars(a),vars(b),t)};
        const direct={set:(s,a)=>gsap.set(s.split(',').map(id=>targets[id]),vars(a))};Function('tl','gsap',v.program)(tl,direct);let count=0;for(const time of v.times){core.totalTime(time,true);const expected=sampleRig(v.spec,time),active='ABCDEFGHX'.split('').filter(m=>targets['#neutral-rig-mouth-'+m].opacity>.5);assert.deepEqual(active,[expected.value],`mouth@${time}/sample${count}`);assert.equal(targets['#neutral-rig-eyes-closed'].opacity>.5,expected.blink,`blink@${time}`);assert.equal(targets['#neutral-rig-eyes-open'].opacity>.5,!expected.blink,`open@${time}`);for(const[k,prop]of[['rotate','rotation'],['x','x'],['y','y']])assert.ok(Math.abs(targets['#neutral-rig-head'][prop]-expected.head[k])<.0001,`head/${k}@${time}: ${targets['#neutral-rig-head'][prop]} vs ${expected.head[k]}`);count++;}
        core.kill();gsap.ticker.sleep();console.log(JSON.stringify({samples:count,scope:'object-property timeline equivalence;notDOM/nativebrowser/phoneticacceptance'}));"""
        result = node(script, {'spec': value, 'program': hf_program(value), 'times': times})
        self.assertEqual(result['samples'], len(times))


if __name__ == '__main__':
    unittest.main()
