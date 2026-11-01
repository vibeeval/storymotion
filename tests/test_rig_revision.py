from test_catalog_integration import authenticated_handler
from pack_fixture_case import PackFixtureCase
"""Manual neutral rig revision integrity with synthetic silence and invented cues.

These tests exercise validation, immutable revisions, local source preparation and
receipt plumbing. NOT_MEDIA bytes are explicit download-binding sentinels. No
renderer, media decoder, provider, phoneme inference or human acceptance runs.
"""
import contextlib
import copy
import json
import math
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from storymotion.dashboard import Dashboard, Handler
from storymotion.edit_plan import verify_staged_assets
from storymotion.engine import Engine, ROOT
from storymotion.rig_revision import RIG_TIMING_MARKER
from storymotion.security import WorkflowError, canonical, digest, file_hash, write_json
from storymotion.viseme import MOUTH_VALUES
from audio_fixture import imported, no_media, source_job
from test_catalog_integration import MemoryConnection


ACCOUNTS = ('sample-flow', 'sample-series')
ACTOR = 'Synthetic rig contract operator'


class RigRevisionTests(PackFixtureCase):
    def setUp(self):
        # Canonical project-local temp path also exercises the no-symlink asset IO.
        self.tmp = tempfile.TemporaryDirectory(prefix='.rig-revision-test-', dir=ROOT)
        self.addCleanup(self.tmp.cleanup)
        self.d = Dashboard(Path(self.tmp.name).resolve())
        self.addCleanup(self.d.clear_keys)
        self.engines = []
        self.addCleanup(self.close_engines)
        native = patch('storymotion.engine.checked_process', side_effect=AssertionError('No native process permitted'))
        native.start()
        self.addCleanup(native.stop)

    def close_engines(self):
        for engine in self.engines:
            if engine._store is not None:
                engine.store.db.close()

    def audio(self, account='sample-flow'):
        root = source_job(self.d, account)
        with no_media():
            audio = imported(self.d, root)['child_job']
        return root, audio

    def body(self, job):
        template = self.d.rigs.template(job)
        spec = copy.deepcopy(template['spec'])
        spec['provenance'].update(method='synthetic_test', tool='Original hand-authored contract fixture',
            note='Invented mouth annotations for synthetic silence; not phonetic or perceptual acceptance',
            approved_by=ACTOR, rights_confirmed=True)
        duration, end = spec['audio_duration_seconds'], spec['timeline_duration_seconds']
        # All nine values are explicitly authored; no word/letter/audio inference.
        boundaries = [0, .1, .2, .3, .4, .5, .6, .7, .8, duration]
        spec['mouthCues'] = [{'start': boundaries[i], 'end': boundaries[i + 1], 'value': value}
                             for i, value in enumerate('ABCDEFGHX')]
        spec['visual_tracks'] = {'blinks': [{'start': .2, 'end': .3}, {'start': 1, 'end': 1.1}],
            'head': [{'time': 0, 'rotate': 0, 'x': 0, 'y': 0},
                     {'time': .5, 'rotate': 4, 'x': 6, 'y': -3},
                     {'time': end, 'rotate': 0, 'x': 0, 'y': 0}]}
        return {'expected_video_sha256': template['expected_video_sha256'], 'spec': spec,
                'approved_by': ACTOR, 'review_pending': True}

    def child(self, job, body=None):
        return self.d.rigs.create(job, self.body(job) if body is None else body)['child_job']

    def state(self):
        with self.d.connection() as db:
            tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            records = {table: [tuple(row) for row in db.execute('SELECT * FROM ' + table + ' ORDER BY 1')]
                       for table in tables}
        files = {str(path.relative_to(self.d.workspace)): file_hash(path)
                 for path in self.d.workspace.rglob('*')
                 if path.is_file() and path.name not in {'jobs.sqlite3', 'jobs.sqlite3-wal', 'jobs.sqlite3-shm'}}
        return records, files

    def edit(self, job, prop='heading'):
        plan = self.d.renders.edit_plan(job, 'hyperframes')['edit_plan']
        scene = plan['scenes'][0]
        value = 'Yalnız bu sahnenin başlığı değişti.' if prop == 'heading' else (
            'push-in' if scene['camera'] == 'locked' else 'locked')
        return self.d.edits.create(job, {'engine': 'hyperframes', 'expected_plan_sha256': plan['plan_sha256'],
            'scene_id': scene['id'], 'property': prop, 'value': value})['child_job']

    def prepared(self, child, engine, workspace=None):
        video = self.d.renders.video_input(self.d.job(child))
        path = self.d.output(child) / ('render-input-' + engine + '.json')
        write_json(path, video)
        runtime = Engine(self.d.workspace / (workspace or 'unit-engine-' + engine))
        self.engines.append(runtime)
        with no_media():
            job = runtime.create(path, render_engine=engine)['job']
            runtime.run(job, 'prepare')
        return runtime, job, runtime.payload(job), runtime.directory(job)

    def render_sentinel(self, child, engine):
        """Hash/receipt plumbing only; never claim these bytes are an MP4."""
        runtime, job, payload, out = self.prepared(child, engine, 'renders')
        video = payload['brief']
        (out / 'render-1080.mp4').write_bytes(b'NOT_MEDIA: synthetic rig download binding sentinel')
        receipt = {'engine': engine, 'render_sha256': file_hash(out / 'render-1080.mp4'),
            'execution_fingerprint': payload['execution']['fingerprint'],
            'audio_timing_sha256': digest(video['audio_timing']), 'audio_sha256': payload['audio_sha256'],
            'rig_sha256': digest(video['rig']), 'rig_definition_sha256': video['rig']['rig_sha256'],
            'synthetic_test_sentinel': True, 'actual_render_decode': False}
        write_json(out / 'render-engine.json', receipt)
        runtime.store.set_stage(job, 'render', 'complete',
            {name: file_hash(out / name) for name in ('render-1080.mp4', 'render-engine.json')})
        with self.d.connection() as db:
            db.execute('INSERT OR REPLACE INTO dashboard_renders VALUES(?,?,?,?,?,?)',
                       (child, engine, job, 'complete', None, 1))
        return runtime, job, payload, out

    def test_empty_template_is_read_only_and_requires_explicit_manual_annotations(self):
        for account in ACCOUNTS:
            _, audio = self.audio(account)
            before = self.state()
            template = self.d.rigs.template(audio)
            self.assertEqual(self.state(), before)
            self.assertEqual(template['spec']['mouthCues'], [])
            self.assertFalse(template['spec']['provenance']['rights_confirmed'])
            self.assertEqual(template['spec']['provenance']['human_phonetic'], 'pending')
            self.assertEqual(template['spec']['provenance']['human_visual'], 'pending')
            self.assertEqual(template['rig_descriptor']['license'], 'original_project_vectors')
            body = self.body(audio)
            body['spec']['mouthCues'] = []
            with self.assertRaises(WorkflowError):
                self.d.rigs.create(audio, body)
            self.assertEqual(self.state(), before)

    def test_two_account_imports_are_immutable_idempotent_and_no_acceptance_is_transferred(self):
        children = []
        for account in ACCOUNTS:
            root, audio = self.audio(account)
            original = copy.deepcopy(self.d.job(audio))
            # A previous job's persisted review is never copied into a new child.
            with self.d.connection() as db:
                db.execute('INSERT INTO dashboard_reviews VALUES(?,?,?,?)', (audio, 'hyperframes', 'old-review', '{}'))
            body = self.body(audio)
            result = self.d.rigs.create(audio, body)
            child = result['child_job']; children.append(child)
            before = self.state()
            reused = self.d.rigs.create(audio, body)
            self.assertEqual(reused['child_job'], child)
            self.assertTrue(reused['reused'])
            self.assertEqual(self.state(), before)
            self.assertEqual(self.d.job(audio), original)
            video = self.d.rigs.guard(child)
            self.assertNotEqual(child, audio)
            self.assertNotIn('audio_revision', self.d.job(child)['payload'])
            self.assertEqual(video['rig'], body['spec'])
            self.assertEqual(set(cue['value'] for cue in video['rig']['mouthCues']), MOUTH_VALUES)
            self.assertEqual(video['audio_timing']['viseme'], RIG_TIMING_MARKER)
            self.assertFalse(result['publication_ready']); self.assertFalse(result['render_started'])
            self.assertEqual(result['provider_calls'], 0)
            self.assertEqual(result['human_phonetic'], 'pending'); self.assertEqual(result['human_visual'], 'pending')
            self.assertEqual(json.loads((self.d.output(child) / 'rig.json').read_text()), video['rig'])
            self.assertEqual(file_hash(self.d.output(child) / video['audio']['file']), video['audio']['sha256'])
            for engine in ('hyperframes', 'remotion'):
                self.assertIsNone(self.d.renders.row(child, engine))
                self.assertEqual(self.d.reviews.state(child, engine)['status'], 'not_started')
        self.assertEqual(len(set(children)), 2)

    def test_invalid_source_hash_range_schema_and_provenance_leave_zero_child_zero_write(self):
        _, audio = self.audio()
        before = self.state()
        variants = [
            lambda x: x.update(expected_video_sha256='0' * 64),
            lambda x: x.update(review_pending=False), lambda x: x.update(approved_by=''),
            lambda x: x.update(file='/private/rig.json'),
            lambda x: x['spec'].update(source_audio_sha256='1' * 64),
            lambda x: x['spec'].update(source_script_sha256='2' * 64),
            lambda x: x['spec'].update(source_timing_sha256='3' * 64),
            lambda x: x['spec'].update(rig_sha256='4' * 64),
            lambda x: x['spec'].update(account='sample-series'),
            lambda x: x['spec'].update(fps=29), lambda x: x['spec'].update(fps=True),
            lambda x: x['spec'].update(audio_duration_seconds=19),
            lambda x: x['spec'].update(timeline_duration_seconds=21),
            lambda x: x['spec']['mouthCues'][1].update(start=.101),
            lambda x: x['spec']['mouthCues'][1].update(start=.099),
            lambda x: x['spec']['mouthCues'][0].update(start=-.1),
            lambda x: x['spec']['mouthCues'][0].update(end=0),
            lambda x: x['spec']['mouthCues'][-1].update(end=19.99),
            lambda x: x['spec']['mouthCues'][0].update(value='Q'),
            lambda x: x['spec']['mouthCues'][0].update(end=math.nan),
            lambda x: x['spec']['mouthCues'][0].update(confidence=1),
            lambda x: x['spec']['visual_tracks']['blinks'][0].update(end=.201),
            lambda x: x['spec']['visual_tracks']['blinks'][1].update(start=.25),
            lambda x: x['spec']['visual_tracks']['head'][0].update(time=.01),
            lambda x: x['spec']['visual_tracks']['head'][-1].update(time=19.99),
            lambda x: x['spec']['visual_tracks']['head'][1].update(rotate=8.01),
            lambda x: x['spec']['visual_tracks']['head'][1].update(x=13),
            lambda x: x['spec']['provenance'].update(method='amplitude_inference'),
            lambda x: x['spec']['provenance'].update(rights_confirmed=False),
            lambda x: x['spec']['provenance'].update(approved_by='Different actor'),
            lambda x: x['spec']['provenance'].update(human_phonetic='pass'),
            lambda x: x['spec']['provenance'].update(human_visual='pass'),
            lambda x: x['spec']['provenance'].update(note='Invalid\u202eannotation direction control'),
        ]
        for index, mutate in enumerate(variants):
            value = self.body(audio); mutate(value)
            with self.subTest(index=index), self.assertRaises((WorkflowError, ValueError)):
                self.d.rigs.create(audio, value)
            self.assertEqual(self.state(), before)

    def test_unsupported_silent_and_visual_descendant_sources_cannot_create_a_rig(self):
        for account in ('sample-reflection', 'sample-mechanism'):
            _, audio = self.audio(account)
            before = self.state()
            with self.assertRaises(WorkflowError): self.d.rigs.template(audio)
            self.assertEqual(self.state(), before)
        silent = source_job(self.d, 'sample-flow')
        before = self.state()
        with self.assertRaises(WorkflowError): self.d.rigs.template(silent)
        self.assertEqual(self.state(), before)
        _, audio = self.audio('sample-series')
        edited = self.edit(audio)
        before = self.state()
        with self.assertRaises(WorkflowError): self.d.rigs.template(edited)
        self.assertEqual(self.state(), before)

    def test_replacement_supersedes_old_rig_and_descendant_without_silent_rollback(self):
        _, audio = self.audio()
        body = self.body(audio); first = self.child(audio, body)
        edited = self.edit(first)
        changed = copy.deepcopy(body); changed['spec']['mouthCues'][0]['value'] = 'X'
        second = self.child(audio, changed)
        self.assertNotEqual(first, second); self.d.rigs.guard(second)
        before = self.state()
        for job in (first, edited):
            with self.subTest(job=job), self.assertRaises(WorkflowError): self.d.audio.guard(job)
        with self.assertRaises(WorkflowError): self.child(audio, body)
        with self.assertRaises(WorkflowError): self.d.rigs.template(first)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.child(audio, changed), second)

    def test_heading_and_camera_edits_keep_manual_tracks_audio_and_words_but_rebind_scene_timing(self):
        for account in ACCOUNTS:
            _, audio = self.audio(account)
            rig = self.child(audio)
            source = self.d.rigs.guard(rig)
            for prop in ('heading', 'camera'):
                child = self.edit(rig, prop)
                video = self.d.renders.video_input(self.d.job(child))
                self.assertEqual(video['audio'], source['audio'])
                self.assertEqual(video['cues'], source['cues'])
                self.assertEqual(video['audio_timing']['words'], source['audio_timing']['words'])
                self.assertEqual(video['rig']['mouthCues'], source['rig']['mouthCues'])
                self.assertEqual(video['rig']['visual_tracks'], source['rig']['visual_tracks'])
                self.assertEqual(video['rig']['provenance'], source['rig']['provenance'])
                self.assertEqual(video['rig']['source_timing_sha256'], digest(video['audio_timing']))
                self.assertNotEqual(video['rig']['source_timing_sha256'], source['rig']['source_timing_sha256'])
                self.assertEqual(video['audio_timing']['scene_sha256'], digest(video['scenes']))
                self.assertEqual(file_hash(self.d.output(child) / video['audio']['file']), source['audio']['sha256'])
                self.assertEqual(json.loads((self.d.output(child) / 'rig.json').read_text()), video['rig'])
                self.assertEqual(self.d.reviews.state(child, 'remotion')['status'], 'not_started')
                with self.assertRaises(WorkflowError): self.d.audio.base(child)

    def test_stored_rig_binding_timing_and_audio_tamper_invalidate_without_repair(self):
        _, audio = self.audio()
        body = self.body(audio); child = self.child(audio, body)
        video = self.d.rigs.guard(child)
        for relative in ('rig.json', 'rig-binding.json', 'audio-timing.json', video['audio']['file']):
            path = self.d.output(child) / relative; original = path.read_bytes()
            path.write_bytes(b'{}' if path.suffix == '.json' else b'TAMPERED_SYNTHETIC_AUDIO')
            before = self.state()
            with self.subTest(relative=relative), self.assertRaises(WorkflowError): self.d.audio.guard(child)
            with self.assertRaises(WorkflowError): self.child(audio, body)
            self.assertEqual(self.state(), before)
            path.write_bytes(original); self.d.rigs.guard(child)

    def test_source_payload_and_child_payload_tamper_fail_closed(self):
        _, audio = self.audio()
        child = self.child(audio)
        for job in (audio, child):
            original = self.d.job(job)['payload']; changed = copy.deepcopy(original)
            changed['input']['title'] = 'Unexpected payload mutation'
            with self.d.connection() as db: db.execute('UPDATE dashboard_jobs SET payload=? WHERE id=?', (canonical(changed), job))
            with self.assertRaises(WorkflowError): self.d.rigs.guard(child)
            with self.d.connection() as db: db.execute('UPDATE dashboard_jobs SET payload=? WHERE id=?', (canonical(original), job))
            self.d.rigs.guard(child)

    def test_reimported_audio_invalidates_rig_scene_edit_and_bound_render_download(self):
        root, audio = self.audio()
        rig = self.child(audio); edited = self.edit(rig)
        self.render_sentinel(rig, 'hyperframes')
        with no_media():
            self.assertEqual(self.d.renders.download(rig, 'hyperframes', 'render-1080.mp4'),
                             b'NOT_MEDIA: synthetic rig download binding sentinel')
        with no_media(): imported(self.d, root, approved_by='New explicit synthetic audio operator')
        for child in (audio, rig, edited):
            with self.subTest(child=child), self.assertRaises(WorkflowError): self.d.audio.guard(child)
        self.assertEqual(self.d.renders.state(rig, 'hyperframes')['status'], 'invalidated')
        with self.assertRaises(WorkflowError): self.d.renders.download(rig, 'hyperframes', 'render-1080.mp4')

    def test_two_engines_prepare_owned_rig_assets_edit_plan_and_source_hashes(self):
        for account in ACCOUNTS:
            _, audio = self.audio(account)
            child = self.child(audio); video = self.d.rigs.guard(child)
            for engine in ('hyperframes', 'remotion'):
                runtime, ident, payload, out = self.prepared(child, engine)
                plan = json.loads((out / 'edit-plan.json').read_text())
                self.assertEqual(json.loads((out / 'rig.json').read_text()), video['rig'])
                self.assertEqual(plan['rig_sha256'], digest(video['rig']))
                self.assertEqual(plan['rig_mode'], 'inset' if account == 'sample-flow' else 'serial-courier')
                self.assertEqual(plan['audio_timing_sha256'], digest(video['audio_timing']))
                self.assertEqual(len(plan['rig_assets']), 2)
                for asset in plan['rig_assets']:
                    self.assertEqual(file_hash(ROOT / asset['path']), asset['sha256'])
                    self.assertEqual(file_hash(out / asset['staged_file']), asset['sha256'])
                self.assertEqual(payload['execution']['fingerprint'], self.d.runtime_execution)
                html = (out / 'index.html').read_text()
                self.assertIn('neutral-rig-mouth-A', html); self.assertIn('neutral-rig-head', html)
                self.assertIn('rig-camera', html); self.assertIn('tl.set(', html)
                self.assertIn('audio', html)
                self.assertEqual(file_hash(out / 'assets/narration.wav'), video['audio']['sha256'])
                verify_staged_assets(payload, out)
                if engine == 'remotion':
                    props = json.loads((out / 'remotion-props.json').read_text())
                    self.assertEqual(props['brief']['rig'], video['rig'])
                    self.assertEqual(props['rig_definition'], json.loads((ROOT / 'renderers/neutral-rig.json').read_text()))
                    self.assertEqual(props['edit_plan'], plan)
                    self.assertIn("from './assets/rig/rig-motion.mjs'", (out / 'remotion-entry.jsx').read_text())
                source = out / 'assets/rig/definition.json'; raw = source.read_bytes(); source.write_bytes(b'{}')
                with self.assertRaises(WorkflowError): verify_staged_assets(payload, out)
                source.write_bytes(raw); verify_staged_assets(payload, out)
                self.assertEqual(runtime.store.stage(ident, 'render')['status'], 'pending')

    def test_late_source_change_and_audio_copy_corruption_leave_zero_child_zero_write(self):
        _, audio = self.audio()
        body = self.body(audio); before = self.state(); original = self.d.job; count = 0
        def late(key):
            nonlocal count
            row = original(key)
            if key == audio:
                count += 1
                if count >= 2: row['payload']['input']['title'] = 'Synthetic concurrent change'
            return row
        with patch.object(self.d, 'job', side_effect=late), self.assertRaises(WorkflowError):
            self.child(audio, body)
        self.assertEqual(self.state(), before)
        copier = shutil.copyfile
        def corrupt(source, target, *args, **kwargs):
            result = copier(source, target, *args, **kwargs)
            Path(target).write_bytes(b'Corrupt synthetic rig audio copy')
            return result
        with patch('storymotion.rig_revision.shutil.copyfile', side_effect=corrupt), self.assertRaises(WorkflowError):
            self.child(audio, body)
        self.assertEqual(self.state(), before)
        self.assertFalse(list(self.d.workspace.glob('rig-import-*')))

    def test_rollback_after_owned_publish_removes_only_uncommitted_output(self):
        _, audio = self.audio(); body = self.body(audio); before = self.state()
        original = self.d.connection; published = []; dashboard = self.d
        class Fault:
            def __init__(self, db): self.db, self.child = db, None
            def __getattr__(self, key): return getattr(self.db, key)
            def execute(self, sql, *args):
                if sql.startswith('INSERT INTO dashboard_jobs'): self.child = args[0][0]
                if sql.startswith('INSERT INTO dashboard_events') and self.child:
                    published.append((dashboard.output(self.child) / 'rig.json').is_file())
                    raise sqlite3.OperationalError('Synthetic rollback after rig publication')
                return self.db.execute(sql, *args)
        @contextlib.contextmanager
        def connection():
            with original() as db: yield Fault(db)
        with patch.object(self.d, 'connection', connection), self.assertRaises(sqlite3.OperationalError):
            self.child(audio, body)
        self.assertEqual(published, [True]); self.assertEqual(self.state(), before)
        self.assertFalse(list(self.d.workspace.glob('rig-import-*')))

    def test_real_commit_then_acknowledgement_error_preserves_durable_result_and_reuses_it(self):
        _, audio = self.audio(); body = self.body(audio); prior = {row['id'] for row in self.d.jobs()}
        original = self.d.connection; acknowledged = []
        @contextlib.contextmanager
        def connection():
            with original() as db:
                yield db
                changed = db.in_transaction and db.total_changes > 0
            if changed and not acknowledged:
                acknowledged.append(True)
                raise sqlite3.OperationalError('Synthetic acknowledgement error after real rig commit')
        with patch.object(self.d, 'connection', connection), self.assertRaises(sqlite3.OperationalError):
            self.child(audio, body)
        self.assertEqual(acknowledged, [True])
        children = [row['id'] for row in self.d.jobs() if row['id'] not in prior]
        self.assertEqual(len(children), 1); child = children[0]
        self.d.rigs.guard(child)
        self.assertEqual(json.loads((self.d.output(child) / 'rig.json').read_text()), body['spec'])
        before = self.state(); self.assertEqual(self.child(audio, body), child)
        self.assertEqual(self.state(), before)
        self.assertFalse(list(self.d.workspace.glob('rig-import-*')))

    def test_http_template_and_import_require_same_origin_exact_body_and_explicit_review(self):
        _, audio = self.audio(); server = SimpleNamespace(server_address=('127.0.0.1', 43333), dashboard=self.d)
        def call(action, body, expected, origin='http://127.0.0.1:43333', host='127.0.0.1:43333', local=True):
            raw = canonical(body).encode()
            headers = ['POST /api/jobs/' + audio + '/' + action + ' HTTP/1.0', 'Host: ' + host,
                'Origin: ' + origin, 'Content-Type: application/json', 'Content-Length: ' + str(len(raw))]
            if local: headers.append('X-Storymotion-Local: 1')
            connection = MemoryConnection(('\r\n'.join(headers) + '\r\n\r\n').encode() + raw)
            authenticated_handler(connection, ('127.0.0.1', 1), server)
            head, result = bytes(connection.output).split(b'\r\n\r\n', 1)
            self.assertEqual(int(head.split()[1]), expected, result)
            return json.loads(result)
        body = self.body(audio); before = self.state()
        call('rig-template', {}, 403, origin='https://attacker.test')
        call('rig-import', body, 403, host='attacker.test')
        call('rig-import', body, 403, local=False)
        call('rig-import', {**body, 'review_pending': False}, 400)
        call('rig-import', {**body, 'path': '/private/rig.json'}, 400)
        self.assertEqual(self.state(), before)
        self.assertEqual(call('rig-template', {}, 200)['expected_video_sha256'], body['expected_video_sha256'])
        result = call('rig-import', body, 200)
        self.assertFalse(result['publication_ready']); self.assertFalse(result['render_started'])
        self.assertEqual(result['provider_calls'], 0)


if __name__ == '__main__':
    unittest.main()
