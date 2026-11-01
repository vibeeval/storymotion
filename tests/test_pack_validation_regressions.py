"""Rejected local data never reaches CSS/HTML or crashes valid pack workflows."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from storymotion import account_packs
from storymotion.account_pack_schema import PROFILE_NUMBERS, validate_render_profile
from storymotion.creative import output_schema
from storymotion.dashboard import Dashboard
from storymotion.engine import Engine
from storymotion.security import WorkflowError

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).parent / 'fixtures/pack-registry'
PAYLOAD = '78}</style><script>window.ACCOUNTPACK_EXECUTION=true</script><style>h1{font-size:78'


class PackValidationRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(FIXTURE_ROOT / 'accountpacks', self.root / 'accountpacks')
        self.user = self.root / 'work/accountpacks'
        self.user.mkdir(parents=True)
        scope = patch.object(account_packs, 'ROOT', self.root)
        scope.start(); self.addCleanup(scope.stop)
        self.good = account_packs.load_pack('sample-flow')

    def bad_pack(self):
        value = copy.deepcopy(self.good)
        value['id'] = 'invalid-demo'; value['profile']['id'] = value['id']; value['fixture']['brand'] = value['id']
        return value

    def write(self, value):
        (self.user / 'invalid-demo.json').write_text(json.dumps(value, ensure_ascii=False))

    def assert_rejected_alongside_good(self, value):
        self.write(value)
        packs, errors = account_packs.catalog()
        self.assertIn('sample-flow', packs)
        self.assertNotIn('invalid-demo', packs)
        self.assertEqual(errors, [{'file': 'invalid-demo.json', 'code': 'CUSTOMER_PROFILE_MALFORMED'}])
        self.assertIn('scenes', output_schema('sample-flow')['properties'])
        with self.assertRaises(WorkflowError):account_packs.load_pack('invalid-demo')

    def test_every_css_numeric_field_rejects_code_strings_bool_nonfinite_and_bounds(self):
        for field, (minimum, maximum) in PROFILE_NUMBERS.items():
            for bad in (PAYLOAD, str(minimum), True, False, None, [], {}, float('inf'), float('-inf'), float('nan'), minimum - 1, maximum + 1):
                with self.subTest(field=field, bad=type(bad).__name__):
                    value = self.bad_pack(); value['profile'][field] = bad
                    self.assert_rejected_alongside_good(value)
            for valid in (minimum, maximum, (minimum + maximum) / 2):
                profile = copy.deepcopy(self.good['profile']); profile[field] = valid
                self.assertEqual(validate_render_profile(profile)[field], valid)

    def test_required_consumed_fields_and_closed_nested_contracts_fail_at_catalog(self):
        for field in self.good:
            with self.subTest(missing=field):
                value = self.bad_pack(); del value[field]
                self.assert_rejected_alongside_good(value)
        mutations = [lambda v: v['scene_contract'].update({'request-route': None}),
                     lambda v: v['scene_contract']['request-route'].update(state_before=[]),
                     lambda v: v['scene_contract']['request-route'].update(extra='unsupported'),
                     lambda v: v['profile'].update(extra='unsupported'),
                     lambda v: v['profile']['palette'].update(ink=PAYLOAD),
                     lambda v: v['series_rules'].update(enabled='false'),
                     lambda v: v['capabilities'].update(rig_mode=PAYLOAD),
                     lambda v: v['voice_defaults'].update(voice_id='not-off'),
                     lambda v: v['fixture']['scenes'][0].update(start=PAYLOAD),
                     lambda v: v['fixture']['creative'].update(characters=None),
                     lambda v: v['fixture'].update(extra='unsupported')]
        for mutate in mutations:
            value = self.bad_pack(); mutate(value); self.assert_rejected_alongside_good(value)

    def test_injection_isolated_and_real_good_prepare_has_no_attacker_markup(self):
        value = self.bad_pack(); value['profile']['title_size'] = PAYLOAD
        self.assert_rejected_alongside_good(value)
        dashboard = Dashboard(self.root / 'session')
        self.addCleanup(dashboard.clear_keys)
        self.assertNotIn('invalid-demo', [a['id'] for a in dashboard.catalog['accounts']])
        self.assertEqual(len(dashboard.catalog['account_pack_errors']), 1)
        video = dashboard.template('sample-flow', 'account-video')['template']['video']
        source = self.root / 'brief.json'; source.write_text(json.dumps(video))
        for renderer in ('hyperframes', 'remotion'):
            engine = Engine(self.root / renderer)
            try:
                key = engine.create(source, render_engine=renderer)['job']; engine.run(key, 'prepare')
                for name in ('index.html', 'cover.html', 'cover.svg'):
                    text = (engine.directory(key) / name).read_text()
                    self.assertNotIn('ACCOUNTPACK_EXECUTION', text)
                    self.assertNotIn('</style><script>', text)
                self.assertIn('font-size:78px', (engine.directory(key) / 'index.html').read_text())
            finally:
                if engine._store:engine._store.db.close()
        # The scene and series surfaces continue using the valid fixture packs.
        from test_scene_plan import fixture
        from storymotion.scene_plan import validate_scene_plan
        brief, _, plan = fixture('sample-flow')
        validate_scene_plan(plan, brief)
        self.assertFalse(dashboard.series.state()['publication_ready'])

    def test_renderer_boundary_rejects_injected_profile_before_output_is_created(self):
        from storymotion.compose import build
        profile = copy.deepcopy(self.good['profile']); profile['title_size'] = PAYLOAD
        output = self.root / 'must-not-exist'
        with self.assertRaises(WorkflowError):build({'profile': profile, 'brief': self.good['fixture']}, output, ROOT)
        self.assertFalse(output.exists())

    def test_malformed_pack_does_not_interrupt_real_series_reference_and_draft_flow(self):
        value = self.bad_pack(); value['scene_contract']['request-route'] = None
        self.assert_rejected_alongside_good(value)
        # Use explicit synthetic receipt fixtures; this exercises the real
        # series contracts and persistence without native rendering or IO.
        from test_series import SerialLifecycleTests
        case = SerialLifecycleTests()
        case.setUp()
        try:
            case.test_two_episode_manual_lifecycle_and_explicit_acceptance()
        finally:
            case.tearDown()

    def test_linked_work_ancestor_never_reads_outside_user_packs(self):
        with tempfile.TemporaryDirectory() as outside:
            outside = Path(outside); (outside / 'accountpacks').mkdir()
            value = self.bad_pack(); (outside / 'accountpacks/invalid-demo.json').write_text(json.dumps(value))
            self.user.rmdir(); (self.root / 'work').rmdir(); (self.root / 'work').symlink_to(outside, target_is_directory=True)
            packs, errors = account_packs.catalog()
            self.assertIn('sample-flow', packs); self.assertNotIn('invalid-demo', packs)
            self.assertEqual(len(errors), 1)
            with self.assertRaises(WorkflowError):account_packs._validate(self.root / 'work/accountpacks/invalid-demo.json')

    def test_duplicate_json_fields_are_rejected_without_catalog_crash(self):
        (self.user / 'invalid-demo.json').write_text('{"id":"invalid-demo","id":"sample-flow"}')
        packs, errors = account_packs.catalog()
        self.assertIn('sample-flow', packs)
        self.assertEqual(len(errors), 1)


if __name__ == '__main__':
    unittest.main()
