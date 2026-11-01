from pack_fixture_case import PackFixtureCase
"""Selected raster integration: real PNG checks, no native tools or render claims."""
import json
from pathlib import Path
import shutil
import stat
import struct
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile
import zlib

from storymotion.edit_plan import verify_staged_assets
from storymotion.engine import Engine, ROOT
from storymotion.raster_io import validate_normalized
from storymotion.security import WorkflowError, digest, file_hash, write_json


ENGINES = ('hyperframes', 'remotion')


def normalized_png():
    """Own neutral 96x64 RGBA geometry; exact CRC/inflated pixels, no metadata."""
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    raw = b''.join(b'\0' + b''.join(bytes((230, 110, 30, 255)) if 24 <= x < 72 and 16 <= y < 48
                                   else bytes((240, 237, 225, 255)) for x in range(96)) for y in range(64))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 96, 64, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def raster_brief(folder, account='sample-mechanism'):
    folder.mkdir(parents=True, exist_ok=True)
    image = folder / 'raster/image.png'
    image.parent.mkdir(exist_ok=True)
    image.write_bytes(normalized_png())
    sha = file_hash(image)
    validate_normalized(image, sha, 96, 64)  # Never replace the ingress parser with a mock.
    brief = json.loads((ROOT / 'tests/fixtures/examples/golden' / (account + '.json')).read_text())
    brief['raster'] = {'schema_version': 1, 'recipe': 'customer-raster-annotation-1',
                       'asset': {'file': 'raster/image.png', 'sha256': sha, 'source_sha256': sha,
                                 'width': 96, 'height': 64, 'container': 'png',
                                 'approved_by': 'Synthetic local test', 'rights_note': 'Own neutral geometric fixture',
                                 'rights_confirmed': True},
                       'views': [{'scene_id': s['id'], 'crop': {'x': .125, 'y': .125, 'width': .75, 'height': .75},
                                  'highlight': {'x': .3, 'y': .3, 'width': .2, 'height': .2},
                                  'label': 'Seçili ayrıntı', 'camera': s['camera']} for s in brief['scenes']]}
    path = folder / 'brief.json'
    write_json(path, brief)
    return path, brief, image


class RasterEngineTests(PackFixtureCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.native = patch('storymotion.engine.checked_process', side_effect=AssertionError('No native process permitted'))
        self.native.start()
        self.engines = []

    def tearDown(self):
        for engine in self.engines:
            if engine._store is not None:
                engine.store.db.close()
        self.native.stop()
        self.tmp.cleanup()

    def engine(self, name, suffix=''):
        engine = Engine(self.root / ('work-' + name + suffix))
        self.engines.append(engine)
        return engine

    def prepared(self, name, suffix=''):
        path, brief, image = raster_brief(self.root / ('input-' + name + suffix))
        engine = self.engine(name, suffix)
        job = engine.create(path, render_engine=name)['job']
        engine.run(job, 'prepare')
        return engine, job, engine.payload(job), engine.directory(job), path, image

    def delivery(self, name, suffix=''):
        engine, job, payload, out, path, image = self.prepared(name, suffix)
        # Deliberately fake media for packaging-integrity tests only. No native
        # MP4 encoding/decode or human/technical video acceptance is asserted.
        for media in ('render-1080.mp4', 'render-mobile.mp4', 'cover.png', 'cover-360.png'):
            (out / media).write_bytes(b'PACKAGING_SENTINEL_NOT_ENCODED_MEDIA:' + media.encode())
        for record in ('render-engine.json', 'qa.json', 'check.json', 'browser-evidence.json'):
            write_json(out / record, {'scope': 'synthetic packaging fixture, not rendered acceptance'})
        engine.perform('delivery', payload, out)
        return engine, job, payload, out, path, image

    def test_two_prepare_engines_compile_selected_source_and_never_latch_fallback(self):
        plans = []
        for name in ENGINES:
            with self.subTest(engine=name):
                engine, job, payload, out, _, image = self.prepared(name)
                plan = payload['edit_plan']
                plans.append(plan)
                self.assertEqual(plan['actual_visual_family'], 'customer-raster-annotation')
                self.assertEqual(plan['raster_sha256'], digest(payload['brief']['raster']))
                self.assertEqual(plan['raster_asset']['sha256'], file_hash(image))
                self.assertEqual(file_hash(out / 'assets/customer-image.png'), file_hash(image))
                self.assertEqual(json.loads((out / 'raster.json').read_text()), payload['brief']['raster'])
                self.assertEqual(json.loads((out / 'edit-plan.json').read_text()), plan)
                markup = (out / 'index.html').read_text()
                for scene in plan['scenes']:
                    self.assertEqual(scene['action'], 'raster-annotation')
                    self.assertIn('href="assets/customer-image.png"', scene['vector'])
                    self.assertIn('viewBox="12 8 72 48"', scene['vector'])
                    self.assertNotIn('-latch', scene['vector'])
                    self.assertNotIn('-hinge', scene['vector'])
                    self.assertIn(scene['vector'], markup)
                self.assertIn('href="assets/customer-image.png"', (out / 'cover.svg').read_text())
                self.assertNotIn('-latch', (out / 'cover.svg').read_text())
                if name == 'remotion':
                    props = json.loads((out / 'remotion-props.json').read_text())
                    self.assertEqual(props['edit_plan'], plan)
                    self.assertEqual(props['vectors'], {f's{i}': s['vector'] for i, s in enumerate(plan['scenes'])})
                self.assertTrue(engine.manifest_valid(job, 'prepare'))
        self.assertEqual(plans[0], plans[1])

    def test_other_profiles_reject_raster_before_job_database_or_prepare(self):
        for account in ('sample-flow', 'sample-reflection', 'sample-series'):
            path, _, _ = raster_brief(self.root / account, account)
            engine = self.engine(account)
            with self.subTest(account=account), self.assertRaises(WorkflowError):
                engine.create(path)
            self.assertIsNone(engine._store)
            self.assertFalse(Path(engine._workspace).exists())

    def test_invalid_normalized_png_or_source_symlink_never_creates_job(self):
        for kind in ('corrupt', 'missing', 'symlink'):
            path, brief, image = raster_brief(self.root / kind)
            if kind == 'corrupt':
                image.write_bytes(b'not a PNG')
                brief['raster']['asset']['sha256'] = file_hash(image)
                write_json(path, brief)  # Hash agreement alone must not pass.
            elif kind == 'missing':
                image.unlink()
            else:
                other = image.with_name('same-bytes.png')
                image.rename(other)
                image.symlink_to(other)
            engine = self.engine(kind)
            with self.subTest(kind=kind), self.assertRaises(WorkflowError):
                engine.create(path)
            self.assertIsNone(engine._store)

    def test_immutable_inputs_snapshot_survives_original_source_mutation_and_resume_reuses_prepare(self):
        for name in ENGINES:
            engine, job, payload, out, _, image = self.prepared(name)
            staged = engine.store.root / '.inputs' / job / 'raster.png'
            stored = json.loads(engine.store.db.execute('SELECT payload FROM jobs WHERE id=?', (job,)).fetchone()[0])
            self.assertEqual(stored['raster_source'], '.inputs/' + job + '/raster.png')
            self.assertEqual(Path(payload['raster_source']), staged)
            self.assertEqual(staged.read_bytes(), normalized_png())
            outputs = [out / 'index.html', out / 'assets/customer-image.png', out / 'raster.json']
            before = [(file_hash(p), p.stat().st_mtime_ns) for p in outputs]
            image.write_bytes(b'original changed after immutable snapshot')
            with patch.object(engine, 'perform', side_effect=AssertionError('Verified prepare should be reused')):
                result = engine.run(job, 'prepare')
            self.assertEqual([(file_hash(p), p.stat().st_mtime_ns) for p in outputs], before)
            self.assertEqual(next(s for s in result['stages'] if s['name'] == 'prepare')['status'], 'complete')

    def test_changed_or_missing_immutable_inputs_block_before_stage_execution(self):
        for name in ENGINES:
            for kind in ('changed', 'missing'):
                engine, job, payload, _, _, _ = self.prepared(name, '-' + kind)
                source = Path(payload['raster_source'])
                if kind == 'changed':
                    source.write_bytes(normalized_png() + b'trailing corruption')
                else:
                    source.unlink()
                with self.subTest(engine=name, kind=kind), patch.object(engine, 'perform', side_effect=AssertionError('No stage execution')):
                    with self.assertRaises(WorkflowError):
                        engine.run(job, 'prepare')

    def test_same_bytes_immutable_input_symlink_is_rejected_on_resume(self):
        for name in ENGINES:
            engine, job, payload, _, _, _ = self.prepared(name)
            source = Path(payload['raster_source'])
            other = engine.store.root / 'same-bytes.png'
            other.write_bytes(source.read_bytes())
            source.unlink()
            source.symlink_to(other)
            with self.subTest(engine=name), patch.object(engine, 'perform', side_effect=AssertionError('No stage execution')):
                with self.assertRaises(WorkflowError):
                    engine.run(job, 'prepare')

    def test_corrupt_copy_rejects_prepare_before_html_for_both_engines(self):
        original = shutil.copyfile
        def corrupt(src, dst, *args, **kwargs):
            result = original(src, dst, *args, **kwargs)
            if Path(dst).name == 'customer-image.png':
                Path(dst).write_bytes(b'corrupt copied raster')
            return result
        for name in ENGINES:
            path, _, _ = raster_brief(self.root / name)
            engine = self.engine(name)
            job = engine.create(path, render_engine=name)['job']
            with self.subTest(engine=name), patch('storymotion.compose.shutil.copyfile', side_effect=corrupt):
                with self.assertRaises(WorkflowError):
                    engine.run(job, 'prepare')
            self.assertEqual(engine.store.stage(job, 'prepare')['status'], 'failed')
            self.assertFalse((engine.directory(job) / 'index.html').exists())

    def test_staged_image_manifest_and_symlink_tampering_reject_before_later_stages(self):
        for name in ENGINES:
            for kind in ('hash', 'manifest', 'missing', 'symlink'):
                engine, job, payload, out, _, _ = self.prepared(name, '-' + kind)
                target = out / 'assets/customer-image.png'
                if kind == 'hash':
                    target.write_bytes(b'corrupt staged raster')
                elif kind == 'manifest':
                    write_json(out / 'raster.json', {**payload['brief']['raster'], 'recipe': 'tampered'})
                elif kind == 'missing':
                    target.unlink()
                else:
                    other = out / 'same-bytes.png'
                    other.write_bytes(target.read_bytes())
                    target.unlink()
                    target.symlink_to(other)
                with self.subTest(engine=name, kind=kind):
                    self.assertFalse(engine.manifest_valid(job, 'prepare'))
                    with self.assertRaises(WorkflowError):
                        verify_staged_assets(payload, out)
                    with self.assertRaises(WorkflowError):
                        engine.perform('check', payload, out)

    def test_resume_repairs_changed_staged_image_even_when_row_manifest_hash_is_forged(self):
        for name in ENGINES:
            engine, job, payload, out, _, _ = self.prepared(name)
            target = out / 'assets/customer-image.png'
            target.write_bytes(b'corrupt staged raster')
            manifest = json.loads(engine.store.stage(job, 'prepare')['manifest'])
            manifest['assets/customer-image.png'] = file_hash(target)
            engine.store.set_stage(job, 'prepare', 'complete', manifest)
            self.assertFalse(engine.manifest_valid(job, 'prepare'))
            engine.run(job, 'prepare')
            self.assertEqual(target.read_bytes(), normalized_png())
            self.assertTrue(engine.manifest_valid(job, 'prepare'))
            for stage in ('check', 'render', 'mobile', 'cover', 'qa', 'delivery'):
                self.assertEqual(engine.store.stage(job, stage)['status'], 'pending')

    def test_delivery_pins_raster_bytes_manifest_and_rights_without_claiming_media_acceptance(self):
        for name in ENGINES:
            _, _, payload, out, _, _ = self.delivery(name)
            verify_staged_assets(payload, out, delivery=True)
            manifest = json.loads((out / 'delivery.json').read_text())
            self.assertEqual(manifest['raster_asset_sha256'], payload['brief']['raster']['asset']['sha256'])
            self.assertEqual(manifest['raster_sha256'], digest(payload['brief']['raster']))
            self.assertEqual(manifest['final_release'], 'pending_human_review')
            self.assertEqual(manifest['customer_asset_distribution'], 'private_project_only_unless_separately_licensed')
            with zipfile.ZipFile(out / 'delivery.zip') as archive:
                self.assertEqual(archive.read('assets/customer-image.png'), normalized_png())
                self.assertEqual(json.loads(archive.read('raster.json')), payload['brief']['raster'])

    def test_zip_raster_duplicate_missing_changed_symlink_and_manifest_are_rejected(self):
        for name in ENGINES:
            for kind in ('duplicate', 'missing', 'changed', 'symlink', 'raster-manifest', 'delivery-binding', 'duplicate-manifest', 'missing-manifest', 'linked-manifest'):
                _, _, payload, out, _, _ = self.delivery(name, '-' + kind)
                path = out / 'delivery.zip'
                with zipfile.ZipFile(path) as archive:
                    members = {n: archive.read(n) for n in archive.namelist()}
                rel = 'assets/customer-image.png'
                if kind == 'missing':
                    del members[rel]
                elif kind == 'changed':
                    members[rel] = b'changed packaged raster'
                elif kind == 'raster-manifest':
                    members['raster.json'] = b'{}'
                elif kind == 'missing-manifest':
                    del members['raster.json']
                elif kind == 'delivery-binding':
                    manifest = json.loads((out / 'delivery.json').read_text())
                    manifest['raster_sha256'] = 'f' * 64
                    write_json(out / 'delivery.json', manifest)
                with warnings.catch_warnings(), zipfile.ZipFile(path, 'w') as archive:
                    warnings.simplefilter('ignore', UserWarning)
                    for entry, data in members.items():
                        if (kind == 'symlink' and entry == rel) or (kind == 'linked-manifest' and entry == 'raster.json'):
                            info = zipfile.ZipInfo(entry)
                            info.create_system = 3
                            info.external_attr = (stat.S_IFLNK | 0o777) << 16
                            archive.writestr(info, data)
                        else:
                            archive.writestr(entry, data)
                    if kind == 'duplicate':
                        archive.writestr(rel, members[rel])
                    elif kind == 'duplicate-manifest':
                        archive.writestr('raster.json', members['raster.json'])
                with self.subTest(engine=name, kind=kind), self.assertRaises(WorkflowError):
                    verify_staged_assets(payload, out, delivery=True)


if __name__ == '__main__':
    unittest.main()
