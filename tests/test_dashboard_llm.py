from pack_fixture_case import PackFixtureCase
import json
import tempfile
import unittest
from pathlib import Path
from storymotion.dashboard import Dashboard
from storymotion.security import WorkflowError
from neutral_identity_fixture import assert_no_source_identity, source_identity_profiles


class DashboardWritingBridge(PackFixtureCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.d=Dashboard(self.tmp.name,llm_mode='demo')
    def tearDown(self):
        self.d.clear_keys();self.tmp.cleanup()
    def proposal(self,account='sample-flow',provider='openai'):
        c=self.d.llm_action('connect',{'provider':provider,'value':'FAKE_WRITER_BRIDGE_ONLY'})
        p=self.d.llm_action('preview',{'connection':c['connection'],
            'context':{'account':account,'title':'Yerel öneri','brief':'Özgün vektör denemesi','caption':'İnceleme taslağı'},
            'model':c['metadata']['models'][0]['id'],'max_output_tokens':2000})
        self.d.llm_action('approve',{'connection':c['connection'],'request':p['request'],
            'maximum_output_tokens':2000,'ack_unknown_cost':True,'rights_confirmed':True,'budget':None})
        self.d.llm.execute(c['connection'],p['request'],asynchronous=False)
        self.assertEqual(self.d.llm.get(p['request'])['status'],'completed')
        return p['request']

    @source_identity_profiles()
    def test_accept_creates_new_immutable_review_job_and_no_audio_or_render(self):
        request=self.proposal()
        result=self.d.llm_action('accept',{'request':request,'brand_identity':{'name':'Yeni sayfam','handle':'yenisayfam'}})
        job=self.d.job(result['accepted_job'])
        self.assertEqual(job['status'],'queued');self.assertEqual(job['payload']['format']['adapter'],'account-pack')
        self.assertTrue(job['payload']['generation']['synthetic']);self.assertFalse(job['payload']['generation']['publication_ready'])
        self.assertEqual(self.d.renders.state(job['id'],'remotion')['status'],'not_started')
        prepared=self.d.prepare(job['id']);self.assertEqual(prepared['status'],'prepared')
        source=self.d.output(job['id'])/'source/index.html'
        self.assertIn('@yenisayfam',source.read_text());assert_no_source_identity(self,source.read_text())
        plan=json.loads((self.d.output(job['id'])/'plan.json').read_text())
        self.assertTrue(plan['provider_executed']);self.assertFalse(plan['audio_generated']);self.assertEqual(plan['paid_calls'],0)

    def test_accept_retry_after_dashboard_commit_reuses_job_despite_template_edit(self):
        request=self.proposal();payload={'request':request,'brand_identity':{'name':'','handle':''}}
        first=self.d.llm_action('accept',payload)
        t=self.d.template('sample-flow','account-video');t['template']['tone']='Changed after first commit'
        self.d.save_template({'account':'sample-flow','format':'account-video',**t})
        # Simulate interruption before the LLM database recorded the callback.
        with self.d.llm.db() as db:db.execute('UPDATE llm_requests SET accepted_job=NULL WHERE id=?',(request,))
        second=self.d.llm_action('accept',payload)
        self.assertEqual(first['accepted_job'],second['accepted_job']);self.assertEqual(len(self.d.jobs()),1)
        self.assertNotEqual(self.d.jobs()[0]['payload']['template']['template']['tone'],'Changed after first commit')

    def test_accepted_identity_change_is_rejected_and_old_job_preserved(self):
        request=self.proposal();first=self.d.llm_action('accept',{'request':request,'brand_identity':{}})
        with self.assertRaises(WorkflowError):
            self.d.llm_action('accept',{'request':request,'brand_identity':{'handle':'different'}})
        self.assertEqual(len(self.d.jobs()),1);self.assertEqual(self.d.job(first['accepted_job'])['payload']['input']['brand_identity']['handle'],'')

    @source_identity_profiles()
    def test_four_profiles_have_real_editable_scene_source(self):
        for account in ['sample-flow','sample-mechanism','sample-series','sample-reflection']:
            with self.subTest(account=account):
                t=self.d.template(account,'account-video');v=t['template']['video']
                job=self.d.enqueue(dict(account=account,format='account-video',title=v['title'],brief=v['brief'],
                    content=v['script'],caption=v['caption'],provider='local',model='manual',task='text',template_revision=0))
                self.d.prepare(job['id'])
                text=(self.d.output(job['id'])/'source/index.html').read_text()
                self.assertIn('data-composition-id',text)
                assert_no_source_identity(self,text)
                self.assertEqual(self.d.renders.validate(job['id'],'remotion')['id'],job['id'])

    def test_unknown_fields_and_default_off_cannot_dispatch(self):
        off=Dashboard(Path(self.tmp.name)/'off')
        try:
            with self.assertRaises(WorkflowError):off.llm_action('connect',{'provider':'openai','value':'FAKE_OFF'})
            with self.assertRaises(WorkflowError):self.d.llm_action('connect',{'provider':'openai','value':'FAKE_OFF','url':'https://elsewhere.test'})
            self.assertEqual(off.jobs(),[])
        finally:off.clear_keys()

    def test_active_session_key_cannot_be_saved_in_job_identity(self):
        self.d.llm.connect('openai','FAKE_OPAQUE_SHORT_123456')
        t=self.d.template('sample-flow','video-script')
        with self.assertRaises(WorkflowError):self.d.enqueue(dict(account='sample-flow',format='video-script',title='Title',
            brief='Brief',content='Text',caption='Caption',provider='local',model='manual',task='text',template_revision=t['revision'],
            brand_identity={'name':'FAKE_OPAQUE_SHORT_123456'}))
        self.assertEqual(self.d.jobs(),[])
