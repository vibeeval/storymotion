from pack_fixture_case import PackFixtureCase
from storymotion.account_packs import render_profile
"""Pure manual scene contract/compiler tests; no renderer, key or provider."""
import copy
import json
import math
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from storymotion.edit_plan import validate_operations
from storymotion.scene_plan import compile_scene, validate_scene_plan
from storymotion.security import WorkflowError, digest
from storymotion.writing_context import audit_bound_claims, snapshot

ROOT = Path(__file__).resolve().parents[1]
SOURCE = {'original-note': {'url': 'https://example.org/original-synthetic-note',
    'title': 'Özgün sentetik test notu', 'locator': 'Test maddesi',
    'excerpt': 'Bu özgün örnek yalnız sözleşme denetimi içindir.',
    'rights_note': 'Own synthetic test text, not external reference material'}}
CONTENT = {'possibility-branches': {'left': 'Yoğun olabilir.', 'right': 'İletişim ritmi farklı olabilir.', 'question': 'Hangi ipucu ayırt eder?'},
           'observation': {'object': 'phone', 'prompt': 'İlk aklımdan geçen ne?', 'observation': 'Bağlamı küçük bir gözlemle ayırt ederim.'},
           'process-route': {'nodes': ['Girdi', 'Onay', 'Sonuç'], 'from_node': 0, 'to_node': 2},
           'object-transform': {'object': 'document', 'before': 'İstek geldi.', 'after': 'Sonuç hazır.'},
           'clue-inspect': {'clue_id': 'nick-01', 'note': 'Aynı nesnenin kaydına döndüm.'},
           'canon-board': {'clue_ids': ['nick-01'], 'note': 'Açık ipucunu aynı nesneye bağladım.'}}
DEFAULTS = {'sample-reflection': 'possibility-branches', 'sample-flow': 'process-route', 'sample-series': 'clue-inspect'}


def fixture(account='sample-flow', kind=None):
    brief = json.loads((ROOT / 'tests/fixtures/examples/golden' / (account + '.json')).read_text())
    profile = render_profile(account)
    binding = {'schema_version': 1, 'account': account, 'sources': None, 'canon': None}
    if account != 'sample-series':
        binding['sources'] = snapshot('sources', account, copy.deepcopy(SOURCE), None)
        brief['claims'] = [{'text': 'Bu özgün sentetik örnek yalnız sözleşme denetimidir.',
                            'source': 'original-note', 'scope': 'No source-truth acceptance; synthetic fixture only'}]
    else:
        data = {'series_id': 'synthetic-series', 'episode_id': 'synthetic-final', 'bible_version': 'test-bible',
                'origin': 'synthetic_reference_test', 'final_sha256': digest('synthetic reference, not real media'),
                'accepted_by': 'Synthetic fixture operator', 'narrator': 'first_person',
                'cast': [{k: row[k] for k in ('id', 'wardrobe')} for row in brief['creative']['characters']],
                'objects': [{'id': brief['continuity']['object_id'], 'state': brief['continuity']['previous'], 'identity_note': 'Same original synthetic reference object'}],
                'open_clues': [{'id': 'nick-01', 'object_id': brief['continuity']['object_id'], 'description': 'Zarfın aynı köşesindeki iz.'}],
                'source_revision': None}
        binding['canon'] = snapshot('canon', account, data, None)
    binding['binding_sha256'] = digest(binding)
    brief['production_context'] = binding
    kind = kind or DEFAULTS[account]
    value = {'schema_version': 1, 'recipe': 'manual-account-scenes-1', 'account': account,
             'canon_revision': binding['canon']['revision'] if binding['canon'] else None,
             'scenes': [{'scene_id': scene['id'], 'kind': kind, 'content': copy.deepcopy(CONTENT[kind]),
                         'claim_indexes': [0] if brief['claims'] else [],
                         'cue_indexes': [i for i, cue in enumerate(brief['cues']) if cue['start'] < scene['end'] and cue['end'] > scene['start']],
                         'object_id': scene['object_id'], 'camera': scene['camera']} for scene in brief['scenes']]}
    return brief, profile, value


def rebind_canon(brief, plan, change):
    binding = brief['production_context']
    data = binding['canon']['data']
    change(data)
    binding['canon'] = snapshot('canon', brief['brand'], data, None)
    binding['binding_sha256'] = digest({k: v for k, v in binding.items() if k != 'binding_sha256'})
    plan['canon_revision'] = binding['canon']['revision']


class ManualSceneContractTests(PackFixtureCase):
    def test_three_accounts_validate_without_mutation_and_return_detached_copy(self):
        for account in DEFAULTS:
            brief, _, plan = fixture(account)
            before = copy.deepcopy((brief, plan))
            value = validate_scene_plan(plan, brief)
            self.assertEqual(value, plan)
            value['scenes'][0]['content']['note' if account == 'sample-series' else 'left' if account == 'sample-reflection' else 'nodes'] = 'Changed'
            self.assertEqual((brief, plan), before)
            self.assertEqual(audit_bound_claims(brief)['status'], 'incomplete')
            self.assertNotIn('publication_ready', plan)

    def test_only_three_profiles_and_no_raster_combination(self):
        brief, _, plan = fixture()
        for account in ('sample-mechanism', 'other', None, [], {}):
            with self.subTest(account=account), self.assertRaises(WorkflowError):
                validate_scene_plan({**plan, 'account': account}, {**brief, 'brand': account})
        for raster in ({}, {'asset': 'x'}, False):
            with self.assertRaises(WorkflowError):
                validate_scene_plan(plan, {**brief, 'raster': raster})
        for creative in (None, {}, True, 'creative'):
            with self.assertRaises(WorkflowError):
                validate_scene_plan(plan, {**brief, 'creative': creative})

    def test_exact_fields_versions_and_per_account_kinds(self):
        brief, _, plan = fixture()
        for path in ((), ('scenes', 0), ('scenes', 0, 'content')):
            value = copy.deepcopy(plan)
            node = value
            for key in path:
                node = node[key]
            node['html'] = '<svg/>'
            with self.assertRaises(WorkflowError):
                validate_scene_plan(value, brief)
        for key in plan:
            value = copy.deepcopy(plan)
            del value[key]
            with self.assertRaises(WorkflowError):
                validate_scene_plan(value, brief)
        for version in (True, 1.0, '1', 2):
            with self.assertRaises(WorkflowError):
                validate_scene_plan({**plan, 'schema_version': version}, brief)
        with self.assertRaises(WorkflowError):
            validate_scene_plan({**plan, 'recipe': 'other'}, brief)
        for kind in ('observation', 'canon-board', 'html', None, []):
            value = copy.deepcopy(plan)
            value['scenes'][0]['kind'] = kind
            with self.assertRaises(WorkflowError):
                validate_scene_plan(value, brief)

    def test_source_order_object_camera_and_unique_ids_are_pinned(self):
        brief, _, plan = fixture()
        for change in ({'scene_id': 'other'}, {'object_id': 'other'}, {'camera': 'push-in'}):
            value = copy.deepcopy(plan)
            value['scenes'][0].update(change)
            with self.assertRaises(WorkflowError):
                validate_scene_plan(value, brief)
        for scenes in (plan['scenes'][:-1], plan['scenes'] + [plan['scenes'][0]], list(reversed(plan['scenes']))):
            with self.assertRaises(WorkflowError):
                validate_scene_plan({**plan, 'scenes': scenes}, brief)
        source = copy.deepcopy(brief)
        source['scenes'][1]['id'] = source['scenes'][0]['id']
        with self.assertRaises(WorkflowError):
            validate_scene_plan(plan, source)

    def test_cue_references_exactly_follow_overlapping_source_intervals(self):
        brief, _, plan = fixture()
        brief['cues'][0]['end'] = 4.1
        plan['scenes'][1]['cue_indexes'] = [0, 1]
        self.assertEqual(validate_scene_plan(plan, brief), plan)
        for indexes in ([], [0], [1, 0], [0, 1, 1], [True], [math.nan], [-1], [999]):
            value = copy.deepcopy(plan)
            value['scenes'][1]['cue_indexes'] = indexes
            with self.subTest(indexes=indexes), self.assertRaises(WorkflowError):
                validate_scene_plan(value, brief)

    def test_claim_indexes_required_unique_in_range_and_bound_to_caller_sources(self):
        for account in ('sample-reflection', 'sample-flow'):
            brief, _, plan = fixture(account)
            for indexes in ([], [True], [0, 0], [-1], [1], ['0'], [None], [math.inf]):
                value = copy.deepcopy(plan)
                value['scenes'][0]['claim_indexes'] = indexes
                with self.subTest(account=account, indexes=indexes), self.assertRaises(WorkflowError):
                    validate_scene_plan(value, brief)
            for change in ('no-context', 'no-claim', 'invented-source', 'tampered-snapshot'):
                value = copy.deepcopy(brief)
                if change == 'no-context':
                    value.pop('production_context')
                elif change == 'no-claim':
                    value['claims'] = []
                elif change == 'invented-source':
                    value['claims'][0]['source'] = 'invented'
                else:
                    value['production_context']['sources']['data']['original-note']['excerpt'] = 'Tampered reference'
                with self.subTest(change=change), self.assertRaises(WorkflowError):
                    validate_scene_plan(plan, value)

    def test_new_public_content_uses_selected_claim_numeric_guard(self):
        brief, _, plan = fixture('sample-flow', 'object-transform')
        plan['scenes'][0]['content']['after'] = 'Yüzde50 yerine50sonuç'
        with self.assertRaisesRegex(WorkflowError, 'Unsourced number'):
            validate_scene_plan(plan, brief)
        brief['claims'][0]['text'] = 'Sentetik örnekte50sonuç.'
        self.assertEqual(validate_scene_plan(plan, brief), plan)
        brief['claims'].append({'text': 'Başka iddiada99.', 'source': 'original-note', 'scope': 'Synthetic only'})
        plan['scenes'][0]['content']['after'] = '99sonuç'
        with self.assertRaisesRegex(WorkflowError, 'Unsourced number'):
            validate_scene_plan(plan, brief)

    def test_new_psychology_content_keeps_conservative_wording_boundary(self):
        brief, _, plan = fixture('sample-reflection')
        for text in ('Kesin nedeni budur.', 'Tanısı kondu.', 'Bozukluğun var.', 'Tedavi eder.', 'Her zaman böyledir.'):
            value = copy.deepcopy(plan)
            value['scenes'][0]['content']['left'] = text
            with self.subTest(text=text), self.assertRaisesRegex(WorkflowError, 'certainty/diagnosis'):
                validate_scene_plan(value, brief)

    def test_plain_copy_no_markup_urls_code_controls_or_oversize(self):
        for account, kind, field, maximum in [('sample-reflection', 'possibility-branches', 'left', 38),
                                              ('sample-reflection', 'observation', 'prompt', 55),
                                              ('sample-flow', 'object-transform', 'before', 28),
                                              ('sample-series', 'clue-inspect', 'note', 55)]:
            brief, _, plan = fixture(account, kind)
            for bad in ('<g/>', 'https://example.org', 'www.example.org', 'javascript:alert(1)',
                        '`code`', 'window.fetch(x)', 'abc\nxyz', '\x00', 'abc\u202e', 'x' * (maximum + 1), '', None):
                value = copy.deepcopy(plan)
                value['scenes'][0]['content'][field] = bad
                with self.subTest(account=account, bad=bad), self.assertRaises(WorkflowError):
                    validate_scene_plan(value, brief)
            value = copy.deepcopy(plan)
            value['scenes'][0]['content'][field] = 'İıŞşĞğÇçÖöÜü & “soru”'
            self.assertEqual(validate_scene_plan(value, brief), value)

    def test_object_enums_and_process_bounds(self):
        for account, kind in [('sample-reflection', 'observation'), ('sample-flow', 'object-transform')]:
            brief, _, plan = fixture(account, kind)
            for obj in ('private-rig', 'svg', None, []):
                value = copy.deepcopy(plan)
                value['scenes'][0]['content']['object'] = obj
                with self.assertRaises(WorkflowError):
                    validate_scene_plan(value, brief)
        brief, _, plan = fixture()
        for change in ({'nodes': ['One']}, {'nodes': ['a'] * 5}, {'nodes': ['a' * 21, 'b']},
                       {'nodes': ['<svg/>', 'b']}, {'from_node': True}, {'from_node': -1},
                       {'to_node': 3}, {'to_node': 0}, {'to_node': 1.0}):
            value = copy.deepcopy(plan)
            value['scenes'][0]['content'].update(change)
            with self.subTest(change=change), self.assertRaises(WorkflowError):
                validate_scene_plan(value, brief)

    def test_serial_requires_valid_exact_reference_and_stays_draft(self):
        brief, _, plan = fixture('sample-series')
        for change in ('missing', 'hash', 'revision', 'promote', 'cast', 'wardrobe', 'object'):
            b, p = copy.deepcopy(brief), copy.deepcopy(plan)
            if change == 'missing':
                b.pop('production_context')
            elif change == 'hash':
                b['production_context']['canon']['data']['accepted_by'] = 'Different'
            elif change == 'revision':
                p['canon_revision'] = 'a' * 64
            elif change == 'promote':
                b['creative']['canon_status'] = 'accepted'
            elif change == 'cast':
                b['scenes'][0]['character_id'] = 'not-accepted'
            elif change == 'wardrobe':
                b['creative']['characters'][0]['wardrobe'] = 'different-shirt'
            else:
                b['scenes'][0]['object_id'] = p['scenes'][0]['object_id'] = 'not-accepted'
            with self.subTest(change=change), self.assertRaises(WorkflowError):
                validate_scene_plan(p, b)
        self.assertEqual(brief['creative']['canon_status'], 'noncanonical_fixture')

    def test_clues_existing_unique_same_accepted_object_and_reference_labels_safe(self):
        for kind in ('clue-inspect', 'canon-board'):
            brief, _, plan = fixture('sample-series', kind)
            for bad in ('other-clue', '../clue', '<script>', None):
                value = copy.deepcopy(plan)
                value['scenes'][0]['content'].update({'clue_id': bad} if kind == 'clue-inspect' else {'clue_ids': [bad]})
                with self.assertRaises(WorkflowError):
                    validate_scene_plan(value, brief)
            b, p = copy.deepcopy(brief), copy.deepcopy(plan)
            def other(data):
                data['objects'].append({'id': 'other-object', 'state': 'closed', 'identity_note': 'Another approved object'})
                data['open_clues'][0]['object_id'] = 'other-object'
            rebind_canon(b, p, other)
            with self.assertRaisesRegex(WorkflowError, 'exact accepted object'):
                validate_scene_plan(p, b)
            b, p = copy.deepcopy(brief), copy.deepcopy(plan)
            rebind_canon(b, p, lambda data: data['open_clues'][0].update(description='<svg onload="x"/>'))
            with self.assertRaises(WorkflowError):
                validate_scene_plan(p, b)
        brief, _, plan = fixture('sample-series', 'canon-board')
        for ids in ([], ['nick-01', 'nick-01'], ['nick-01'] * 4, 'nick-01'):
            value = copy.deepcopy(plan)
            value['scenes'][0]['content']['clue_ids'] = ids
            with self.assertRaises(WorkflowError):
                validate_scene_plan(value, brief)

    def test_scene_and_cue_timings_are_finite_and_at_least_minimum(self):
        brief, _, plan = fixture()
        for field, bad in (('end', 1.5), ('start', True), ('end', math.nan), ('end', math.inf), ('camera', [])):
            value = copy.deepcopy(brief)
            value['scenes'][0][field] = bad
            with self.assertRaises(WorkflowError):
                validate_scene_plan(plan, value)
        for bad in (math.nan, True, -1, 0):
            value = copy.deepcopy(brief)
            value['cues'][0]['end'] = bad
            with self.assertRaises(WorkflowError):
                validate_scene_plan(plan, value)


class ManualSceneCompilerTests(PackFixtureCase):
    def compile(self, account, kind, camera=None):
        brief, profile, plan = fixture(account, kind)
        if camera:
            brief['scenes'][0]['camera'] = plan['scenes'][0]['camera'] = camera
        return (*compile_scene(brief['scenes'][0], plan['scenes'][0], profile, 's0', brief), brief, plan)

    def test_six_materially_distinct_owned_scenes_match_two_engine_motion_vocabulary(self):
        vectors = set()
        kinds = [('sample-reflection', 'possibility-branches'), ('sample-reflection', 'observation'),
                 ('sample-flow', 'process-route'), ('sample-flow', 'object-transform'),
                 ('sample-series', 'clue-inspect'), ('sample-series', 'canon-board')]
        for account, kind in kinds:
            vector, ops, brief, _ = self.compile(account, kind)
            vectors.add(vector)
            root = ET.fromstring(vector)
            ids = {e.attrib['id']: e.tag.rsplit('}', 1)[-1] for e in root.iter() if 'id' in e.attrib}
            validate_operations(ops, brief['scenes'][0]['end'] - brief['scenes'][0]['start'])
            self.assertEqual(ids['s0-camera'], 'g')
            for op in ops:
                self.assertIn(ids['s0-' + op['target']], {'g', 'circle', 'path'})
            self.assertNotIn('<image', vector)
            self.assertNotIn('<script', vector)
            self.assertNotIn('<foreignObject', vector)
            self.assertNotIn('-latch', vector)
            self.assertNotIn('private', vector)
        self.assertEqual(len(vectors), 6)

    def test_process_route_token_moves_between_declared_nodes_not_camera(self):
        vector, ops, _, _ = self.compile('sample-flow', 'process-route')
        move = next(op for op in ops if op['target'] == 'token' and op['op'] == 'tween')
        self.assertEqual(move['before']['x'], 170)
        self.assertEqual(move['after']['x'], 910)
        self.assertIn('Şematik süreç', vector)
        self.assertIn('gerçek ürün arayüzü değil', vector)
        self.assertFalse(any(op['target'] == 'camera' and op['op'] == 'tween' for op in ops))

    def test_observation_enums_and_transform_objects_have_distinct_geometry(self):
        for account, kind, objects in [('sample-reflection', 'observation', ('phone', 'clock', 'chair')),
                                       ('sample-flow', 'object-transform', ('document', 'device', 'container'))]:
            brief, profile, plan = fixture(account, kind)
            result = set()
            for obj in objects:
                plan['scenes'][0]['content']['object'] = obj
                result.add(compile_scene(brief['scenes'][0], plan['scenes'][0], profile, 's0', brief)[0])
            self.assertEqual(len(result), 3)

    def test_camera_wrapper_and_fixed_clip_are_separate_from_object_operations(self):
        for camera in ('locked', 'push-in', 'follow-object'):
            vector, ops, brief, _ = self.compile('sample-reflection', 'observation', camera)
            ET.fromstring(vector)
            self.assertIn('<g clip-path="url(#s0-frame)"><g id="s0-camera">', vector)
            camera_ops = [op for op in ops if op['target'] == 'camera']
            self.assertEqual(len(camera_ops), 1 if camera == 'locked' else 2)
            self.assertTrue(any(op['target'] == 'object' for op in ops))
            validate_operations(ops, brief['scenes'][0]['end'])

    def test_clue_description_and_fixture_status_come_from_accepted_reference_only(self):
        for kind in ('clue-inspect', 'canon-board'):
            vector, _, brief, plan = self.compile('sample-series', kind)
            self.assertIn('Zarfın aynı köşesindeki iz.', vector)
            self.assertIn('Sentetik referans provası', vector)
            self.assertIn('yeni kanon değil', vector)
            self.assertNotIn('Deniz', vector)
            profile = render_profile('sample-series')
            rebind_canon(brief, plan, lambda data: data.update(origin='customer_attested_final'))
            vector, _ = compile_scene(brief['scenes'][0], plan['scenes'][0], profile, 's0', brief)
            self.assertIn('Kabul referansına bağlı taslak', vector)
            self.assertNotIn('Sentetik referans provası', vector)

    def test_compiler_is_deterministic_and_plain_copy_always_xml_escaped(self):
        brief, profile, plan = fixture('sample-reflection', 'observation')
        plan['scenes'][0]['content']['prompt'] = 'Önce & “sonra”'
        inputs = copy.deepcopy((brief, profile, plan))
        a = compile_scene(brief['scenes'][0], plan['scenes'][0], profile, 's0', brief)
        b = compile_scene(brief['scenes'][0], plan['scenes'][0], profile, 's0', brief)
        self.assertEqual(a, b)
        self.assertEqual(inputs, (brief, profile, plan))
        self.assertIn('Önce &amp; “sonra”', a[0])
        ET.fromstring(a[0])
        a[1][0]['values']['x'] = 999
        self.assertEqual(compile_scene(brief['scenes'][0], plan['scenes'][0], profile, 's0', brief)[1][0]['values']['x'], 0)

    def test_direct_compiler_rejects_profile_ident_palette_code_and_foreign_scene(self):
        brief, profile, plan = fixture()
        for change in ('profile', 'ident', 'palette', 'code', 'scene'):
            p, item, scene = copy.deepcopy(profile), copy.deepcopy(plan['scenes'][0]), copy.deepcopy(brief['scenes'][0])
            ident = 's0'
            if change == 'profile':
                p['id'] = 'other'
            elif change == 'ident':
                ident = 's0" onload="x'
            elif change == 'palette':
                p['palette']['ink'] = 'red" onload="x'
            elif change == 'code':
                item['content']['nodes'][0] = '<script>x</script>'
            else:
                scene['heading'] = 'Not the pinned source scene'
            with self.subTest(change=change), self.assertRaises(WorkflowError):
                compile_scene(scene, item, p, ident, brief)

    def test_compiler_has_no_native_provider_or_asset_load_dependency(self):
        with patch('storymotion.engine.checked_process', side_effect=AssertionError('No subprocess')):
            vector, ops, _, _ = self.compile('sample-flow', 'process-route')
        self.assertTrue(vector)
        self.assertTrue(ops)


if __name__ == '__main__':
    unittest.main()
