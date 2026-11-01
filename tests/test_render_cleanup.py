"""Real SQLite fault paths, synthetic workers; never native render execution."""
import sqlite3
import threading
from unittest.mock import patch
import unittest
from storymotion.security import WorkflowError
from storymotion.instance_guard import WorkspaceInstance

import test_family_render as fixture
from test_dashboard_render_private import enqueue


class RenderCleanupTests(unittest.TestCase):
    def setUp(self):
        self.case=fixture.FamilyRenderTests();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.d=self.case.d;self.r=self.d.renders;self.s=self.case.s;self.normal=enqueue(self.d)
        self.addCleanup(self.remove_test_owned_orphans)

    def remove_test_owned_orphans(self):
        # Test-only recovery after red assertions, so inherited defects do not
        # prevent temporary-fixture teardown. Never invoked by product code.
        with self.r.lock:
            for key,(event,thread) in list(self.r.active.items()):
                if thread.ident is None or not thread.is_alive():
                    self.r.active.pop(key);self.d.render_slot.release(self.r.slot_tokens.pop(key,None))
        with self.s.lock:
            for key,(event,thread,generation,slot) in list(self.s.active.items()):
                if thread.ident is None or not thread.is_alive():self.s.active.pop(key);self.d.render_slot.release(slot)

    def normal_start(self):
        with patch('storymotion.dashboard_render.require_engine',return_value=None):return self.r.start(self.normal,'hyperframes')

    def join_normal(self):
        with self.r.lock:entry=self.r.active.get((self.normal,'hyperframes'))
        if entry:entry[1].join(13);self.assertFalse(entry[1].is_alive())

    def assert_reusable(self):
        self.assertFalse(self.r.active);self.assertFalse(self.r.slot_tokens);self.assertIsNone(self.d.render_slot.current)
        self.r.close()
        row=self.case.start();self.assertEqual(self.case.settle(row['attempt'])['status'],'complete')
        with patch('storymotion.dashboard_render.Engine.run',return_value=None):
            self.assertEqual(self.normal_start()['status'],'started');self.join_normal()
        self.assertFalse(self.r.active);self.assertFalse(self.r.slot_tokens);self.assertIsNone(self.d.render_slot.current)
        self.r.close()

    def test_normal_start_failure_records_failed_releases_owner_and_allows_both_dispatchers(self):
        with patch.object(threading.Thread,'start',side_effect=RuntimeError('TEST_ONLY_START_FAILURE')):
            with self.assertRaises(RuntimeError):self.normal_start()
        self.assertFalse(self.r.active);self.assertFalse(self.r.slot_tokens)
        self.assertEqual(self.r.row(self.normal,'hyperframes')['status'],'failed')
        self.assertEqual(self.r.row(self.normal,'hyperframes')['error'],'LOCAL_RENDER_THREAD_START_FAILED')
        self.assert_reusable()

    def test_normal_start_record_and_logger_failure_still_release_owned_state(self):
        connection=patch.object(self.d,'connection',side_effect=sqlite3.OperationalError('TEST_ONLY_PRIVATE_VALUE'))
        def startup(thread):connection.start();raise RuntimeError('TEST_ONLY_START_FAILURE')
        try:
            with patch.object(threading.Thread,'start',autospec=True,side_effect=startup),patch.object(self.d.local_log,'warning',side_effect=OSError('TEST_ONLY_LOG_FAILURE')):
                with self.assertRaisesRegex(RuntimeError,'TEST_ONLY_START_FAILURE'):self.normal_start()
        finally:connection.stop()
        self.assertFalse(self.r.active);self.assertFalse(self.r.slot_tokens);self.assertIsNone(self.d.render_slot.current)
        self.assertEqual(self.r.row(self.normal,'hyperframes')['status'],'running')
        self.assertTrue(self.r.state(self.normal,'hyperframes')['status'].startswith('interrupted'))
        self.assert_reusable()

    def test_real_sqlite_contention_at_normal_completion_cleans_memory_and_preserves_uncertainty(self):
        entered=threading.Event();release=threading.Event()
        def worker(*args,**kw):entered.set();self.assertTrue(release.wait(5))
        keeper=sqlite3.connect(self.d.workspace/'jobs.sqlite3')
        try:
            with patch('storymotion.dashboard_render.Engine.run',side_effect=worker):
                self.assertEqual(self.normal_start()['status'],'started');self.assertTrue(entered.wait(3))
                with self.r.lock:thread=self.r.active[(self.normal,'hyperframes')][1]
                keeper.execute('BEGIN IMMEDIATE');release.set();thread.join(13);self.assertFalse(thread.is_alive())
            self.assertFalse(self.r.active);self.assertFalse(self.r.slot_tokens);self.assertIsNone(self.d.render_slot.current)
            self.assertEqual(self.r.row(self.normal,'hyperframes')['status'],'running')
            self.assertTrue(self.r.state(self.normal,'hyperframes')['status'].startswith('interrupted'))
            log=(self.d.workspace/'logs/local.log').read_text()
            self.assertIn('LOCAL_WRITE_FAILED OperationalError',log);self.assertNotIn('database is locked',log)
        finally:release.set();keeper.rollback();keeper.close()
        self.assert_reusable()

    def test_family_start_and_real_sqlite_failure_is_unconfirmed_retriable_and_closeable(self):
        keeper=sqlite3.connect(self.d.workspace/'jobs.sqlite3')
        def startup(thread):keeper.execute('BEGIN IMMEDIATE');raise RuntimeError('TEST_ONLY_START_FAILURE')
        try:
            with patch.object(threading.Thread,'start',autospec=True,side_effect=startup):
                with self.assertRaisesRegex(RuntimeError,'TEST_ONLY_START_FAILURE'):self.case.start()
            self.assertFalse(self.s.active);self.assertIsNone(self.d.render_slot.current)
            row=self.case.state();self.assertEqual(row['status'],'interrupted_unconfirmed')
            self.assertEqual(self.s.row('neutral',self.case.job,row['attempt'])['status'],'queued')
        finally:keeper.rollback();keeper.close()
        retried=self.case.start(self.case.payload('retry',row),'retry');self.assertEqual(retried['generation'],2)
        self.assertEqual(self.case.settle(retried['attempt'])['status'],'complete');self.s.close()

    def test_old_normal_completion_cannot_pop_or_overwrite_new_owner(self):
        entered=threading.Event();release=threading.Event()
        def worker(*args,**kw):entered.set();self.assertTrue(release.wait(5))
        with patch('storymotion.dashboard_render.Engine.run',side_effect=worker):
            self.normal_start();self.assertTrue(entered.wait(3))
            key=(self.normal,'hyperframes')
            with self.r.lock:
                old=self.r.active[key];old_slot=self.r.slot_tokens[key]
                self.d.render_slot.release(old_slot);new_slot=self.d.render_slot.claim(('normal','TEST_ONLY_NEW_OWNER'))
                foreign=(threading.Event(),threading.Thread(target=lambda:None));self.r.active[key]=foreign;self.r.slot_tokens[key]=new_slot
            with self.d.connection() as db:db.execute("UPDATE dashboard_renders SET engine_job=?,status='running' WHERE job=? AND engine=?",('f'*24,self.normal,'hyperframes'))
            release.set();old[1].join(5);self.assertFalse(old[1].is_alive())
        self.assertIs(self.r.active[key],foreign);self.assertEqual(self.r.slot_tokens[key],new_slot)
        self.assertEqual(self.d.render_slot.current[0],new_slot);self.assertEqual(self.r.row(self.normal,'hyperframes')['status'],'running')
        self.assertEqual(self.r.row(self.normal,'hyperframes')['engine_job'],'f'*24)

    def test_family_start_failure_cannot_remove_transferred_generation_or_slot(self):
        foreign={}
        def transfer(account,job,attempt,generation,*args):
            owned=self.s.active[attempt];self.d.render_slot.release(owned[3]);slot=self.d.render_slot.claim(('family','TEST_ONLY_NEW_OWNER'))
            entry=(threading.Event(),threading.Thread(target=lambda:None),generation+1,slot)
            self.s.active[attempt]=entry;foreign.update(attempt=attempt,entry=entry,slot=slot);return False
        with patch.object(threading.Thread,'start',side_effect=RuntimeError('TEST_ONLY_START_FAILURE')),patch.object(self.s,'finish',side_effect=transfer):
            with self.assertRaises(RuntimeError):self.case.start()
        self.assertIs(self.s.active[foreign['attempt']],foreign['entry']);self.assertEqual(self.d.render_slot.current[0],foreign['slot'])

    def interrupted_ack(self, service, after_running=None, error=KeyboardInterrupt, on_interrupt=None):
        """Real Thread.start/native bootstrap; only its acknowledgement wait fails."""
        real_start=threading.Thread.start;threads=[];self.ack_threads=threads
        def start(thread):
            gate=getattr(thread._target,'__self__',None)
            if thread._target!=service.work and getattr(gate,'target',None)!=service.work:return real_start(thread)
            threads.append(thread);real_wait=thread._started.wait
            def ack(timeout=None):
                self.assertTrue(real_wait(3),'Owned native thread did not start')
                if hasattr(gate,'entered'):self.assertTrue(gate.entered.wait(3),'Owned target did not enter')
                if after_running:self.assertTrue(after_running.wait(3),'Real DB running transition not observed')
                if on_interrupt:on_interrupt()
                raise error('TEST_ONLY_START_ACK_INTERRUPTION')
            with patch.object(thread._started,'wait',side_effect=ack):return real_start(thread)
        return patch.object(threading.Thread,'start',new=start),threads

    def hold_worker(self, service):
        entered=threading.Event();release=threading.Event();self.worker_release=release
        def work(*args,**kwargs):
            entered.set()
            if not release.wait(30):raise AssertionError('Test-owned worker barrier expired')
            return self.case.fake(*args) if service is self.s else None
        if service is self.s:self.case.execute.side_effect=work
        else:
            scope=patch('storymotion.dashboard_render.Engine.run',side_effect=work);scope.start();self.addCleanup(scope.stop)
        def drain():
            release.set()
            with service.lock:threads=[v[1] for v in service.active.values()]
            threads+=getattr(self,'ack_threads',[])
            for thread in threads:
                if thread.ident is not None:thread.join(5)
        self.addCleanup(drain)
        return entered,release

    def assert_instance_retained(self, thread):
        from test_instance_guard import mocked_transport
        from storymotion.dashboard import LocalDashboardServer,Handler
        guard=WorkspaceInstance(self.d.workspace).acquire()
        with mocked_transport():server=LocalDashboardServer(('127.0.0.1',43334),Handler)
        # Exact real services/guard, mocked socket transport only.
        server.dashboard=self.d;server.instance_guard=guard
        def close_after_test_worker():
            self.worker_release.set()
            if thread.ident is not None:thread.join(5)
            server.server_close()
        self.addCleanup(close_after_test_worker)
        real_join=thread.join
        with patch.object(thread,'join',side_effect=lambda timeout=None:real_join(.01)):
            with self.assertRaisesRegex(WorkflowError,'BACKGROUND_WORK_ACTIVE'):server.server_close()
        with self.assertRaisesRegex(WorkflowError,'WORKSPACE_IN_USE'):WorkspaceInstance(self.d.workspace).acquire()
        self.assertIsNotNone(guard.fd)
        return server

    def test_family_actual_start_ack_interrupt_retains_slot_generation_and_instance_until_exit(self):
        entered,release=self.hold_worker(self.s);running=threading.Event();original=self.s.transition
        def transition(*args,**kwargs):
            result=original(*args,**kwargs)
            if result and args[5]=='running':running.set()
            return result
        ack,threads=self.interrupted_ack(self.s,running)
        with patch.object(self.s,'transition',side_effect=transition),ack:
            with self.assertRaises(KeyboardInterrupt):self.case.start()
        self.assertTrue(entered.wait(3));thread=threads[0];self.assertTrue(thread.is_alive())
        row=self.case.state();self.assertEqual(row['status'],'running');self.assertEqual(row['error'],'FAMILY_RENDER_THREAD_START_UNCONFIRMED')
        self.assertEqual(len(self.s.active),1);self.assertIsNotNone(self.d.render_slot.current)
        with self.assertRaisesRegex(WorkflowError,'WORKER_BUSY|NOT_RETRYABLE'):self.case.start(self.case.payload('retry',row),'retry')
        self.assertEqual(self.normal_start()['status'],'local_render_already_running');self.assertEqual(self.case.execute.call_count,1)
        server=self.assert_instance_retained(thread);release.set();thread.join(5);self.assertFalse(thread.is_alive())
        self.assertFalse(self.s.active);self.assertIsNone(self.d.render_slot.current)
        self.assertEqual(self.case.state()['status'],'cancelled');server.server_close()
        with WorkspaceInstance(self.d.workspace):pass

    def test_normal_actual_start_ack_interrupt_retains_slot_and_instance_until_exit(self):
        entered,release=self.hold_worker(self.r);ack,threads=self.interrupted_ack(self.r)
        with ack:
            with self.assertRaises(KeyboardInterrupt):self.normal_start()
        self.assertTrue(entered.wait(3));thread=threads[0];self.assertTrue(thread.is_alive())
        self.assertEqual(len(self.r.active),1);self.assertIsNotNone(self.d.render_slot.current)
        self.assertEqual(self.r.row(self.normal,'hyperframes')['error'],'LOCAL_RENDER_THREAD_START_UNCONFIRMED')
        with self.assertRaisesRegex(WorkflowError,'WORKER_BUSY'):self.case.start()
        self.assertEqual(self.normal_start()['status'],'local_render_already_running')
        server=self.assert_instance_retained(thread);release.set();thread.join(5);self.assertFalse(thread.is_alive())
        self.assertFalse(self.r.active);self.assertFalse(self.r.slot_tokens);self.assertIsNone(self.d.render_slot.current)
        server.server_close()
        with WorkspaceInstance(self.d.workspace):pass

    def test_ack_exception_after_start_and_late_completion_are_not_failed_before_start(self):
        entered,release=self.hold_worker(self.s);ack,threads=self.interrupted_ack(self.s,error=RuntimeError)
        with ack:
            with self.assertRaises(RuntimeError):self.case.start()
        self.assertTrue(entered.wait(3));row=self.case.state();self.assertEqual(row['status'],'running')
        self.assertEqual(self.case.execute.call_count,1);release.set();threads[0].join(5)
        self.assertEqual(self.case.state()['status'],'complete');self.assertFalse(self.s.active);self.assertIsNone(self.d.render_slot.current)

    def test_normal_ack_exception_and_late_completion_keep_truthful_terminal_state(self):
        entered,release=self.hold_worker(self.r);ack,threads=self.interrupted_ack(self.r,error=RuntimeError)
        with ack:
            with self.assertRaises(RuntimeError):self.normal_start()
        self.assertTrue(entered.wait(3));self.assertEqual(self.r.row(self.normal,'hyperframes')['status'],'running')
        self.assertIsNotNone(self.d.render_slot.current);release.set();threads[0].join(5)
        row=self.r.row(self.normal,'hyperframes');self.assertEqual(row['status'],'complete');self.assertIsNone(row['error'])
        self.assertFalse(self.r.active);self.assertFalse(self.r.slot_tokens);self.assertIsNone(self.d.render_slot.current)

    def test_start_ack_bookkeeping_failure_still_keeps_live_normal_owner(self):
        entered,release=self.hold_worker(self.r)
        failure=patch.object(self.d,'connection',side_effect=sqlite3.OperationalError('TEST_ONLY_PRIVATE_ACK_VALUE'))
        ack,threads=self.interrupted_ack(self.r,on_interrupt=failure.start)
        try:
            with ack:
                with self.assertRaises(KeyboardInterrupt):self.normal_start()
        finally:failure.stop()
        self.assertTrue(entered.wait(3));self.assertTrue(threads[0].is_alive())
        self.assertEqual(len(self.r.active),1);self.assertIsNotNone(self.d.render_slot.current)
        self.assertEqual(self.r.row(self.normal,'hyperframes')['status'],'running')
        self.assertIsNone(self.r.row(self.normal,'hyperframes')['error'])
        log=(self.d.workspace/'logs/local.log').read_text();self.assertIn('LOCAL_WRITE_FAILED OperationalError',log);self.assertNotIn('TEST_ONLY_PRIVATE_ACK_VALUE',log)
        release.set();threads[0].join(5);self.assertEqual(self.r.row(self.normal,'hyperframes')['status'],'complete')
        self.assertFalse(self.r.active);self.assertIsNone(self.d.render_slot.current)

    def test_entry_gate_fences_delayed_real_bootstrap_and_admits_only_once(self):
        from storymotion.render_slot import WorkerStart
        before=threading.Event();release=threading.Event();calls=[]
        gate=WorkerStart(lambda:calls.append('entered'),())
        def delayed():
            before.set()
            if not release.wait(5):raise AssertionError('Test bootstrap barrier expired')
            gate.run()
        thread=threading.Thread(target=delayed)
        thread.start()
        try:
            self.assertTrue(before.wait(3));self.assertTrue(thread.is_alive())
            self.assertTrue(gate.abort_before_entry());self.assertFalse(gate.entered.is_set())
            gate.run();self.assertEqual(calls,[])
        finally:release.set();thread.join(5)
        self.assertFalse(thread.is_alive());self.assertEqual(calls,[])
        gate=WorkerStart(lambda:calls.append('once'),());gate.run()
        self.assertFalse(gate.abort_before_entry());gate.run();self.assertEqual(calls,['once'])
