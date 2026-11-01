"""Atomic replacement and explicit owned SQLite lifecycle, local fixtures only."""
import concurrent.futures
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from pack_fixture_case import PackFixtureCase
from storymotion import security
from storymotion.dashboard import Dashboard, make_server
from storymotion.engine import Engine
from storymotion.qa_review import ReviewService
from storymotion.store import Store
from storymotion.security import WorkflowError, write_json


class AtomicJsonTests(unittest.TestCase):
    def test_parallel_writers_never_share_temp_or_publish_partial_json(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'state.json';write_json(path,{'writer':-1,'data':'x'*3000})
            planted=Path(temp)/'state.json.tmp';planted.write_text('keep existing file')
            seen=[];errors=[];stop=threading.Event();replace=security.os.replace
            def capture(source,destination):seen.append(str(source));return replace(source,destination)
            def read():
                while not stop.is_set():
                    try:
                        value=json.loads(path.read_text());assert set(value)=={'writer','data'} and value['data']=='x'*3000
                    except Exception as error:errors.append(type(error).__name__)
            reader=threading.Thread(target=read);reader.start()
            try:
                with patch('storymotion.security.os.replace',side_effect=capture):
                    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                        list(pool.map(lambda n:write_json(path,{'writer':n,'data':'x'*3000}),range(30)))
            finally:stop.set();reader.join(3)
            self.assertFalse(errors);self.assertEqual(len(seen),30);self.assertEqual(len(set(seen)),30)
            self.assertEqual(planted.read_text(),'keep existing file')
            self.assertEqual(list(Path(temp).glob('.state.json.*.tmp')),[])

    def test_failure_before_replace_preserves_old_bytes_and_cleans_only_owned_temp(self):
        for method in ('fsync','replace'):
            with self.subTest(method=method),tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'state.json';path.write_text('{"old":true}')
                with patch('storymotion.security.os.'+method,side_effect=OSError('synthetic write failure')):
                    with self.assertRaises(OSError):write_json(path,{'new':True})
                self.assertEqual(path.read_text(),'{"old":true}')
                self.assertEqual(list(Path(temp).glob('.*.tmp')),[])

    def test_json_validation_precedes_filesystem_change_and_fsync_covers_file_and_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'new/state.json'
            with self.assertRaises(ValueError):write_json(path,{'invalid':float('nan')})
            self.assertFalse(path.parent.exists())
            real=security.os.fsync
            with patch('storymotion.security.os.fsync',side_effect=real) as sync:
                write_json(path,{'valid':1})
            self.assertEqual(sync.call_count,2)


class ConnectionLifecycleTests(PackFixtureCase):
    def test_store_context_closes_on_success_and_exception_without_implicit_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            with Store(Path(temp)/'ok') as store:connection=store.db
            with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')
            store.close()
            with self.assertRaises(RuntimeError):
                with Store(Path(temp)/'failed') as failed:
                    second=failed.db;raise RuntimeError('synthetic context failure')
            with self.assertRaises(sqlite3.ProgrammingError):second.execute('SELECT 1')

    def test_engine_lazy_close_does_not_create_database_and_context_closes_created_store(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'absent';engine=Engine(path);engine.close();self.assertFalse(path.exists())
            with Engine(Path(temp)/'owned') as engine:connection=engine.store.db
            with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')
            engine.close()

    def test_dashboard_prepare_closes_store_on_success_and_failed_build(self):
        with tempfile.TemporaryDirectory() as temp:
            d=Dashboard(temp);self.addCleanup(d.clear_keys)
            video=d.template('sample-flow','account-video')['template']['video']
            def job(title):return d.enqueue({'account':'sample-flow','format':'account-video','title':title,'brief':video['brief'],'content':video['script'],'caption':video['caption'],'provider':'local','model':'manual','task':'text','template_revision':0})['id']
            first=job('First');second=job('Second');connections=[];close=Store.close
            def capture(store):connections.append(store.db);close(store)
            with patch.object(Store,'close',capture):
                d.prepare(first)
                with patch('storymotion.compose.build',side_effect=WorkflowError('synthetic failure')):
                    with self.assertRaises(WorkflowError):d.prepare(second)
            self.assertEqual(len(connections),2)
            for connection in connections:
                with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')

    def test_qa_context_and_server_shutdown_close_owned_review_connection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with ReviewService(root/'qa',media_root=root/'media') as qa:connection=qa.db
            with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')
            qa.close()
            from test_instance_guard import mocked_transport
            with mocked_transport():
                server=make_server(root/'server',43333)
                service=server.dashboard.reviews.runtime();connection=service.db
                server.server_close();server.server_close()
            with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')
