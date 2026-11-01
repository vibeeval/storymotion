"""Actual authenticated Handler, offline memory HTTP; no native/provider calls."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from unittest.mock import patch
import unittest

from storymotion import account_packs
from storymotion.dashboard import Handler
from storymotion.security import canonical, digest
from test_catalog_integration import MemoryConnection
import test_template_credential_intake as credential_fixture
from test_template_credential_intake import LLM_OPAQUE, VOICE_OPAQUE, patterned
from test_template_intake import SOURCE, covering_claims


class FamilyHistoryHttpTests(unittest.TestCase):
    setUp_base = credential_fixture.TemplateCredentialHttpTests.setUp
    payload = credential_fixture.TemplateCredentialHttpTests.payload
    snapshot = credential_fixture.TemplateCredentialHttpTests.snapshot
    assert_no_secret = credential_fixture.TemplateCredentialHttpTests.assert_no_secret

    def setUp(self):
        original = account_packs.catalog
        def packs():
            values, errors = original();second = copy.deepcopy(values['neutral'])
            second['id'] = 'second';second['display_name'] = 'Second fixture'
            values['second'] = second
            return values, errors
        scope = patch.object(account_packs, 'catalog', side_effect=packs)
        scope.start();self.addCleanup(scope.stop)
        self.setUp_base()
        code, state, _ = self.post('/api/writing-context/save-sources', {
            'account': 'neutral', 'expected_revision': None, 'sources': SOURCE, 'rights_confirmed': True})
        self.assertEqual(code, 200);self.source_revision = state['sources']['revision']

    def post(self, path, data):
        return credential_fixture.TemplateCredentialHttpTests.request(self, path, data)

    def get(self, path, *, cookie=True, headers=()):
        lines = ['GET ' + path + ' HTTP/1.0', 'Host: 127.0.0.1:43333']
        if cookie:lines.append('Cookie: ' + self.cookie)
        lines += list(headers)
        connection = MemoryConnection(('\r\n'.join(lines) + '\r\n\r\n').encode())
        Handler(connection, ('127.0.0.1', 1), self.server)
        raw = bytes(connection.output);head, body = raw.split(b'\r\n\r\n', 1)
        code = int(head.split()[1])
        return code, json.loads(body) if b'application/json' in head else body, raw

    def prepare(self, family='kinetic-grid', engine='hyperframes'):
        data = self.payload(family, engine)
        data.update(claims=covering_claims(data['spec']), source_revision=self.source_revision)
        code, result, raw = self.post('/api/template-families/prepare', data)
        self.assertEqual(code, 200, result);self.assert_no_secret(raw)
        return data, result

    def detail(self, result):
        code, value, _ = self.get(result['detail_url'])
        self.assertEqual(code, 200, value)
        return value

    def mutate(self, sql, args):
        with sqlite3.connect(self.root/'family-renders/jobs.sqlite3') as db:db.execute(sql, args)

    def test_empty_history_is_read_only_and_does_not_create_engine_store(self):
        before = self.snapshot()
        code, value, _ = self.get('/api/family-jobs/neutral')
        self.assertEqual((code, value['jobs']), (200, []))
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root/'family-renders').exists())

    def test_four_prepare_variants_reopen_download_and_reuse_without_get_mutation(self):
        for family in self.specs:
            for engine in ('hyperframes', 'remotion'):
                with self.subTest(family=family, engine=engine):
                    data, result = self.prepare(family, engine)
                    before = self.snapshot()
                    code, listing, _ = self.get('/api/family-jobs/neutral')
                    self.assertEqual(code, 200)
                    self.assertIn(result['job'], [item['job'] for item in listing['jobs']])
                    detail = self.detail(result)
                    self.assertEqual(detail['artifacts_status'], 'verified', detail)
                    self.assertFalse(detail['actual_render']);self.assertEqual(detail['spec'], data['spec'])
                    self.assertEqual(detail['ref']['kind'], 'family')
                    self.assertEqual(detail['publication_acceptance'], 'pending')
                    self.assertNotIn('payload', detail);self.assertNotIn('manifest', detail)
                    for entry in detail['files']:
                        code, raw, response = self.get(entry['download_url'])
                        self.assertEqual(code, 200, entry)
                        self.assertEqual(hashlib.sha256(raw).hexdigest(), entry['sha256'])
                        self.assertIn(b'Content-Disposition: attachment', response)
                        self.assertIn(b"sandbox; default-src 'none'", response)
                        self.assert_no_secret(response)
                        self.assertNotIn(str(self.root).encode(), response)
                    cover = next(e for e in detail['files'] if e['name']=='cover.svg')
                    code, raw, response = self.get(cover['view_url'])
                    self.assertEqual(code, 200);self.assertIn(b'image/svg+xml', response)
                    non_svg = next(e for e in detail['files'] if e['name']=='index.html')
                    self.assertEqual(self.get(non_svg['download_url']+'/view')[0], 400)
                    self.assertEqual(self.snapshot(), before, 'GET changed file bytes/mtime or events')
                    code, retry, _ = self.post('/api/template-families/prepare', data)
                    self.assertEqual(code, 200);self.assertEqual(result['job'], retry['job'])
        with sqlite3.connect(self.root/'family-renders/jobs.sqlite3') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM jobs').fetchone()[0], 4)
        # Recreate the read adapter: history is in the store, not page/process RAM.
        from storymotion.template_studio import TemplateStudio
        self.d.template_studio = TemplateStudio(self.d)
        self.assertEqual(len(self.get('/api/family-jobs/neutral')[1]['jobs']), 4)

    def test_account_type_and_normal_job_namespaces_never_fallback(self):
        _, result = self.prepare();detail = self.detail(result)
        item = detail['files'][0]
        self.assertEqual(self.get('/api/family-jobs/second')[1]['jobs'], [])
        for path in (result['detail_url'].replace('/neutral/', '/second/'),
                     item['download_url'].replace('/neutral/', '/second/'),
                     '/api/jobs/'+result['job'], '/files/'+result['job']+'/cover.svg',
                     '/api/family-jobs/neutral/normal/'+result['job'],
                     '/api/family-jobs/neutral/'+'a'*24):
            self.assertEqual(self.get(path)[0], 400, path)
        # Same raw ID in the normal dashboard database does not change routing.
        with self.d.connection() as db:
            db.execute('INSERT INTO dashboard_jobs(id,payload,status,created) VALUES(?,?,?,?)',
                (result['job'], canonical({'arbitrary_fixture': True}), 'queued', 'fixture'))
        self.assertEqual(self.detail(result)['spec'], detail['spec'])
        self.assertEqual(self.get('/api/jobs')[0], 200)

    def test_auth_host_origin_encoded_paths_and_closing_guards(self):
        _, result = self.prepare();artifact = self.detail(result)['files'][0]['download_url']
        for path in ('/api/family-jobs/neutral', result['detail_url'], artifact):
            self.assertEqual(self.get(path, cookie=False)[0], 401)
            self.assertEqual(self.get(path, headers=('Host: evil.test',))[0], 403)
            self.assertEqual(self.get(path, headers=('Origin: https://evil.test',))[0], 403)
            self.assertEqual(self.get(path, headers=('Origin: http://127.0.0.1:43333',)*2)[0], 403)
        for path in ('/api/family-jobs/neutral%2fother', '/api/family-jobs/%2e%2e',
                     '/api/family-jobs/neutral/%252e%252e', artifact+'/extra',
                     artifact.replace('/neutral/', '/neutral%2fsecond/'),
                     '/family-files/neutral/'+result['job']+'/../../jobs.sqlite3'):
            self.assertEqual(self.get(path)[0], 400, path)
        self.server._closing = True
        self.assertEqual(self.get(result['detail_url'])[0], 403)

    def test_failed_incomplete_and_tampered_manifest_have_no_file_links(self):
        _, result = self.prepare();detail = self.detail(result);url = detail['files'][0]['download_url']
        key = result['job']
        with sqlite3.connect(self.root/'family-renders/jobs.sqlite3') as db:
            manifest = json.loads(db.execute("SELECT manifest FROM stages WHERE job=? AND name='prepare'", (key,)).fetchone()[0])
        for mode in ('missing', 'hash', 'traversal', 'extra', 'not-complete'):
            altered = dict(manifest)
            if mode=='missing':altered.pop('cover.svg')
            if mode=='hash':altered['cover.svg'] = '0'*64
            if mode=='traversal':altered['../jobs.sqlite3'] = '0'*64
            if mode=='extra':altered['unlisted.txt'] = '0'*64
            self.mutate("UPDATE stages SET manifest=?,status=?,error=? WHERE job=? AND name='prepare'",
                        (canonical(altered), 'failed' if mode=='not-complete' else 'complete', LLM_OPAQUE, key))
            before = self.snapshot()
            # This fixture deliberately poisons the pre-existing DB error.
            # Prove it exists BEFORE GET; only the response/log/export boundary
            # must remain secretless, and GET must not mutate the poisoned store.
            self.assertIn(LLM_OPAQUE.encode(), before[0]['family-renders/jobs.sqlite3'][0])
            value = self.detail(result)
            self.assertEqual(value['files'], []);self.assertEqual(value['artifacts_status'], 'unavailable')
            code, _, raw = self.get(url);self.assertEqual(code, 400)
            for secret in (LLM_OPAQUE, VOICE_OPAQUE, patterned()):self.assertNotIn(secret.encode(), raw)
            for path in self.root.rglob('*.log'):self.assertNotIn(LLM_OPAQUE.encode(), path.read_bytes())
            self.assertEqual(self.snapshot(), before, 'Read changed a deliberately pre-poisoned fixture')

    def test_changed_file_and_old_token_fail_closed(self):
        _, result = self.prepare();detail = self.detail(result)
        entry = next(e for e in detail['files'] if e['name']=='caption.txt')
        out = self.root/'family-renders'/result['job']
        (out/'caption.txt').write_text('Changed fixture\n')
        self.assertEqual(self.detail(result)['files'], [])
        self.assertEqual(self.get(entry['download_url'])[0], 400)
        with sqlite3.connect(self.root/'family-renders/jobs.sqlite3') as db:
            manifest = json.loads(db.execute("SELECT manifest FROM stages WHERE job=? AND name='prepare'", (result['job'],)).fetchone()[0])
        manifest['caption.txt'] = hashlib.sha256((out/'caption.txt').read_bytes()).hexdigest()
        self.mutate("UPDATE stages SET manifest=? WHERE job=? AND name='prepare'", (canonical(manifest), result['job']))
        self.assertEqual(self.detail(result)['artifacts_status'], 'unavailable', 'Caption must still bind the persisted brief')
        self.assertEqual(self.get(entry['download_url'])[0], 400, 'Token did not bind the full manifest revision')

    def test_file_symlink_hardlink_and_job_directory_links_are_rejected(self):
        _, result = self.prepare();detail = self.detail(result);entry = detail['files'][0]
        out = self.root/'family-renders'/result['job'];target = out/'cover.svg';saved = target.read_bytes()
        external = self.root/'outside.svg';external.write_bytes(saved)
        for kind in ('symlink', 'hardlink'):
            target.unlink()
            if kind=='symlink':target.symlink_to(external)
            else:os.link(external, target)
            self.assertEqual(self.detail(result)['files'], [])
            self.assertEqual(self.get(entry['download_url'])[0], 400)
            target.unlink();target.write_bytes(saved)
        moved = out.with_name('saved-output');out.rename(moved);out.symlink_to(moved, target_is_directory=True)
        self.assertEqual(self.detail(result)['files'], [])
        self.assertEqual(self.get(entry['download_url'])[0], 400)

    def test_db_and_family_root_links_are_rejected_without_following_them(self):
        _, result = self.prepare();root = self.root/'family-renders';db = root/'jobs.sqlite3'
        saved = self.root/'saved-db';db.rename(saved);db.symlink_to(saved)
        self.assertEqual(self.get(result['detail_url'])[0], 400)
        db.unlink();os.link(saved, db)
        self.assertEqual(self.get(result['detail_url'])[0], 400)
        db.unlink();saved.rename(db)
        moved = self.root/'moved';root.rename(moved);root.symlink_to(moved, target_is_directory=True)
        self.assertEqual(self.get('/api/family-jobs/neutral')[0], 400)

    def test_both_broker_credentials_patterns_and_private_paths_never_export(self):
        _, result = self.prepare();detail = self.detail(result);key = result['job']
        out = self.root/'family-renders'/key;path = out/'caption.txt'
        with sqlite3.connect(self.root/'family-renders/jobs.sqlite3') as db:
            manifest = json.loads(db.execute("SELECT manifest FROM stages WHERE job=? AND name='prepare'", (key,)).fetchone()[0])
        for secret in (LLM_OPAQUE, VOICE_OPAQUE, patterned(), '/Users/private-owner/data'):
            path.write_text(secret)
            manifest['caption.txt'] = hashlib.sha256(path.read_bytes()).hexdigest()
            self.mutate("UPDATE stages SET manifest=? WHERE job=? AND name='prepare'", (canonical(manifest), key))
            for url in (result['detail_url'], detail['files'][0]['download_url']):
                code, value, raw = self.get(url)
                self.assertIn(code, (200, 400));self.assertNotIn(secret.encode(), raw)
                if code==200:self.assertEqual(value['files'], [])
        # No raw stage error is ever exported.
        self.mutate("UPDATE stages SET status='failed',error=? WHERE job=?", (VOICE_OPAQUE, key))
        self.assertNotIn(VOICE_OPAQUE.encode(), self.get(result['detail_url'])[2])

    def test_unrecognized_legacy_producer_cannot_expose_pre_p0_artifacts(self):
        _, result = self.prepare()
        with sqlite3.connect(self.root/'family-renders/jobs.sqlite3') as db:
            row = db.execute('SELECT payload FROM jobs WHERE id=?', (result['job'],)).fetchone()
        payload = json.loads(row[0]);payload['execution']['files']['storymotion/template_studio.py'] = '0'*64
        payload['execution']['fingerprint'] = digest(payload['execution']['files']);key = digest(payload)[:24]
        self.mutate('INSERT INTO jobs(id,payload,created) VALUES(?,?,?)', (key, canonical(payload), '2026-10-27T00:00:00+00:00'))
        value = self.get('/api/family-jobs/neutral')[1]
        self.assertEqual(len(value['jobs']), 1);self.assertEqual(value['unavailable_records'], 1)
        self.assertEqual(self.get('/api/family-jobs/neutral/'+key)[0], 400)

    def test_external_workflow_lock_and_studio_busy_are_not_reads_or_mutations(self):
        import fcntl
        _, result = self.prepare();before = self.snapshot()
        with (self.root/'family-renders/.workflow.lock').open('rb') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.get(result['detail_url'])[0], 400)
        self.assertEqual(self.snapshot(), before)
        with patch.object(self.d.template_studio, 'lock') as lock:
            lock.acquire.return_value = False
            self.assertEqual(self.get(result['detail_url'])[0], 400)
            lock.release.assert_not_called()

    def test_forged_identity_malformed_payload_and_missing_input_do_not_export(self):
        _, result = self.prepare();key = result['job']
        with sqlite3.connect(self.root/'family-renders/jobs.sqlite3') as db:
            payload = db.execute('SELECT payload FROM jobs WHERE id=?', (key,)).fetchone()[0]
        wrong = json.loads(payload);wrong['brief']['template_family']['parameters']['title'] = 'Changed'
        for raw in (canonical(wrong), '{"brief":', '{"brief":1,"brief":2}', '[]'):
            self.mutate('UPDATE jobs SET payload=? WHERE id=?', (raw, key))
            self.assertEqual(self.get(result['detail_url'])[0], 400)
        self.mutate('UPDATE jobs SET payload=? WHERE id=?', (payload, key))
        _, good = self.prepare('contour-trace')
        source = self.root/'family-inputs'/(digest(json.loads(payload)['brief'])+'.json')
        source.unlink()
        self.assertEqual(self.get(result['detail_url'])[0], 400)
        listing = self.get('/api/family-jobs/neutral')[1]
        self.assertEqual([item['job'] for item in listing['jobs']], [good['job']])
        self.assertEqual(listing['unavailable_records'], 1)
        self.assertEqual(self.detail(good)['artifacts_status'], 'verified')

    def test_historical_safe_records_read_without_authorizing_new_execution(self):
        _, result = self.prepare();before = self.snapshot()
        with patch('storymotion.provenance.execution_provenance', return_value={'fingerprint': '0'*64}):
            value = self.detail(result)
            self.assertFalse(value['source_current']);self.assertEqual(value['artifacts_status'], 'verified')
        self.assertEqual(self.snapshot(), before)

    def test_wal_or_hot_journal_is_refused_without_sqlite_sidecar_creation(self):
        _, result = self.prepare()
        sidecar = self.root/'family-renders/jobs.sqlite3-journal';sidecar.write_bytes(b'Synthetic hot journal')
        # Do not let a test snapshot's own SQLite dump attempt recovery of the
        # deliberately hot journal. Byte+mtime equality covers every DB/event.
        def snapshot_files():
            return {str(p.relative_to(self.root)):(p.read_bytes(),p.stat().st_mtime_ns) if p.is_file() else None for p in self.root.rglob('*')}
        before = snapshot_files()
        with patch('storymotion.family_jobs.sqlite3.connect') as connect:
            self.assertEqual(self.get(result['detail_url'])[0], 400)
            connect.assert_not_called()
        self.assertEqual(snapshot_files(), before)
        self.assertFalse((sidecar.parent/'jobs.sqlite3-shm').exists())

    def test_read_connections_close_after_success_and_manifest_errors(self):
        _, result = self.prepare();connections = [];original = sqlite3.connect
        class Recording(sqlite3.Connection):
            closed = False
            def close(self):self.closed = True;super().close()
        def connect(*args, **kwargs):
            kwargs['factory'] = Recording;db = original(*args, **kwargs);connections.append(db);return db
        with patch('storymotion.family_jobs.sqlite3.connect', side_effect=connect):
            self.assertEqual(self.get('/api/family-jobs/neutral')[0], 200)
            self.detail(result)
            (self.root/'family-renders'/result['job']/'cover.svg').unlink()
            self.assertEqual(self.detail(result)['files'], [])
        self.assertEqual(len(connections), 3);self.assertTrue(all(db.closed for db in connections))
