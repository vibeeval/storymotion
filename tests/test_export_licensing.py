"""Scoped source-export license notices; local preparation only, no native/network."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from storymotion import development_templates, source_catalog, template_families
from storymotion.engine import Engine
from storymotion.local_state import private_directory
from storymotion.security import WorkflowError, write_json
from tools.harness_fixtures import template_fixture_brief
import test_family_history_http as history_fixture

ROOT = Path(__file__).resolve().parents[1]
NOTICE = 'notices/StoryMotion-MIT.txt'
SCOPE_NOTICE = 'notices/StoryMotion-MIT-SCOPE.txt'
SCOPE = 'StoryMotion_original_code_and_documentation_only'
PALETTE_SCOPE = 'MIT_original_StoryMotion_palette_only'


class ExportLicensingTests(unittest.TestCase):
    def test_first_party_notice_is_exact_current_root_license_with_explicit_scope(self):
        raw = (ROOT / 'LICENSE').read_bytes()
        self.assertEqual((ROOT / 'vendor' / NOTICE).read_bytes(), raw)
        self.assertTrue(raw.startswith(b'MIT License\n'))
        self.assertIn(b'Copyright (c) 2026 StoryMotion contributors', raw)
        scope = (ROOT / 'vendor' / SCOPE_NOTICE).read_text()
        for marker in ('original StoryMotion code', 'documentation', 'third-party',
                       'fonts', 'media', 'separate'):
            self.assertIn(marker, scope)

    def test_protected_base_and_development_exports_preserve_notices_for_both_engines(self):
        case = history_fixture.FamilyHistoryHttpTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        original = (ROOT / 'LICENSE').read_bytes()
        for family in case.specs:
            for engine in ('hyperframes', 'remotion'):
                with self.subTest(family=family, engine=engine):
                    _, prepared = case.prepare(family, engine)
                    detail = case.detail(prepared)
                    self.assertEqual(detail['artifacts_status'], 'verified')
                    out = case.root / 'family-renders' / prepared['job']
                    selection = json.loads((out / 'template-selection.json').read_text())
                    licensed = selection['storymotion_license']
                    self.assertEqual(licensed['spdx'], 'MIT')
                    self.assertEqual(licensed['scope'], SCOPE)
                    self.assertEqual(licensed['notice_path'], 'assets/' + NOTICE)
                    self.assertEqual(licensed['scope_notice_path'], 'assets/' + SCOPE_NOTICE)
                    self.assertEqual(licensed['notice_sha256'], hashlib.sha256(original).hexdigest())
                    self.assertEqual((out / licensed['notice_path']).read_bytes(), original)
                    # Exact protected-history verification above checks the complete
                    # preparation manifest, including all vendor-derived notices.
                    for source in (ROOT / 'vendor').rglob('*'):
                        if source.is_file():
                            exported = out / 'assets' / source.relative_to(ROOT / 'vendor')
                            self.assertEqual(exported.read_bytes(), source.read_bytes())
                    brief = next(row for row in detail['files'] if row['name'] == 'BRIEF.md')
                    code, body, _ = case.get(brief['download_url'])
                    self.assertEqual(code, 200)
                    self.assertIn(b' '.join(original.split()), b' '.join(body.split()))
                    self.assertIn(b'original StoryMotion code', body)
                    self.assertIn(b'third-party', body)
                    self.assertFalse((out / 'render-1080.mp4').exists())
                    # Package synthetic placeholders solely to exercise the real
                    # delivery file list. This is not media/render verification.
                    for name in ('cover.png', 'cover-360.png', 'render-1080.mp4',
                                 'render-mobile.mp4', 'render-engine.json', 'qa.json',
                                 'check.json', 'browser-evidence.json'):
                        (out / name).write_bytes(b'TEST_ONLY_SYNTHETIC_EXPORT_ARTIFACT')
                    with Engine(case.root / 'family-renders') as runtime:
                        runtime.perform('delivery', runtime.payload(prepared['job']), out)
                    manifest = json.loads((out / 'delivery.json').read_text())['files']
                    with zipfile.ZipFile(out / 'delivery.zip') as archive:
                        for relative in (NOTICE, SCOPE_NOTICE):
                            name = 'assets/' + relative
                            self.assertEqual(archive.namelist().count(name), 1)
                            raw = (ROOT / 'vendor' / relative).read_bytes()
                            self.assertEqual(archive.read(name), raw)
                            self.assertEqual(manifest[name], hashlib.sha256(raw).hexdigest())

    def test_tampered_export_notice_blocks_protected_history_without_allowlist_changes(self):
        case = history_fixture.FamilyHistoryHttpTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        _, prepared = case.prepare('kinetic-grid')
        self.assertEqual(case.detail(prepared)['artifacts_status'], 'verified')
        notice = case.root / 'family-renders' / prepared['job'] / 'assets' / NOTICE
        notice.write_bytes(notice.read_bytes() + b'\nChanged notice.\n')
        self.assertEqual(case.detail(prepared)['artifacts_status'], 'unavailable')

    def test_mismatched_root_and_first_party_notice_refuse_export_before_asset_copy(self):
        spec = json.loads((ROOT / 'fixtures/template-families.json').read_text())['families']['kinetic-grid'][0]['spec']
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            brief = root / 'input.json'
            write_json(brief, template_fixture_brief('neutral', spec))
            with Engine(root / 'work') as engine:
                _, payload = engine.plan(brief)
            source = root / 'source'
            (source / 'vendor/notices').mkdir(parents=True)
            (source / 'LICENSE').write_bytes((ROOT / 'LICENSE').read_bytes() + b'\nChanged source license.\n')
            (source / 'vendor' / NOTICE).write_bytes((ROOT / 'LICENSE').read_bytes())
            (source / 'vendor' / SCOPE_NOTICE).write_bytes((ROOT / 'vendor' / SCOPE_NOTICE).read_bytes())
            output = root / 'export'
            private_directory(output)
            with self.assertRaisesRegex(WorkflowError, 'StoryMotion MIT notice'):
                template_families.build(payload, output, source)
            self.assertFalse((output / 'assets').exists())
            self.assertFalse((output / 'index.html').exists())

    def test_development_and_adapter_metadata_do_not_relicense_external_sources(self):
        for family in development_templates.FAMILIES:
            row = development_templates.adaptation(family)
            self.assertEqual(row['license'], 'MIT')
            self.assertEqual(row['implementation_license'], 'MIT')
            self.assertEqual(row['source_license'], 'metadata_reference_not_a_code_grant')
            self.assertIn('original StoryMotion code', row['scope'])
            self.assertIn('not included', row['scope'])
        for row in template_families.adapter_catalog():
            self.assertEqual(row['implementation_license'], 'MIT')

    def test_palette_scope_is_exact_and_old_product_terms_are_rejected(self):
        self.assertEqual({row['license_scope'] for row in source_catalog.metadata('styles')},
                         {PALETTE_SCOPE})
        original = source_catalog.pinned
        bad = copy.deepcopy(original('catalog/style-gallery.json'))
        bad['styles'][0]['license_scope'] = 'original_product_terms'
        with patch.object(source_catalog, 'pinned',
                          side_effect=lambda name: bad if name == 'catalog/style-gallery.json' else original(name)):
            with self.assertRaises(WorkflowError):
                source_catalog.metadata('styles')
