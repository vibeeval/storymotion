from pack_fixture_case import PackFixtureCase
"""Offline raster lifecycle contracts; Sharp and audio tools are mocked.

Images are complete original neutral RGBA PNGs. Audio is the existing synthetic
silence fixture with invented anchors; these tests do not assert human QA.
"""
import base64
import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from storymotion.dashboard import Dashboard
from storymotion.engine import ROOT
from storymotion.raster_revision import pinned_path
from storymotion.security import WorkflowError, digest, file_hash
from audio_fixture import imported, no_media, source_job
from test_raster_io import chunk, png


class RasterRevisionTests(PackFixtureCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.raster-revision-test-', dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.d = Dashboard(Path(self.temp.name).resolve())
        self.addCleanup(self.d.clear_keys)
        self.parent = source_job(self.d)
        self.pixels = png()

    def body(self, job=None):
        video = self.d.renders.video_input(self.d.job(job or self.parent))
        return {'image_base64': base64.b64encode(self.pixels).decode(), 'container': 'png',
                'expected_source_sha256': hashlib.sha256(self.pixels).hexdigest(),
                'approved_by': 'Synthetic raster contract operator',
                'rights_note': 'Original neutral geometric fixture; no customer media', 'rights_confirmed': True,
                'views': [{'scene_id': scene['id'], 'crop': {'x': 0, 'y': 0, 'width': 1, 'height': 1},
                           'highlight': {'x': .2, 'y': .2, 'width': .3, 'height': .3},
                           'label': 'Test ayrıntısı', 'camera': scene['camera']} for scene in video['scenes']]}

    def decoder(self, argv, **kwargs):
        self.assertEqual(argv[:3], ['node', ROOT / 'tools/raster.mjs', 'normalize'])
        Path(argv[-1]).write_bytes(png())
        return b'{"width":64,"height":64,"format":"png"}'

    def image(self, parent=None, body=None):
        parent = parent or self.parent
        with patch('storymotion.engine.checked_process', side_effect=self.decoder):
            return self.d.raster.import_local(parent, body or self.body(parent))

    def edit(self, job):
        plan = self.d.renders.edit_plan(job, 'hyperframes')['edit_plan']
        return self.d.edits.create(job, {'engine': 'hyperframes', 'expected_plan_sha256': plan['plan_sha256'],
                                        'scene_id': plan['scenes'][0]['id'], 'property': 'heading',
                                        'value': 'Seçilen ayrıntıya yakından bakalım.'})['child_job']

    def state(self):
        with self.d.connection() as db:
            records = {name: [tuple(row) for row in db.execute('SELECT * FROM ' + name + ' ORDER BY 1')]
                       for name in ('dashboard_jobs', 'dashboard_raster_heads', 'dashboard_raster_revisions', 'dashboard_events')}
        files = {str(path.relative_to(self.d.workspace)): file_hash(path)
                 for path in self.d.workspace.rglob('*') if path.is_file() and path.name != 'jobs.sqlite3'}
        return records, files

    def test_explicit_import_is_immutable_idempotent_and_does_not_render(self):
        original = copy.deepcopy(self.d.job(self.parent))
        body = self.body()
        first = self.image(body=body)
        child = first['child_job']
        before = self.state()
        second = self.image(body=body)
        self.assertEqual(first['child_job'], second['child_job'])
        self.assertFalse(first['reused'])
        self.assertTrue(second['reused'])
        self.assertEqual(self.state(), before)
        self.assertEqual(self.d.job(self.parent), original)
        self.assertEqual(len(self.d.jobs()), 2)
        self.assertEqual(first['provider_calls'], 0)
        self.assertFalse(first['render_started'])
        self.assertFalse(first['publication_ready'])
        self.assertEqual(first['job']['status'], 'queued')
        video = self.d.renders.video_input(self.d.job(child))
        self.assertEqual(video, self.d.raster.guard(child))
        self.assertEqual(video['raster']['asset']['source_sha256'], body['expected_source_sha256'])
        self.assertEqual(file_hash(self.d.output(child) / 'raster/image.png'), video['raster']['asset']['sha256'])
        self.assertEqual(json.loads((self.d.output(child) / 'raster.json').read_text()), video['raster'])
        for engine in ('hyperframes', 'remotion'):
            self.assertIsNone(self.d.renders.row(child, engine))
            self.assertEqual(self.d.reviews.state(child, engine)['status'], 'not_started')
            self.assertFalse(self.d.renders.edit_plan(child, engine)['render_started'])
        self.assertFalse(list(self.d.workspace.glob('raster-import-*')))

    def test_replacing_crop_invalidates_old_raster_and_dependent_edit_without_silent_rollback(self):
        body = self.body()
        a = self.image(body=body)['child_job']
        edited = self.edit(a)
        changed = copy.deepcopy(body)
        changed['views'][0]['crop'] = {'x': .1, 'y': .1, 'width': .8, 'height': .8}
        b = self.image(body=changed)['child_job']
        self.assertNotEqual(a, b)
        self.d.raster.guard(b)
        for job in (a, edited):
            with self.subTest(job=job), self.assertRaises(WorkflowError):
                self.d.renders.video_input(self.d.job(job))
        before = self.state()
        with self.assertRaisesRegex(WorkflowError, 'superseded'):
            self.image(body=body)
        self.assertEqual(self.state(), before)
        with self.d.connection() as db:
            self.assertEqual(db.execute('SELECT child FROM dashboard_raster_heads WHERE parent=?', (self.parent,)).fetchone()[0], b)

    def test_new_source_image_hash_has_new_immutable_child_even_when_normalized_pixels_match(self):
        first = self.image()['child_job']
        self.pixels = png(extra=chunk(b'tEXt', b'Comment\0Second original fixture selection'))
        second = self.image()['child_job']
        a = self.d.job(first)['payload']['template']['template']['video']['raster']['asset']
        b = self.d.raster.guard(second)['raster']['asset']
        self.assertNotEqual(first, second)
        self.assertEqual(a['sha256'], b['sha256'])
        self.assertNotEqual(a['source_sha256'], b['source_sha256'])
        with self.assertRaises(WorkflowError):
            self.d.raster.guard(first)

    def test_audio_to_raster_to_edit_preserves_exact_audio_words_and_rebinds_scene_timing(self):
        with no_media():
            audio = imported(self.d, self.parent)['child_job']
        source = self.d.renders.video_input(self.d.job(audio))
        body = self.body(audio)
        body['views'][0]['camera'] = 'locked' if source['scenes'][0]['camera'] != 'locked' else 'push-in'
        raster = self.image(audio, body)['child_job']
        raster_video = self.d.raster.guard(raster)
        edited = self.edit(raster)
        edit_video = self.d.edits.guard(edited)
        for child, video in ((raster, raster_video), (edited, edit_video)):
            with self.subTest(child=child):
                self.assertEqual(source['audio'], video['audio'])
                self.assertEqual(source['script'], video['script'])
                self.assertEqual(source['cues'], video['cues'])
                self.assertEqual(source['audio_timing']['words'], video['audio_timing']['words'])
                self.assertEqual(video['audio_timing']['scene_sha256'], digest(video['scenes']))
                self.assertEqual(file_hash(self.d.output(child) / video['audio']['file']), video['audio']['sha256'])
                self.assertEqual(json.loads((self.d.output(child) / 'audio-timing.json').read_text()), video['audio_timing'])
                self.assertEqual(file_hash(self.d.output(child) / 'raster/image.png'), raster_video['raster']['asset']['sha256'])
                for engine in ('hyperframes', 'remotion'):
                    self.assertIsNone(self.d.renders.row(child, engine))
                    self.assertEqual(self.d.reviews.state(child, engine)['status'], 'not_started')
                    self.d.renders.edit_plan(child, engine)
        self.assertNotEqual(source['audio_timing']['scene_sha256'], raster_video['audio_timing']['scene_sha256'])
        self.assertNotEqual(raster_video['audio_timing']['scene_sha256'], edit_video['audio_timing']['scene_sha256'])
        with self.assertRaises(WorkflowError):
            self.d.audio.base(raster)
        with self.assertRaises(WorkflowError):
            self.d.raster.base(edited)

    def test_new_audio_invalidates_raster_and_edit_from_previous_audio(self):
        with no_media():
            audio = imported(self.d, self.parent)['child_job']
        raster = self.image(audio)['child_job']
        edited = self.edit(raster)
        with no_media():
            next_audio = imported(self.d, self.parent, approved_by='New synthetic approval')['child_job']
        self.assertNotEqual(next_audio, audio)
        for child in (raster, edited):
            with self.subTest(child=child), self.assertRaises(WorkflowError):
                self.d.audio.guard(child)
        self.d.raster.guard(self.image(next_audio)['child_job'])

    def test_invalid_upload_metadata_and_bytes_leave_zero_child_zero_files(self):
        original = self.state()
        changes = [
            {'rights_confirmed': False}, {'approved_by': ''}, {'rights_note': ''},
            {'expected_source_sha256': 'a' * 64}, {'image_base64': 'not-base64?'},
            {'image_base64': 'https://example.invalid/image.png'}, {'container': 'svg'},
            {'path': '/private/image.png'}, {'url': 'https://example.invalid/image.png'},
            {'image_base64': base64.b64encode(b'<svg/>').decode(), 'expected_source_sha256': hashlib.sha256(b'<svg/>').hexdigest()},
        ]
        with patch('storymotion.engine.checked_process') as decoder:
            for change in changes:
                body = self.body()
                body.update(change)
                with self.subTest(fields=list(change)), self.assertRaises(WorkflowError):
                    self.d.raster.import_local(self.parent, body)
                self.assertEqual(self.state(), original)
            decoder.assert_not_called()

    def test_invalid_views_leave_zero_child_zero_files_after_decode(self):
        before = self.state()
        changes = [lambda b: b['views'].pop(), lambda b: b['views'].reverse(),
                   lambda b: b['views'][0].update(scene_id='another-scene'),
                   lambda b: b['views'][0].update(label='<script>bad</script>'),
                   lambda b: b['views'][0]['crop'].update(x=.9, width=.2),
                   lambda b: b['views'][0].update(camera='arbitrary-camera')]
        for change in changes:
            body = self.body()
            change(body)
            with self.subTest(change=change), self.assertRaises(WorkflowError):
                self.image(body=body)
            self.assertEqual(self.state(), before)

    def test_invalid_json_types_are_domain_errors_with_zero_child_zero_files(self):
        before = self.state()
        for bad in (None, [], True, 'not-an-object'):
            with self.subTest(body_type=type(bad).__name__), self.assertRaises(WorkflowError):
                self.d.raster.import_local(self.parent, bad)
            self.assertEqual(self.state(), before)
        for field, bad in (('container', []), ('container', {}), ('image_base64', []),
                           ('approved_by', True), ('rights_confirmed', 1), ('views', None)):
            value = self.body()
            value[field] = bad
            with self.subTest(field=field, kind=type(bad).__name__), self.assertRaises(WorkflowError):
                self.image(body=value)
            self.assertEqual(self.state(), before)

    def test_other_profiles_and_recursive_raster_sources_are_rejected_before_decode(self):
        for account in ('sample-reflection', 'sample-flow', 'sample-series'):
            parent = source_job(self.d, account)
            before = self.state()
            with patch('storymotion.engine.checked_process') as decoder, self.assertRaises(WorkflowError):
                self.d.raster.import_local(parent, self.body(parent))
            decoder.assert_not_called()
            self.assertEqual(self.state(), before)
        child = self.image()['child_job']
        before = self.state()
        with patch('storymotion.engine.checked_process') as decoder, self.assertRaises(WorkflowError):
            self.d.raster.import_local(child, self.body(child))
        decoder.assert_not_called()
        self.assertEqual(self.state(), before)

    def test_decoder_failure_and_corrupted_copy_leave_zero_child_zero_files(self):
        before = self.state()
        with patch('storymotion.engine.checked_process', side_effect=WorkflowError('Synthetic decode failure')), self.assertRaises(WorkflowError):
            self.d.raster.import_local(self.parent, self.body())
        self.assertEqual(self.state(), before)
        copyfile = shutil.copyfile
        def corrupted(source, target, *args, **kwargs):
            copied = copyfile(source, target, *args, **kwargs)
            if Path(target).name == 'image.png':
                Path(target).write_bytes(b'corrupt snapshot')
            return copied
        with patch('shutil.copyfile', side_effect=corrupted), self.assertRaises(WorkflowError):
            self.image()
        self.assertEqual(self.state(), before)

    def test_changed_or_missing_pinned_pixels_and_manifest_invalidate_without_repair(self):
        child = self.image()['child_job']
        out = self.d.output(child)
        target = out / 'raster/image.png'
        raster = out / 'raster.json'
        saved, manifest = target.read_bytes(), raster.read_bytes()
        for alter in (lambda: target.write_bytes(saved + b'trailing'), lambda: target.unlink(), lambda: raster.write_text('{}')):
            alter()
            for engine in ('hyperframes', 'remotion'):
                with self.subTest(engine=engine), self.assertRaises(WorkflowError):
                    self.d.renders.edit_plan(child, engine)
            before = self.state()
            with self.assertRaises(WorkflowError):
                self.image()
            self.assertEqual(self.state(), before)
            target.write_bytes(saved)
            raster.write_bytes(manifest)
            self.d.raster.guard(child)

    def test_pinned_pixel_symlinks_and_symlink_ancestors_are_rejected(self):
        child = self.image()['child_job']
        out = self.d.output(child)
        target = out / 'raster/image.png'
        data = target.read_bytes()
        other = self.d.workspace / 'neutral-other.png'
        other.write_bytes(data)
        target.unlink()
        target.symlink_to(other)
        with self.assertRaises(WorkflowError):
            self.d.raster.guard(child)
        self.assertEqual(other.read_bytes(), data)
        target.unlink()
        target.write_bytes(data)
        alias = self.d.workspace / 'alias-raster'
        alias.symlink_to(out / 'raster', target_is_directory=True)
        for root, relative in ((out, '/private/image.png'), (out, '../image.png'),
                               (self.d.workspace, 'alias-raster/image.png'), (alias, 'image.png')):
            with self.subTest(relative=relative), self.assertRaises(WorkflowError):
                pinned_path(root, relative)
        self.d.raster.guard(child)

    def test_payload_and_binding_records_cannot_be_rebound(self):
        child = self.image()['child_job']
        parent = self.d.job(self.parent)
        payload = copy.deepcopy(parent['payload'])
        payload['input']['title'] = 'Unexpected source title'
        with self.d.connection() as db:
            db.execute('UPDATE dashboard_jobs SET payload=? WHERE id=?', (json.dumps(payload), self.parent))
        with self.assertRaises(WorkflowError):
            self.d.raster.guard(child)
        with self.d.connection() as db:
            db.execute('UPDATE dashboard_jobs SET payload=? WHERE id=?', (json.dumps(parent['payload']), self.parent))
            db.execute('UPDATE dashboard_raster_revisions SET binding_sha256=? WHERE child=?', ('0' * 64, child))
        with self.assertRaises(WorkflowError):
            self.d.raster.guard(child)

    def test_audio_snapshot_corruption_is_atomic_without_child_or_persistent_files(self):
        with no_media():
            audio = imported(self.d, self.parent)['child_job']
        before = self.state()
        copyfile = shutil.copyfile
        def corrupted(source, target, *args, **kwargs):
            copied = copyfile(source, target, *args, **kwargs)
            if Path(target).suffix == '.wav':
                Path(target).write_bytes(b'corrupt synthetic audio snapshot')
            return copied
        with patch('shutil.copyfile', side_effect=corrupted), self.assertRaises(WorkflowError):
            self.image(audio)
        self.assertEqual(self.state(), before)


if __name__ == '__main__':
    unittest.main()
