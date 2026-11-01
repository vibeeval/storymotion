"""Authenticated Handler preparation must reject secrets before all persistence.

Only explicitly synthetic RAM broker entries and isolated local fixtures are used.
HTTP is parsed by the actual Handler over memory streams; no socket/provider call.
"""
import copy
from contextlib import closing
import html
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from storymotion.dashboard import Dashboard, Handler
from storymotion.security import canonical
from storymotion.template_families import make_brief
from test_catalog_integration import MemoryConnection, issued_cookie
from test_template_intake import SOURCE, covering_claims


ROOT = Path(__file__).resolve().parents[1]
LLM_OPAQUE = 'FAKE_LLM_"\\opaque'
VOICE_OPAQUE = 'TEST_ONLY_VOICE_"\\opaque'


def patterned():
    return 'sk-' + 'A' * 24


class TemplateCredentialHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.d = Dashboard(self.root)
        self.addCleanup(self.d.close_local_log)
        self.addCleanup(self.d.reviews.close)
        self.addCleanup(self.d.renders.close)
        self.addCleanup(self.d.clear_keys)
        self.addCleanup(self.d.eleven.broker.clear)
        self.addCleanup(self.d.llm.broker.clear)
        self.d.local_log  # Production make_server configures diagnostics before HTTP.
        self.server = SimpleNamespace(server_address=('127.0.0.1', 43333), dashboard=self.d)
        self.cookie = issued_cookie(self.server)
        self.d.llm.broker.put('openai', 'synthetic-job', 'synthetic-request', LLM_OPAQUE, synthetic=True)
        self.d.eleven.broker.put('elevenlabs', 'synthetic-job', 'synthetic-request', VOICE_OPAQUE, synthetic=True)
        self.specs = {
            'kinetic-grid': json.loads((ROOT / 'fixtures/template-families.json').read_text())['families']['kinetic-grid'][0]['spec'],
            'contour-trace': json.loads((ROOT / 'fixtures/development-templates/contour-trace.json').read_text())['cases'][0]['spec'],
        }
        for target in ('socket.socket.connect', 'socket.socket.bind', 'urllib.request.urlopen',
                       'storymotion.engine.checked_process'):
            blocker = patch(target, side_effect=AssertionError('No network or native process in this test'))
            blocker.start()
            self.addCleanup(blocker.stop)

    def request(self, path, data, *, cookie=True, origin='http://127.0.0.1:43333', marker='1'):
        body = json.dumps(data).encode()
        lines = ['POST ' + path + ' HTTP/1.0', 'Host: 127.0.0.1:43333']
        if cookie:
            lines.append('Cookie: ' + self.cookie)
        lines += ['Origin: ' + origin, 'X-Storymotion-Local: ' + marker,
                  'Content-Type: application/json', 'Content-Length: ' + str(len(body))]
        connection = MemoryConnection(('\r\n'.join(lines) + '\r\n\r\n').encode() + body)
        Handler(connection, ('127.0.0.1', 1), self.server)
        response = bytes(connection.output)
        head, raw = response.split(b'\r\n\r\n', 1)
        return int(head.split()[1]), json.loads(raw), response

    def payload(self, family, engine='hyperframes'):
        return {'account': 'neutral', 'engine': engine, 'spec': copy.deepcopy(self.specs[family])}

    def snapshot(self):
        # Includes DB bytes/mtime and every directory: rejection must not create
        # family-inputs, an Engine workspace, SQLite sidecars or any log output.
        paths = {}
        dumps = {}
        for path in sorted(self.root.rglob('*')):
            name = str(path.relative_to(self.root))
            if path.is_file():
                paths[name] = (path.read_bytes(), path.stat().st_mtime_ns)
                if path.suffix == '.sqlite3':
                    with closing(sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True)) as db:
                        dumps[name] = tuple(db.iterdump())
            else:
                paths[name] = None
        return paths, dumps

    def assert_no_secret(self, response=b''):
        tokens = []
        for value in (LLM_OPAQUE, VOICE_OPAQUE, patterned()):
            tokens.extend((value.encode(), canonical(value).encode(), canonical(canonical(value)).encode(),
                           html.escape(value, quote=True).encode()))
        self.assertFalse(any(token in response for token in tokens), 'Credential reached HTTP response')
        for path in self.root.rglob('*'):
            if path.is_file():
                raw = path.read_bytes()
                self.assertFalse(any(token in raw for token in tokens),
                                 'Credential reached workspace file: ' + str(path.relative_to(self.root)))

    def assert_rejected_without_mutation(self, data):
        before = self.snapshot()
        with patch('storymotion.template_studio.make_brief', wraps=make_brief) as normalize:
            code, value, response = self.request('/api/template-families/prepare', data)
            self.assert_no_secret(response)
            self.assertEqual(code, 400)
            self.assertEqual(normalize.call_count, 0, 'Unsafe request reached normalization')
        self.assertTrue(self.snapshot() == before, 'Rejected preparation mutated files, databases or events')
        self.assertFalse((self.root / 'family-inputs').exists())
        self.assertFalse((self.root / 'family-renders').exists())

    def test_active_llm_opaque_base_title_is_rejected_before_any_mutation(self):
        data = self.payload('kinetic-grid')
        data['spec']['parameters']['title'] = LLM_OPAQUE
        self.assert_rejected_without_mutation(data)

    def test_patterned_development_title_never_leaves_a_family_input_file(self):
        data = self.payload('contour-trace')
        data['spec']['parameters']['title'] = patterned()
        self.assert_rejected_without_mutation(data)

    def test_both_families_engines_and_brokers_reject_visible_and_nested_secrets(self):
        credentials = {'pattern': patterned(), 'llm': LLM_OPAQUE, 'voice': VOICE_OPAQUE}
        for family in self.specs:
            for engine in ('hyperframes', 'remotion'):
                for kind, key in credentials.items():
                    for location in ('title', 'nested-cue', 'invalid-extra'):
                        with self.subTest(family=family, engine=engine, credential_kind=kind, location=location):
                            data = self.payload(family, engine)
                            p = data['spec']['parameters']
                            if location == 'title':
                                p['title'] = key
                            elif location == 'nested-cue':
                                p['cues'][0]['text'] = key
                                p['narration'] = ' '.join(c['text'] for c in p['cues'])
                            else:
                                data['unknown-field'] = {'nested': [{'value': key}]}
                                data['engine'] = 'invalid-engine'
                            self.assert_rejected_without_mutation(data)

    def test_credential_field_names_are_rejected_even_without_a_key_pattern(self):
        for family in self.specs:
            data = self.payload(family)
            data['unknown-field'] = {'nested': [{'access_token': 'ordinary-text'}]}
            with self.subTest(family=family):
                self.assert_rejected_without_mutation(data)

    def test_invalid_intake_without_credentials_does_not_write(self):
        for family in self.specs:
            data = self.payload(family)
            data['spec']['parameters']['duration'] = None
            before = self.snapshot()
            code, value, response = self.request('/api/template-families/prepare', data)
            self.assertEqual(code, 400)
            self.assert_no_secret(response)
            self.assertTrue(self.snapshot() == before, 'Invalid intake mutated persistent state')

    def test_normalized_brief_is_checked_again_before_context_or_file_writes(self):
        original = make_brief
        for family in self.specs:
            for kind, key in {'pattern': patterned(), 'llm': LLM_OPAQUE, 'voice': VOICE_OPAQUE}.items():
                with self.subTest(family=family, credential_kind=kind):
                    before = self.snapshot()
                    def normalized(*args, **kwargs):
                        brief = original(*args, **kwargs)
                        brief['caption'] = key
                        return brief
                    with patch('storymotion.template_studio.make_brief', side_effect=normalized), \
                         patch.object(self.d.llm.contexts, 'assert_current', wraps=self.d.llm.contexts.assert_current) as current:
                        code, value, response = self.request('/api/template-families/prepare', self.payload(family))
                        self.assertEqual(code, 400)
                        self.assert_no_secret(response)
                        self.assertEqual(current.call_count, 0)
                    self.assertTrue(self.snapshot() == before, 'Unsafe normalized brief mutated persistent state')

    def test_positive_source_bound_preparation_with_active_brokers_keeps_both_engines(self):
        code, state, response = self.request('/api/writing-context/save-sources', {
            'account': 'neutral', 'expected_revision': None, 'sources': SOURCE, 'rights_confirmed': True})
        self.assertEqual(code, 200)
        revision = state['sources']['revision']
        for family in self.specs:
            for engine in ('hyperframes', 'remotion'):
                with self.subTest(family=family, engine=engine):
                    data = self.payload(family, engine)
                    data.update(claims=covering_claims(data['spec']), source_revision=revision)
                    with patch.object(self.d, 'clean', wraps=self.d.clean) as clean:
                        code, value, response = self.request('/api/template-families/prepare', data)
                        self.assertEqual(code, 200)
                        self.assertEqual(clean.call_count, 2)
                    self.assertEqual(value['status'], 'prepare_only')
                    self.assertFalse(value['actual_render'])
                    self.assertEqual(value['provider_calls'], 0)
                    out = self.root / 'family-renders' / value['job']
                    binding = json.loads((out / 'writing-context.json').read_text())['binding']
                    self.assertEqual(binding['sources']['revision'], revision)
                    self.assertFalse((out / 'render-1080.mp4').exists())
                    self.assert_no_secret(response)

    def test_auth_origin_and_marker_still_reject_before_preparation(self):
        data = self.payload('kinetic-grid')
        before = self.snapshot()
        with patch.object(self.d.template_studio, 'prepare', wraps=self.d.template_studio.prepare) as prepare:
            for kwargs, expected in (({'cookie': False}, 401),
                                     ({'origin': 'https://attacker.invalid'}, 403),
                                     ({'marker': '0'}, 403)):
                code, value, response = self.request('/api/template-families/prepare', data, **kwargs)
                self.assertEqual(code, expected)
                self.assert_no_secret(response)
            self.assertEqual(prepare.call_count, 0)
        self.assertTrue(self.snapshot() == before, 'Rejected HTTP gate mutated persistent state')
