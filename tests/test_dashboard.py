from pack_fixture_case import PackFixtureCase
from test_catalog_integration import session_headers
import copy
import http.client
import io
import json
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from storymotion.dashboard import Dashboard,Handler
from storymotion.security import WorkflowError,scan_bytes


class DashboardTests(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.d=Dashboard(self.root/'work')
    def tearDown(self):self.d.clear_keys();self.tmp.cleanup()
    def data(self,account='sample-flow',fmt='video-script'):
        t=self.d.template(account,fmt)
        content=t['template']['video']['script'] if t['template']['video'] else 'A manually written fixture.'
        return {'account':account,'format':fmt,'title':'Local fixture','brief':'Local fixture brief','content':content,
                'caption':'Local fixture caption','provider':'local','model':'manual','task':'plan' if fmt in {'miniature-asmr','psychology-animation','video-brief'} else 'text','template_revision':t['revision']}
    def job(self,**kwargs):return self.d.enqueue(self.data(**kwargs))

    def test_registry_is_open_and_contains_all_named_accounts(self):
        self.assertFalse(self.d.catalog['inventory_complete'])
        self.assertEqual({a['id'] for a in self.d.catalog['accounts']},{'sample-flow','sample-mechanism','sample-series','sample-reflection'})
        self.assertNotIn('sample-flow-lab',{a['id'] for a in self.d.catalog['accounts']})

    def test_account_format_binding_enforced(self):
        with self.assertRaises(WorkflowError):self.job(account='sample-flow',fmt='serial-2d')
    def test_provider_model_task_enforced(self):
        d=self.data();d.update(provider='elevenlabs',model='eleven_v4',task='text')
        with self.assertRaises(WorkflowError):self.d.enqueue(d)
    def test_selected_disabled_provider_is_never_called(self):
        d=self.data();d.update(provider='openai',model='model-selection-pending');j=self.d.enqueue(d);self.d.prepare(j['id'])
        plan=json.loads((self.d.output(j['id'])/'plan.json').read_text());self.assertFalse(plan['provider_executed']);self.assertEqual(plan['paid_calls'],0)
    def test_queue_is_idempotent(self):
        a=self.job();b=self.job();self.assertEqual(a['id'],b['id']);self.assertEqual(len(self.d.jobs()),1)
    def test_prepare_and_export_real_text_package(self):
        j=self.job();p=self.d.prepare(j['id']);self.assertEqual(p['status'],'prepared')
        result=self.d.export(j['id']);self.assertEqual(result['status'],'review_copy')
        with zipfile.ZipFile(self.d.output(j['id'])/'package.zip') as z:
            self.assertIsNone(z.testzip());self.assertIn('draft.md',z.namelist());self.assertIn('plan.json',z.namelist())
    def test_no_key_or_key_state_in_export(self):
        self.d.demo_key({'provider':'openai','value':'FAKE_PRIVATE_DEMO'})
        j=self.job();self.d.prepare(j['id']);self.d.export(j['id'])
        with zipfile.ZipFile(self.d.output(j['id'])/'package.zip') as z:
            for f in z.namelist():self.assertNotIn(b'FAKE_PRIVATE_DEMO',z.read(f))
        self.assertNotIn(b'FAKE_PRIVATE_DEMO',(self.root/'work/jobs.sqlite3').read_bytes())
    def test_real_key_rejected_no_value_echo(self):
        fake='sk-'+'z'*28
        with self.assertRaises(WorkflowError) as e:self.d.demo_key({'provider':'openai','value':fake})
        self.assertNotIn(fake,str(e.exception));self.assertFalse(self.d.slots)
    def test_fake_key_only_ram_and_never_returned(self):
        self.d.demo_key({'provider':'openai','value':'FAKE_DEMO_ONLY'})
        status=self.d.key_status();self.assertTrue(status['slots']);self.assertNotIn('FAKE_DEMO_ONLY',json.dumps(status))
        self.assertFalse(Dashboard(self.root/'work').key_status()['slots'])
    def test_fake_key_expiration_and_clear(self):
        self.d.demo_key({'provider':'openai','value':'FAKE_DEMO_ONLY'})
        self.d.slots['openai']['until']=0;self.assertEqual(self.d.key_status()['slots'],[])
        self.d.demo_key({'provider':'openai','value':'FAKE_DEMO_ONLY'});self.d.clear_keys();self.assertFalse(self.d.slots)
    def test_template_revision_conflict(self):
        t=self.d.template('sample-flow','video-script');req={'account':'sample-flow','format':'video-script',**t}
        self.assertEqual(self.d.save_template(req)['revision'],1)
        with self.assertRaisesRegex(WorkflowError,'değişti'):self.d.save_template(req)
    def test_queue_binds_template_revision(self):
        d=self.data();t=self.d.template('sample-flow','video-script');self.d.save_template({'account':'sample-flow','format':'video-script',**t})
        with self.assertRaisesRegex(WorkflowError,'revizyonu'):self.d.enqueue(d)
    def test_existing_job_keeps_template_snapshot(self):
        j=self.job();t=self.d.template('sample-flow','video-script');t['template']['tone']='Changed local tone'
        self.d.save_template({'account':'sample-flow','format':'video-script',**t})
        self.assertNotEqual(self.d.job(j['id'])['payload']['template']['template']['tone'],'Changed local tone')
    def test_secret_fields_rejected_at_any_depth(self):
        t=self.d.template('sample-flow','video-script');t['template']['extra']={'api_key':'FAKE_DEMO_ONLY'}
        with self.assertRaisesRegex(WorkflowError,'credential'):self.d.save_template({'account':'sample-flow','format':'video-script',**t})
    def test_secret_text_refused(self):
        d=self.data();d['content']='sk-'+'z'*28
        with self.assertRaises(WorkflowError):self.d.enqueue(d)
        self.assertFalse(self.d.jobs())
    def test_video_prepare_creates_real_editable_source(self):
        j=self.job(account='sample-mechanism',fmt='short-explainer');self.d.prepare(j['id'])
        self.assertTrue((self.d.output(j['id'])/'source/index.html').is_file());self.assertTrue((self.d.output(j['id'])/'cover.svg').is_file())
    def test_pending_adapter_produces_plan_not_video(self):
        j=self.job(account='sample-reflection',fmt='psychology-animation');self.d.prepare(j['id'])
        out=self.d.output(j['id']);self.assertTrue((out/'plan.json').is_file());self.assertFalse(list(out.rglob('*.mp4')))
    def test_tampered_output_prevents_export(self):
        j=self.job();self.d.prepare(j['id']);(self.d.output(j['id'])/'draft.md').write_text('tampered')
        with self.assertRaisesRegex(WorkflowError,'değişti'):self.d.export(j['id'])
        self.d.prepare(j['id']);self.d.export(j['id'])
    def test_prepare_reuses_artifacts(self):
        j=self.job();self.d.prepare(j['id']);p=self.d.output(j['id'])/'draft.md';stamp=p.stat().st_mtime_ns
        self.d.prepare(j['id']);self.assertEqual(p.stat().st_mtime_ns,stamp)
    def test_budget_does_not_enable_calls(self):
        j=self.job();r=self.d.budget(j['id'],{'max_usd':'.01','quote_source':'Mock only','approved_by':'Test fixture'})
        self.assertFalse(r['live_calls_enabled']);self.assertFalse(r['provider_billing_cap']);self.assertEqual(r['actual_microusd'],0)
    def test_invalid_job_path_rejected(self):
        with self.assertRaises(WorkflowError):self.d.job('../../etc/passwd')
    def test_http_origin_and_host_gates(self):
        h=Handler.__new__(Handler);h.server=types.SimpleNamespace(server_address=('127.0.0.1',4397));h.headers=http.client.HTTPMessage()
        h.headers['Host']='127.0.0.1:4397';self.assertTrue(h.allowed());self.assertFalse(h.allowed(True))
        h.headers['Origin']='http://evil.invalid';h.headers['X-Storymotion-Local']='1';self.assertFalse(h.allowed(True))
        h.headers.replace_header('Origin','http://127.0.0.1:4397');self.assertTrue(h.allowed(True))
        h.headers.replace_header('Host','rebinding.invalid:4397');self.assertFalse(h.allowed())
    def test_http_real_key_is_clean_error(self):
        h=Handler.__new__(Handler);h.server=types.SimpleNamespace(server_address=('127.0.0.1',4397),dashboard=self.d)
        h.headers=session_headers(h.server,write=True);raw=json.dumps({'provider':'openai','value':'sk-'+'z'*28}).encode()
        for k,v in {'Content-Type':'application/json','Content-Length':str(len(raw))}.items():h.headers[k]=v
        h.path='/api/keys';h.rfile=io.BytesIO(raw);responses=[];h.send=lambda s,v:responses.append((s,v));h.do_POST()
        self.assertEqual(responses[0][0],400);self.assertNotIn('sk-',json.dumps(responses));self.assertFalse(self.d.slots)
    def test_static_files_have_no_remote_assets_or_storage(self):
        from storymotion.engine import ROOT
        js=(ROOT/'dashboard/app.js').read_text();html=(ROOT/'dashboard/index.html').read_text()
        self.assertNotIn('localStorage',js);self.assertNotIn('sessionStorage',js);self.assertNotIn('innerHTML',js);self.assertNotIn('https://',html)


if __name__=='__main__':unittest.main()
