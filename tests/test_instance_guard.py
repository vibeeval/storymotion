from pack_fixture_case import PackFixtureCase
"""Real POSIX file locks/owned Python children; socket lifecycle is mocked."""
import contextlib
import os
import select
import socketserver
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from storymotion.instance_guard import WorkspaceInstance
from storymotion.dashboard import make_server,LocalDashboardServer,Handler
from storymotion.engine import ROOT
from storymotion.security import WorkflowError


@contextlib.contextmanager
def mocked_transport():
    def init(server,address,handler,bind_and_activate=True):
        server.server_address=address;server.RequestHandlerClass=handler
        server.socket=types.SimpleNamespace(close=Mock());server._threads=types.SimpleNamespace(join=Mock())
    with patch('storymotion.dashboard.http.server.ThreadingHTTPServer.__init__',init),patch.object(LocalDashboardServer,'server_bind') as bind,patch.object(LocalDashboardServer,'server_activate') as activate:
        yield bind,activate


class WorkspaceLockTests(PackFixtureCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'workspace'
    def tearDown(self):self.tmp.cleanup()
    def child(self,body):
        return subprocess.Popen([sys.executable,'-c',body,str(self.root)],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
            env={k:os.environ[k] for k in ('PATH','LANG','LC_ALL','TMPDIR') if k in os.environ})
    def ready(self,p):
        readable,_,_=select.select([p.stdout],[],[],3);self.assertTrue(readable,'Owned lock process did not respond')
        self.assertEqual(p.stdout.readline().strip(),'HELD')
    def test_same_process_exclusion_and_persistent_inode_reuse(self):
        guard=WorkspaceInstance(self.root).acquire();inode=guard.path.stat().st_ino
        try:
            self.assertFalse(os.get_inheritable(guard.fd))
            with self.assertRaisesRegex(WorkflowError,'WORKSPACE_IN_USE'):WorkspaceInstance(self.root).acquire()
        finally:guard.close();guard.close()
        self.assertTrue(guard.path.exists());self.assertEqual(guard.path.stat().st_ino,inode)
        with WorkspaceInstance(self.root):self.assertEqual(guard.path.stat().st_ino,inode)
    def test_real_second_process_is_rejected_while_owner_holds_lock(self):
        code="from storymotion.instance_guard import WorkspaceInstance\nfrom storymotion.security import WorkflowError\nimport sys\ntry:\n WorkspaceInstance(sys.argv[1]).acquire()\nexcept WorkflowError:\n print('BLOCKED');sys.exit(7)\nsys.exit(9)"
        with WorkspaceInstance(self.root):
            p=self.child(code)
            try:stdout,stderr=p.communicate(timeout=5);self.assertEqual((p.returncode,stdout.strip()),(7,'BLOCKED'),stderr)
            finally:
                if p.poll() is None:p.kill();p.communicate(timeout=3)
    def test_abrupt_owned_process_exit_releases_kernel_lock_without_unlink(self):
        code="from storymotion.instance_guard import WorkspaceInstance\nimport sys\ng=WorkspaceInstance(sys.argv[1]).acquire()\nprint('HELD',flush=True)\nsys.stdin.read(1)"
        p=self.child(code)
        try:
            self.ready(p)
            with self.assertRaisesRegex(WorkflowError,'WORKSPACE_IN_USE'):WorkspaceInstance(self.root).acquire()
            p.kill();p.communicate(timeout=3)
            with WorkspaceInstance(self.root):pass
            self.assertTrue((self.root/'.dashboard-instance.lock').exists())
        finally:
            if p.poll() is None:p.kill();p.communicate(timeout=3)
    def test_normal_owned_process_exit_releases_kernel_lock(self):
        code="from storymotion.instance_guard import WorkspaceInstance\nimport sys\nwith WorkspaceInstance(sys.argv[1]):\n print('HELD',flush=True)\n sys.stdin.read(1)"
        p=self.child(code)
        try:
            self.ready(p);p.communicate(input='q',timeout=3);self.assertEqual(p.returncode,0)
            with WorkspaceInstance(self.root):pass
        finally:
            if p.poll() is None:p.kill();p.communicate(timeout=3)
    def test_lock_file_symlink_or_hardlink_is_refused_without_following(self):
        self.root.mkdir(mode=0o700);other=Path(self.tmp.name)/'unrelated';other.write_text('keep')
        path=self.root/'.dashboard-instance.lock';path.symlink_to(other)
        with self.assertRaisesRegex(WorkflowError,'GUARD_UNAVAILABLE'):WorkspaceInstance(self.root).acquire()
        self.assertEqual(other.read_text(),'keep');path.unlink();os.link(other,path)
        with self.assertRaisesRegex(WorkflowError,'LOCK_FILE_INVALID'):WorkspaceInstance(self.root).acquire()
        self.assertEqual(other.read_text(),'keep')


class ServerInstanceLifecycleTests(PackFixtureCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'workspace'
    def tearDown(self):self.tmp.cleanup()
    def test_second_active_server_is_rejected_before_socket_creation_or_bind(self):
        with mocked_transport() as (bind,activate):
            one=make_server(self.root,43111)
            try:
                with self.assertRaisesRegex(WorkflowError,'WORKSPACE_IN_USE'):make_server(self.root,43112)
                self.assertEqual(bind.call_count,1);self.assertEqual(activate.call_count,1)
            finally:one.server_close()
            two=make_server(self.root,43112);two.server_close()
    def test_mock_server_in_other_process_blocks_factory_until_process_exit(self):
        code="import sys\nsys.path.insert(0,'tests')\nfrom test_instance_guard import mocked_transport\nfrom storymotion.dashboard import make_server\nwith mocked_transport():\n s=make_server(sys.argv[1],43111)\n try:\n  print('HELD',flush=True)\n  sys.stdin.read(1)\n finally:s.server_close()"
        p=subprocess.Popen([sys.executable,'-c',code,str(self.root)],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
            env={k:os.environ[k] for k in ('PATH','LANG','LC_ALL','TMPDIR') if k in os.environ})
        try:
            readable,_,_=select.select([p.stdout],[],[],3);self.assertTrue(readable);self.assertEqual(p.stdout.readline().strip(),'HELD')
            with mocked_transport() as (bind,activate):
                with self.assertRaisesRegex(WorkflowError,'WORKSPACE_IN_USE'):make_server(self.root,43112)
                bind.assert_not_called();activate.assert_not_called()
                p.communicate(input='q',timeout=3);self.assertEqual(p.returncode,0)
                server=make_server(self.root,43112);server.server_close()
        finally:
            if p.poll() is None:p.kill();p.communicate(timeout=3)
    def test_symlink_relative_and_dot_aliases_share_one_server_guard(self):
        with mocked_transport():
            one=make_server(self.root,43111);alias=Path(self.tmp.name)/'alias';alias.symlink_to(self.root,target_is_directory=True)
            try:
                for path in [alias,alias/'missing/..',Path(os.path.relpath(self.root,Path.cwd()))]:
                    with self.subTest(path=str(path)),self.assertRaisesRegex(WorkflowError,'WORKSPACE_IN_USE'):make_server(path,43112)
            finally:one.server_close()
    def test_distinct_workspaces_can_have_independent_servers(self):
        with mocked_transport():
            one=make_server(self.root,43111);two=make_server(Path(self.tmp.name)/'other',43112)
            try:self.assertNotEqual(one.dashboard.workspace,two.dashboard.workspace)
            finally:one.server_close();two.server_close()
    def test_normal_close_drains_http_workers_before_guard_release_and_is_idempotent(self):
        with mocked_transport():
            server=make_server(self.root,43111);events=[]
            def drain():
                with self.assertRaisesRegex(WorkflowError,'WORKSPACE_IN_USE'):WorkspaceInstance(self.root).acquire()
                events.append('drained')
            server._threads.join.side_effect=drain
            server.server_close();server.server_close();self.assertEqual(events,['drained'])
            with WorkspaceInstance(self.root):pass
            self.assertFalse(server.daemon_threads);self.assertTrue(server.block_on_close)
    def test_concurrent_close_cannot_release_guard_while_first_drains_real_http_thread(self):
        # stdlib _Threads.join pops its list before waiting. A concurrent close
        # must not interpret that empty list as a completed drain.
        release=threading.Event();joining=threading.Event();second_started=threading.Event();second_done=threading.Event();errors=[]
        class OwnedHttpThread(threading.Thread):
            def join(self,*args,**kwargs):
                joining.set();return super().join(*args,**kwargs)
        worker=OwnedHttpThread(target=lambda:release.wait(5),daemon=False)
        def close(server,second=False):
            if second:second_started.set()
            try:server.server_close()
            except Exception as ex:errors.append(ex)
            finally:
                if second:second_done.set()
        with mocked_transport():
            server=make_server(self.root,43111);worker.start()
            server._threads=socketserver._Threads();server._threads.append(worker)
            first=threading.Thread(target=close,args=(server,));second=threading.Thread(target=close,args=(server,True))
            try:
                first.start();self.assertTrue(joining.wait(2),'First close did not enter stdlib thread join')
                self.assertEqual(len(server._threads),0);self.assertTrue(worker.is_alive())
                second.start();self.assertTrue(second_started.wait(2))
                self.assertFalse(second_done.wait(.2),'Concurrent close returned before the first HTTP worker drained')
                self.assertTrue(first.is_alive())
                with self.assertRaisesRegex(WorkflowError,'WORKSPACE_IN_USE'):make_server(self.root,43112)
            finally:
                release.set();worker.join(2)
                for thread in (first,second):
                    if thread.ident is not None:thread.join(2)
                server.server_close()
            self.assertFalse(first.is_alive());self.assertFalse(second.is_alive());self.assertEqual(errors,[])
            self.assertEqual(server.socket.close.call_count,1)
            replacement=make_server(self.root,43112);replacement.server_close()
    def test_interrupted_http_drain_cannot_be_retried_as_an_empty_success(self):
        release=threading.Event()
        class OwnedHttpThread(threading.Thread):
            def join(self,*args,**kwargs):raise RuntimeError('Synthetic interrupted HTTP drain')
        worker=OwnedHttpThread(target=lambda:release.wait(5),daemon=False)
        with mocked_transport():
            server=make_server(self.root,43111);worker.start()
            server._threads=socketserver._Threads();server._threads.append(worker)
            try:
                with self.assertRaisesRegex(RuntimeError,'interrupted HTTP drain'):server.server_close()
                self.assertEqual(len(server._threads),0);self.assertTrue(worker.is_alive())
                with self.assertRaisesRegex(WorkflowError,'HTTP_DRAIN_INCOMPLETE'):server.server_close()
                with self.assertRaisesRegex(WorkflowError,'WORKSPACE_IN_USE'):make_server(self.root,43112)
            finally:
                release.set();threading.Thread.join(worker,2)
                # Test owns this failed server and confirms the worker ended;
                # production recovery intentionally requires process exit.
                server.instance_guard.close()
            self.assertFalse(worker.is_alive())
    def test_dashboard_or_bind_initialization_failure_releases_guard(self):
        with mocked_transport() as (bind,activate):
            with patch('storymotion.dashboard.Dashboard',side_effect=RuntimeError('synthetic init failure')):
                with self.assertRaises(RuntimeError):make_server(self.root,43111)
            with WorkspaceInstance(self.root):pass
            bind.side_effect=OSError('synthetic bind failure')
            with self.assertRaises(OSError):make_server(self.root,43111)
            with WorkspaceInstance(self.root):pass
    def test_unsettled_background_worker_retains_lock_until_successful_reclose(self):
        with mocked_transport():
            server=make_server(self.root,43111);thread=types.SimpleNamespace(is_alive=lambda:True,join=Mock())
            server.dashboard.eleven.threads['synthetic']=thread
            try:
                with self.assertRaisesRegex(WorkflowError,'BACKGROUND_WORK_ACTIVE'):server.server_close()
                with self.assertRaisesRegex(WorkflowError,'WORKSPACE_IN_USE'):WorkspaceInstance(self.root).acquire()
            finally:server.dashboard.eleven.threads.clear();server.server_close()
            with WorkspaceInstance(self.root):pass
    def test_owned_request_socket_timeout_is_bounded_without_real_socket(self):
        server=LocalDashboardServer.__new__(LocalDashboardServer);connection=types.SimpleNamespace(settimeout=Mock())
        with patch('storymotion.dashboard.http.server.ThreadingHTTPServer.get_request',return_value=(connection,('127.0.0.1',1))):
            self.assertEqual(server.get_request()[0],connection);connection.settimeout.assert_called_once_with(30)
    def test_closing_server_rejects_pending_write_requests(self):
        from http.client import HTTPMessage
        h=Handler.__new__(Handler);h.server=types.SimpleNamespace(server_address=('127.0.0.1',43111),_closing=True)
        values={'Host':'127.0.0.1:43111','Origin':'http://127.0.0.1:43111','X-Storymotion-Local':'1'}
        def headers():
            result=HTTPMessage()
            for key,value in values.items():result[key]=value
            return result
        h.headers=headers()
        self.assertTrue(h.allowed(False));self.assertFalse(h.allowed(True))
        h.server._closing=False
        self.assertTrue(h.allowed(True))
        for key,value in values.items():
            h.headers=headers();h.headers[key]=value
            self.assertEqual(len(h.headers.get_all(key)),2)
            self.assertFalse(h.allowed(True),key)
            if key=='Host':self.assertFalse(h.allowed(False))
