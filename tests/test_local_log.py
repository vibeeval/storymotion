"""Owned bounded diagnostics without URL, request, exception-value or key logging."""
import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pack_fixture_case import PackFixtureCase
from test_catalog_integration import MemoryConnection
from storymotion.dashboard import Dashboard, Handler, LocalDashboardServer, make_server
from storymotion.local_log import LocalLog
from storymotion.security import WorkflowError


class LocalLogTests(PackFixtureCase):
    def test_handler_and_server_errors_write_only_static_codes_and_class(self):
        with tempfile.TemporaryDirectory() as temp:
            boot='FAKE_'+'B'*38;session='FAKE_'+'S'*38
            with patch('storymotion.local_session.secrets.token_urlsafe',side_effect=[boot,session]):d=Dashboard(temp)
            self.addCleanup(d.clear_keys);self.addCleanup(d.close_local_log)
            server=SimpleNamespace(server_address=('127.0.0.1',43333),dashboard=d)
            cookie=d.session_auth.bootstrap(boot,43333).split(';',1)[0]
            secret='FAKE_BYOK_PRIVATE_VALUE';private='https://private.invalid/#bootstrap='+boot+' Cookie: '+cookie+' rawbody='+secret
            connection=MemoryConnection(('GET /api/jobs HTTP/1.0\r\nHost: 127.0.0.1:43333\r\nCookie: '+cookie+'\r\n\r\n').encode())
            with patch.object(d,'jobs',side_effect=RuntimeError(private)),contextlib.redirect_stderr(io.StringIO()) as stderr:
                Handler(connection,('127.0.0.1',1),server)
            self.assertEqual(stderr.getvalue(),'');self.assertIn(b' 500 ',bytes(connection.output))
            s=LocalDashboardServer.__new__(LocalDashboardServer);s.dashboard=d
            try:raise RuntimeError(private)
            except RuntimeError:s.handle_error(private,('127.0.0.1',1))
            text=(Path(temp)/'logs/local.log').read_text()
            self.assertIn('LOCAL_READ_FAILED RuntimeError',text);self.assertIn('LOCAL_HTTP_FAILED RuntimeError',text)
            for value in (boot,session,secret,private,'Cookie','https://','rawbody'):
                self.assertNotIn(value,text);self.assertNotIn(value.encode(),bytes(connection.output))

    def test_rotation_permissions_isolation_and_shutdown_revoke_log_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            left=Path(temp).resolve()/'left';right=Path(temp).resolve()/'right';left.mkdir(mode=0o700);right.mkdir(mode=0o700)
            a=LocalLog(left);b=LocalLog(right);self.addCleanup(a.close);self.addCleanup(b.close)
            a.handler.maxBytes=200
            for _ in range(30):self.assertTrue(a.warning('LOCAL_READ_FAILED',RuntimeError('FAKE_NEVER_LOG_ME')))
            self.assertTrue(b.warning('LOCAL_WRITE_FAILED',ValueError('FAKE_OTHER_PRIVATE_VALUE')))
            files=list((left/'logs').iterdir());self.assertLessEqual(len(files),3)
            self.assertEqual((left/'logs').stat().st_mode&0o777,0o700)
            for file in files:
                self.assertLessEqual(file.stat().st_size,200);self.assertEqual(file.stat().st_mode&0o777,0o600)
                self.assertNotIn('FAKE_',file.read_text());self.assertNotIn('LOCAL_WRITE_FAILED',file.read_text())
            self.assertNotIn('LOCAL_READ_FAILED',(right/'logs/local.log').read_text())
            a.close();before={p.name:p.read_bytes() for p in files}
            self.assertFalse(a.warning('LOCAL_HTTP_FAILED',RuntimeError('late')))
            self.assertEqual(before,{p.name:p.read_bytes() for p in files});self.assertIsNone(a.handler.stream)
            from test_instance_guard import mocked_transport
            with mocked_transport():
                server=make_server(Path(temp)/'server',43333)
                log=server.dashboard.local_log;log.warning('LOCAL_READ_FAILED',RuntimeError('synthetic'))
                server.server_close();self.assertTrue(log.closed);self.assertIsNone(log.handler.stream)

    def test_link_hardlink_or_permissive_log_paths_never_write_outside(self):
        for name,kind in [('logs','directory'),('logs/local.log','symlink'),('logs/local.log.1','hardlink')]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp,tempfile.TemporaryDirectory() as outside:
                root=Path(temp).resolve();external=Path(outside).resolve()/'original';external.write_text('keep')
                if kind=='directory':(root/name).symlink_to(outside,target_is_directory=True)
                else:
                    (root/'logs').mkdir(mode=0o700)
                    if kind=='symlink':(root/name).symlink_to(external)
                    else:os.link(external,root/name)
                with self.assertRaises(WorkflowError):LocalLog(root)
                self.assertEqual(external.read_text(),'keep')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();(root/'logs').mkdir(mode=0o755);(root/'logs').chmod(0o755)
            with self.assertRaisesRegex(WorkflowError,'LOCAL_LOG_UNSAFE'):LocalLog(root)
            self.assertEqual((root/'logs').stat().st_mode&0o777,0o755)

    def test_unknown_code_class_and_write_failure_cannot_echo_values_or_fallback_to_stderr(self):
        with tempfile.TemporaryDirectory() as temp:
            log=LocalLog(Path(temp).resolve());self.addCleanup(log.close)
            self.assertFalse(log.warning('FAKE_UNKNOWN_PRIVATE_CODE',RuntimeError('FAKE_PRIVATE_VALUE')))
            custom=type('FAKE_PRIVATE_CLASS',(RuntimeError,),{})
            self.assertTrue(log.warning('LOCAL_READ_FAILED',custom('FAKE_PRIVATE_VALUE')))
            text=(Path(temp)/'logs/local.log').read_text();self.assertIn('LOCAL_READ_FAILED Exception',text);self.assertNotIn('FAKE_',text)
            with patch.object(log.handler,'emit',side_effect=OSError('FAKE_STORAGE_PRIVATE_VALUE')),contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertFalse(log.warning('LOCAL_READ_FAILED',RuntimeError('FAKE_VALUE')))
            self.assertTrue(log.failed);self.assertEqual(stderr.getvalue(),'')
