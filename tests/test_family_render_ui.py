"""Authenticated real Handler fixtures -> actual gallery/render scripts in a DOM.

Every execution boundary is mocked. Synthetic bytes are never native MP4 proof.
"""
import json
import os
from pathlib import Path
import subprocess
import threading
import unittest
from unittest.mock import patch

from storymotion import family_render
from storymotion.security import WorkflowError
from storymotion.template_families import capabilities
import test_family_render as render_fixture

ROOT=Path(__file__).resolve().parents[1]


class FamilyRenderUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        case=render_fixture.FamilyRenderTests();case.setUp()
        def get(path):
            code,value,_=case.f.get(path)
            if code!=200:raise AssertionError(value)
            return value
        def post(action,data):
            code,value,_=case.post(action,data)
            if code!=200:raise AssertionError(value)
            return value
        def hold():
            entered=threading.Event();release=threading.Event()
            def work(*args):
                entered.set()
                if not release.wait(30):raise AssertionError('Owned UI fixture worker timed out')
                return case.fake(*args)
            case.execute.side_effect=work
            return entered,release
        root='/api/family-renders/neutral/'+case.job
        try:
            initial=get(root);start_data=case.payload();entered,release=hold()
            try:
                started=post('start',start_data)
                if not entered.wait(5):raise AssertionError('Owned fixture did not run')
                running=get(root);replay=post('start',start_data)
                if case.execute.call_count!=1:raise AssertionError('Duplicate Handler dispatch')
                cancel_data={k:running[k] for k in ('engine','attempt','generation')};cancelling=post('cancel',cancel_data)
            finally:release.set()
            case.settle(started['attempt']);cancelled=get(root)
            retry_data=case.payload('retry',cancelled);entered,release=hold()
            try:
                retried=post('retry',retry_data)
                if not entered.wait(5):raise AssertionError('Retry worker did not run')
                retry_running=get(root)
            finally:release.set()
            case.settle(retried['attempt']);complete=get(root)
            downloads={}
            for file in complete['files']:
                code,raw,_=case.f.get(file['download_url'])
                if code!=200 or not raw.startswith(b'TEST_ONLY_SYNTHETIC_NOT_MP4'):raise AssertionError('Verified synthetic download failed')
                downloads[file['name']]=len(raw)
            _,other=case.f.prepare('contour-trace','remotion')
            detail=get('/api/family-jobs/neutral/'+case.job);other_detail=get(other['detail_url'])
            other_initial=get('/api/family-renders/neutral/'+other['job'])
            listing=get('/api/family-jobs/neutral')
            cls.data={'catalog':capabilities(),'html':(ROOT/'dashboard/index.html').read_text(),
                'source':(ROOT/'dashboard/template-families.js').read_text(),
                'prependSources':[(ROOT/'dashboard/template-editor.js').read_text(),(ROOT/'dashboard/family-render.js').read_text()],
                'listing':listing,'details':[detail,other_detail],'other_initial':other_initial,
                'happy':dict(initial=initial,start_data=start_data,started=started,running=running,replay=replay,
                    cancel_data=cancel_data,cancelling=cancelling,cancelled=cancelled,retry_data=retry_data,
                    retried=retried,retry_running=retry_running,complete=complete,downloads=downloads)}
        finally:case.doCleanups()
        # Independently prepared roots for failure/runtime/restart fixture states.
        for name in ('failed','blocked','restart'):
            case=render_fixture.FamilyRenderTests();case.setUp();root='/api/family-renders/neutral/'+case.job
            try:
                initial=get(root)
                if name=='blocked':
                    with patch.object(family_render,'require_engine',side_effect=WorkflowError('TEST_ONLY_MISSING_RUNTIME')):
                        value=post('start',case.payload());case.settle(value['attempt'])
                else:
                    case.execute.side_effect=WorkflowError('TEST_ONLY_WORKER_FAILURE');value=post('start',case.payload());case.settle(value['attempt'])
                if name=='restart':
                    with case.d.connection() as db:db.execute("UPDATE family_render_attempts SET status='running',error='FAMILY_RENDER_THREAD_START_UNCONFIRMED' WHERE id=?",(value['attempt'],))
                    new=family_render.FamilyRender(case.d);case.d.family_renders=new;case.s=new;case.addCleanup(new.close)
                    worker=patch.object(new,'execute',side_effect=case.fake);worker.start();case.addCleanup(worker.stop)
                state=get(root);data=case.payload('retry',state)
                case.execute.side_effect=case.fake
                result=post('retry',data);case.settle(result['attempt']);done=get(root)
                cls.data[name]={'initial':initial,'detail':get('/api/family-jobs/neutral/'+case.job),
                    'listing':get('/api/family-jobs/neutral'),'state':state,'retry_data':data,'retried':result,'complete':done}
            finally:case.doCleanups()

    def probe(self,groups):
        result=subprocess.run(['node',str(ROOT/'tests/family_render_probe.mjs')],input=json.dumps({**self.data,'groups':groups}),
            text=True,capture_output=True,cwd=ROOT,timeout=120,env={'PATH':os.environ.get('PATH',''),'DO_NOT_TRACK':'1'})
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        value=json.loads(result.stdout);self.assertEqual(value['passed'],groups);self.assertEqual(value['failures'],[])

    def test_handler_start_status_cancel_retry_and_verified_links(self):self.probe(['flow'])
    def test_double_click_and_uncertain_request_replay_are_idempotent(self):self.probe(['idempotence'])
    def test_stale_selection_success_and_error_never_change_new_context(self):self.probe(['stale'])
    def test_malformed_action_binding_and_forged_outputs_fail_closed(self):self.probe(['malformed'])
    def test_runtime_failure_restart_recovery_requires_explicit_new_attempt(self):self.probe(['recovery'])
    def test_saved_render_selection_preserves_editor_ram_and_source_history(self):self.probe(['drafts'])
    def test_saved_preparation_current_source_engine_and_generation_limits(self):self.probe(['bindings'])
