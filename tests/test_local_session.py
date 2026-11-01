"""Real HTTP parsing over memory streams; fake one-launch tokens, no sockets."""
import io
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

from pack_fixture_case import PackFixtureCase
from test_catalog_integration import MemoryConnection
from storymotion.dashboard import Dashboard, Handler
from storymotion.local_session import COOKIE_NAME, LocalSession, request_path
from storymotion.security import WorkflowError

BOOT = 'FAKE_' + 'B' * 38
SESSION = 'FAKE_' + 'S' * 38


class LocalSessionHttpTests(PackFixtureCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        with patch('storymotion.local_session.secrets.token_urlsafe', side_effect=[BOOT, SESSION]) as generate:
            self.d = Dashboard(self.temp.name)
        self.assertEqual(generate.call_args_list, [unittest.mock.call(32), unittest.mock.call(32)])
        self.addCleanup(self.d.clear_keys)
        self.addCleanup(self.d.close_local_log)
        self.server = SimpleNamespace(server_address=('127.0.0.1', 43333), dashboard=self.d)

    def call(self, path, *, method='GET', body=None, cookie=None, token=None, host='127.0.0.1:43333', origin='http://127.0.0.1:43333', marker='1'):
        raw = b'' if body is None else json.dumps(body).encode()
        head = [method+' '+path+' HTTP/1.0', 'Host: '+host]
        if cookie is not None:head.append('Cookie: '+cookie)
        if token is not None:head.append('X-Storymotion-Token: '+token)
        if method == 'POST':head += ['Origin: '+origin, 'X-Storymotion-Local: '+marker, 'Content-Type: application/json', 'Content-Length: '+str(len(raw))]
        connection = MemoryConnection(('\r\n'.join(head)+'\r\n\r\n').encode()+raw)
        Handler(connection, ('127.0.0.1', 1), self.server)
        headers, payload = bytes(connection.output).split(b'\r\n\r\n', 1)
        return int(headers.split()[1]), headers.decode(), payload

    def bootstrap(self):
        status, headers, payload = self.call('/api/bootstrap', method='POST', body={}, token=BOOT)
        self.assertEqual(status, 200)
        self.assertIn('HttpOnly', headers); self.assertIn('SameSite=Strict', headers); self.assertIn('Path=/', headers)
        self.assertNotIn('Max-Age', headers); self.assertNotIn('Expires=', headers)
        self.assertNotIn(BOOT.encode(), payload); self.assertNotIn(SESSION.encode(), payload)
        return self.d.session_auth.cookie_name(43333)+'='+SESSION

    def test_all_api_and_work_files_require_session_before_read_or_action(self):
        for path in ('/api/catalog', '/api/keys', '/api/jobs', '/api/workflows', '/api/worker', '/api/unknown', '/%61pi/catalog', '/api/writing-contexts/%zz', '/files/id/profile.json'):
            self.assertEqual(self.call(path)[0], 401, path)
        self.assertEqual(self.call('/api/jobs', method='POST', body={})[0], 401)
        self.assertEqual(self.d.jobs(), [])
        cookie = self.bootstrap()
        self.assertEqual(self.call('/api/catalog', cookie=cookie)[0], 200)
        self.assertEqual(self.call('/api/jobs', cookie=cookie)[0], 200)

    def test_bootstrap_one_use_host_origin_marker_and_cookie_binding(self):
        self.assertEqual(self.call('/api/bootstrap', method='POST', body={}, token=BOOT, host='attacker.test')[0], 403)
        self.assertEqual(self.call('/api/bootstrap', method='POST', body={}, token=BOOT, origin='https://attacker.test')[0], 403)
        self.assertEqual(self.call('/api/bootstrap', method='POST', body={}, token=BOOT, marker='0')[0], 403)
        self.assertEqual(self.call('/api/bootstrap', method='POST', body={}, token='invalid')[0], 401)
        cookie = self.bootstrap()
        self.assertEqual(self.call('/api/bootstrap', method='POST', body={}, token=BOOT)[0], 401)
        self.assertEqual(self.call('/api/catalog', cookie=COOKIE_NAME+'=wrong')[0], 401)
        self.assertEqual(self.call('/api/catalog', token=BOOT)[0], 401)
        self.assertEqual(self.call('/api/catalog', cookie=cookie, host='attacker.test')[0], 403)
        self.assertEqual(self.call('/api/worker/run-once', method='POST', body={}, cookie=cookie, origin='https://attacker.test')[0], 403)
        self.assertEqual(self.call('/api/worker/run-once', method='POST', body={}, cookie=cookie, marker='0')[0], 403)
        self.assertEqual(self.call('/api/catalog', cookie=cookie+'; '+cookie)[0], 401)
        self.d.session_auth.close()
        self.assertEqual(self.call('/api/catalog', cookie=cookie)[0], 401)

    def test_writing_context_identifiers_decode_once_and_preserve_401_200_400(self):
        valid='/api/writing-contexts/sample-flow'
        self.assertEqual(self.call(valid)[0], 401)
        cookie=self.bootstrap()
        self.assertEqual(self.call(valid, cookie=cookie)[0], 200)
        self.assertEqual(self.call('/api/writing-contexts/%73ample-flow', cookie=cookie)[0], 200)
        for value in ('../sample-flow', '%2e%2e%2fsample-flow', '%252e%252e%252fsecret', 'sample%2fflow', '%5csecret', '%00', '%zz', 'sample-flow/extra'):
            self.assertEqual(self.call('/api/writing-contexts/'+value, cookie=cookie)[0], 400, value)
        for path in ('/api//catalog', '/api/catalog?token=fake', '/api/catalog%3fsecret', '/%ff'):
            self.assertEqual(self.call(path, cookie=cookie)[0], 400, path)

    def test_tokens_rotate_per_launch_and_static_shell_stays_public(self):
        first=self.d.session_auth.launch_url(43333)
        second=LocalSession().launch_url(43333)
        self.assertNotEqual(first, second)
        self.assertEqual(urlsplit(first).fragment, 'bootstrap='+BOOT)
        self.assertNotIn(BOOT, urlsplit(first).path)
        self.assertEqual(self.call('/')[0], 200)
        self.bootstrap()
        self.assertEqual(self.d.session_auth.launch_url(43333), 'http://127.0.0.1:43333/')

    def test_independent_ports_keep_independent_session_cookies(self):
        from email.message import Message
        with patch('storymotion.local_session.secrets.token_urlsafe',side_effect=['FAKE_'+'C'*38,'FAKE_'+'D'*38]):
            other=LocalSession()
        first=self.bootstrap();second=other.bootstrap('FAKE_'+'C'*38,43334).split(';',1)[0]
        self.assertNotEqual(first.split('=',1)[0],second.split('=',1)[0])
        headers=Message();headers['Cookie']=first+'; '+second
        self.assertTrue(self.d.session_auth.authenticated(headers,43333))
        self.assertTrue(other.authenticated(headers,43334))
        self.assertFalse(other.authenticated(headers,43333))
        self.assertFalse(self.d.session_auth.authenticated(headers,43334))

    def test_encoded_download_retains_revision_lock_through_response_and_logs_no_values(self):
        cookie=self.bootstrap();held=[]
        class Lock:
            def __enter__(self):held.append(True)
            def __exit__(self,*args):held.pop()
        def download(*args):
            self.assertTrue(held)
            return b'FAKE_VERIFIED_MEDIA'
        self.d.revision_lock=Lock()
        with patch.object(self.d.renders,'download',side_effect=download):
            status,_,payload=self.call('/%72ender-files/'+'a'*24+'/hyperframes/render-1080.mp4',cookie=cookie)
        self.assertEqual(status,200);self.assertEqual(payload,b'FAKE_VERIFIED_MEDIA');self.assertFalse(held)
        with patch.object(self.d,'jobs',side_effect=RuntimeError('FAKE_VALUE_MUST_NOT_BE_LOGGED')):
            with self.assertLogs(self.d.local_log.logger,level='WARNING') as logs:
                status,_,payload=self.call('/api/jobs',cookie=cookie)
        self.assertEqual(status,500)
        self.assertNotIn('FAKE_VALUE_MUST_NOT_BE_LOGGED',''.join(logs.output))
        self.assertNotIn(BOOT,' / '.join(logs.output));self.assertNotIn(SESSION,' / '.join(logs.output))
        self.assertNotIn(b'FAKE_VALUE_MUST_NOT_BE_LOGGED',payload)

    def test_raw_control_and_absolute_request_targets_are_rejected(self):
        for path in ('/api/cat\talog','/api/\ncatalog','http://127.0.0.1:43333/api/catalog','//other/api/catalog'):
            with self.subTest(path=repr(path)),self.assertRaises(WorkflowError):request_path(path)


if __name__ == '__main__':unittest.main()
