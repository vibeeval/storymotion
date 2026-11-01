from pack_fixture_case import PackFixtureCase
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from storymotion.dashboard import Dashboard
from storymotion.security import WorkflowError


class DashboardRenderGates(PackFixtureCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.d=Dashboard(self.tmp.name)
    def tearDown(self):self.d.renders.close();self.d.clear_keys();self.tmp.cleanup()
    def job(self,account,fmt):
        t=self.d.template(account,fmt)['template'];v=t['video']
        return self.d.enqueue({'account':account,'format':fmt,'title':v['title'] if v else 'Local plan',
            'brief':v['brief'] if v else 'Local plan','content':v['script'] if v else 'Local plan',
            'caption':v['caption'] if v else 'Local plan','provider':'local','model':'manual','task':'text','template_revision':0})['id']
    def test_plan_only_accounts_cannot_start_renderer(self):
        for account,fmt in [('sample-flow','video-script'),('sample-reflection','psychology-animation')]:
            job=self.job(account,fmt)
            with patch('storymotion.dashboard_render.require_engine',side_effect=AssertionError('must not launch')):
                with self.assertRaisesRegex(WorkflowError,'adaptörü'):self.d.renders.start(job,'remotion')
    def test_unknown_engine_and_extra_fields_never_dispatch(self):
        job=self.job('sample-mechanism','short-explainer')
        with self.assertRaises(WorkflowError):self.d.render_action(job,'render',{'engine':'automatic'})
        with self.assertRaises(WorkflowError):self.d.render_action(job,'render',{'engine':'hyperframes','command':'bad'})
    def test_unrendered_file_and_foreign_filename_refused(self):
        job=self.job('sample-mechanism','short-explainer')
        self.assertEqual(self.d.renders.state(job,'remotion')['status'],'not_started')
        for name in ['render-1080.mp4','../../jobs.sqlite3']:
            with self.assertRaises(WorkflowError):self.d.renders.download(job,'remotion',name)
    def test_cancel_only_own_job_event(self):
        first=self.job('sample-mechanism','short-explainer');second=self.job('sample-series','serial-2d')
        one=threading.Event();two=threading.Event()
        with self.d.renders.lock:self.d.renders.active={(first,'hyperframes'):(one,threading.current_thread()),(second,'remotion'):(two,threading.current_thread())}
        self.d.renders.cancel(first,'hyperframes');self.assertTrue(one.is_set());self.assertFalse(two.is_set())
        self.d.renders.active.clear()
