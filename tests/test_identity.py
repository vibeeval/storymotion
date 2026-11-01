from pack_fixture_case import PackFixtureCase
from storymotion.account_packs import render_profile
import copy
import json
import tempfile
import unittest
from pathlib import Path
from storymotion.dashboard import Dashboard
from storymotion.engine import Engine, ROOT
from storymotion.identity import normalize_identity, apply_identity
from storymotion.security import WorkflowError
from neutral_identity_fixture import assert_no_source_identity, source_identity_profiles


class CustomerIdentityTests(PackFixtureCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Dashboard(self.tmp.name)

    def tearDown(self):
        self.d.clear_keys()
        self.tmp.cleanup()

    def data(self, identity=None):
        v = self.d.template('sample-mechanism', 'short-explainer')['template']['video']
        d = dict(account='sample-mechanism', format='short-explainer', title=v['title'],
                 brief=v['brief'], content=v['script'], caption='Müşteri taslağı',
                 provider='local', model='manual', task='text', template_revision=0)
        if identity is not None:
            d['brand_identity'] = identity
        return d

    @source_identity_profiles()
    def test_default_new_job_has_neutral_identity_and_no_source_handle_in_output(self):
        job = self.d.enqueue(self.data())
        self.assertEqual(job['payload']['input']['brand_identity'], {'name': '', 'handle': ''})
        self.d.prepare(job['id'])
        source = self.d.output(job['id']) / 'source'
        for name in ['index.html', 'cover.svg', 'caption.txt']:
            text = (source / name).read_text()
            assert_no_source_identity(self, text)

    def test_customer_identity_changes_output_but_keeps_internal_profile_and_input(self):
        data = self.data({'name': 'Yeni Sayfam', 'handle': 'yenisayfam'})
        original = copy.deepcopy(data)
        job = self.d.enqueue(data)
        self.assertEqual(data, original)
        self.assertEqual(job['payload']['input']['brand_identity']['handle'], '@yenisayfam')
        self.d.prepare(job['id'])
        text = (self.d.output(job['id']) / 'source/index.html').read_text()
        self.assertIn('@yenisayfam', text)
        self.assertEqual(job['payload']['account']['id'], 'sample-mechanism')
        self.assertEqual(self.d.enqueue(data)['id'], job['id'])
        self.assertNotEqual(self.d.enqueue(self.data())['id'], job['id'])

    def test_new_cli_reference_job_without_identity_is_neutral(self):
        e = Engine(Path(self.tmp.name) / 'cli')
        _, payload = e.plan(ROOT / 'tests/fixtures/examples/sample-mechanism.json')
        self.assertEqual(payload['profile']['handle'], '')
        e.store.db.close()

    def test_invalid_identity_refused_before_job_write(self):
        for identity in [{'name': '<script>'}, {'handle': 'https://example.test'},
                         {'name': 'x\ny'}, {'name': 'x' * 61}, {'handle': '@bad handle'},
                         {'secret': 'x'}, {'name': 5}]:
            with self.subTest(identity=identity):
                with self.assertRaises(WorkflowError):
                    self.d.enqueue(self.data(identity))
        self.assertEqual(self.d.jobs(), [])

    def test_identity_does_not_mutate_rules_or_profile(self):
        p = render_profile('sample-mechanism')
        previous = copy.deepcopy(p)
        revised = apply_identity(p, {'name': 'Kendi sayfam'})
        self.assertEqual(p, previous)
        self.assertEqual(revised['id'], p['id'])
        self.assertEqual(revised['palette'], p['palette'])
        self.assertEqual(revised['handle'], '')
        self.assertEqual(normalize_identity({'name': '  İç Dünya  '}), {'name': 'İç Dünya', 'handle': ''})
