from pack_fixture_case import PackFixtureCase
from storymotion.account_packs import render_profile
import copy
import json
import math
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from storymotion.edit_plan import validate_operations
from storymotion.raster_view import compile_view, validate_raster
from storymotion.security import WorkflowError


ROOT = Path(__file__).resolve().parents[1]
_MISSING = object()


def fixture():
    brief = json.loads((ROOT / 'tests/fixtures/examples/golden/sample-mechanism.json').read_text())
    profile = render_profile('sample-mechanism')
    asset = {'file': 'raster/image.png', 'sha256': 'a' * 64,
             'source_sha256': 'b' * 64, 'width': 1200, 'height': 900,
             'container': 'png', 'approved_by': 'Yerel test operatörü',
             'rights_note': 'Özgün geometrik test görseli.', 'rights_confirmed': True}
    value = {'schema_version': 1, 'recipe': 'customer-raster-annotation-1', 'asset': asset,
             'views': [{'scene_id': s['id'], 'crop': {'x': .1, 'y': .1, 'width': .8, 'height': .8},
                        'highlight': {'x': .3, 'y': .2, 'width': .2, 'height': .3},
                        'label': 'Ayrıntıya bakın', 'camera': s['camera']} for s in brief['scenes']]}
    return brief, profile, value


class RasterViewContractTests(PackFixtureCase):
    def setUp(self):
        self.brief, self.profile, self.value = fixture()

    def reject(self, value=_MISSING, brief=_MISSING):
        with self.assertRaises(WorkflowError):
            validate_raster(self.value if value is _MISSING else value,
                            self.brief if brief is _MISSING else brief)

    def test_exact_contract_is_detached_copy(self):
        original = copy.deepcopy(self.value)
        result = validate_raster(self.value, self.brief)
        self.assertEqual(result, original)
        result['asset']['width'] = 64
        result['views'][0]['crop']['x'] = 0
        self.assertEqual(self.value, original)

    def test_only_owned_profile_with_creative_brief(self):
        for brand in ('sample-flow', 'sample-series', 'biraz-iceri', None):
            with self.subTest(brand=brand):
                self.reject(brief={**self.brief, 'brand': brand})
        for creative in (None, {}, True, 'yes', []):
            with self.subTest(creative=creative):
                self.reject(brief={**self.brief, 'creative': creative})

    def test_extra_fields_in_any_layer_rejected(self):
        paths = [(), ('asset',), ('views', 0), ('views', 0, 'crop'), ('views', 0, 'highlight')]
        for path in paths:
            value = copy.deepcopy(self.value)
            node = value
            for part in path:
                node = node[part]
            node['rig'] = '<svg onload="alert(1)"/>'
            with self.subTest(path=path):
                self.reject(value)

    def test_missing_fields_and_wrong_types_rejected(self):
        for name in self.value:
            value = copy.deepcopy(self.value)
            del value[name]
            self.reject(value)
        for bad in (None, [], 'raster', 1, True):
            self.reject(bad)
        for field in self.value['asset']:
            value = copy.deepcopy(self.value)
            del value['asset'][field]
            self.reject(value)
        for field in self.value['views'][0]:
            value = copy.deepcopy(self.value)
            del value['views'][0][field]
            self.reject(value)

    def test_versions_and_asset_filename_are_fixed(self):
        for version in (True, '1', 2, 1.0):
            self.reject({**self.value, 'schema_version': version})
        self.reject({**self.value, 'recipe': 'customer-html'})
        for filename in ('../image.png', '/tmp/image.png', 'https://example.com/a.png', 'raster/image.svg'):
            value = copy.deepcopy(self.value)
            value['asset']['file'] = filename
            self.reject(value)
        for container in ('jpeg', 'svg', 'PNG'):
            value = copy.deepcopy(self.value)
            value['asset']['container'] = container
            self.reject(value)

    def test_hashes_dimensions_and_rights_are_strict(self):
        for field in ('sha256', 'source_sha256'):
            for bad in ('a' * 63, 'A' * 64, 'g' * 64, None, 1):
                value = copy.deepcopy(self.value)
                value['asset'][field] = bad
                self.reject(value)
        for field in ('width', 'height'):
            for bad in (True, 64.0, 63, 4097, None, float('inf')):
                value = copy.deepcopy(self.value)
                value['asset'][field] = bad
                self.reject(value)
        value = copy.deepcopy(self.value)
        value['asset'].update(width=4096, height=4096)
        self.reject(value)
        for field, bad in (('approved_by', ''), ('approved_by', ' '), ('approved_by', 'x' * 201),
                           ('rights_note', ''), ('rights_note', 'x' * 1001),
                           ('rights_confirmed', False), ('rights_confirmed', 1)):
            value = copy.deepcopy(self.value)
            value['asset'][field] = bad
            self.reject(value)

    def test_every_source_scene_once_in_original_order(self):
        for views in (self.value['views'][:-1], self.value['views'] + [self.value['views'][0]],
                      list(reversed(self.value['views'])), None):
            self.reject({**self.value, 'views': views})
        value = copy.deepcopy(self.value)
        value['views'][1]['scene_id'] = value['views'][0]['scene_id']
        self.reject(value)
        brief = copy.deepcopy(self.brief)
        brief['scenes'][1]['id'] = brief['scenes'][0]['id']
        self.reject(brief=brief)
        for bad in ('../scene', '<g>', '', 1, None):
            brief = copy.deepcopy(self.brief)
            brief['scenes'][0]['id'] = bad
            value = copy.deepcopy(self.value)
            value['views'][0]['scene_id'] = bad
            self.reject(value, brief)

    def test_rectangles_finite_normalized_and_not_boolean(self):
        for rect in ('crop', 'highlight'):
            for key in ('x', 'y', 'width', 'height'):
                for bad in (True, False, None, '0.2', math.nan, math.inf, -math.inf, -.01, 1.01):
                    value = copy.deepcopy(self.value)
                    value['views'][0][rect][key] = bad
                    with self.subTest(rect=rect, key=key, bad=bad):
                        self.reject(value)
        for rect, minimum in (('crop', .05), ('highlight', .01)):
            for key in ('width', 'height'):
                value = copy.deepcopy(self.value)
                value['views'][0][rect][key] = minimum - .000001
                self.reject(value)
        for rect in ('crop', 'highlight'):
            value = copy.deepcopy(self.value)
            value['views'][0][rect].update(x=.9, width=.2)
            self.reject(value)

    def test_highlight_wholly_inside_crop_or_absent(self):
        for rect in ({'x': .09, 'y': .2, 'width': .2, 'height': .3},
                     {'x': .3, 'y': .09, 'width': .2, 'height': .3},
                     {'x': .8, 'y': .2, 'width': .2, 'height': .3},
                     {'x': .3, 'y': .8, 'width': .2, 'height': .2}):
            value = copy.deepcopy(self.value)
            value['views'][0]['highlight'] = rect
            self.reject(value)
        value = copy.deepcopy(self.value)
        value['views'][0]['highlight'] = None
        self.assertEqual(validate_raster(value, self.brief), value)

    def test_labels_are_short_plain_text(self):
        for bad in ('<script>alert(1)</script>', '<image href="x"/>', 'https://example.com',
                    'www.example.com', 'example.com/a', 'javascript:alert(1)',
                    '`code`', '()=>{}', 'window.fetch(x)', 'abc\nxyz', 'abc\x00',
                    'abc\u202exyz', 'x' * 51, None, True):
            value = copy.deepcopy(self.value)
            value['views'][0]['label'] = bad
            with self.subTest(label=bad):
                self.reject(value)
        for good in ('', 'İı Şş Ğğ Çç Öö Üü', 'Önce & sonra', '“Neden?” diye sor', 'x' * 50):
            value = copy.deepcopy(self.value)
            value['views'][0]['label'] = good
            self.assertEqual(validate_raster(value, self.brief), value)

    def test_camera_matches_source_and_scene_duration(self):
        value = copy.deepcopy(self.value)
        value['views'][0]['camera'] = 'locked'
        self.reject(value)
        for camera in ('orbit', True, [], None):
            value = copy.deepcopy(self.value)
            value['views'][0]['camera'] = camera
            self.reject(value)
        for end in (1.5, True, math.nan, math.inf, '4'):
            brief = copy.deepcopy(self.brief)
            brief['scenes'][0]['end'] = end
            self.reject(brief=brief)


class RasterCompilerTests(PackFixtureCase):
    def setUp(self):
        self.brief, self.profile, self.value = fixture()
        self.scene, self.view = self.brief['scenes'][0], self.value['views'][0]
        self.asset = self.value['asset']

    def compile(self, scene=None, view=None, asset=None, profile=None, ident='s0'):
        return compile_view(self.scene if scene is None else scene,
                            self.view if view is None else view,
                            self.asset if asset is None else asset,
                            self.profile if profile is None else profile, ident)

    def test_real_source_pixels_crop_and_fixed_local_image(self):
        vector, ops = self.compile()
        root = ET.fromstring(vector)
        ns = {'s': 'http://www.w3.org/2000/svg'}
        image = root.find('.//s:image', ns)
        self.assertEqual(image.attrib, {'href': 'assets/customer-image.png', 'x': '0', 'y': '0', 'width': '1200', 'height': '900'})
        crop = root.find('.//s:svg', ns)
        self.assertEqual(crop.attrib['viewBox'], '120 90 960 720')
        self.assertEqual([crop.attrib[k] for k in ('x', 'y', 'width', 'height')], ['90', '70', '900', '720'])
        self.assertEqual(crop.attrib['preserveAspectRatio'], 'xMidYMid meet')
        highlight = root.find('.//s:g[@id="s0-highlight"]/s:rect', ns)
        self.assertEqual([highlight.attrib[k] for k in ('x', 'y', 'width', 'height')], ['360', '180', '240', '270'])
        self.assertNotIn('hinge', vector)
        self.assertNotIn('latch', vector)
        self.assertNotIn('<path', vector)
        self.assertNotIn('<script', vector)
        self.assertNotIn('http://', vector.replace('http://www.w3.org/2000/svg', ''))
        validate_operations(ops, 4)

    def test_fixed_outer_clip_camera_and_annotation_targets_are_separate(self):
        root = ET.fromstring(self.compile()[0])
        ns = {'s': 'http://www.w3.org/2000/svg'}
        clip = root.find('.//s:clipPath/s:rect', ns)
        self.assertEqual(clip.attrib, {'x': '90', 'y': '70', 'width': '900', 'height': '720'})
        camera = root.find('.//s:g[@id="s0-camera"]', ns)
        self.assertIsNotNone(camera.find('.//s:g[@id="s0-highlight"]', ns))
        self.assertIsNotNone(root.find('.//s:g[@clip-path="url(#s0-viewport)"]/s:g[@id="s0-camera"]', ns))
        self.assertNotIn('transform', camera.attrib)

    def test_plain_label_is_xml_escaped_and_within_label_area(self):
        view = {**self.view, 'label': 'Önce & "sonra"'}
        vector, _ = self.compile(view=view)
        self.assertIn('Önce &amp; &quot;sonra&quot;', vector)
        root = ET.fromstring(vector)
        text = root.find('{http://www.w3.org/2000/svg}text')
        self.assertEqual(text.attrib['y'], '850')
        self.assertEqual(text.text, view['label'])
        self.assertLessEqual(float(text.attrib['textLength']), 900)
        self.assertEqual(text.attrib['lengthAdjust'], 'spacingAndGlyphs')

    def test_all_camera_modes_are_bounded_and_use_existing_seek_safe_vocabulary(self):
        for camera in ('locked', 'push-in', 'follow-object'):
            scene = {**self.scene, 'camera': camera, 'end': 1.6}
            view = {**self.view, 'camera': camera}
            vector, ops = self.compile(scene=scene, view=view)
            validate_operations(ops, 1.6)
            self.assertTrue(all(op['target'] in {'camera', 'highlight'} for op in ops))
            for op in ops:
                self.assertIn('id="s0-' + op['target'] + '"', vector)
            tweens = [op for op in ops if op['target'] == 'camera' and op['op'] == 'tween']
            self.assertEqual(len(tweens), int(camera != 'locked'))
            if tweens:
                op = tweens[0]
                self.assertEqual(op['ease'], 'cubic-in-out')
                self.assertLessEqual(op['offset'] + op['duration'], 1.6)
                self.assertEqual(op['after']['scale'], 1.08)
                self.assertLessEqual(abs(op['after']['x']), 36)
                self.assertLessEqual(abs(op['after']['y']), 28.8)
        follow = self.compile(scene={**self.scene, 'camera': 'follow-object'},
                              view={**self.view, 'camera': 'follow-object'})[1][-1]
        self.assertNotEqual(follow['after']['x'], 0)
        self.assertNotEqual(follow['after']['y'], 0)

    def test_no_highlight_keeps_owned_target_without_invented_geometry(self):
        vector, ops = self.compile(view={**self.view, 'highlight': None})
        self.assertIn('<g id="s0-highlight"></g>', vector)
        self.assertFalse(any(op['target'] == 'highlight' and op['op'] == 'tween' for op in ops))
        validate_operations(ops, 4)

    def test_compiler_is_deterministic_and_does_not_mutate_inputs(self):
        inputs = copy.deepcopy((self.scene, self.view, self.asset, self.profile))
        first = self.compile()
        self.assertEqual(first, self.compile())
        self.assertEqual(inputs, (self.scene, self.view, self.asset, self.profile))
        first[1][0]['values']['x'] = 999
        self.assertEqual(self.compile()[1][0]['values']['x'], 0)

    def test_direct_compiler_calls_validate_untrusted_pieces(self):
        cases = [{'profile': {**self.profile, 'id': 'sample-series'}},
                 {'profile': {**self.profile, 'palette': {**self.profile['palette'], 'ink': 'red" onload="x'}}},
                 {'ident': 's0" onload="x'}, {'ident': 's0/path'},
                 {'view': {**self.view, 'label': '<svg/>'}},
                 {'asset': {**self.asset, 'file': 'https://bad.example/a.png'}},
                 {'scene': {**self.scene, 'end': 1}}]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(WorkflowError):
                    self.compile(**kwargs)


if __name__ == '__main__':
    unittest.main()
