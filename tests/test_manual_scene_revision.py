from test_catalog_integration import authenticated_handler
from pack_fixture_case import PackFixtureCase
"""Original/synthetic manual scene contracts, never creative or human acceptance.

Prepare emits owned SVG/HTML only. Packaging tests use explicit NOT_MEDIA
sentinels; no provider, browser, native renderer or audio decoder is invoked.
"""
import copy
import contextlib
import hashlib
import json
import shutil
import sqlite3
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from storymotion.dashboard import Dashboard, Handler
from storymotion.edit_plan import verify_staged_assets
from storymotion.engine import Engine, ROOT
from storymotion.security import WorkflowError, canonical, digest, file_hash, write_json
from storymotion.writing_context import canon, snapshot
from audio_fixture import imported, no_media
from test_writing_context import accepted_reference
from test_catalog_integration import MemoryConnection


ACCOUNTS = ('sample-reflection', 'sample-flow', 'sample-series')


def authored_fixture(account, accepted=True):
    brief = json.loads((ROOT / 'tests/fixtures/examples/edit-plans' / (account + '.json')).read_text())
    brief.pop('brand_identity', None)
    if account == 'sample-series' and accepted:
        binding = brief['production_context']
        reference = accepted_reference(binding['sources']['revision'])
        reference['objects'][0]['id'] = brief['continuity']['object_id']
        reference['objects'][0]['state'] = brief['continuity']['previous']
        reference['open_clues'][0]['object_id'] = brief['continuity']['object_id']
        reference['cast'] = [{k: character[k] for k in ('id', 'wardrobe')} for character in brief['creative']['characters']]
        binding['canon'] = snapshot('canon', account, canon(reference), None)
        binding['binding_sha256'] = digest({k: v for k, v in binding.items() if k != 'binding_sha256'})
    return brief


def manual_plan(video):
    account = video['brand']
    binding = video.get('production_context') or {}
    accepted = binding.get('canon')
    scenes = []
    for i, scene in enumerate(video['scenes']):
        if account == 'sample-reflection':
            kind, content = ('possibility-branches', {'left': 'Yoğun bir gün olabilir.', 'right': 'Başka bir ritim olabilir.', 'question': 'Hangi ayrıntıyı gözleyebilirim?'}) if i % 2 == 0 else (
                'observation', {'object': 'clock', 'prompt': 'Saatin yanındaki ayrıntıya bakalım.', 'observation': 'Şimdilik yalnız gördüğümü not ediyorum.'})
        elif account == 'sample-flow':
            kind, content = ('process-route', {'nodes': ['Girdi', 'Onay', 'Sonuç'], 'from_node': 0, 'to_node': 2}) if i % 2 == 0 else (
                'object-transform', {'object': 'document', 'before': 'Seçili kayıt', 'after': 'İşlenmiş kayıt'})
        else:
            clues = [row['id'] for row in accepted['data']['open_clues']] if accepted else ['nick-01']
            kind, content = ('clue-inspect', {'clue_id': clues[0], 'note': 'Aynı nesnenin küçük izine bakıyorum.'}) if i % 2 == 0 else (
                'canon-board', {'clue_ids': clues[:2], 'note': 'Yalnız kabul edilmiş izleri yan yana koydum.'})
        scenes.append({'scene_id': scene['id'], 'kind': kind, 'content': content,
                       'claim_indexes': [min(i, len(video['claims']) - 1)] if account != 'sample-series' else [],
                       'cue_indexes': [n for n, cue in enumerate(video['cues']) if cue['start'] < scene['end'] and cue['end'] > scene['start']],
                       'object_id': scene['object_id'], 'camera': scene['camera']})
    return {'schema_version': 1, 'recipe': 'manual-account-scenes-1', 'account': account,
            'canon_revision': accepted['revision'] if accepted else None, 'scenes': scenes}


class ManualSceneRevisionTests(PackFixtureCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.manual-plan-test-', dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.d = Dashboard(Path(self.temp.name).resolve())
        self.addCleanup(self.d.clear_keys)
        self.native = patch('storymotion.engine.checked_process', side_effect=AssertionError('No native process permitted'))
        self.native.start()
        self.addCleanup(self.native.stop)
        self.engines = []
        self.addCleanup(self.close_engines)

    def close_engines(self):
        for engine in self.engines:
            if engine._store is not None:
                engine.store.db.close()

    def source(self, account='sample-reflection', accepted=True, change=None):
        video = authored_fixture(account, accepted)
        if change:
            change(video)
        old = self.d.template(account, 'account-video')
        value = copy.deepcopy(old['template'])
        value['video'] = video
        saved = self.d.save_template({'account': account, 'format': 'account-video', 'revision': old['revision'], 'template': value})
        return self.d.enqueue({'account': account, 'format': 'account-video', 'title': video['title'], 'brief': video['brief'],
                               'content': video['script'], 'caption': video['caption'], 'provider': 'local', 'model': 'manual',
                               'task': 'text', 'template_revision': saved['revision']})['id']

    def body(self, job):
        video = self.d.renders.video_input(self.d.job(job))
        return {'plan': manual_plan(video), 'expected_video_sha256': digest(video),
                'approved_by': 'Synthetic manual plan operator', 'review_pending': True}

    def child(self, job, data=None):
        return self.d.plans.create(job, self.body(job) if data is None else data)['child_job']

    def edit(self, job, prop='heading'):
        plan = self.d.renders.edit_plan(job, 'hyperframes')['edit_plan']
        value = 'Bu sahnenin özgün başlığı değişti.' if prop == 'heading' else ('push-in' if plan['scenes'][0]['camera'] == 'locked' else 'locked')
        return self.d.edits.create(job, {'engine': 'hyperframes', 'expected_plan_sha256': plan['plan_sha256'],
                                        'scene_id': plan['scenes'][0]['id'], 'property': prop, 'value': value})['child_job']

    def state(self):
        with self.d.connection() as db:
            tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            records = {table: [tuple(row) for row in db.execute('SELECT * FROM ' + table + ' ORDER BY 1')] for table in tables}
        files = {str(path.relative_to(self.d.workspace)): file_hash(path)
                 for path in self.d.workspace.rglob('*') if path.is_file() and path.name != 'jobs.sqlite3'}
        return records, files

    def prepared(self, child, engine):
        out = self.d.output(child)
        video = self.d.renders.video_input(self.d.job(child))
        path = out / ('unit-input-' + engine + '.json')
        write_json(path, video)
        runtime = Engine(self.d.workspace / ('unit-engine-' + engine))
        self.engines.append(runtime)
        job = runtime.create(path, render_engine=engine)['job']
        runtime.run(job, 'prepare')
        return runtime, job, runtime.payload(job), runtime.directory(job)

    def delivered(self, child, engine):
        runtime, job, payload, out = self.prepared(child, engine)
        for name in ('render-1080.mp4', 'render-mobile.mp4', 'cover.png', 'cover-360.png'):
            (out / name).write_bytes(b'NOT_MEDIA: manual scene package binding sentinel:' + name.encode())
        for name in ('qa.json', 'check.json', 'browser-evidence.json'):
            write_json(out / name, {'synthetic_packaging_test': True, 'actual_render_decode_browser': False, 'human_acceptance': 'pending'})
        write_json(out / 'render-engine.json', {'engine': engine, 'render_sha256': file_hash(out / 'render-1080.mp4'),
                                               'execution_fingerprint': payload['execution']['fingerprint'],
                                               'scene_plan_sha256': digest(payload['brief']['scene_plan']),
                                               'synthetic_packaging_test': True, 'actual_render': False})
        runtime.perform('delivery', payload, out)
        return runtime, job, payload, out

    def test_three_profile_imports_are_immutable_idempotent_distinct_and_manual_review_pending(self):
        kinds = {}
        for account in ACCOUNTS:
            parent = self.source(account)
            original = copy.deepcopy(self.d.job(parent))
            before_canon = self.d.llm.contexts.state(account)
            body = self.body(parent)
            result = self.d.plans.create(parent, body)
            child = result['child_job']
            state = self.state()
            self.assertEqual(self.child(parent, body), child)
            self.assertEqual(self.state(), state)
            self.assertEqual(self.d.job(parent), original)
            self.assertEqual(self.d.llm.contexts.state(account), before_canon)
            video = self.d.plans.guard(child)
            self.assertEqual(video['scene_plan'], body['plan'])
            self.assertEqual(video['script'], original['payload']['input']['content'])
            self.assertEqual(json.loads((self.d.output(child) / 'manual-plan.json').read_text()), body['plan'])
            self.assertIn('scene_plan_revision', self.d.job(child)['payload'])
            self.assertEqual(result['provider_calls'], 0)
            self.assertFalse(result['render_started'])
            self.assertFalse(result['publication_ready'])
            kinds[account] = {row['kind'] for row in body['plan']['scenes']}
            for engine in ('hyperframes', 'remotion'):
                plan = self.d.renders.edit_plan(child, engine)['edit_plan']
                self.assertEqual(plan['actual_visual_family'], 'manual-account-scene-plan')
                self.assertEqual(plan['acceptance']['status'], 'incomplete')
                self.assertFalse(plan['acceptance']['publication_ready'])
                self.assertIsNone(self.d.renders.row(child, engine))
                self.assertEqual(self.d.reviews.state(child, engine)['status'], 'not_started')
        self.assertEqual(kinds['sample-reflection'], {'possibility-branches', 'observation'})
        self.assertEqual(kinds['sample-flow'], {'process-route', 'object-transform'})
        self.assertEqual(kinds['sample-series'], {'clue-inspect', 'canon-board'})

    def test_source_claims_and_accepted_canon_remain_reference_bindings_without_truth_or_promotion(self):
        for account in ACCOUNTS:
            parent = self.source(account)
            source = self.d.renders.video_input(self.d.job(parent))
            child = self.child(parent)
            video = self.d.plans.guard(child)
            self.assertEqual(video['production_context'], source['production_context'])
            self.assertEqual(video['claims'], source['claims'])
            if account == 'sample-series':
                self.assertEqual(video['scene_plan']['canon_revision'], source['production_context']['canon']['revision'])
                self.assertEqual(video['creative']['canon_status'], 'noncanonical_fixture')
                self.assertEqual(video['production_context']['canon']['data']['origin'], 'synthetic_reference_test')
            for engine in ('hyperframes', 'remotion'):
                plan = self.d.renders.edit_plan(child, engine)['edit_plan']
                self.assertEqual(plan['source_binding_sha256'], source['production_context']['binding_sha256'])
                self.assertEqual(plan['claim_traceability']['status'], 'incomplete')
                self.assertEqual(plan['acceptance']['source_truth'], 'pending_human_review')

    def test_bad_expected_binding_missing_consent_extra_fields_and_invalid_plan_leave_zero_child_zero_write(self):
        parent = self.source()
        before = self.state()
        variants = [lambda x: x.update(expected_video_sha256='0' * 64), lambda x: x.update(review_pending=False),
                    lambda x: x.update(approved_by=''), lambda x: x.update(path='/private/plan.json'),
                    lambda x: x['plan'].update(account='sample-flow'), lambda x: x['plan']['scenes'].pop(),
                    lambda x: x['plan']['scenes'][0].update(claim_indexes=[]),
                    lambda x: x['plan']['scenes'][0].update(claim_indexes=[999]),
                    lambda x: x['plan']['scenes'][0].update(cue_indexes=[]),
                    lambda x: x['plan']['scenes'][0].update(object_id='invented-object'),
                    lambda x: x['plan']['scenes'][0]['content'].update(left='<script>bad</script>')]
        for mutate in variants:
            value = self.body(parent)
            mutate(value)
            with self.subTest(mutate=mutate), self.assertRaises(WorkflowError):
                self.d.plans.create(parent, value)
            self.assertEqual(self.state(), before)

    def test_yarin_requires_accepted_snapshot_and_existing_clue_object_and_cast(self):
        missing = self.source('sample-series', accepted=False)
        before = self.state()
        with self.assertRaises(WorkflowError):
            self.d.plans.create(missing, self.body(missing))
        self.assertEqual(self.state(), before)
        parent = self.source('sample-series')
        before = self.state()
        for mutate in (lambda x: x['plan'].update(canon_revision='0' * 64),
                       lambda x: x['plan']['scenes'][0]['content'].update(clue_id='invented-clue'),
                       lambda x: x['plan']['scenes'][1]['content'].update(clue_ids=['invented-clue']),
                       lambda x: x['plan']['scenes'][0].update(object_id='invented-object')):
            value = self.body(parent)
            mutate(value)
            with self.subTest(mutate=mutate), self.assertRaises(WorkflowError):
                self.d.plans.create(parent, value)
            self.assertEqual(self.state(), before)

    def test_replacement_supersedes_old_and_edit_descendant_without_silent_reactivation(self):
        parent = self.source()
        first_body = self.body(parent)
        a = self.child(parent, first_body)
        edited = self.edit(a)
        changed = copy.deepcopy(first_body)
        changed['plan']['scenes'][0]['content']['left'] = 'Başka bir olasılık olabilir.'
        b = self.child(parent, changed)
        self.assertNotEqual(a, b)
        self.d.plans.guard(b)
        for child in (a, edited):
            with self.subTest(child=child), self.assertRaises(WorkflowError):
                self.d.renders.video_input(self.d.job(child))
        state = self.state()
        with self.assertRaises(WorkflowError):
            self.child(parent, first_body)
        self.assertEqual(self.state(), state)

    def test_current_audio_to_plan_to_edit_preserves_audio_and_updates_scene_timing(self):
        for account in ACCOUNTS:
            root = self.source(account)
            with no_media():
                audio = imported(self.d, root)['child_job']
            source = self.d.renders.video_input(self.d.job(audio))
            body = self.body(audio)
            body['plan']['scenes'][0]['camera'] = 'push-in' if source['scenes'][0]['camera'] == 'locked' else 'locked'
            planned = self.child(audio, body)
            edited = self.edit(planned)
            for child in (planned, edited):
                video = self.d.renders.video_input(self.d.job(child))
                self.assertEqual(video['audio'], source['audio'])
                self.assertEqual(video['cues'], source['cues'])
                self.assertEqual(video['audio_timing']['words'], source['audio_timing']['words'])
                self.assertEqual(video['audio_timing']['scene_sha256'], digest(video['scenes']))
                self.assertEqual(file_hash(self.d.output(child) / video['audio']['file']), source['audio']['sha256'])
                self.assertEqual(json.loads((self.d.output(child) / 'audio-timing.json').read_text()), video['audio_timing'])
                self.assertEqual(json.loads((self.d.output(child) / 'manual-plan.json').read_text()), video['scene_plan'])
            self.assertNotEqual(source['audio_timing']['scene_sha256'], self.d.plans.guard(planned)['audio_timing']['scene_sha256'])
            with self.assertRaises(WorkflowError):
                self.d.audio.base(planned)
            with no_media():
                imported(self.d, root, approved_by='New synthetic audio operator')
            for child in (planned, edited):
                with self.subTest(child=child), self.assertRaises(WorkflowError):
                    self.d.audio.guard(child)

    def test_raster_and_recursive_plan_edit_sources_are_rejected_without_writes(self):
        parent = self.source('sample-mechanism')
        before = self.state()
        value = {'plan': {'schema_version': 1}, 'expected_video_sha256': digest(self.d.renders.video_input(self.d.job(parent))),
                 'approved_by': 'Synthetic manual operator', 'review_pending': True}
        with self.assertRaises(WorkflowError):
            self.d.plans.create(parent, value)
        self.assertEqual(self.state(), before)
        parent = self.source()
        planned = self.child(parent)
        edited = self.edit(planned)
        for child in (planned, edited):
            before = self.state()
            with self.subTest(child=child), self.assertRaises(WorkflowError):
                self.d.plans.create(child, self.body(child))
            self.assertEqual(self.state(), before)

    def test_stored_manifest_payload_and_source_tamper_invalidate_without_repair(self):
        parent = self.source()
        body = self.body(parent)
        child = self.child(parent, body)
        path = self.d.output(child) / 'manual-plan.json'
        original = path.read_bytes()
        path.write_text('{}')
        before = self.state()
        with self.assertRaises(WorkflowError):
            self.d.plans.guard(child)
        with self.assertRaises(WorkflowError):
            self.child(parent, body)
        self.assertEqual(self.state(), before)
        path.write_bytes(original)
        self.d.plans.guard(child)
        parent_row = self.d.job(parent)
        changed = copy.deepcopy(parent_row['payload'])
        changed['input']['title'] = 'Changed source title'
        with self.d.connection() as db:
            db.execute('UPDATE dashboard_jobs SET payload=? WHERE id=?', (canonical(changed), parent))
        with self.assertRaises(WorkflowError):
            self.d.plans.guard(child)
        with self.d.connection() as db:
            db.execute('UPDATE dashboard_jobs SET payload=? WHERE id=?', (canonical(parent_row['payload']), parent))
        self.d.plans.guard(child)
        row = self.d.job(child)
        row['payload']['template']['template']['video']['scene_plan']['scenes'][0]['content']['left'] = 'Tampered after commit'
        with self.d.connection() as db:
            db.execute('UPDATE dashboard_jobs SET payload=? WHERE id=?', (canonical(row['payload']), child))
        with self.assertRaises(WorkflowError):
            self.d.plans.guard(child)

    def test_late_source_mutation_is_rejected_before_child_commit(self):
        parent = self.source()
        data = self.body(parent)
        before = self.state()
        original = self.d.job
        count = 0
        def late(key):
            nonlocal count
            row = original(key)
            if key == parent:
                count += 1
                if count >= 2:
                    row['payload']['input']['title'] = 'Synthetic concurrently changed source'
            return row
        with patch.object(self.d, 'job', side_effect=late), self.assertRaises(WorkflowError):
            self.d.plans.create(parent, data)
        self.assertEqual(self.state(), before)

    def test_failed_audio_copy_rolls_back_whole_child_and_stage(self):
        root = self.source()
        with no_media():
            audio = imported(self.d, root)['child_job']
        value = self.body(audio)
        before = self.state()
        copier = shutil.copyfile
        def broken(source, target, *args, **kwargs):
            result = copier(source, target, *args, **kwargs)
            if Path(target).suffix == '.wav':
                Path(target).write_bytes(b'Corrupt synthetic audio snapshot')
            return result
        with patch('shutil.copyfile', side_effect=broken), self.assertRaises(WorkflowError):
            self.d.plans.create(audio, value)
        self.assertEqual(self.state(), before)

    def test_manual_publish_rollback_removes_own_uncommitted_child_and_preserves_parent(self):
        parent = self.source()
        body = self.body(parent)
        before = self.state()
        original = self.d.connection
        published = []
        dashboard = self.d
        class Fault:
            def __init__(self, db):
                self.db = db
                self.child = None
            def __getattr__(self, key):
                return getattr(self.db, key)
            def execute(self, sql, *args):
                if sql.startswith('INSERT INTO dashboard_jobs'):
                    self.child = args[0][0]
                if sql.startswith('INSERT INTO dashboard_events') and self.child:
                    # The real rename and SQLite inserts have already happened.
                    published.append((dashboard.output(self.child) / 'manual-plan.json').is_file())
                    raise sqlite3.OperationalError('Synthetic rollback after manual publication')
                return self.db.execute(sql, *args)
        @contextlib.contextmanager
        def connection():
            with original() as db:
                yield Fault(db)
        with patch.object(self.d, 'connection', connection), self.assertRaises(sqlite3.OperationalError):
            self.d.plans.create(parent, body)
        self.assertEqual(published, [True])
        self.assertEqual(self.state(), before)
        self.assertFalse(list(self.d.workspace.glob('manual-plan-*')))

    def test_manual_real_commit_then_ack_error_preserves_complete_durable_child_and_reuses_it(self):
        parent = self.source('sample-flow')
        body = self.body(parent)
        original = self.d.connection
        acknowledged = []
        @contextlib.contextmanager
        def connection():
            with original() as db:
                yield db
                changed = db.in_transaction and db.total_changes > 0
            # Raise only after the real Dashboard context committed and closed.
            if changed and not acknowledged:
                acknowledged.append(True)
                raise sqlite3.OperationalError('Synthetic acknowledgement error after real manual commit')
        with patch.object(self.d, 'connection', connection), self.assertRaises(sqlite3.OperationalError):
            self.d.plans.create(parent, body)
        self.assertEqual(acknowledged, [True])
        children = [row for row in self.d.jobs() if row['id'] != parent]
        self.assertEqual(len(children), 1)
        child = children[0]['id']
        self.d.plans.guard(child)
        self.assertEqual(json.loads((self.d.output(child) / 'manual-plan.json').read_text()), body['plan'])
        before_reuse = self.state()
        self.assertEqual(self.child(parent, body), child)
        self.assertEqual(self.state(), before_reuse)
        self.assertFalse(list(self.d.workspace.glob('manual-plan-*')))

    def test_manual_edit_publish_rollback_preserves_completed_plan_and_removes_only_new_edit(self):
        parent = self.child(self.source())
        before = self.state()
        original = self.d.connection
        published = []
        dashboard = self.d
        class Fault:
            def __init__(self, db):
                self.db = db
                self.child = None
            def __getattr__(self, key):
                return getattr(self.db, key)
            def execute(self, sql, *args):
                if sql.startswith('INSERT INTO dashboard_jobs'):
                    self.child = args[0][0]
                if sql.startswith('INSERT INTO dashboard_events') and self.child:
                    out = dashboard.output(self.child)
                    published.append((out / 'manual-plan.json').is_file() and (out / 'revision.json').is_file())
                    raise sqlite3.OperationalError('Synthetic rollback after manual edit publication')
                return self.db.execute(sql, *args)
        @contextlib.contextmanager
        def connection():
            with original() as db:
                yield Fault(db)
        with patch.object(self.d, 'connection', connection), self.assertRaises(sqlite3.OperationalError):
            self.edit(parent)
        self.assertEqual(published, [True])
        self.assertEqual(self.state(), before)
        self.d.plans.guard(parent)
        self.assertFalse(list(self.d.workspace.glob('scene-revision-*')))

    def test_manual_edit_real_commit_then_ack_error_preserves_complete_edit_and_reuses_it(self):
        parent = self.child(self.source('sample-flow'))
        prior_ids = {row['id'] for row in self.d.jobs()}
        original = self.d.connection
        acknowledged = []
        @contextlib.contextmanager
        def connection():
            with original() as db:
                yield db
                changed = db.in_transaction and db.total_changes > 0
            if changed and not acknowledged:
                acknowledged.append(True)
                raise sqlite3.OperationalError('Synthetic acknowledgement error after real manual edit commit')
        with patch.object(self.d, 'connection', connection), self.assertRaises(sqlite3.OperationalError):
            self.edit(parent)
        self.assertEqual(acknowledged, [True])
        children = [row for row in self.d.jobs() if row['id'] not in prior_ids]
        self.assertEqual(len(children), 1)
        child = children[0]['id']
        self.d.edits.guard(child)
        self.d.plans.guard(parent)
        self.assertTrue((self.d.output(child) / 'manual-plan.json').is_file())
        self.assertTrue((self.d.output(child) / 'revision.json').is_file())
        before_reuse = self.state()
        self.assertEqual(self.edit(parent), child)
        self.assertEqual(self.state(), before_reuse)
        self.assertFalse(list(self.d.workspace.glob('scene-revision-*')))

    def test_official_scene_plan_http_action_requires_local_origin_and_exact_binding(self):
        parent = self.source('sample-flow')
        path = '/api/jobs/' + parent + '/scene-plan'
        server = SimpleNamespace(server_address=('127.0.0.1', 43333), dashboard=self.d)
        def call(body, status, origin='http://127.0.0.1:43333'):
            raw = canonical(body).encode()
            request = ('POST ' + path + ' HTTP/1.0\r\nHost: 127.0.0.1:43333\r\nOrigin: ' + origin +
                       '\r\nX-Storymotion-Local: 1\r\nContent-Type: application/json\r\nContent-Length: ' + str(len(raw)) + '\r\n\r\n').encode() + raw
            connection = MemoryConnection(request)
            authenticated_handler(connection, ('127.0.0.1', 1), server)
            header, value = bytes(connection.output).split(b'\r\n\r\n', 1)
            self.assertEqual(int(header.split()[1]), status, value)
            return json.loads(value)
        before = self.state()
        body = self.body(parent)
        call(body, 403, 'https://attacker.invalid')
        self.assertEqual(self.state(), before)
        call({**body, 'expected_video_sha256': '0' * 64}, 400)
        self.assertEqual(self.state(), before)
        result = call(body, 200)
        self.assertFalse(result['render_started'])
        self.assertEqual(result['provider_calls'], 0)
        self.d.plans.guard(result['child_job'])

    def test_two_engines_prepare_actual_manual_svg_and_keep_exact_sources_without_native_process(self):
        for account in ACCOUNTS:
            parent = self.source(account)
            child = self.child(parent)
            video = self.d.plans.guard(child)
            plans = []
            for name in ('hyperframes', 'remotion'):
                runtime, job, payload, out = self.prepared(child, name)
                plan = payload['edit_plan']
                plans.append(plan)
                self.assertEqual(plan['actual_visual_family'], 'manual-account-scene-plan')
                self.assertEqual(json.loads((out / 'manual-plan.json').read_text()), video['scene_plan'])
                self.assertEqual(json.loads((out / 'source-brief.json').read_text())['scene_plan'], video['scene_plan'])
                self.assertEqual(json.loads((out / 'writing-context.json').read_text())['binding'], video['production_context'])
                markup = (out / 'index.html').read_text()
                for index, scene in enumerate(plan['scenes']):
                    self.assertIn(scene['vector'], markup)
                    self.assertIn('<svg', scene['vector'])
                    self.assertNotIn('<image', scene['vector'])
                    authored = video['scene_plan']['scenes'][index]['content']
                    label = next((authored[k] for k in ('left', 'prompt', 'before', 'note') if k in authored), None)
                    if label is None:
                        label = authored['nodes'][0]
                    visible_copy = ' '.join(text.strip() for text in ET.fromstring(scene['vector']).itertext() if text.strip())
                    self.assertIn(label, visible_copy)
                    self.assertEqual(scene['cue_indexes'], video['scene_plan']['scenes'][index]['cue_indexes'])
                    self.assertTrue(scene['object_motion'])
                    self.assertTrue(all(op['target'] != 'camera' for op in scene['object_motion']))
                    self.assertTrue(all(op['target'] == 'camera' for op in scene['camera_motion']))
                if name == 'remotion':
                    self.assertEqual(json.loads((out / 'remotion-props.json').read_text())['edit_plan'], plan)
                self.assertTrue(runtime.manifest_valid(job, 'prepare'))
            self.assertEqual(plans[0], plans[1])

    def test_packaged_plan_and_receipt_are_exactly_bound_and_changed_zip_is_rejected(self):
        child = self.child(self.source('sample-flow'))
        for name in ('hyperframes', 'remotion'):
            runtime, job, payload, out = self.delivered(child, name)
            video = payload['brief']
            manifest = json.loads((out / 'delivery.json').read_text())
            self.assertEqual(manifest['scene_plan_sha256'], digest(video['scene_plan']))
            self.assertEqual(json.loads((out / 'render-engine.json').read_text())['scene_plan_sha256'], digest(video['scene_plan']))
            with zipfile.ZipFile(out / 'delivery.zip') as archive:
                self.assertEqual(json.loads(archive.read('manual-plan.json')), video['scene_plan'])
                self.assertEqual(hashlib.sha256(archive.read('manual-plan.json')).hexdigest(), manifest['files']['manual-plan.json'])
                self.assertIn(b'NOT_MEDIA:', archive.read('render-1080.mp4'))
            verify_staged_assets(payload, out, delivery=True)
            with zipfile.ZipFile(out / 'delivery.zip') as archive:
                members = {item.filename: archive.read(item) for item in archive.infolist()}
            members['manual-plan.json'] = b'{}'
            with zipfile.ZipFile(out / 'delivery.zip', 'w') as archive:
                for key, value in members.items():
                    archive.writestr(key, value)
            with self.assertRaises(WorkflowError):
                verify_staged_assets(payload, out, delivery=True)


if __name__ == '__main__':
    unittest.main()
