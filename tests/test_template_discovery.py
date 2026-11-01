"""Phase 3 editorial discovery join: exact 91 IDs, null scores, honest media flags."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from storymotion import template_discovery
from storymotion.dashboard import Dashboard, Handler
from storymotion.security import WorkflowError
from storymotion.template_families import FAMILIES, capabilities
from test_catalog_integration import MemoryConnection, issued_cookie


class TemplateDiscoveryTests(unittest.TestCase):
    def test_exact_91_join_null_scores_and_media_flags(self):
        rows = template_discovery.catalog()
        value = capabilities()
        self.assertEqual(set(rows), set(FAMILIES))
        self.assertEqual(len(value['families']), 91)
        self.assertEqual({f['id'] for f in value['families']}, set(FAMILIES))
        self.assertEqual(value['discovery_source_sha256'], template_discovery.SOURCE_SHA256)
        media = {f['id'] for f in value['families'] if f['requires_caller_media']}
        self.assertEqual(len(media), 14)
        for family in value['families']:
            editorial = rows[family['id']]
            self.assertIsNone(family['visual_score'])
            self.assertIsNone(family['preview_url'])
            self.assertEqual(family['preview_state'], 'missing_preview')
            self.assertEqual(family['instagram_assessment']['status'], 'not_assessed')
            self.assertIsNone(family['instagram_assessment']['score_100'])
            self.assertEqual(family['age_hypothesis']['status'], 'hypothesis_not_measured')
            self.assertEqual(family['age_hypothesis']['label'], '18+')
            self.assertEqual(family['requires_caller_media'], editorial['requires_caller_media'])
            self.assertEqual(family['niches'], editorial['niches'])
            self.assertTrue(family['niches'] and family['content_types'] and family['sample_topics'])
            self.assertEqual(family['readiness'], 'caller_media_proxy_only' if family['requires_caller_media'] else 'prepare_only_native_pending')
            self.assertFalse(family['engines']['hyperframes']['render_verified'])
            self.assertFalse(family['engines']['remotion']['render_verified'])

    def test_search_filter_reset_combinations_use_honest_fields(self):
        families = capabilities()['families']
        niches = sorted({n for f in families for n in f['niches']})
        types = sorted({n for f in families for n in f['content_types']})
        self.assertTrue(niches and types)
        for niche in niches:
            matched = [f for f in families if niche in f['niches']]
            self.assertTrue(matched)
            self.assertEqual(len(matched), len({f['id'] for f in matched}))
        proxies = [f for f in families if f['requires_caller_media']]
        vectors = [f for f in families if not f['requires_caller_media']]
        self.assertEqual(len(proxies), 14)
        self.assertEqual(len(proxies) + len(vectors), 91)
        query = 'vektör olmayan-eşleşme-xyz'
        self.assertEqual([f for f in families if query in json.dumps(f, ensure_ascii=False)], [])

    def test_pin_tamper_and_score_injection_are_refused(self):
        raw = json.loads((Path(template_discovery.ROOT)/'catalog/template-discovery-91.json').read_text())
        with tempfile.TemporaryDirectory() as td, patch.object(template_discovery, 'ROOT', Path(td)):
            root = Path(td);(root/'catalog').mkdir()
            bad = json.loads(json.dumps(raw));bad['families'][0]['visual_score'] = 12
            (root/'catalog/template-discovery-91.json').write_text(json.dumps(bad))
            with self.assertRaises(WorkflowError):
                template_discovery.catalog()
            missing = json.loads(json.dumps(raw));missing['families'] = missing['families'][:90]
            (root/'catalog/template-discovery-91.json').write_text(json.dumps(missing))
            with self.assertRaises(WorkflowError):
                template_discovery.catalog()
            (root/'catalog/template-discovery-91.json').write_text('{"schema_version":1}')
            with self.assertRaises(WorkflowError):
                template_discovery.catalog()


class TemplateDiscoveryHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.d = Dashboard(Path(self.tmp.name).resolve());self.addCleanup(self.d.clear_keys);self.addCleanup(self.d.renders.close);self.addCleanup(self.d.close_local_log)
        self.server = SimpleNamespace(server_address=('127.0.0.1', 43333), dashboard=self.d)
        self.cookie = issued_cookie(self.server)

    def test_catalog_route_exposes_91_honest_discovery_fields(self):
        data = ('GET /api/template-families HTTP/1.0\r\nHost: 127.0.0.1:43333\r\nCookie: ' + self.cookie + '\r\n\r\n').encode()
        connection = MemoryConnection(data);Handler(connection, ('127.0.0.1', 1), self.server)
        head, raw = bytes(connection.output).split(b'\r\n\r\n', 1)
        self.assertEqual(int(head.split()[1]), 200)
        value = json.loads(raw)
        self.assertEqual(len(value['families']), 91)
        self.assertEqual(value['discovery_source_sha256'], template_discovery.SOURCE_SHA256)
        self.assertEqual(sum(1 for f in value['families'] if f['requires_caller_media']), 14)
        self.assertTrue(all(f['visual_score'] is None and f['preview_url'] is None and f['preview_state'] == 'missing_preview' for f in value['families']))
        unauthorized = MemoryConnection(b'GET /api/template-families HTTP/1.0\r\nHost: 127.0.0.1:43333\r\n\r\n')
        Handler(unauthorized, ('127.0.0.1', 1), self.server)
        self.assertEqual(int(bytes(unauthorized.output).split()[1]), 401)
